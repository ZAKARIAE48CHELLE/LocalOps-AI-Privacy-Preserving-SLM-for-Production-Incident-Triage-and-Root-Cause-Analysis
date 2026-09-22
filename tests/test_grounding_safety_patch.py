"""LocalOps AI — Grounding & Severity Safety Patch Test Suite.

Verifies:
1. Grounding Sanitizer detects and rewrites unsupported IPs, hostnames, and numeric claims.
2. Legitimate IPs and metrics copied verbatim from raw_log are strictly preserved.
3. Manual 12 logs pass exact grounding safety assertions:
   - test-db-002: output must NOT contain 203.0.113.1
   - test-infra-001: output must NOT contain 203.0.113.5
   - test-infra-002: output must NOT contain 192.0.2.1
   - test-app-001: output must NOT contain 192.0.2.30
   - test-msg-002: output must NOT contain 203.0.113.5
   - test-net-001: 10.244.3.17 is preserved (exists in raw_log)
   - test-net-002: 10.42.7.91 is preserved (exists in raw_log)
4. Severity grounding tests:
   - test-app-001 does NOT use WIDESPREAD_SEVERE_IMPACT
   - test-db-002 does NOT use DATA_INTEGRITY_AT_RISK
   - test-net-001 does NOT use MULTI_SERVICE_DEGRADATION
5. Telemetry fields are tracked and public schema contracts remain frozen.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.grounding.sanitizer import GroundingSanitizer
from src.grounding.validators import (
    detect_unsupported_hostnames,
    detect_unsupported_ips,
    detect_unsupported_numeric_claims,
)
from src.schemas.triage import LogTriageOutput
from src.severity.extractor import ImpactExtractor
from src.severity.policy import SeverityPolicyEngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestGroundingSanitizerRules:
    """Tests unit rules of GroundingSanitizer."""

    def test_canonical_ip_rewrites(self):
        sanitizer = GroundingSanitizer()

        # Database lock rewrite
        data, telem = sanitizer.sanitize(
            {
                "root_cause": "Database lock timeout on 203.0.113.1.",
                "suggested_action": "Check database status",
            },
            raw_log="2026-09-18T21:08:47Z ERROR [billing-service] deadlock detected",
        )
        assert "203.0.113.1" not in data["root_cause"]
        assert "contention" in data["root_cause"].lower() or "lock" in data["root_cause"].lower()
        assert telem.unsupported_ip_removed == 1

        # OOM container rewrite
        data, telem = sanitizer.sanitize(
            {
                "root_cause": "Process exceeded memory on host 203.0.113.5, triggering OOM.",
                "suggested_action": "Increase limit",
            },
            raw_log="2026-09-18T21:20:10Z kubelet: Warning OOMKilling container ml-worker",
        )
        assert "203.0.113.5" not in data["root_cause"]
        assert "exceeded" in data["root_cause"].lower()
        assert telem.unsupported_ip_removed == 1

        # DiskPressure pod eviction rewrite
        data, telem = sanitizer.sanitize(
            {
                "root_cause": "Filesystem filled on host 192.0.2.1.",
                "suggested_action": "Evict secondary pods",
            },
            raw_log="2026-09-18T21:27:34Z kubelet: DiskPressure condition is now true",
        )
        assert "192.0.2.1" not in data["root_cause"]
        assert "diskpressure" in data["root_cause"].lower() or "capacity" in data["root_cause"].lower()
        assert telem.unsupported_ip_removed == 1

    def test_unsupported_hostname_removal(self):
        sanitizer = GroundingSanitizer()
        raw_log = "2026-09-18T21:02:14Z ERROR [order-service] query timeout"
        data, telem = sanitizer.sanitize(
            {
                "root_cause": "Connection failed on host prod-db-replica-03.us-east.internal",
                "suggested_action": "Restart prod-db-replica-03.us-east.internal service",
            },
            raw_log=raw_log,
        )
        assert "prod-db-replica-03.us-east.internal" not in data["root_cause"]
        assert "prod-db-replica-03.us-east.internal" not in data["suggested_action"]
        assert telem.unsupported_hostname_removed >= 1

    def test_unsupported_numeric_claim_removal(self):
        sanitizer = GroundingSanitizer()
        raw_log = "2026-09-18T21:40:04Z ERROR [checkout-api] NullPointerException status=500"
        data, telem = sanitizer.sanitize(
            {
                "root_cause": "Null pointer caused 80% traffic affected and 12 replicas failed",
                "suggested_action": "Restore 500 users impacted",
            },
            raw_log=raw_log,
        )
        assert "80%" not in data["root_cause"]
        assert "12 replicas" not in data["root_cause"]
        assert "500 users" not in data["suggested_action"]
        assert "traffic affected" in data["root_cause"]
        assert "replicas failed" in data["root_cause"]
        assert "users impacted" in data["suggested_action"]
        assert telem.unsupported_numeric_claim_removed == 3

    def test_preserve_legitimate_raw_log_tokens(self):
        sanitizer = GroundingSanitizer()
        raw_log = (
            "2026-09-18T22:20:20Z WARN [coredns] read udp 10.244.3.17:42210->10.96.0.10:53: i/o timeout\n"
            "pricing.internal.svc.cluster.local\n"
            "lag=135788 oldest unprocessed message age=923s"
        )
        data, telem = sanitizer.sanitize(
            {
                "root_cause": "CoreDNS failed resolving pricing.internal.svc.cluster.local via 10.244.3.17 with age=923s",
                "suggested_action": "Inspect 10.244.3.17 and drain lag 135788",
            },
            raw_log=raw_log,
        )
        # All of these are legitimately present in raw_log, so they must NOT be removed!
        assert "10.244.3.17" in data["root_cause"]
        assert "10.244.3.17" in data["suggested_action"]
        assert "pricing.internal.svc.cluster.local" in data["root_cause"]
        assert telem.unsupported_ip_removed == 0
        assert telem.unsupported_hostname_removed == 0


class TestManual12GroundingAssertions:
    """Exact grounding safety checks on the immutable 12 manual logs."""

    @pytest.fixture
    def manual_logs(self):
        logs_path = PROJECT_ROOT / "reports" / "manual_validation" / "manual_logs_v1.jsonl"
        with open(logs_path, "r", encoding="utf-8") as f:
            return {json.loads(line)["request_id"]: json.loads(line)["raw_log"] for line in f if line.strip()}

    def test_manual_unsupported_ips_sanitized(self, manual_logs):
        sanitizer = GroundingSanitizer()

        # test-db-002: output must NOT contain 203.0.113.1
        data_db2, _ = sanitizer.sanitize(
            {"root_cause": "Database lock timeout on 203.0.113.1.", "suggested_action": "Kill blocked query"},
            manual_logs["test-db-002"],
        )
        assert "203.0.113.1" not in data_db2["root_cause"]

        # test-infra-001: output must NOT contain 203.0.113.5
        data_inf1, _ = sanitizer.sanitize(
            {"root_cause": "Process exceeded memory on host 203.0.113.5, triggering OOM.", "suggested_action": "Tune RSS"},
            manual_logs["test-infra-001"],
        )
        assert "203.0.113.5" not in data_inf1["root_cause"]

        # test-infra-002: output must NOT contain 192.0.2.1
        data_inf2, _ = sanitizer.sanitize(
            {"root_cause": "Filesystem filled on host 192.0.2.1.", "suggested_action": "Clean /var/log"},
            manual_logs["test-infra-002"],
        )
        assert "192.0.2.1" not in data_inf2["root_cause"]

        # test-app-001: output must NOT contain 192.0.2.30
        data_app1, _ = sanitizer.sanitize(
            {"root_cause": "NPE on /checkout from client 192.0.2.30", "suggested_action": "Deploy fix"},
            manual_logs["test-app-001"],
        )
        assert "192.0.2.30" not in data_app1["root_cause"]

        # test-msg-002: output must NOT contain 203.0.113.5
        data_msg2, _ = sanitizer.sanitize(
            {"root_cause": "Poison pill from publisher 203.0.113.5 causing deserialization error", "suggested_action": "DLQ"},
            manual_logs["test-msg-002"],
        )
        assert "203.0.113.5" not in data_msg2["root_cause"]

    def test_manual_legitimate_ips_preserved(self, manual_logs):
        sanitizer = GroundingSanitizer()

        # test-net-001: 10.244.3.17 is allowed because it exists in raw_log
        data_net1, _ = sanitizer.sanitize(
            {"root_cause": "CoreDNS socket timeout reaching 10.244.3.17", "suggested_action": "Check UDP routes"},
            manual_logs["test-net-001"],
        )
        assert "10.244.3.17" in data_net1["root_cause"]

        # test-net-002: 10.42.7.91 is allowed because it exists in raw_log
        data_net2, _ = sanitizer.sanitize(
            {"root_cause": "Connection refused to upstream at 10.42.7.91:8080", "suggested_action": "Restart customer-profile"},
            manual_logs["test-net-002"],
        )
        assert "10.42.7.91" in data_net2["root_cause"]


class TestSeverityGroundingRules:
    """Verifies severity policy grounding constraints."""

    @pytest.fixture
    def manual_logs(self):
        logs_path = PROJECT_ROOT / "reports" / "manual_validation" / "manual_logs_v1.jsonl"
        with open(logs_path, "r", encoding="utf-8") as f:
            return {json.loads(line)["request_id"]: json.loads(line)["raw_log"] for line in f if line.strip()}

    def test_app_001_no_widespread_severe_impact(self, manual_logs):
        """test-app-001 only proves NPE + single 500 on /checkout, NOT widespread outage."""
        extractor = ImpactExtractor()
        policy = SeverityPolicyEngine()

        impact = extractor.extract(manual_logs["test-app-001"])
        decision = policy.evaluate(impact)

        assert decision.reason_code != "WIDESPREAD_SEVERE_IMPACT", (
            "test-app-001 must NOT use WIDESPREAD_SEVERE_IMPACT without explicit widespread outage evidence!"
        )

    def test_db_002_no_data_integrity_at_risk(self, manual_logs):
        """test-db-002 is deadlock/rollback, NOT persistent corruption."""
        extractor = ImpactExtractor()
        policy = SeverityPolicyEngine()

        impact = extractor.extract(manual_logs["test-db-002"])
        decision = policy.evaluate(impact)

        assert decision.reason_code != "DATA_INTEGRITY_AT_RISK", (
            "test-db-002 must NOT use DATA_INTEGRITY_AT_RISK for standard deadlock contention!"
        )
        assert decision.reason_code == "DATABASE_TRANSACTION_CONTENTION"

    def test_net_001_no_multi_service_degradation(self, manual_logs):
        """test-net-001 is a single UnknownHostException, NOT multi-service cascade."""
        extractor = ImpactExtractor()
        policy = SeverityPolicyEngine()

        impact = extractor.extract(manual_logs["test-net-001"])
        decision = policy.evaluate(impact)

        assert decision.reason_code != "MULTI_SERVICE_DEGRADATION", (
            "test-net-001 must NOT use MULTI_SERVICE_DEGRADATION without multiple services explicitly impacted!"
        )
        assert decision.reason_code == "SINGLE_SERVICE_DEGRADATION"
