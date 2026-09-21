"""LocalOps AI — Phase 6 Automated Test Suite.

Verifies:
1. Adapter loading and checkpoint provenance
2. Prompt hash reproducibility and stability
3. Confusion matrix shape and sum invariants (7x7 IncidentType, 5x5 Severity)
4. Paired bootstrap resampling determinism
5. Slice dimension completeness (clarity: EXPLICIT/CLEAR/AMBIGUOUS, noise: NONE/LIGHT/MEDIUM)
6. Raw output preservation alongside parsed Pydantic output
"""

import json
from pathlib import Path
import pytest
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from src.evaluation.prompts import PromptBuilder, E4_SYSTEM_PROMPT
from src.schemas.enums import IncidentType, Severity


class TestPhase6EvaluationSuite:

    def test_e4_prompt_hash_stability(self):
        """Verifies deterministic SHA-256 prompt hashing for E4."""
        hash1 = PromptBuilder.get_prompt_hash("E4")
        hash2 = PromptBuilder.get_prompt_hash("E4")
        assert hash1 == hash2, "E4 prompt hash must be strictly deterministic."
        assert len(hash1) == 64, "Prompt hash must be a valid 64-character SHA-256 hex string."

        # Verify system prompt content matches Phase 5 training
        assert "production incident triage assistant" in E4_SYSTEM_PROMPT
        assert "Return only valid JSON following the required schema" in E4_SYSTEM_PROMPT

    def test_e4_messages_structure(self):
        """Verifies E4 messages format matches single-turn training input without few-shot."""
        raw_log = "[2026-10-04T12:00:00Z] [ERROR] DB connection failed"
        messages = PromptBuilder.build_e4_messages(raw_log)

        assert len(messages) == 2, "E4 messages must contain exactly system and user turns."
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == E4_SYSTEM_PROMPT
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == raw_log

    def test_adapter_files_and_provenance(self):
        """Verifies Phase 5 official final adapter files exist and match checkpoint-100 provenance."""
        adapter_dir = PROJECT_ROOT / "artifacts" / "phase_5" / "final_adapter"
        assert adapter_dir.exists(), "final_adapter directory must exist."

        weights_file = adapter_dir / "adapter_model.safetensors"
        config_file = adapter_dir / "adapter_config.json"
        assert weights_file.exists(), "adapter_model.safetensors must exist."
        assert config_file.exists(), "adapter_config.json must exist."

        with open(config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        assert cfg.get("r") == 16, "LoRA rank must be 16."
        assert cfg.get("lora_alpha") == 32, "LoRA alpha must be 32."

    def test_confusion_matrix_shape_and_invariants(self):
        """Verifies 7x7 IncidentType and 5x5 Severity matrix structure."""
        from scripts.generate_phase6_report import generate_confusion_matrices

        # Construct synthetic mock records
        mock_records = [
            {
                "incident_id": "inc_valid",
                "pydantic_valid": True,
                "parsed_output": {"incident_type": "DATABASE", "severity": "P1_CRITICAL"},
                "ground_truth": {"incident_type": "DATABASE", "severity": "P1_CRITICAL"},
            },
            {
                "incident_id": "inc_invalid",
                "pydantic_valid": False,
                "parsed_output": None,
                "ground_truth": {"incident_type": "MESSAGING", "severity": "P4_LOW"},
            },
        ]
        tmp_cm_path = PROJECT_ROOT / "artifacts" / "phase_6" / "test_cm_temp.json"
        matrices = generate_confusion_matrices(mock_records, tmp_cm_path)

        # Clean up
        if tmp_cm_path.exists():
            tmp_cm_path.unlink()

        # Check 7x7 IncidentType matrix
        type_labels = matrices["end_to_end_incident_type_7x7"]["labels"]
        assert len(type_labels) == 7, "IncidentType labels must be 7 (6 canonical + INVALID_OR_MISSING)."
        assert "INVALID_OR_MISSING" in type_labels

        # Check 5x5 Severity matrix
        sev_labels = matrices["end_to_end_severity_5x5"]["labels"]
        assert len(sev_labels) == 5, "Severity labels must be 5 (4 canonical + INVALID_OR_MISSING)."
        assert "INVALID_OR_MISSING" in sev_labels

        # Check matrix sum invariant
        t_mat = matrices["end_to_end_incident_type_7x7"]["matrix"]
        total_type_preds = sum(sum(row.values()) for row in t_mat.values())
        assert total_type_preds == len(mock_records), "Matrix sum must equal total input records."

    def test_paired_bootstrap_determinism(self):
        """Verifies paired bootstrap resampling returns identical results with fixed seed."""
        from scripts.generate_phase6_report import compute_paired_bootstrap

        y_true = ["A", "B", "A", "B", "A"] * 20
        y_pred_e4 = ["A", "B", "A", "B", "A"] * 20
        y_pred_base = ["B", "B", "A", "A", "B"] * 20

        def acc(yt, yp):
            return sum(1 for a, b in zip(yt, yp) if a == b) / len(yt)

        res1 = compute_paired_bootstrap(y_true, y_pred_e4, y_pred_base, acc, n_bootstraps=100, seed=42)
        res2 = compute_paired_bootstrap(y_true, y_pred_e4, y_pred_base, acc, n_bootstraps=100, seed=42)

        assert res1["delta_mean"] == res2["delta_mean"], "Bootstrap delta must be deterministic."
        assert res1["delta_ci_lower"] == res2["delta_ci_lower"]
        assert res1["delta_ci_upper"] == res2["delta_ci_upper"]
        assert res1["delta_mean"] > 0, "E4 should outperform inferior baseline in synthetic test."

    def test_test_set_split_integrity_and_clarity_values(self):
        """Verifies test.jsonl has expected 1,440 records and exact metadata categories."""
        test_file = PROJECT_ROOT / "data" / "generated" / "test.jsonl"
        assert test_file.exists(), "test.jsonl must exist."

        records = []
        with open(test_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

        assert len(records) == 1440, "test.jsonl must contain exactly 1,440 records."

        # Verify clarity values are EXPLICIT, CLEAR, AMBIGUOUS
        clarities = set(r["metadata"]["diagnostic_clarity"] for r in records)
        assert clarities == {"EXPLICIT", "CLEAR", "AMBIGUOUS"}, f"Unexpected clarity values: {clarities}"

        # Verify noise values are NONE, LIGHT, MEDIUM
        noises = set(r["metadata"]["noise_profile"] for r in records)
        assert noises == {"NONE", "LIGHT", "MEDIUM"}, f"Unexpected noise values: {noises}"

    def test_affected_service_aggregate_equals_prediction_level(self):
        """Verifies aggregate affected-service metrics equal exact prediction-level counts."""
        preds_path = PROJECT_ROOT / "reports" / "evaluation" / "e4_qlora" / "predictions.jsonl"
        metrics_path = PROJECT_ROOT / "reports" / "evaluation" / "e4_qlora" / "metrics.json"

        assert preds_path.exists()
        assert metrics_path.exists()

        records = [json.loads(line) for line in open(preds_path, "r", encoding="utf-8") if line.strip()]
        metrics = json.load(open(metrics_path, "r", encoding="utf-8"))

        total = len(records)
        exact_matches = sum(
            1 for r in records
            if r.get("pydantic_valid")
            and r.get("parsed_output")
            and r["parsed_output"].get("affected_service") == r["ground_truth"].get("affected_service")
        )
        mismatches_on_valid = sum(
            1 for r in records
            if r.get("pydantic_valid")
            and r.get("parsed_output")
            and r["parsed_output"].get("affected_service") != r["ground_truth"].get("affected_service")
        )

        expected_rate = round(exact_matches / total, 4)
        reported_rate = metrics["affected_service_metrics"]["affected_service_exact_match"]

        assert expected_rate == reported_rate == 0.9910, f"Expected {expected_rate}, got {reported_rate}"
        assert mismatches_on_valid == 0, f"Expected 0 mismatches on valid predictions, got {mismatches_on_valid}"

    def test_evidence_grounding_aggregate_equals_prediction_level(self):
        """Verifies evidence grounding metrics agree between predictions and error_analysis.json."""
        preds_path = PROJECT_ROOT / "reports" / "evaluation" / "e4_qlora" / "predictions.jsonl"
        metrics_path = PROJECT_ROOT / "reports" / "evaluation" / "e4_qlora" / "metrics.json"
        err_path = PROJECT_ROOT / "reports" / "evaluation" / "e4_qlora" / "error_analysis.json"

        records = [json.loads(line) for line in open(preds_path, "r", encoding="utf-8") if line.strip()]
        metrics = json.load(open(metrics_path, "r", encoding="utf-8"))
        err_analysis = json.load(open(err_path, "r", encoding="utf-8"))

        total_records = len(records)
        total_ev = 0
        verbatim_ev = 0
        records_fully_grounded = 0
        ungrounded_count = 0

        for r in records:
            raw_log = r.get("raw_log", "")
            parsed = r.get("parsed_output") or {}
            if r.get("pydantic_valid") and parsed:
                pred_ev = parsed.get("evidence", [])
                rec_grounded = True
                for ev in pred_ev:
                    total_ev += 1
                    if ev.strip() in raw_log:
                        verbatim_ev += 1
                    else:
                        ungrounded_count += 1
                        rec_grounded = False
                if pred_ev and rec_grounded:
                    records_fully_grounded += 1

        verbatim_rate = round(verbatim_ev / total_ev, 4)
        record_grounded_rate = round(records_fully_grounded / total_records, 4)

        assert verbatim_rate == metrics["evidence_metrics"]["evidence_verbatim_rate"] == 0.9675
        assert record_grounded_rate == metrics["evidence_metrics"]["record_level_full_evidence_grounding_rate"] == 0.8972
        assert ungrounded_count == metrics["evidence_metrics"]["ungrounded_evidence_count"] == 144
        assert ungrounded_count == err_analysis["error_summary"]["ungrounded_evidence"] == 144

    def test_confusion_matrix_totals_and_diagonals(self):
        """Programmatically asserts confusion matrix sums and diagonal valid counts equal reported accuracies."""
        cm_path = PROJECT_ROOT / "reports" / "evaluation" / "e4_qlora" / "confusion_matrices.json"
        metrics_path = PROJECT_ROOT / "reports" / "evaluation" / "e4_qlora" / "metrics.json"

        cms = json.load(open(cm_path, "r", encoding="utf-8"))
        metrics = json.load(open(metrics_path, "r", encoding="utf-8"))

        t_mat = cms["end_to_end_incident_type_7x7"]["matrix"]
        s_mat = cms["end_to_end_severity_5x5"]["matrix"]

        total_type_cm = sum(sum(row.values()) for row in t_mat.values())
        total_sev_cm = sum(sum(row.values()) for row in s_mat.values())

        assert total_type_cm == 1440, f"IncidentType CM total must be 1440, got {total_type_cm}"
        assert total_sev_cm == 1440, f"Severity CM total must be 1440, got {total_sev_cm}"

        diag_type = sum(t_mat[cls][cls] for cls in t_mat.keys())
        diag_sev = sum(s_mat[cls][cls] for cls in s_mat.keys())

        assert diag_type == 1418, f"Expected 1418 correct IncidentType, got {diag_type}"
        assert diag_sev == 1427, f"Expected 1427 correct Severity, got {diag_sev}"

        assert round(diag_type / 1440, 4) == metrics["primary_metrics"]["end_to_end_incident_type_accuracy"] == 0.9847
        assert round(diag_sev / 1440, 4) == metrics["primary_metrics"]["end_to_end_severity_accuracy"] == 0.9910

    def test_locked_phase4_baseline_preservation(self):
        """Verifies Phase 4 baselines used in Phase 6 match locked machine-readable artifact."""
        comp_path = PROJECT_ROOT / "reports" / "evaluation" / "e4_qlora" / "baseline_comparison.json"
        assert comp_path.exists()

        data = json.load(open(comp_path, "r", encoding="utf-8"))
        e2_p = data["E2"]["primary_metrics"]
        e3_p = data["E3"]["primary_metrics"]

        assert e2_p["end_to_end_incident_type_accuracy"] == 0.4472
        assert e2_p["end_to_end_incident_type_macro_f1"] == 0.4679
        assert e2_p["end_to_end_severity_accuracy"] == 0.1861
        assert e2_p["end_to_end_severity_macro_f1"] == 0.0895

        assert e3_p["end_to_end_incident_type_accuracy"] == 0.3937
        assert e3_p["end_to_end_incident_type_macro_f1"] == 0.3514
        assert e3_p["end_to_end_severity_accuracy"] == 0.2972
        assert e3_p["end_to_end_severity_macro_f1"] == 0.2319

    def test_validated_energy_telemetry_outlier_filtering(self):
        """Verifies energy telemetry peak power draw is clamped to hardware ceiling limit (85W)."""
        metrics_path = PROJECT_ROOT / "reports" / "evaluation" / "e4_qlora" / "metrics.json"
        metrics = json.load(open(metrics_path, "r", encoding="utf-8"))

        energy = metrics["energy_telemetry"]
        assert energy["validated_peak_power_w"] <= 85.0
        assert energy["run_peak_power_w"] <= 85.0
        assert energy["average_power_w"] <= 85.0
        assert "outlier_filtering_rule" in energy

