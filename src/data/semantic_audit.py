"""
Semantic Audit Engine for LocalOps AI Synthetic Dataset Templates.
Performs comprehensive semantic QA auditing across all 360 templates.
Verifies mutual internal consistency, failure mechanism isolation, HTTP status harmony,
temporal claims, and technology-grounded remediation.
"""

from datetime import datetime
import json
from pathlib import Path
import random
import re
from typing import Optional

from src.data.models import DatasetSplit, NoiseProfile
from src.data.templates import ALL_TEMPLATES
from src.data.templates.base import LogTemplate


class TemplateSemanticAuditor:
    """Audits all 360 templates for semantic consistency and failure mechanism isolation."""

    def __init__(self, templates: Optional[list[LogTemplate]] = None):
        self.templates = templates if templates is not None else ALL_TEMPLATES

    def audit_template(self, template: LogTemplate, seed: int = 42) -> tuple[bool, list[str]]:
        """
        Audits a single template by generating realizations across all its impact scenarios.
        Returns: (passed, errors)
        """
        errors: list[str] = []

        # Audit each impact scenario
        for scenario_idx, scenario in enumerate(template.impact_scenarios):
            rng = random.Random(seed + scenario_idx * 100)
            try:
                incident_id, target, metadata, raw_log = template.render_record(
                    rng=rng,
                    sample_index=scenario_idx,
                    seed=seed,
                    noise_profile=NoiseProfile.NONE,
                )
            except Exception as e:
                errors.append(f"Failed to render template {template.template_id} scenario {scenario_idx}: {e}")
                continue

            # 1. Contradiction Detection
            if "NotReady" in raw_log and "remained Ready" in raw_log:
                errors.append("Contradictory claim: 'remained Ready' found alongside 'NotReady' in log text")
            if "100% full" in raw_log and "stabilized at 68%" in raw_log:
                errors.append("Contradictory claim: disk full error negated by 'stabilized at 68%'")

            # 2. HTTP Status Code Harmony
            sig = metadata.signature_profile.upper()
            rc = target.root_cause
            act = target.suggested_action

            if "504" in sig:
                if "502 Bad Gateway" in rc or "502" in act:
                    errors.append(f"HTTP 504 template has 502 root cause or action: '{rc}'")
                if "503 Service Unavailable" in rc or "503" in act:
                    errors.append(f"HTTP 504 template has 503 root cause or action: '{rc}'")
            elif "502" in sig:
                if "504 Gateway Timeout" in rc or "504" in act:
                    errors.append(f"HTTP 502 template has 504 root cause or action: '{rc}'")
                if "503" in rc or "503" in act:
                    errors.append(f"HTTP 502 template has 503 root cause or action: '{rc}'")
            elif "503" in sig:
                if "504 Gateway Timeout" in rc or "504" in act:
                    errors.append(f"HTTP 503 template has 504 root cause or action: '{rc}'")
                if "502 Bad Gateway" in rc or "502" in act:
                    errors.append(f"HTTP 503 template has 502 root cause or action: '{rc}'")

            # 3. Cassandra-Specific Diagnosis Check
            if "CASSANDRA_READ_TIMEOUT" in sig:
                if "unindexed" in rc or "full-table" in rc or "EXPLAIN ANALYZE" in act:
                    errors.append(
                        f"Cassandra query timeout uses relational table scan diagnosis/action: rc='{rc}', act='{act}'"
                    )
                if not any(k in rc.lower() for k in ["quorum", "replica", "coordinator", "timeout"]):
                    errors.append(f"Cassandra query timeout root cause lacks Cassandra replica/quorum concepts: '{rc}'")

            # 4. Competing TLS Mechanism Check
            if "CERT_EXPIRED" in sig:
                if "TLSv1.0" in raw_log or "cipher mismatch" in raw_log or "no shared cipher" in raw_log:
                    errors.append("TLS certificate expired template contains competing cipher/protocol failure tokens")
                if "TLSv1.0" in rc or "cipher" in rc:
                    errors.append("TLS certificate expired template has competing cipher/protocol root cause")
            elif "CIPHER" in sig:
                if "certificate expired" in raw_log or "NotAfter" in raw_log:
                    errors.append("TLS cipher mismatch template contains competing certificate expired tokens")
                if "certificate expired" in rc or "validity period" in rc:
                    errors.append("TLS cipher mismatch template has competing certificate expired root cause")

            # 5. Temporal Claims Consistency
            ts_matches = re.findall(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\]", raw_log)
            exp_ago_match = re.search(r"expired\s+(\d+)\s+seconds\s+ago", raw_log, re.IGNORECASE)
            exp_at_match = re.search(r"expired\s+at\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", raw_log, re.IGNORECASE)
            if exp_ago_match and exp_at_match and ts_matches:
                claimed_seconds = int(exp_ago_match.group(1))
                exp_dt = datetime.fromisoformat(exp_at_match.group(1).replace("Z", "+00:00"))
                inc_dt = datetime.fromisoformat(ts_matches[0].replace("Z", "+00:00"))
                actual_delta = abs((inc_dt - exp_dt).total_seconds())
                if abs(actual_delta - claimed_seconds) > 3:
                    errors.append(
                        f"Temporal mismatch: claimed {claimed_seconds}s ago vs timestamp delta {actual_delta:.0f}s"
                    )

            prev_exec_match = re.search(r"(?:was already executed at|executed at)\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", raw_log, re.IGNORECASE)
            if prev_exec_match and ts_matches:
                exec_dt = datetime.fromisoformat(prev_exec_match.group(1).replace("Z", "+00:00"))
                inc_dt = datetime.fromisoformat(ts_matches[0].replace("Z", "+00:00"))
                if exec_dt >= inc_dt:
                    errors.append(f"Historical execution timestamp {exec_dt} is not prior to incident timestamp {inc_dt}")

            not_after_match = re.search(r"NotAfter:\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", raw_log)
            if not_after_match and ts_matches:
                na_dt = datetime.fromisoformat(not_after_match.group(1).replace("Z", "+00:00"))
                inc_dt = datetime.fromisoformat(ts_matches[0].replace("Z", "+00:00"))
                if na_dt >= inc_dt:
                    errors.append(f"Certificate NotAfter timestamp {na_dt} is not prior to incident timestamp {inc_dt}")

            # 6. Expected and Forbidden Tokens
            for exp in template.expected_tokens:
                if exp not in raw_log and exp not in rc:
                    errors.append(f"Expected token '{exp}' missing from raw_log and root_cause")
            for forb in template.forbidden_tokens:
                if forb in raw_log or forb in rc or forb in act:
                    errors.append(f"Forbidden token '{forb}' found in raw_log, root_cause, or action")

            # 7. Root-Cause Evidential Scope Validation
            if not template.observed_failure_mechanism:
                errors.append(f"Template {template.template_id} missing observed_failure_mechanism definition")
            if not template.possible_hypotheses:
                errors.append(f"Template {template.template_id} missing possible_hypotheses definition")

            # Verify that root cause variants only assert the observable failure mechanism,
            # unless specific strong evidence for an underlying hypothesis exists in the raw log.
            speculative_claims = {
                "connection leak": ["connection leak", "unclosed connection", "abandoned connection"],
                "lingering connections": ["lingering connection"],
                "query surge": ["query surge", "traffic surge"],
                "slow query": ["slow query", "slow queries", "long-running query"],
                "unindexed": ["unindexed", "missing index"],
                "full table scan": ["full table scan", "seq scan", "sequential scan"],
                "zombie process": ["zombie process", "defunct process"],
                "memory leak": ["memory leak", "heap leak"],
            }
            for claim, keywords in speculative_claims.items():
                if any(kw in rc.lower() for kw in keywords):
                    # If root cause asserts this hypothesis as fact, verify log contains evidence
                    if not any(kw in raw_log.lower() for kw in keywords):
                        errors.append(
                            f"Evidential scope violation: root cause asserts '{claim}' without raw log evidence: '{rc}'"
                        )

        passed = (len(errors) == 0)
        return passed, errors

    def run_full_audit(self, output_path: Optional[Path | str] = None) -> dict[str, object]:
        """Runs audit on all templates and generates the QA report."""
        template_reports = []
        passed_count = 0
        failed_count = 0

        for t in self.templates:
            passed, errors = self.audit_template(t)
            if passed:
                passed_count += 1
                status = "PASSED"
            else:
                failed_count += 1
                status = "FAILED"

            template_reports.append({
                "template_id": t.template_id,
                "incident_family": t.family.value,
                "technology": t.technology,
                "runtime": t.runtime,
                "signature_profile": t.signature_profile,
                "failure_mechanism": t.failure_mechanism or t.signature_profile,
                "observed_failure_mechanism": t.observed_failure_mechanism,
                "possible_hypotheses": t.possible_hypotheses,
                "assigned_split": t.assigned_split.value,
                "audit_status": status,
                "errors": errors,
            })

        report = {
            "summary": {
                "total_templates": len(self.templates),
                "passed": passed_count,
                "failed": failed_count,
                "audit_timestamp": datetime.now().isoformat(),
            },
            "templates": template_reports,
        }

        if output_path:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)

        return report


if __name__ == "__main__":
    auditor = TemplateSemanticAuditor()
    report = auditor.run_full_audit("reports/template_semantic_audit.json")
    print(f"Audit Complete: {report['summary']['passed']}/{report['summary']['total_templates']} passed, {report['summary']['failed']} failed.")
