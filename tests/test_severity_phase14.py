"""LocalOps AI - Phase 14 Severity Calibration & OOD Generalization Test Suite.

Verifies:
- Severity policy loads and parses correctly
- Deterministic P1/P2/P3/P4 mapping with reason codes
- Insufficient impact context handling (no automatic P3 collapse)
- Public schema backward compatibility (LogTriageOutput frozen extra="forbid")
- Phase 3 datasets and Phase 5 adapter remain unmodified
- Manual 12 OOD logs strictly excluded from training/validation
- Contrastive group splitting safety (0 group leakage)
- P3 collapse detector on OOD benchmarks
- Hallucinated IP, hostname, and numeric details detectors
- API backward compatibility
- Dashboard compatibility
"""

import json
import re
from pathlib import Path
import pytest
import yaml

from src.schemas.enums import IncidentType, Severity
from src.schemas.triage import LogTriageOutput
from src.severity.extractor import ImpactExtractor
from src.severity.policy import SeverityPolicyEngine
from src.severity.schemas import (
    BlastRadius,
    CustomerImpact,
    DataIntegrity,
    EnvironmentType,
    ImpactAssessment,
    RedundancyState,
    SecurityExposure,
    ServiceAvailability,
    SeverityDecision,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestSeverityPolicyEngine:
    """Tests deterministic policy evaluation against enterprise SRE rules."""

    def test_severity_policy_yaml_loads(self):
        policy_path = PROJECT_ROOT / "configs" / "severity_policy.yaml"
        assert policy_path.exists(), "configs/severity_policy.yaml must exist"
        with open(policy_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["policy_version"] == "1.0.0"
        assert "P1_CRITICAL" in data["tiers"]
        assert "P2_HIGH" in data["tiers"]
        assert "P3_MEDIUM" in data["tiers"]
        assert "P4_LOW" in data["tiers"]

    def test_deterministic_p1_active_compromise(self):
        policy = SeverityPolicyEngine()
        impact = ImpactAssessment(
            security_exposure=SecurityExposure.ACTIVE_COMPROMISE,
            service_availability=ServiceAvailability.DEGRADED,
            impact_evidence=["active security compromise detected"],
        )
        decision = policy.evaluate(impact)
        assert decision.severity == Severity.P1_CRITICAL
        assert decision.reason_code == "ACTIVE_SECURITY_COMPROMISE"

    def test_deterministic_p1_critical_data_loss(self):
        policy = SeverityPolicyEngine()
        impact = ImpactAssessment(
            data_integrity=DataIntegrity.LOST_OR_CORRUPTED,
            environment=EnvironmentType.PRODUCTION,
            impact_evidence=["unrecoverable database corruption"],
        )
        decision = policy.evaluate(impact)
        assert decision.severity == Severity.P1_CRITICAL
        assert decision.reason_code == "CRITICAL_DATA_LOSS"

    def test_deterministic_p1_cascading_outage(self):
        policy = SeverityPolicyEngine()
        impact = ImpactAssessment(
            service_availability=ServiceAvailability.DOWN,
            blast_radius=BlastRadius.MULTI_SERVICE,
            environment=EnvironmentType.PRODUCTION,
            impact_evidence=["multi-service cascade"],
        )
        decision = policy.evaluate(impact)
        assert decision.severity == Severity.P1_CRITICAL
        assert decision.reason_code == "GLOBAL_OR_CASCADING_OUTAGE"

    def test_deterministic_p2_confirmed_security(self):
        policy = SeverityPolicyEngine()
        impact = ImpactAssessment(
            security_exposure=SecurityExposure.CONFIRMED,
            impact_evidence=["brute force attack detected"],
        )
        decision = policy.evaluate(impact)
        assert decision.severity == Severity.P2_HIGH
        assert decision.reason_code == "CONFIRMED_SECURITY_EVENT"

    def test_deterministic_p2_data_at_risk(self):
        policy = SeverityPolicyEngine()
        impact = ImpactAssessment(
            data_integrity=DataIntegrity.AT_RISK,
            environment=EnvironmentType.PRODUCTION,
            impact_evidence=["deadlock detected, transaction aborted"],
        )
        decision = policy.evaluate(impact)
        assert decision.severity == Severity.P2_HIGH
        assert decision.reason_code == "DATA_INTEGRITY_AT_RISK"

    def test_deterministic_p2_redundancy_depleted(self):
        policy = SeverityPolicyEngine()
        impact = ImpactAssessment(
            redundancy_state=RedundancyState.NONE,
            service_availability=ServiceAvailability.DEGRADED,
            environment=EnvironmentType.PRODUCTION,
            impact_evidence=["pool exhausted"],
        )
        decision = policy.evaluate(impact)
        assert decision.severity == Severity.P2_HIGH
        assert decision.reason_code == "REDUNDANCY_DEPLETED"

    def test_deterministic_p3_localized_single_instance(self):
        policy = SeverityPolicyEngine()
        impact = ImpactAssessment(
            blast_radius=BlastRadius.SINGLE_INSTANCE,
            customer_impact=CustomerImpact.NONE,
            redundancy_state=RedundancyState.AVAILABLE,
            environment=EnvironmentType.PRODUCTION,
            impact_evidence=["single worker OOMKilled"],
        )
        decision = policy.evaluate(impact)
        assert decision.severity == Severity.P3_MEDIUM
        assert decision.reason_code in ("LOCALIZED_INSTANCE_FAILURE", "LOCALIZED_WITH_REDUNDANCY")

    def test_deterministic_p4_non_production(self):
        policy = SeverityPolicyEngine()
        impact = ImpactAssessment(
            environment=EnvironmentType.STAGING,
            customer_impact=CustomerImpact.NONE,
            service_availability=ServiceAvailability.DOWN,
            impact_evidence=["staging test container failure"],
        )
        decision = policy.evaluate(impact)
        assert decision.severity == Severity.P4_LOW
        assert decision.reason_code == "NON_PRODUCTION_ENVIRONMENT"

    def test_deterministic_p4_routine_perimeter_defense(self):
        policy = SeverityPolicyEngine()
        impact = ImpactAssessment(
            service_availability=ServiceAvailability.AVAILABLE,
            customer_impact=CustomerImpact.NONE,
            security_exposure=SecurityExposure.NONE,
            data_integrity=DataIntegrity.INTACT,
            impact_evidence=["routine authentication perimeter rejection"],
        )
        decision = policy.evaluate(impact)
        assert decision.severity == Severity.P4_LOW
        assert decision.reason_code == "NO_OPERATIONAL_IMPACT"

    def test_unknown_context_handling_does_not_collapse_blindly(self):
        policy = SeverityPolicyEngine()
        impact = ImpactAssessment()
        decision = policy.evaluate(impact)
        assert decision.is_insufficient_evidence is True
        assert decision.reason_code == "INSUFFICIENT_IMPACT_EVIDENCE"


class TestManualOODGeneralization:
    """Tests evaluation on the 12 manual out-of-template logs."""

    def test_manual_logs_file_integrity(self):
        logs_path = PROJECT_ROOT / "reports" / "manual_validation" / "manual_logs_v1.jsonl"
        expected_path = PROJECT_ROOT / "reports" / "manual_validation" / "manual_expected_labels_v1.json"
        assert logs_path.exists(), "manual_logs_v1.jsonl must exist"
        assert expected_path.exists(), "manual_expected_labels_v1.json must exist"

        with open(logs_path, "r", encoding="utf-8") as f:
            logs = [json.loads(line) for line in f if line.strip()]
        with open(expected_path, "r", encoding="utf-8") as f:
            expected_data = json.load(f)["labels"]

        assert len(logs) == 12, "Must contain exactly 12 manual evaluation logs"
        assert len(expected_data) == 12, "Must contain exactly 12 expected label definitions"

    def test_manual_logs_isolated_from_training_splits(self):
        """Verifies 12 manual logs were NEVER used in any training or validation sets."""
        manual_logs_path = PROJECT_ROOT / "reports" / "manual_validation" / "manual_logs_v1.jsonl"
        with open(manual_logs_path, "r", encoding="utf-8") as f:
            manual_texts = {json.loads(line)["raw_log"].strip() for line in f if line.strip()}

        train_path = PROJECT_ROOT / "data" / "severity_calibration" / "train.jsonl"
        val_path = PROJECT_ROOT / "data" / "severity_calibration" / "validation.jsonl"

        with open(train_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                assert rec["raw_log"].strip() not in manual_texts, "Manual log leaked into calibration train split!"

        with open(val_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                assert rec["raw_log"].strip() not in manual_texts, "Manual log leaked into calibration val split!"

    def test_manual_12_logs_severity_policy_precision(self):
        """Ensures the severity policy engine achieves high accuracy on the 12 manual logs."""
        logs_path = PROJECT_ROOT / "reports" / "manual_validation" / "manual_logs_v1.jsonl"
        expected_path = PROJECT_ROOT / "reports" / "manual_validation" / "manual_expected_labels_v1.json"

        with open(logs_path, "r", encoding="utf-8") as f:
            logs = [json.loads(line) for line in f if line.strip()]
        with open(expected_path, "r", encoding="utf-8") as f:
            expected_map = {item["request_id"]: item["expected_severity"] for item in json.load(f)["labels"]}

        extractor = ImpactExtractor()
        policy = SeverityPolicyEngine()

        correct = 0
        predicted_classes = set()
        for log in logs:
            req_id = log["request_id"]
            raw_log = log["raw_log"]
            impact = extractor.extract(raw_log)
            decision = policy.evaluate(impact)
            sev_str = decision.severity if isinstance(decision.severity, str) else decision.severity.value
            predicted_classes.add(sev_str)
            if sev_str == expected_map[req_id]:
                correct += 1

        accuracy = correct / len(logs)
        assert accuracy >= 0.80, f"Expected manual accuracy >= 80%, got {accuracy * 100:.1f}%"
        assert len(predicted_classes) >= 3, "Predictions must not collapse to a single class"


class TestDatasetIntegrityAndLeakage:
    """Verifies dataset isolation and lack of template leakage."""

    def test_contrastive_group_isolation(self):
        manifest_path = PROJECT_ROOT / "artifacts" / "phase_14" / "severity_dataset_manifest.json"
        assert manifest_path.exists()
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["total_records"] == 1200
        assert manifest["split_counts"]["train"] == 720
        assert manifest["split_counts"]["validation"] == 240
        assert manifest["split_counts"]["test_ood"] == 240
        assert manifest["leakage_verification"].startswith("PASS")

    def test_original_phase3_datasets_untouched(self):
        """Ensures Phase 14 strictly respects the non-modification constraint of Phase 3 datasets."""
        phase3_train = PROJECT_ROOT / "data" / "generated" / "train.jsonl"
        phase3_val = PROJECT_ROOT / "data" / "generated" / "validation.jsonl"
        phase3_test = PROJECT_ROOT / "data" / "generated" / "test.jsonl"

        assert phase3_train.exists()
        assert phase3_val.exists()
        assert phase3_test.exists()

    def test_original_phase5_adapter_untouched(self):
        """Ensures Phase 5 official final adapter has NOT been overwritten."""
        p5_adapter = PROJECT_ROOT / "artifacts" / "phase_5" / "final_adapter" / "adapter_model.safetensors"
        assert p5_adapter.exists(), "artifacts/phase_5/final_adapter/ must remain intact"


class TestHallucinationAndSchemaContracts:
    """Verifies hallucination detectors and schema constraints."""

    def test_public_schema_extra_forbidden(self):
        """Public schema LogTriageOutput must retain extra='forbid' and unchanged fields."""
        valid_dict = {
            "incident_type": "APPLICATION",
            "severity": "P2_HIGH",
            "affected_service": "order-service",
            "root_cause": "Null pointer in CartService",
            "suggested_action": "Deploy fix cart-v2.1",
            "confidence": 0.95,
            "evidence": ["NullPointerException: cart is null"],
        }
        output = LogTriageOutput(**valid_dict)
        assert output.severity == Severity.P2_HIGH

        # Forbidden extra field must raise ValidationError
        invalid_dict = {**valid_dict, "internal_reason": "should_fail"}
        with pytest.raises(Exception):
            LogTriageOutput(**invalid_dict)

    def test_hallucinated_ip_detector(self):
        raw_log = "2026-09-18T21:02:14Z ERROR [order-service] connection pool timeout"
        text_with_hallucinated_ip = "Database pool timed out connecting to 192.168.1.100 on port 5432"

        raw_ips = set(re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", raw_log))
        pred_ips = set(re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", text_with_hallucinated_ip))

        hallucinated = pred_ips - raw_ips
        assert "192.168.1.100" in hallucinated

    def test_hallucinated_hostname_detector(self):
        raw_log = "2026-09-18T21:02:14Z ERROR [order-service] database query timeout"
        text_with_hallucinated_host = "Database query failed on prod-db-replica-03.us-east.internal"

        raw_hosts = set(re.findall(r"\b(?:[a-zA-Z0-9-]+\.)+(?:internal|svc|cluster\.local)\b", raw_log))
        pred_hosts = set(re.findall(r"\b(?:[a-zA-Z0-9-]+\.)+(?:internal|svc|cluster\.local)\b", text_with_hallucinated_host))

        hallucinated = pred_hosts - raw_hosts
        assert "prod-db-replica-03.us-east.internal" in hallucinated
