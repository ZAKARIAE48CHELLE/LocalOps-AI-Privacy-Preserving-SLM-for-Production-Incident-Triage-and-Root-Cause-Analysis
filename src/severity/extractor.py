"""LocalOps AI — Impact Signal Extractor (Phase 14).

Extracts operational impact signals from raw logs and diagnostic context
under strict grounding rules:
- Only facts explicitly supported by raw log telemetry are extracted.
- A single HTTP 500 does NOT imply widespread outage or DOWN availability.
- A database deadlock does NOT automatically imply DATA_INTEGRITY_AT_RISK.
- A single UnknownHostException does NOT imply MULTI_SERVICE_DEGRADATION.
- Every signal stores value, source (EXPLICIT | DERIVED_SAFE | UNKNOWN), and evidence.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from src.severity.schemas import (
    BlastRadius,
    CustomerImpact,
    DataIntegrity,
    EnvironmentType,
    GroundedSignal,
    ImpactAssessment,
    RedundancyState,
    SecurityExposure,
    ServiceAvailability,
    SignalSource,
)


class ImpactExtractor:
    """Extracts strictly grounded operational impact indicators from raw logs."""

    def _find_span(self, text: str, pattern: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """Finds first regex match span and substring in text."""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0), match.start(), match.end()
        return None, None, None

    def extract(self, raw_log: str, root_cause: str = "", suggested_action: str = "") -> ImpactAssessment:
        combined_text = f"{raw_log}\n{root_cause}\n{suggested_action}"
        raw_log_lower = raw_log.lower()
        impact_evidence: List[str] = []
        grounded_signals: Dict[str, GroundedSignal] = {}

        # ---------------------------------------------------------------------
        # 1. Environment Detection
        # ---------------------------------------------------------------------
        env = EnvironmentType.PRODUCTION
        env_source = SignalSource.DERIVED_SAFE
        env_evidence = "default production environment"
        env_sub, env_s, env_e = self._find_span(raw_log, r"\b(staging|stage|dev|development|qa|sandbox|non-prod)\b")
        if env_sub:
            env = EnvironmentType.STAGING
            env_source = SignalSource.EXPLICIT
            env_evidence = f"non-production environment marker: '{env_sub}'"
            impact_evidence.append(env_evidence)
        elif "production" in raw_log_lower:
            env_source = SignalSource.EXPLICIT
            env_evidence = "explicit production environment marker"
            impact_evidence.append(env_evidence)

        grounded_signals["environment"] = GroundedSignal(
            value=env.value,
            evidence=env_evidence,
            substring=env_sub,
            evidence_start=env_s,
            evidence_end=env_e,
            source=env_source,
        )

        # ---------------------------------------------------------------------
        # 2. Security Exposure Detection
        # ---------------------------------------------------------------------
        sec = SecurityExposure.NONE
        sec_source = SignalSource.UNKNOWN
        sec_evidence = "no security anomalies observed"
        sec_sub, sec_s, sec_e = self._find_span(
            raw_log,
            r"\b(active compromise|data exfiltration|privilege escalation achieved|remote code execution|cve-)\b",
        )
        if sec_sub:
            sec = SecurityExposure.ACTIVE_COMPROMISE
            sec_source = SignalSource.EXPLICIT
            sec_evidence = f"active compromise: '{sec_sub}'"
            impact_evidence.append(sec_evidence)
        else:
            sec_sub, sec_s, sec_e = self._find_span(
                raw_log,
                r"\b(brute force|failed login attempts|account.*locked|unauthorized access attempt|credential stuffing|\d+ failed.*attempts)\b",
            )
            if sec_sub:
                sec = SecurityExposure.CONFIRMED
                sec_source = SignalSource.EXPLICIT
                sec_evidence = f"confirmed security event: '{sec_sub}'"
                impact_evidence.append(sec_evidence)
            else:
                sec_sub, sec_s, sec_e = self._find_span(
                    raw_log,
                    r"\b(token expired|jwt expired|expiredjwtexception|invalid_token|401 unauthorized|request rejected status=401)\b",
                )
                if sec_sub:
                    sec = SecurityExposure.NONE
                    sec_source = SignalSource.EXPLICIT
                    sec_evidence = f"routine defense perimeter rejection: '{sec_sub}'"
                    impact_evidence.append(sec_evidence)
                else:
                    sec_sub, sec_s, sec_e = self._find_span(
                        raw_log,
                        r"\b(jwt validation failed|permission.*denied|403 forbidden)\b",
                    )
                    if sec_sub:
                        sec = SecurityExposure.SUSPICIOUS
                        sec_source = SignalSource.EXPLICIT
                        sec_evidence = f"suspicious security event: '{sec_sub}'"
                        impact_evidence.append(sec_evidence)

        grounded_signals["security_exposure"] = GroundedSignal(
            value=sec.value,
            evidence=sec_evidence,
            substring=sec_sub,
            evidence_start=sec_s,
            evidence_end=sec_e,
            source=sec_source,
        )

        # ---------------------------------------------------------------------
        # 3. Data Integrity & Deadlock Contention Rules
        # Deadlock alone must NOT automatically produce DATA_INTEGRITY_AT_RISK.
        # ---------------------------------------------------------------------
        data_integrity = DataIntegrity.INTACT
        data_source = SignalSource.DERIVED_SAFE
        data_evidence = "data integrity intact"
        transaction_contention = False

        data_sub, data_s, data_e = self._find_span(
            raw_log,
            r"\b(data loss|unrecoverable.*data|database corruption|permanent loss|lost records|wal corruption)\b",
        )
        if data_sub:
            data_integrity = DataIntegrity.LOST_OR_CORRUPTED
            data_source = SignalSource.EXPLICIT
            data_evidence = f"data loss or corruption: '{data_sub}'"
            impact_evidence.append(data_evidence)
        else:
            # Only assign AT_RISK if explicit corruption/integrity risk words occur
            data_sub, data_s, data_e = self._find_span(
                raw_log,
                r"\b(corruption|lost writes|inconsistent records|failed recovery|data mismatch|partial commit|integrity constraint violation with damaged state)\b",
            )
            if data_sub:
                data_integrity = DataIntegrity.AT_RISK
                data_source = SignalSource.EXPLICIT
                data_evidence = f"data integrity at risk: '{data_sub}'"
                impact_evidence.append(data_evidence)
            else:
                # Check for database deadlock / transaction contention
                tx_sub, tx_s, tx_e = self._find_span(
                    raw_log,
                    r"\b(deadlock detected|deadlock|transaction aborted|transaction rollback|lock timeout|sharelock)\b",
                )
                if tx_sub:
                    transaction_contention = True
                    data_integrity = DataIntegrity.INTACT
                    data_source = SignalSource.DERIVED_SAFE
                    data_evidence = f"transaction contention without corruption: '{tx_sub}'"
                    impact_evidence.append(data_evidence)

        grounded_signals["data_integrity"] = GroundedSignal(
            value=data_integrity.value,
            evidence=data_evidence,
            substring=data_sub,
            evidence_start=data_s,
            evidence_end=data_e,
            source=data_source,
        )

        # ---------------------------------------------------------------------
        # 4. Service Availability & Service Error Observed
        # A single HTTP 500 or NPE must NOT infer service DOWN.
        # ---------------------------------------------------------------------
        service_error_observed = bool(
            re.search(r"\b(status=500|error|exception|fatal|panic|oomkill|timeout|refused|fail)\b", raw_log, re.IGNORECASE)
        )
        avail = ServiceAvailability.UNKNOWN
        avail_source = SignalSource.UNKNOWN
        avail_evidence = "availability unknown from context"

        # Explicit DOWN requires total outage proof
        avail_sub, avail_s, avail_e = self._find_span(
            raw_log,
            r"\b(complete outage|100% (requests|traffic) fail|all replicas unavailable|checkout unavailable|global outage|error rate 95%|all replicas oomkilled|fatal exception in interrupt|kernel panic|down and unreachable)\b",
        )
        if avail_sub:
            avail = ServiceAvailability.DOWN
            avail_source = SignalSource.EXPLICIT
            avail_evidence = f"service down: '{avail_sub}'"
            impact_evidence.append(avail_evidence)
        else:
            # Explicit DEGRADED requires verified service degradation
            avail_sub, avail_s, avail_e = self._find_span(
                raw_log,
                r"\b(connection is not available|pool\.idle=0|pool\.waiting=\d+|fatal: sorry, too many clients|diskpressure|circuitbreaker.*open|connect\(\) failed.*connection refused|502 bad gateway|response_status=502|kafka consumer group.*lag increasing|i/o timeout|read udp.*timeout)\b",
            )
            if avail_sub:
                avail = ServiceAvailability.DEGRADED
                avail_source = SignalSource.EXPLICIT
                avail_evidence = f"service degradation: '{avail_sub}'"
                impact_evidence.append(avail_evidence)
            else:
                avail_sub, avail_s, avail_e = self._find_span(
                    raw_log,
                    r"\b(restarted automatically|healthy replicas absorbed|self-healed|pod status.*running|request rejected status=401)\b",
                )
                if avail_sub:
                    avail = ServiceAvailability.AVAILABLE
                    avail_source = SignalSource.EXPLICIT
                    avail_evidence = f"service available: '{avail_sub}'"
                    impact_evidence.append(avail_evidence)
                elif service_error_observed:
                    # An error was observed but without proof of outage or persistent degradation
                    avail = ServiceAvailability.UNKNOWN
                    avail_source = SignalSource.DERIVED_SAFE
                    avail_evidence = "service error observed without outage proof"
                    impact_evidence.append(avail_evidence)

        grounded_signals["service_availability"] = GroundedSignal(
            value=avail.value,
            evidence=avail_evidence,
            substring=avail_sub,
            evidence_start=avail_s,
            evidence_end=avail_e,
            source=avail_source,
        )

        # ---------------------------------------------------------------------
        # 5. Blast Radius
        # A single UnknownHostException must NOT imply MULTI_SERVICE_DEGRADATION.
        # ---------------------------------------------------------------------
        blast = BlastRadius.UNKNOWN
        blast_source = SignalSource.UNKNOWN
        blast_evidence = "blast radius unknown"

        blast_sub, blast_s, blast_e = self._find_span(
            raw_log,
            r"\b(global outage|multi-region|cross-region|all regions|worldwide)\b",
        )
        if blast_sub:
            blast = BlastRadius.GLOBAL
            blast_source = SignalSource.EXPLICIT
            blast_evidence = f"global blast radius: '{blast_sub}'"
            impact_evidence.append(blast_evidence)
        else:
            # Multi-service requires multiple services explicitly impacted
            blast_sub, blast_s, blast_e = self._find_span(
                raw_log,
                r"\b(multi-service cascade|cascading failure|cluster-wide partition|multiple downstream services unavailable)\b",
            )
            if blast_sub:
                blast = BlastRadius.MULTI_SERVICE
                blast_source = SignalSource.EXPLICIT
                blast_evidence = f"multi-service cascade: '{blast_sub}'"
                impact_evidence.append(blast_evidence)
            else:
                # Single instance failure
                blast_sub, blast_s, blast_e = self._find_span(
                    raw_log,
                    r"\b(oomkilling container|container.*terminated.*oomkilled|exitcode=137|single pod|single instance|single container|isolated to|worker-\d+|evicting pod|document graph|delivery_tag=)\b",
                )
                if blast_sub:
                    blast = BlastRadius.SINGLE_INSTANCE
                    blast_source = SignalSource.EXPLICIT
                    blast_evidence = f"single instance failure: '{blast_sub}'"
                    impact_evidence.append(blast_evidence)
                else:
                    # Single service or dependency
                    blast_sub, blast_s, blast_e = self._find_span(
                        raw_log,
                        r"\b(unknownhostexception|upstream_service=|502.*upstream|connect\(\) failed.*connection refused|hikaripool|pool\.active|fatal: sorry, too many clients|transaction aborted after \d+ retries)\b",
                    )
                    if blast_sub:
                        blast = BlastRadius.SINGLE_SERVICE
                        blast_source = SignalSource.DERIVED_SAFE
                        blast_evidence = f"single service failure: '{blast_sub}'"
                        impact_evidence.append(blast_evidence)

        grounded_signals["blast_radius"] = GroundedSignal(
            value=blast.value,
            evidence=blast_evidence,
            substring=blast_sub,
            evidence_start=blast_s,
            evidence_end=blast_e,
            source=blast_source,
        )

        # ---------------------------------------------------------------------
        # 6. Customer Impact Detection
        # A single 500 must NOT infer SEVERE customer impact.
        # ---------------------------------------------------------------------
        cust = CustomerImpact.UNKNOWN
        cust_source = SignalSource.UNKNOWN
        cust_evidence = "customer impact unknown"

        cust_sub, cust_s, cust_e = self._find_span(
            raw_log,
            r"\b(widespread.*customer|all users unable|global customer outage|100% requests failing|critical business halt)\b",
        )
        if cust_sub:
            cust = CustomerImpact.SEVERE
            cust_source = SignalSource.EXPLICIT
            cust_evidence = f"severe customer impact: '{cust_sub}'"
            impact_evidence.append(cust_evidence)
        else:
            cust_sub, cust_s, cust_e = self._find_span(
                raw_log,
                r"\b(sla breach|oldest unprocessed message age|lag=\d+|request timed out after \d+ms.*pool\.waiting)\b",
            )
            if cust_sub:
                cust = CustomerImpact.HIGH
                cust_source = SignalSource.EXPLICIT
                cust_evidence = f"high customer impact / SLA breach: '{cust_sub}'"
                impact_evidence.append(cust_evidence)
            else:
                cust_sub, cust_s, cust_e = self._find_span(
                    raw_log,
                    r"\b(requeued redelivery_count|single task failure|malformed cyclic document|transient retry)\b",
                )
                if cust_sub:
                    cust = CustomerImpact.LIMITED
                    cust_source = SignalSource.DERIVED_SAFE
                    cust_evidence = f"limited customer impact: '{cust_sub}'"
                    impact_evidence.append(cust_evidence)
                else:
                    cust_sub, cust_s, cust_e = self._find_span(
                        raw_log,
                        r"\b(request rejected status=401|routine defense|zero user impact)\b",
                    )
                    if cust_sub:
                        cust = CustomerImpact.NONE
                        cust_source = SignalSource.EXPLICIT
                        cust_evidence = f"zero customer impact: '{cust_sub}'"
                        impact_evidence.append(cust_evidence)

        grounded_signals["customer_impact"] = GroundedSignal(
            value=cust.value,
            evidence=cust_evidence,
            substring=cust_sub,
            evidence_start=cust_s,
            evidence_end=cust_e,
            source=cust_source,
        )

        # ---------------------------------------------------------------------
        # 7. Redundancy Detection
        # ---------------------------------------------------------------------
        red = RedundancyState.UNKNOWN
        red_source = SignalSource.UNKNOWN
        red_evidence = "redundancy state unknown"

        red_sub, red_s, red_e = self._find_span(
            raw_log,
            r"\b(healthy replicas absorbed|failover active|redundancy intact|standby healthy)\b",
        )
        if red_sub:
            red = RedundancyState.AVAILABLE
            red_source = SignalSource.EXPLICIT
            red_evidence = f"redundancy intact: '{red_sub}'"
            impact_evidence.append(red_evidence)
        else:
            red_sub, red_s, red_e = self._find_span(
                raw_log,
                r"\b(pool\.active=\d+ pool\.idle=0|no healthy replicas|all replicas down|last standing replica)\b",
            )
            if red_sub:
                red = RedundancyState.NONE
                red_source = SignalSource.EXPLICIT
                red_evidence = f"redundancy depleted / exhausted: '{red_sub}'"
                impact_evidence.append(red_evidence)
            else:
                red_sub, red_s, red_e = self._find_span(
                    raw_log,
                    r"\b(\d+ of \d+ replicas|degraded redundancy|single point of failure)\b",
                )
                if red_sub:
                    red = RedundancyState.DEGRADED
                    red_source = SignalSource.EXPLICIT
                    red_evidence = f"degraded redundancy: '{red_sub}'"
                    impact_evidence.append(red_evidence)

        grounded_signals["redundancy_state"] = GroundedSignal(
            value=red.value,
            evidence=red_evidence,
            substring=red_sub,
            evidence_start=red_s,
            evidence_end=red_e,
            source=red_source,
        )

        return ImpactAssessment(
            service_availability=avail,
            blast_radius=blast,
            customer_impact=cust,
            redundancy_state=red,
            data_integrity=data_integrity,
            security_exposure=sec,
            environment=env,
            service_error_observed=service_error_observed,
            transaction_contention=transaction_contention,
            impact_evidence=impact_evidence,
            grounded_signals=grounded_signals,
        )
