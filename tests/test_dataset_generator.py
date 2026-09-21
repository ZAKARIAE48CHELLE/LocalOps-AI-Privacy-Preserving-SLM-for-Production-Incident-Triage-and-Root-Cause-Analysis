"""Tests for synthetic incident triage dataset engineering (Phase 3)."""

from datetime import datetime
import json
from pathlib import Path
import re
import pytest

from src.schemas.enums import IncidentFamily, IncidentType, Severity
from src.schemas.triage import LogTriageOutput
from src.data.family_catalog import (
    FAMILY_TO_INCIDENT_TYPE,
    CATEGORY_TO_FAMILIES,
    get_incident_type_for_family,
    get_category_for_family,
)
from src.data.models import (
    DatasetRecord,
    DatasetSplit,
    DiagnosticClarity,
    NoiseProfile,
    RecordMetadata,
)
from src.data.templates import ALL_TEMPLATES, TEMPLATES_BY_FAMILY, TEMPLATES_BY_ID
from src.data.templates.base import normalize_structural_fingerprint
from src.data.splitter import SplitManager
from src.data.generator import DatasetGenerator
from src.data.validation import DatasetValidator
from src.data.statistics import DatasetStatistics


class TestFamilyCatalog:
    """Validate completeness and taxonomy mappings of the 36 IncidentFamily catalog."""

    def test_all_36_families_represented(self):
        assert len(FAMILY_TO_INCIDENT_TYPE) == 36
        for family in IncidentFamily:
            assert family in FAMILY_TO_INCIDENT_TYPE

    def test_six_categories_six_families_each(self):
        assert len(CATEGORY_TO_FAMILIES) == 6
        for cat, families in CATEGORY_TO_FAMILIES.items():
            assert len(families) == 6, f"Category {cat} does not have exactly 6 families"

    def test_family_type_resolution(self):
        assert get_incident_type_for_family(IncidentFamily.DB_CONNECTION_POOL_STARVATION) == IncidentType.DATABASE
        assert get_incident_type_for_family(IncidentFamily.INFRA_CPU_THROTTLING) == IncidentType.INFRASTRUCTURE
        assert get_incident_type_for_family(IncidentFamily.APP_UNHANDLED_EXCEPTION) == IncidentType.APPLICATION
        assert get_incident_type_for_family(IncidentFamily.SEC_CREDENTIAL_OR_TOKEN_EXPIRATION) == IncidentType.SECURITY
        assert get_incident_type_for_family(IncidentFamily.NET_TLS_HANDSHAKE_FAILURE) == IncidentType.NETWORK
        assert get_incident_type_for_family(IncidentFamily.MSG_CONSUMER_LAG_ACCUMULATION) == IncidentType.MESSAGING


class TestTemplateRegistry:
    """Validate 360 templates registry, isolation, and structural fingerprints."""

    def test_exactly_360_templates(self):
        assert len(ALL_TEMPLATES) == 360

    def test_unique_template_ids(self):
        assert len(TEMPLATES_BY_ID) == 360

    def test_ten_templates_per_family(self):
        assert len(TEMPLATES_BY_FAMILY) == 36
        for family, templates in TEMPLATES_BY_FAMILY.items():
            assert len(templates) == 10, f"Family {family} has {len(templates)} templates, expected 10"

    def test_split_manager_isolation(self):
        manager = SplitManager()
        train_t, val_t, test_t = manager.split_templates(ALL_TEMPLATES)

        assert len(train_t) == 216  # 36 * 6
        assert len(val_t) == 72    # 36 * 2
        assert len(test_t) == 72   # 36 * 2

        # Verify template ID sets are completely disjoint
        train_ids = {t.template_id for t in train_t}
        val_ids = {t.template_id for t in val_t}
        test_ids = {t.template_id for t in test_t}

        assert train_ids.isdisjoint(val_ids)
        assert train_ids.isdisjoint(test_ids)
        assert val_ids.isdisjoint(test_ids)

    def test_zero_cross_split_structural_fingerprint_overlap(self):
        manager = SplitManager()
        overlap = manager.verify_structural_isolation(ALL_TEMPLATES)
        assert overlap == 0, f"Expected 0 cross-split structural fingerprint overlap, found {overlap}"

    def test_fingerprint_normalization_replaces_variable_slots(self):
        raw = "2026-09-14T10:00:00Z [orders-svc] timeout connecting to 10.0.1.45:5432 after 30000ms trace_id=c123456789012345"
        normalized = normalize_structural_fingerprint(raw)
        assert "<TIMESTAMP>" in normalized
        assert "<IP>" in normalized
        assert "<NUM>" in normalized
        assert "10.0.1.45" not in normalized
        assert "30000" not in normalized

    def test_all_templates_have_normalized_metadata(self):
        for template in ALL_TEMPLATES:
            assert template.technology, f"Template {template.template_id} missing technology"
            assert template.runtime, f"Template {template.template_id} missing runtime"
            assert template.signature_profile, f"Template {template.template_id} missing signature_profile"
            # Ensure impact scenarios have 4 levels including P4_LOW
            severities = {scen.severity for scen in template.impact_scenarios}
            assert Severity.P4_LOW in severities, f"Template {template.template_id} missing P4_LOW scenario"
            assert len(severities) == 4, f"Template {template.template_id} does not have all 4 severity levels"


class TestDeterministicGeneration:
    """Validate reproducibility, seed invariance, and target ground-truth constraints."""

    def test_reproducible_records_from_seed(self):
        gen1 = DatasetGenerator(seed=42)
        gen2 = DatasetGenerator(seed=42)

        template = ALL_TEMPLATES[0]
        rec1 = gen1.generate_record(template, DatasetSplit.TRAIN, sample_index=0)
        rec2 = gen2.generate_record(template, DatasetSplit.TRAIN, sample_index=0)

        assert rec1.incident_id == rec2.incident_id
        assert rec1.input_log == rec2.input_log
        assert rec1.target.model_dump() == rec2.target.model_dump()
        assert rec1.metadata.model_dump() == rec2.metadata.model_dump()

    def test_incident_id_is_deterministic(self):
        gen = DatasetGenerator(seed=42)
        template = ALL_TEMPLATES[0]
        rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=5)
        expected_id = gen._generate_incident_id(template, 5)
        assert rec.incident_id == expected_id
        assert rec.incident_id.startswith(f"inc_{template.family.value.lower()}_{template.template_id.lower()}_")

    def test_target_conforms_to_log_triage_output(self):
        gen = DatasetGenerator(seed=42)
        template = ALL_TEMPLATES[1]
        rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=1)

        # Confirm target is instance of LogTriageOutput
        assert isinstance(rec.target, LogTriageOutput)
        assert rec.target.incident_type in IncidentType
        assert rec.target.severity in Severity
        assert 0.0 <= rec.target.confidence <= 1.0
        assert len(rec.target.evidence) >= 1
        for item in rec.target.evidence:
            assert len(item) >= 5
        assert len(rec.target.affected_service) >= 2

    def test_verbatim_evidence_and_service_grounding(self):
        gen = DatasetGenerator(seed=101)
        for i in range(15):
            template = ALL_TEMPLATES[i * 10]
            rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=i)
            # Every Evidence item MUST be a verbatim substring of input_log
            for ev in rec.target.evidence:
                assert ev in rec.input_log, (
                    f"Evidence '{ev}' not in input_log for {rec.incident_id}"
                )
            # Affected service MUST be present in input_log
            assert rec.target.affected_service in rec.input_log, (
                f"Service '{rec.target.affected_service}' not in input_log for {rec.incident_id}"
            )

    def test_diagnostic_clarity_confidence_heuristics(self):
        gen = DatasetGenerator(seed=42)
        for template in ALL_TEMPLATES[:20]:
            rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=0)
            clarity = rec.metadata.diagnostic_clarity
            conf = rec.target.confidence
            if clarity == DiagnosticClarity.EXPLICIT:
                assert 0.90 <= conf <= 0.99
            elif clarity == DiagnosticClarity.CLEAR:
                assert 0.78 <= conf <= 0.89
            elif clarity == DiagnosticClarity.AMBIGUOUS:
                assert 0.60 <= conf <= 0.73

    def test_p4_low_coverage_generated(self):
        gen = DatasetGenerator(seed=42)
        severities = set()
        for i in range(40):
            template = ALL_TEMPLATES[i % len(ALL_TEMPLATES)]
            rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=i)
            severities.add(rec.target.severity)
        assert Severity.P4_LOW in severities
        assert len(severities) == 4

    def test_severity_and_diagnostic_clarity_are_decoupled(self):
        gen = DatasetGenerator(seed=42)
        pairs = set()
        for i in range(100):
            template = ALL_TEMPLATES[i % len(ALL_TEMPLATES)]
            rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=i)
            pairs.add((rec.target.severity, rec.metadata.diagnostic_clarity))
        # With 4 severities and 3 clarities, decoupling ensures multiple combinations appear
        assert len(pairs) >= 8, f"Expected decoupled distribution, got only {len(pairs)} pairs"

    def test_timestamp_coherence_and_monotonicity(self):
        ts_regex = re.compile(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\]")
        gen = DatasetGenerator(seed=42)
        for i in range(30):
            template = ALL_TEMPLATES[i * 5]
            rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=i)
            matches = ts_regex.findall(rec.raw_log)
            assert len(matches) >= 2
            dts = [datetime.fromisoformat(m.replace("Z", "+00:00")) for m in matches]
            # Must be strictly monotonic non-decreasing
            for idx in range(len(dts) - 1):
                assert dts[idx] <= dts[idx + 1], f"Non-monotonic timestamps in {rec.incident_id}"
            # Span must be within realistic window (<300s)
            span = (max(dts) - min(dts)).total_seconds()
            assert span <= 300, f"Excessive timestamp span {span}s in {rec.incident_id}"


class TestDatasetValidationAndIntegrity:
    """Validate full validation pipeline and corruption detection."""

    def test_validator_passes_on_valid_mini_dataset(self, tmp_path):
        gen = DatasetGenerator(seed=42)
        gen.generate_all(output_dir=tmp_path, examples_per_template=1)

        validator = DatasetValidator(data_dir=tmp_path)
        results = validator.validate_all()

        assert results.passed is True
        assert len(results.errors) == 0
        assert results.total_records_checked == 360
        assert results.metrics["cross_split_template_leakage"] == 0
        assert results.metrics["cross_split_structural_fingerprint_overlap"] == 0
        assert results.metrics["missing_severities"] == 0

    def test_validator_catches_ungrounded_evidence(self, tmp_path):
        gen = DatasetGenerator(seed=42)
        gen.generate_all(output_dir=tmp_path, examples_per_template=1)

        # Corrupt train.jsonl with ungrounded evidence
        train_path = tmp_path / "train.jsonl"
        lines = train_path.read_text(encoding="utf-8").strip().split("\n")
        first_rec = json.loads(lines[0])
        first_rec["target"]["evidence"] = ["THIS_STRING_DOES_NOT_EXIST_IN_THE_LOG"]
        lines[0] = json.dumps(first_rec)
        train_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        validator = DatasetValidator(data_dir=tmp_path)
        results = validator.validate_all()

        assert results.passed is False
        assert any("Evidence not found as exact substring" in err for err in results.errors)


class TestDatasetStatistics:
    """Validate summary statistics, target phrase leakage isolation, and manifest generation."""

    def test_statistics_and_manifest_generation(self, tmp_path):
        gen = DatasetGenerator(seed=42)
        gen.generate_all(output_dir=tmp_path, examples_per_template=1)

        stats = DatasetStatistics(data_dir=tmp_path)
        report = stats.compute_all()

        assert report["total_records"] == 360
        assert report["split_distribution"]["train"] == 216
        assert report["split_distribution"]["validation"] == 72
        assert report["split_distribution"]["test"] == 72

        # Check decoupling cross-tab
        sev_clarity = report["severity_x_diagnostic_clarity"]
        assert len(sev_clarity) == 4
        for sev in ["P1_CRITICAL", "P2_HIGH", "P3_MEDIUM", "P4_LOW"]:
            assert sev in sev_clarity
            assert len(sev_clarity[sev]) >= 2

        # Check target phrase leakage is 0.0
        assert report["target_phrase_split_leakage"]["exact_test_root_cause_seen_in_train_rate"] == 0.0
        assert report["target_phrase_split_leakage"]["exact_test_action_seen_in_train_rate"] == 0.0

        manifest_path = tmp_path / "manifest.json"
        saved_manifest = stats.save_manifest(manifest_path)
        assert saved_manifest.exists()

        manifest_content = json.loads(saved_manifest.read_text(encoding="utf-8"))
        assert "train.jsonl" in manifest_content["files"]
        assert "sha256" in manifest_content["files"]["train.jsonl"]
        assert "configuration" in manifest_content
        assert manifest_content["configuration"]["seed"] == 42
        assert manifest_content["configuration"]["total_templates"] == 360


class TestSemanticQualityAndRegression:
    """Curated semantic regression tests for previously observed edge cases."""

    def test_cassandra_local_quorum_timeout(self):
        template = TEMPLATES_BY_ID["DB_TOUT_05"]
        assert template.family == IncidentFamily.DB_QUERY_TIMEOUT
        assert template.technology == "Cassandra"
        assert template.signature_profile == "CASSANDRA_READ_TIMEOUT_QUORUM"

        gen = DatasetGenerator(seed=42)
        rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=1)

        # Must NOT diagnose as unindexed table scan
        assert "unindexed" not in rec.target.root_cause.lower()
        assert "explain analyze" not in rec.target.suggested_action.lower()
        # Must diagnose as replica quorum timeout
        assert any(k in rec.target.root_cause.lower() for k in ["quorum", "replica", "coordinator", "timeout"])
        assert any(k in rec.target.suggested_action.lower() for k in ["replica", "nodetool", "latency", "timeout"])

    def test_kubernetes_node_not_ready_disk_pressure(self):
        template = TEMPLATES_BY_ID["INF_NNR_09"]
        assert template.family == IncidentFamily.INFRA_NODE_NOT_READY
        assert template.technology == "GKE"
        assert template.signature_profile == "GKE_NODE_DISK_PRESSURE_NOTREADY"

        gen = DatasetGenerator(seed=42)
        rec = gen.generate_record(template, DatasetSplit.TEST, sample_index=1)

        assert "KubeletHasDiskPressure" in rec.raw_log
        assert "remained Ready" not in rec.raw_log
        assert "diskpressure" in rec.target.root_cause.lower() or "disk pressure" in rec.target.root_cause.lower()

    def test_crashloop_backoff(self):
        template = TEMPLATES_BY_ID["INF_CLB_01"]
        assert template.family == IncidentFamily.INFRA_CRASHLOOP_BACKOFF
        assert template.signature_profile == "K8S_FAILED_TO_START_CONTAINER"

        gen = DatasetGenerator(seed=42)
        rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=1)

        assert "failed to start container" in rec.raw_log
        assert "Back-off restarting failed container" in rec.raw_log
        assert any(k in rec.target.root_cause.lower() for k in ["crash", "initialization", "configuration", "startup", "fail"])

    def test_rust_serde_json_missing_field(self):
        template = TEMPLATES_BY_ID["APP_SER_09"]
        assert template.family == IncidentFamily.APP_SERIALIZATION_FAILURE
        assert template.technology == "Rust/Serde"
        assert template.signature_profile == "RUST_SERDE_JSON_MISSING_FIELD"

        gen = DatasetGenerator(seed=42)
        rec = gen.generate_record(template, DatasetSplit.TEST, sample_index=1)

        assert "missing field `customer_id`" in rec.raw_log
        assert any(k in rec.target.root_cause.lower() for k in ["deserialization", "serde", "schema", "payload", "json"])

    def test_tls_certificate_expiration(self):
        template = TEMPLATES_BY_ID["NET_TLS_01"]
        assert template.family == IncidentFamily.NET_TLS_HANDSHAKE_FAILURE
        assert template.signature_profile == "JAVA_PKIX_CERT_EXPIRED"

        gen = DatasetGenerator(seed=42)
        rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=1)

        assert "javax.net.ssl.SSLHandshakeException" in rec.raw_log
        assert "validity check failed: NotAfter:" in rec.raw_log
        # Competing failure mechanisms strictly forbidden
        assert "TLSv1.0" not in rec.raw_log
        assert "cipher mismatch" not in rec.raw_log
        assert "certificate" in rec.target.root_cause.lower()
        assert "renew" in rec.target.suggested_action.lower() or "rotate" in rec.target.suggested_action.lower()

    def test_tls_protocol_mismatch(self):
        template = TEMPLATES_BY_ID["NET_TLS_09"]
        assert template.family == IncidentFamily.NET_TLS_HANDSHAKE_FAILURE
        assert template.signature_profile == "ENVOY_SSL_DISALLOWED_TLS10"

        gen = DatasetGenerator(seed=42)
        rec = gen.generate_record(template, DatasetSplit.TEST, sample_index=1)

        assert "disallowed TLSv1.0" in rec.raw_log
        # Competing failure mechanisms strictly forbidden
        assert "NotAfter" not in rec.raw_log
        assert "certificate has expired" not in rec.raw_log
        assert "protocol" in rec.target.root_cause.lower()
        assert "tlsv1" in rec.target.suggested_action.lower() or "upgrade" in rec.target.suggested_action.lower()

    def test_aws_alb_504_gateway_timeout(self):
        template = TEMPLATES_BY_ID["NET_GTW_04"]
        assert template.family == IncidentFamily.NET_INGRESS_GATEWAY_TIMEOUT
        assert template.technology == "AWS ALB"
        assert template.signature_profile == "AWS_ALB_504_TIMEOUT"

        gen = DatasetGenerator(seed=42)
        rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=1)

        assert "504 -" in rec.raw_log
        assert "502 Bad Gateway" not in rec.target.root_cause
        assert "alb" in rec.target.root_cause.lower() or "504" in rec.target.root_cause
        assert any(k in rec.target.suggested_action.lower() for k in ["alb", "target", "latency", "timeout"])

    def test_nats_jetstream_storage_limit(self):
        template = TEMPLATES_BY_ID["MSG_BKP_09"]
        assert template.family == IncidentFamily.MSG_QUEUE_STORAGE_BACKPRESSURE
        assert template.technology == "NATS JetStream"
        assert template.signature_profile == "NATS_JETSTREAM_STORAGE_LIMIT"

        gen = DatasetGenerator(seed=42)
        rec = gen.generate_record(template, DatasetSplit.TEST, sample_index=1)

        assert "storage limit reached" in rec.raw_log
        assert "jetstream" in rec.target.root_cause.lower() or "storage" in rec.target.root_cause.lower() or "limit" in rec.target.root_cause.lower()

    def test_container_oomkilled(self):
        template = TEMPLATES_BY_ID["INF_OOM_01"]
        assert template.family == IncidentFamily.INFRA_POD_OOMKILLED
        assert template.signature_profile == "K8S_CONTAINER_EXIT_137"

        gen = DatasetGenerator(seed=42)
        rec = gen.generate_record(template, DatasetSplit.TRAIN, sample_index=1)

        assert "exit code 137" in rec.raw_log
        assert "oom" in rec.target.root_cause.lower() or "memory" in rec.target.root_cause.lower()

    def test_all_360_templates_pass_semantic_audit(self):
        from src.data.semantic_audit import TemplateSemanticAuditor
        auditor = TemplateSemanticAuditor()
        report = auditor.run_full_audit()
        assert report["summary"]["total_templates"] == 360
        assert report["summary"]["passed"] == 360
        assert report["summary"]["failed"] == 0

    def test_noise_frequencies_match_configured_distribution(self):
        """Verify that generated noise profile frequencies match the resolved configured distribution within stochastic tolerance."""
        import collections
        gen = DatasetGenerator(seed=42)
        records_by_split = gen.generate()
        all_records = [rec for split in records_by_split.values() for rec in split]
        total = len(all_records)
        assert total == 7200

        counts = collections.Counter(rec.metadata.noise_profile for rec in all_records)
        for profile, expected_ratio in gen.noise_distribution.items():
            actual_ratio = counts[profile.value] / total
            # Tolerance +/- 3% (0.03) for 7,200 records
            assert abs(actual_ratio - expected_ratio) < 0.03, (
                f"Noise profile {profile.value} ratio {actual_ratio:.4f} deviates from expected {expected_ratio:.4f} beyond tolerance"
            )

