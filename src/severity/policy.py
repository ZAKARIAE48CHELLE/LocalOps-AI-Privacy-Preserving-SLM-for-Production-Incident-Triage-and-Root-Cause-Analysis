"""LocalOps AI — Severity Policy Engine (Phase 14).

Deterministically maps operational impact signals (ImpactAssessment) to
operational severity tiers (P1_CRITICAL, P2_HIGH, P3_MEDIUM, P4_LOW)
according to canonical enterprise SRE policies.
"""

from __future__ import annotations

from typing import List, Optional
from src.schemas.enums import Severity
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


class SeverityPolicyEngine:
    """Deterministic severity evaluation engine based on operational impact."""

    VERSION = "1.0.0"

    def evaluate(self, impact: ImpactAssessment) -> SeverityDecision:
        """Evaluates an ImpactAssessment against prioritized policy rules."""

        # ---------------------------------------------------------------------
        # 1. P1_CRITICAL Rules (Catastrophic Impact / Severe Security / Data Loss)
        # ---------------------------------------------------------------------
        if impact.security_exposure == SecurityExposure.ACTIVE_COMPROMISE:
            return SeverityDecision(
                severity=Severity.P1_CRITICAL,
                reason_code="ACTIVE_SECURITY_COMPROMISE",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.data_integrity == DataIntegrity.LOST_OR_CORRUPTED
            and impact.environment == EnvironmentType.PRODUCTION
        ):
            return SeverityDecision(
                severity=Severity.P1_CRITICAL,
                reason_code="CRITICAL_DATA_LOSS",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.service_availability == ServiceAvailability.DOWN
            and impact.blast_radius in (
                BlastRadius.MULTI_SERVICE,
                BlastRadius.MULTI_REGION,
                BlastRadius.GLOBAL,
            )
            and impact.environment == EnvironmentType.PRODUCTION
        ):
            return SeverityDecision(
                severity=Severity.P1_CRITICAL,
                reason_code="GLOBAL_OR_CASCADING_OUTAGE",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.customer_impact == CustomerImpact.SEVERE
            and (
                impact.blast_radius in (BlastRadius.MULTI_REGION, BlastRadius.GLOBAL)
                or impact.workaround_available is False
                or impact.service_availability in (ServiceAvailability.DOWN, ServiceAvailability.PARTIAL)
            )
        ):
            return SeverityDecision(
                severity=Severity.P1_CRITICAL,
                reason_code="WIDESPREAD_SEVERE_IMPACT",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        # ---------------------------------------------------------------------
        # 2. P4_LOW Rules (Non-Production / Transient Warnings / Zero Impact)
        # ---------------------------------------------------------------------
        if (
            impact.environment in (EnvironmentType.STAGING, EnvironmentType.DEVELOPMENT)
            and impact.customer_impact in (CustomerImpact.NONE, CustomerImpact.LIMITED, CustomerImpact.UNKNOWN)
        ):
            return SeverityDecision(
                severity=Severity.P4_LOW,
                reason_code="NON_PRODUCTION_ENVIRONMENT",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.service_availability == ServiceAvailability.AVAILABLE
            and impact.customer_impact == CustomerImpact.NONE
            and impact.security_exposure == SecurityExposure.NONE
            and impact.data_integrity in (DataIntegrity.INTACT, DataIntegrity.UNKNOWN)
        ):
            return SeverityDecision(
                severity=Severity.P4_LOW,
                reason_code="NO_OPERATIONAL_IMPACT",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        # ---------------------------------------------------------------------
        # 3. P2_HIGH Rules (Major Degradation / High Impact / Saturated Capacity)
        # ---------------------------------------------------------------------
        if impact.security_exposure == SecurityExposure.CONFIRMED:
            return SeverityDecision(
                severity=Severity.P2_HIGH,
                reason_code="CONFIRMED_SECURITY_EVENT",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.data_integrity == DataIntegrity.AT_RISK
            and impact.environment == EnvironmentType.PRODUCTION
        ):
            return SeverityDecision(
                severity=Severity.P2_HIGH,
                reason_code="DATA_INTEGRITY_AT_RISK",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.service_availability in (ServiceAvailability.DOWN, ServiceAvailability.PARTIAL, ServiceAvailability.DEGRADED)
            and impact.customer_impact in (CustomerImpact.HIGH, CustomerImpact.SEVERE)
        ):
            return SeverityDecision(
                severity=Severity.P2_HIGH,
                reason_code="MAJOR_SERVICE_DEGRADATION",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.redundancy_state in (RedundancyState.DEGRADED, RedundancyState.NONE)
            and impact.service_availability in (ServiceAvailability.DEGRADED, ServiceAvailability.DOWN, ServiceAvailability.PARTIAL)
            and impact.environment == EnvironmentType.PRODUCTION
        ):
            return SeverityDecision(
                severity=Severity.P2_HIGH,
                reason_code="REDUNDANCY_DEPLETED",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.blast_radius in (BlastRadius.MULTI_SERVICE, BlastRadius.MULTI_REGION)
            and impact.service_availability in (ServiceAvailability.DEGRADED, ServiceAvailability.PARTIAL, ServiceAvailability.DOWN)
            and impact.environment == EnvironmentType.PRODUCTION
        ):
            return SeverityDecision(
                severity=Severity.P2_HIGH,
                reason_code="MULTI_SERVICE_DEGRADATION",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.blast_radius == BlastRadius.SINGLE_SERVICE
            and impact.customer_impact == CustomerImpact.HIGH
            and impact.workaround_available is False
        ):
            return SeverityDecision(
                severity=Severity.P2_HIGH,
                reason_code="CRITICAL_PATH_DEGRADED",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        # ---------------------------------------------------------------------
        # 4. P3_MEDIUM Rules (Localized Failure / Healthy Redundancy / Limited Impact)
        # ---------------------------------------------------------------------
        if impact.blast_radius == BlastRadius.SINGLE_INSTANCE:
            return SeverityDecision(
                severity=Severity.P3_MEDIUM,
                reason_code="LOCALIZED_INSTANCE_FAILURE",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.blast_radius in (BlastRadius.SINGLE_INSTANCE, BlastRadius.SINGLE_SERVICE)
            and impact.redundancy_state == RedundancyState.AVAILABLE
            and impact.customer_impact in (CustomerImpact.NONE, CustomerImpact.LIMITED, CustomerImpact.MODERATE)
        ):
            return SeverityDecision(
                severity=Severity.P3_MEDIUM,
                reason_code="LOCALIZED_WITH_REDUNDANCY",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.service_availability == ServiceAvailability.DEGRADED
            and impact.customer_impact == CustomerImpact.LIMITED
        ):
            return SeverityDecision(
                severity=Severity.P3_MEDIUM,
                reason_code="LIMITED_SERVICE_DEGRADATION",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        if (
            impact.security_exposure == SecurityExposure.SUSPICIOUS
            and impact.blast_radius == BlastRadius.SINGLE_INSTANCE
        ):
            return SeverityDecision(
                severity=Severity.P3_MEDIUM,
                reason_code="SUSPICIOUS_ANOMALY",
                policy_version=self.VERSION,
                evidence_signals=impact.impact_evidence,
            )

        # ---------------------------------------------------------------------
        # 5. Default Fallback (Indicates Insufficient Explicit Impact Evidence)
        # ---------------------------------------------------------------------
        return SeverityDecision(
            severity=Severity.P3_MEDIUM,
            reason_code="INSUFFICIENT_IMPACT_EVIDENCE",
            policy_version=self.VERSION,
            is_insufficient_evidence=True,
            evidence_signals=impact.impact_evidence,
        )
