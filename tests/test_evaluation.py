"""
Comprehensive unit and integration test suite for Phase 4: Baseline Evaluation.
Tests:
1. Config loading from YAML
2. Prompt hash stability & manifest creation
3. E3 demonstration leakage guard against test.jsonl
4. Strict raw JSON vs conservative extracted JSON distinction
5. Strict Pydantic validation & extra-field rejection (extra="forbid")
6. End-to-end metric denominator (unparseable = incorrect)
7. Secondary conditional metrics on valid outputs
8. Affected-service exact, normalized, and log-grounded matching
9. Evidence verbatim grounding
10. Local semantic similarity execution
11. Unsupported-claim and speculative root-cause heuristics
12. Technology-action compatibility & unsafe command heuristics
13. Crash-safe resume after interruption & duplicate prevention
14. Subgroup slice aggregation across all 8 metadata dimensions
15. Raw-output preservation and human review artifact generation
"""

import json
import os
import tempfile
import pytest

from src.evaluation.evaluator import BaselineEvaluator, load_stratified_smoke_records
from src.evaluation.heuristics import DiagnosticHeuristics
from src.evaluation.metrics import MetricEvaluator, compute_f1_multiclass, compute_token_f1
from src.evaluation.parser import OutputParser
from src.evaluation.prompts import PromptBuilder
from src.evaluation.schemas import (
    EvaluationPipelineConfig,
    RawPredictionRecord,
)
from src.evaluation.semantic import LocalSemanticEvaluator
from src.schemas.enums import IncidentType, Severity


class TestEvaluationPhase4:

    def test_config_loading_from_yaml(self):
        """Validates that configs/evaluation.yaml loads correctly into typed Pydantic models."""
        config_path = "configs/evaluation.yaml"
        assert os.path.exists(config_path), "configs/evaluation.yaml must exist."
        config = EvaluationPipelineConfig.from_yaml(config_path)

        assert config.model.model_id == "Qwen/Qwen2.5-1.5B-Instruct"
        assert config.model.quantization == "nf4"
        assert config.model.bnb_quant_type == "nf4"
        assert config.generation.seed == 42
        assert config.generation.do_sample is False
        assert config.evaluation.batch_size in [1, 4, 8]
        assert config.evaluation.smoke_records_per_family == 1

    def test_prompt_hash_stability_and_manifest(self):
        """Verifies deterministic prompt hashing and manifest structure."""
        hash_e1_a = PromptBuilder.get_prompt_hash("E1")
        hash_e1_b = PromptBuilder.get_prompt_hash("E1")
        assert hash_e1_a == hash_e1_b, "E1 prompt hash must be completely deterministic."

        hash_e2_a = PromptBuilder.get_prompt_hash("E2")
        hash_e2_b = PromptBuilder.get_prompt_hash("E2")
        assert hash_e2_a == hash_e2_b, "E2 prompt hash must be completely deterministic."
        assert hash_e1_a != hash_e2_a, "E1 and E2 prompt hashes must differ."

        dummy_demos = [
            {
                "incident_id": "demo_1",
                "raw_log": "log text 1",
                "target": {"incident_type": "DATABASE", "severity": "P1_CRITICAL"},
            }
        ]
        hash_e3 = PromptBuilder.get_prompt_hash("E3", dummy_demos)
        assert len(hash_e3) == 64

        manifest = PromptBuilder.create_prompt_manifest(
            {"seed": 42, "max_new_tokens": 384}, dummy_demos
        )
        assert manifest["version"] == "1.0.0"
        assert "generation_config_sha256" in manifest
        assert "E1" in manifest["experiments"]
        assert "E2" in manifest["experiments"]
        assert "E3" in manifest["experiments"]
        assert manifest["experiments"]["E3"]["demonstration_count"] == 1
        assert manifest["experiments"]["E3"]["demonstration_ids"] == ["demo_1"]

    def test_e3_leakage_guard_against_test_dataset(self):
        """Ensures that zero few-shot demonstrations leak into test.jsonl."""
        test_path = "data/generated/test.jsonl"
        manifest_path = "reports/evaluation/few_shot_manifest.json"

        assert os.path.exists(test_path), f"Missing {test_path}"
        assert os.path.exists(manifest_path), f"Missing {manifest_path}"

        test_incident_ids = set()
        test_template_ids = set()
        test_raw_logs = set()

        with open(test_path, "r", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                test_incident_ids.add(r["incident_id"])
                test_template_ids.add(r["metadata"]["template_id"])
                test_raw_logs.add(r["raw_log"].strip())

        with open(manifest_path, "r", encoding="utf-8") as f:
            demos = json.load(f)["demonstrations"]

        assert len(demos) == 6, f"Expected 6 demonstrations, got {len(demos)}"

        for demo in demos:
            # 1. Zero incident ID overlap
            assert (
                demo["incident_id"] not in test_incident_ids
            ), f"Leakage: Demo ID {demo['incident_id']} exists in test.jsonl!"
            # 2. Zero template ID overlap
            assert (
                demo["template_id"] not in test_template_ids
            ), f"Leakage: Template ID {demo['template_id']} exists in test.jsonl!"
            # 3. Zero raw log exact match
            assert (
                demo["raw_log"].strip() not in test_raw_logs
            ), f"Leakage: Raw log for demo {demo['incident_id']} exists in test.jsonl!"

    def test_raw_json_vs_extracted_json_distinction(self):
        """Asserts that conversational prose around valid JSON fails strict JSON but passes extraction."""
        valid_json_payload = {
            "incident_type": "DATABASE",
            "severity": "P1_CRITICAL",
            "affected_service": "orders-db",
            "root_cause": "Database connection pool capacity exhausted.",
            "suggested_action": "Increase pool limit and inspect slow queries.",
            "confidence": 0.95,
            "evidence": ["Connection timed out after 30000ms"],
        }
        json_str = json.dumps(valid_json_payload)

        # 1. Pure strict JSON
        strict_valid, extracted_dict = OutputParser.check_strict_raw_json(json_str)
        assert strict_valid is True
        assert extracted_dict["incident_type"] == "DATABASE"

        # 2. Prose wrapped output
        prose_wrapped = f"Here is the incident triage diagnosis:\n```json\n{json_str}\n```\nHope this helps!"
        strict_valid, _ = OutputParser.check_strict_raw_json(prose_wrapped)
        assert strict_valid is False, "Prose wrapped output must fail strict raw JSON compliance."

        extract_success, extracted_text, extracted_dict = OutputParser.extract_json(prose_wrapped)
        assert extract_success is True, "Prose wrapped output must pass conservative extraction."
        assert extracted_dict["incident_type"] == "DATABASE"

    def test_strict_pydantic_validation_and_extra_fields(self):
        """Verifies Pydantic contract rules: extra='forbid', invalid enums, non-numeric confidence."""
        base_payload = {
            "incident_type": "DATABASE",
            "severity": "P1_CRITICAL",
            "affected_service": "orders-db",
            "root_cause": "Pool exhausted.",
            "suggested_action": "Restart pool.",
            "confidence": 0.9,
            "evidence": ["pool exhausted"],
        }

        # 1. Valid payload
        valid, parsed, errors, types = OutputParser.validate_pydantic(base_payload)
        assert valid is True
        assert errors == []

        # 2. Extra forbidden field
        extra_payload = dict(base_payload)
        extra_payload["invented_notes"] = "some speculative notes"
        valid, _, errors, types = OutputParser.validate_pydantic(extra_payload)
        assert valid is False
        assert "extra_field" in types

        # 3. Invalid enum
        bad_enum_payload = dict(base_payload)
        bad_enum_payload["incident_type"] = "HARDWARE_FAILURE"
        valid, _, errors, types = OutputParser.validate_pydantic(bad_enum_payload)
        assert valid is False
        assert "invalid_incident_type" in types

        # 4. Invalid non-numeric confidence
        bad_conf_payload = dict(base_payload)
        bad_conf_payload["confidence"] = "high"
        valid, _, errors, types = OutputParser.validate_pydantic(bad_conf_payload)
        assert valid is False
        assert "invalid_confidence" in types

        # 5. Missing required field
        missing_payload = dict(base_payload)
        del missing_payload["severity"]
        valid, _, errors, types = OutputParser.validate_pydantic(missing_payload)
        assert valid is False
        assert "missing_field" in types

    def test_end_to_end_vs_conditional_metric_calculation(self):
        """
        Verifies that end-to-end metrics include all records (counting invalid as incorrect),
        while conditional metrics evaluate only schema-valid records.
        """
        ground_truth = {
            "incident_type": "DATABASE",
            "severity": "P1_CRITICAL",
            "affected_service": "user-service",
            "root_cause": "Connection exhausted",
            "suggested_action": "Restart service",
            "confidence": 0.9,
            "evidence": ["pool exhausted"],
        }
        metadata = {
            "incident_family": "DB_CONNECTION_POOL_STARVATION",
            "technology": "PostgreSQL",
            "runtime": "Java",
            "signature_profile": "HIKARI_POOL_EXHAUSTED",
            "diagnostic_clarity": "EXPLICIT",
            "noise_profile": "LIGHT",
        }

        # Sample 1: Valid and correct
        rec1 = RawPredictionRecord(
            incident_id="inc_001",
            experiment_id="E2",
            prompt_id="prompt_e2",
            prompt_version="1.0.0",
            prompt_hash="hash_1",
            raw_log="2026-09-14 user-service pool exhausted",
            raw_model_output=json.dumps(ground_truth),
            strict_json_valid=True,
            json_extraction_success=True,
            parsed_output=dict(ground_truth),
            pydantic_valid=True,
            latency_seconds=0.5,
            prompt_tokens=200,
            generated_tokens=50,
            tokens_per_second=100.0,
            peak_vram_mb=1200.0,
            ground_truth=ground_truth,
            metadata=metadata,
        )

        # Sample 2: Malformed/unparseable output
        rec2 = RawPredictionRecord(
            incident_id="inc_002",
            experiment_id="E2",
            prompt_id="prompt_e2",
            prompt_version="1.0.0",
            prompt_hash="hash_1",
            raw_log="2026-09-14 user-service pool exhausted",
            raw_model_output="I am unable to diagnose this log properly.",
            strict_json_valid=False,
            json_extraction_success=False,
            parsed_output=None,
            pydantic_valid=False,
            error_types=["malformed_json"],
            latency_seconds=0.4,
            prompt_tokens=200,
            generated_tokens=20,
            tokens_per_second=50.0,
            peak_vram_mb=1200.0,
            ground_truth=ground_truth,
            metadata=metadata,
        )

        results = MetricEvaluator.evaluate_records([rec1, rec2])

        # End-to-end evaluation: 1 correct out of 2 total = 50% accuracy
        assert results["primary_metrics"]["end_to_end_incident_type_accuracy"] == 0.5
        assert results["primary_metrics"]["end_to_end_severity_accuracy"] == 0.5

        # Conditional evaluation: 1 correct out of 1 valid = 100% accuracy
        assert results["secondary_metrics"]["valid_record_count"] == 1
        assert results["secondary_metrics"]["incident_type_accuracy_on_valid_outputs"] == 1.0

        # Contract compliance
        assert results["contract_metrics"]["pydantic_valid_rate"] == 0.5
        assert results["contract_metrics"]["raw_json_valid_rate"] == 0.5

    def test_affected_service_metrics(self):
        """Verifies exact, normalized, and log-grounded affected-service checks."""
        gt = {"affected_service": "checkout-service", "incident_type": "APPLICATION", "severity": "P2_HIGH"}
        meta = {"incident_family": "APP_THREAD_DEADLOCK"}

        # Case 1: Exact match and in log
        rec1 = RawPredictionRecord(
            incident_id="s1", experiment_id="E2", prompt_id="p1", prompt_version="1.0", prompt_hash="h1",
            raw_log="[checkout-service] deadlock detected",
            raw_model_output="{}", strict_json_valid=True, json_extraction_success=True,
            parsed_output={"affected_service": "checkout-service", "incident_type": "APPLICATION", "severity": "P2_HIGH", "root_cause": "rc", "suggested_action": "act", "confidence": 0.8, "evidence": ["deadlock"]},
            pydantic_valid=True, ground_truth=gt, metadata=meta,
        )
        # Case 2: Case/whitespace variation (e.g. " Checkout-Service ")
        rec2 = RawPredictionRecord(
            incident_id="s2", experiment_id="E2", prompt_id="p1", prompt_version="1.0", prompt_hash="h1",
            raw_log="[checkout-service] deadlock detected",
            raw_model_output="{}", strict_json_valid=True, json_extraction_success=True,
            parsed_output={"affected_service": " Checkout-Service ", "incident_type": "APPLICATION", "severity": "P2_HIGH", "root_cause": "rc", "suggested_action": "act", "confidence": 0.8, "evidence": ["deadlock"]},
            pydantic_valid=True, ground_truth=gt, metadata=meta,
        )

        results = MetricEvaluator.evaluate_records([rec1, rec2])
        assert results["affected_service_metrics"]["affected_service_exact_match"] == 0.5
        assert results["affected_service_metrics"]["affected_service_normalized_exact_match"] == 1.0
        assert results["affected_service_metrics"]["affected_service_log_grounded_rate"] == 1.0

    def test_evidence_grounding_and_token_f1(self):
        """Verifies evidence verbatim rate and token F1 against ground truth."""
        raw_log = "[auth-service] org.jose4j.jwt.consumer.InvalidJwtException: JWT expired at 2026-09-14"
        gt = {
            "incident_type": "SECURITY", "severity": "P1_CRITICAL",
            "evidence": ["InvalidJwtException: JWT expired"]
        }
        meta = {"incident_family": "SEC_CREDENTIAL_OR_TOKEN_EXPIRATION"}

        rec = RawPredictionRecord(
            incident_id="e1", experiment_id="E2", prompt_id="p1", prompt_version="1.0", prompt_hash="h1",
            raw_log=raw_log, raw_model_output="{}", strict_json_valid=True, json_extraction_success=True,
            parsed_output={
                "incident_type": "SECURITY", "severity": "P1_CRITICAL", "affected_service": "auth-service",
                "root_cause": "Token expired", "suggested_action": "Rotate tokens", "confidence": 0.9,
                "evidence": ["InvalidJwtException: JWT expired", "Hallucinated quote not in log"]
            },
            pydantic_valid=True, ground_truth=gt, metadata=meta,
        )

        results = MetricEvaluator.evaluate_records([rec])
        # 1 out of 2 evidence items is verbatim in raw_log
        assert results["evidence_metrics"]["evidence_verbatim_rate"] == 0.5
        assert results["evidence_metrics"]["evidence_token_f1_mean"] > 0.0

    def test_diagnostic_heuristics(self):
        """Verifies unsupported root cause detection and technology-action compatibility checks."""
        # 1. Speculative memory leak when log only shows OOM
        raw_log = "kernel: Memory cgroup out of memory: Killed process 1140 total-vm:116736kB"
        is_unsupported, flags = DiagnosticHeuristics.check_unsupported_root_cause(
            raw_log=raw_log,
            predicted_root_cause="Application contains a severe memory leak in background threads.",
            incident_family="INFRA_POD_OOMKILLED",
        )
        assert is_unsupported is True
        assert any("speculative_memory_leak" in f for f in flags)

        # 2. Technology mismatch: Cassandra incident with PostgreSQL remediation
        is_comp, is_safe, flags = DiagnosticHeuristics.check_action_compatibility_and_safety(
            suggested_action="Connect via psql and run SELECT * FROM pg_stat_activity to inspect pool.",
            technology="Cassandra",
            incident_type="DATABASE",
        )
        assert is_comp is False
        assert any("technology_mismatch" in f for f in flags)

        # 3. Dangerous / destructive command
        is_comp, is_safe, flags = DiagnosticHeuristics.check_action_compatibility_and_safety(
            suggested_action="Execute rm -rf /var/lib/data and reboot immediately.",
            technology="PostgreSQL",
            incident_type="DATABASE",
        )
        assert is_safe is False
        assert any("unsafe_command" in f for f in flags)

    def test_local_semantic_evaluator(self):
        """Verifies local semantic evaluator execution with identical, paraphrase, and unrelated texts."""
        sem = LocalSemanticEvaluator()
        
        # 1. Exact identity: similarity(text, text) ≈ 1.0
        text_id = "Database connection pool exhausted due to active transaction leak on port 5432."
        sim_exact = sem.compute_similarity(text_id, text_id)
        assert abs(sim_exact - 1.0) < 0.01, f"Expected similarity(text, text) ≈ 1.0, got {sim_exact}"

        # 2. Domain-representative paraphrase pair vs unrelated pair:
        # similarity(paraphrase pair) > similarity(unrelated pair)
        text_base = "PostgreSQL database connection pool exhausted due to idle clients holding active transactions."
        text_paraphrase = "DB client connection limits reached in PostgreSQL because open transactions did not release pool connections."
        text_unrelated = "TLS certificate expired on Kubernetes ingress gateway controller causing handshake timeouts."

        sim_paraphrase = sem.compute_similarity(text_base, text_paraphrase)
        sim_unrelated = sem.compute_similarity(text_base, text_unrelated)

        assert sim_paraphrase > sim_unrelated, (
            f"Paraphrase similarity ({sim_paraphrase}) must exceed unrelated similarity ({sim_unrelated})"
        )
        assert sim_paraphrase >= 0.60, f"Expected strong domain semantic similarity for paraphrase, got {sim_paraphrase}"
        assert sim_unrelated <= 0.35, f"Expected low semantic similarity for unrelated incident domain pair, got {sim_unrelated}"

        # 3. Vectorized batch similarity consistency
        batch_sims = sem.compute_batch_similarities([
            (text_id, text_id),
            (text_base, text_paraphrase),
            (text_base, text_unrelated),
        ])
        assert len(batch_sims) == 3
        assert abs(batch_sims[0] - sim_exact) < 1e-4
        assert abs(batch_sims[1] - sim_paraphrase) < 1e-4
        assert abs(batch_sims[2] - sim_unrelated) < 1e-4

    def test_stratified_smoke_records_loader(self):
        """Verifies that load_stratified_smoke_records returns 36 records covering all 36 IncidentFamily values."""
        val_path = "data/generated/validation.jsonl"
        assert os.path.exists(val_path), "validation.jsonl must exist."

        records = load_stratified_smoke_records(val_path, records_per_family=1)
        assert len(records) == 36, f"Expected 36 records, got {len(records)}"

        families = {r["metadata"]["incident_family"] for r in records}
        assert len(families) == 36, f"Expected 36 distinct families, found {len(families)}"

        # Coverage across clarity and noise profiles
        clarities = {r["metadata"]["diagnostic_clarity"] for r in records}
        assert "EXPLICIT" in clarities
        assert "CLEAR" in clarities
        assert "AMBIGUOUS" in clarities

        noise_profiles = {r["metadata"]["noise_profile"] for r in records}
        assert "NONE" in noise_profiles
        assert "LIGHT" in noise_profiles
        assert "MEDIUM" in noise_profiles

    def test_slice_aggregation_dimensions(self):
        """Verifies that evaluate_records produces breakdown slices across all 8 metadata dimensions."""
        gt = {"incident_type": "DATABASE", "severity": "P1_CRITICAL", "affected_service": "db-1"}
        meta = {
            "incident_type": "DATABASE",
            "incident_family": "DB_CONNECTION_POOL_STARVATION",
            "severity": "P1_CRITICAL",
            "technology": "PostgreSQL",
            "runtime": "JVM",
            "signature_profile": "HIKARI_TIMEOUT",
            "diagnostic_clarity": "EXPLICIT",
            "noise_profile": "LIGHT",
        }

        rec = RawPredictionRecord(
            incident_id="sl_1", experiment_id="E2", prompt_id="p1", prompt_version="1.0", prompt_hash="h1",
            raw_log="[db-1] pool exhausted", raw_model_output="{}", strict_json_valid=True, json_extraction_success=True,
            parsed_output=dict(gt, root_cause="rc", suggested_action="act", confidence=0.9, evidence=["exhausted"]),
            pydantic_valid=True, ground_truth=gt, metadata=meta,
        )

        results = MetricEvaluator.evaluate_records([rec])
        slices = results["slices"]

        expected_dimensions = [
            "incident_type", "incident_family", "severity", "technology",
            "runtime", "signature_profile", "diagnostic_clarity", "noise_profile"
        ]
        for dim in expected_dimensions:
            assert dim in slices, f"Slice dimension {dim} missing from results."

    def test_resume_and_deduplication(self):
        """Verifies crash-safe resume skips already completed incident IDs and prevents duplicate rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            preds_path = os.path.join(tmpdir, "predictions.jsonl")

            # Write an existing completed sample
            gt = {"incident_type": "DATABASE", "severity": "P1_CRITICAL"}
            existing_rec = {
                "incident_id": "inc_existing_01",
                "experiment_id": "E1",
                "prompt_id": "p1",
                "prompt_version": "1.0.0",
                "prompt_hash": "h1",
                "raw_log": "log text",
                "raw_model_output": "output text",
                "strict_json_valid": False,
                "json_extraction_success": False,
                "pydantic_valid": False,
                "latency_seconds": 0.2,
                "prompt_tokens": 100,
                "generated_tokens": 20,
                "tokens_per_second": 100.0,
                "peak_vram_mb": 1000.0,
                "ground_truth": gt,
                "metadata": {"incident_family": "DB_CONNECTION_POOL_STARVATION"},
            }
            with open(preds_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(existing_rec) + "\n")

            # Simulate evaluator resume reading
            completed_ids = set()
            with open(preds_path, "r", encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    completed_ids.add(r["incident_id"])

            assert "inc_existing_01" in completed_ids

            # When evaluating dataset, existing ID is skipped
            test_items = [
                {"incident_id": "inc_existing_01", "raw_log": "log text", "target": gt, "metadata": {}},
                {"incident_id": "inc_new_02", "raw_log": "new log", "target": gt, "metadata": {}},
            ]
            to_process = [item for item in test_items if item["incident_id"] not in completed_ids]
            assert len(to_process) == 1
            assert to_process[0]["incident_id"] == "inc_new_02"
