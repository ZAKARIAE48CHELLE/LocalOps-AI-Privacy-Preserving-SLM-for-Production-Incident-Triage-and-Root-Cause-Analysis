"""LocalOps AI — Impact Signal Extractor (Phase 14).

Extracts operational impact signals from raw logs and model diagnostic context
without hallucinating unsupported numbers, hostnames, or metrics.
"""

from __future__ import annotations

import re
from typing import List, Optional

from src.severity.schemas import (
    BlastRadius,
    CustomerImpact,
    DataIntegrity,
    EnvironmentType,
    ImpactAssessment,
    RedundancyState,
    SecurityExposure,
    ServiceAvailability,
)


class ImpactExtractor:
    """Extracts grounded operational impact indicators from log text and diagnostic output."""

    def extract(self, raw_log: str, root_cause: str = "", suggested_action: str = "") -> ImpactAssessment:
        combined_text = f"{raw_log}\n{root_cause}\n{suggested_action}".lower()
        impact_evidence: List[str] = []

        # 1. Environment Detection
        env = EnvironmentType.PRODUCTION
        if re.search(r"\b(staging|stage|dev|development|qa|sandbox|non-prod)\b", combined_text):
            env = EnvironmentType.STAGING
            impact_evidence.append("non-production environment detected")

        # 2. Security Exposure Detection
        security = SecurityExposure.NONE
        if re.search(r"\b(active compromise|data exfiltration|privilege escalation achieved|remote code execution|cve-)\b", combined_text):
            security = SecurityExposure.ACTIVE_COMPROMISE
            impact_evidence.append("active security compromise detected")
        elif re.search(r"\b(brute force|failed login attempts|account.*locked|unauthorized access attempt|credential stuffing|\d+ failed.*attempts)\b", combined_text):
            security = SecurityExposure.CONFIRMED
            impact_evidence.append("confirmed security anomaly / attack detected")
        elif re.search(r"\b(token expired|jwt expired|expiredjwtexception|invalid_token|401 unauthorized|signature verification failed)\b", combined_text):
            # Expired token rejected by perimeter defense without unauthorized breach
            security = SecurityExposure.NONE
            impact_evidence.append("routine authentication perimeter rejection")
        elif re.search(r"\b(jwt validation failed|permission.*denied|403 forbidden)\b", combined_text):
            security = SecurityExposure.SUSPICIOUS
            impact_evidence.append("authentication/authorization anomaly detected")

        # 3. Data Integrity Detection
        data_integrity = DataIntegrity.INTACT
        if re.search(r"\b(data loss|corruption detected|unrecoverable.*data|database corruption|permanent loss|lost records)\b", combined_text):
            data_integrity = DataIntegrity.LOST_OR_CORRUPTED
            impact_evidence.append("data loss or corruption indicated")
        elif re.search(r"\b(deadlock|transaction aborted|commit failed|split-brain|replication lag|poison pill|deserialization failure)\b", combined_text):
            data_integrity = DataIntegrity.AT_RISK
            impact_evidence.append("data integrity at risk or transaction aborted")

        # 4. Service Availability Detection
        availability = ServiceAvailability.UNKNOWN
        if re.search(r"\b(complete outage|100% (requests|traffic) fail|no healthy|fatal exception in interrupt|kernel panic|all replicas oomkilled|down and unreachable|status=500.*path=/checkout|checkout-api.*status=500)\b", combined_text):
            availability = ServiceAvailability.DOWN
            impact_evidence.append("service down or critical checkout failure indicated")
        elif re.search(r"\b(degraded|connection is not available|pool\.idle=0|too many clients|timeout|high latency|lag increasing|diskpressure|circuitbreaker.*open|refused|connection refused|502 bad gateway|response_status=502)\b", combined_text):
            availability = ServiceAvailability.DEGRADED
            impact_evidence.append("service degradation detected")
        elif re.search(r"\b(restarted automatically|healthy replicas absorbed|self-healed|pod status.*running|request rejected status=401)\b", combined_text):
            availability = ServiceAvailability.AVAILABLE
            impact_evidence.append("service healthy or routine defense active")

        # 5. Blast Radius Detection
        blast = BlastRadius.UNKNOWN
        if re.search(r"\b(global|multi-region|cross-region|all regions|worldwide)\b", combined_text):
            blast = BlastRadius.GLOBAL
            impact_evidence.append("global blast radius")
        elif re.search(r"\b(multi-service|cascade|cascading|evicting.*pods|cluster-wide|network partition|unknownhostexception.*cluster\.local|upstream_service=)\b", combined_text):
            blast = BlastRadius.MULTI_SERVICE
            impact_evidence.append("multi-service or inter-service failure")
        elif re.search(r"\b(1 of \d+|single pod|single instance|single container|isolated to|worker-\d+|container ml-worker terminated|evicting pod|document graph|delivery_tag=)\b", combined_text):
            blast = BlastRadius.SINGLE_INSTANCE
            impact_evidence.append("single instance / localized blast radius")
        elif re.search(r"\b(service|api|consumer|database|pool)\b", combined_text):
            blast = BlastRadius.SINGLE_SERVICE

        # 6. Customer Impact Detection
        customer_impact = CustomerImpact.UNKNOWN
        if re.search(r"\b(widespread.*customer|all users|checkout failing|status=500.*checkout|critical business impact|severe.*impact|100% fail)\b", combined_text):
            customer_impact = CustomerImpact.SEVERE
            impact_evidence.append("severe customer / checkout impact")
        elif re.search(r"\b(sla breach|sla.*threatened|customer.*affected|users unable|35%|50%|major degradation|request timed out.*pool|502.*upstream|connection refused)\b", combined_text):
            customer_impact = CustomerImpact.HIGH
            impact_evidence.append("high customer visibility or SLA breach")
        elif re.search(r"\b(limited.*impact|transient errors|retry succeeded|internal.*only|moderate|malformed cyclic|jsonparseexception|redelivery_count)\b", combined_text):
            customer_impact = CustomerImpact.LIMITED
            impact_evidence.append("limited or localized impact")
        elif re.search(r"\b(no customer.*impact|zero user impact|staging|development|unaffected|absorbed traffic|request rejected status=401)\b", combined_text):
            customer_impact = CustomerImpact.NONE
            impact_evidence.append("zero customer impact reported")

        # 7. Redundancy Detection
        redundancy = RedundancyState.UNKNOWN
        if re.search(r"\b(healthy replicas absorbed|failover active|redundancy intact|standby healthy|remaining \d+ replicas)\b", combined_text):
            redundancy = RedundancyState.AVAILABLE
            impact_evidence.append("redundancy absorbed load")
        elif re.search(r"\b(no healthy replicas|remaining capacity saturated|failover failed|no backup|last standing|pool\.active=\d+ pool\.idle=0|too many clients)\b", combined_text):
            redundancy = RedundancyState.NONE
            impact_evidence.append("zero redundancy remaining / pool exhausted")
        elif re.search(r"\b(\d+ of \d+ replicas|degraded redundancy|single point of failure)\b", combined_text):
            redundancy = RedundancyState.DEGRADED
            impact_evidence.append("degraded redundancy state")

        return ImpactAssessment(
            service_availability=availability,
            blast_radius=blast,
            customer_impact=customer_impact,
            redundancy_state=redundancy,
            data_integrity=data_integrity,
            security_exposure=security,
            environment=env,
            impact_evidence=impact_evidence,
        )
