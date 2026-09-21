"""LocalOps AI — Impact & Severity Schemas (Phase 14)."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.schemas.enums import Severity


class ServiceAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    PARTIAL = "PARTIAL"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


class BlastRadius(str, Enum):
    SINGLE_INSTANCE = "SINGLE_INSTANCE"
    SINGLE_SERVICE = "SINGLE_SERVICE"
    MULTI_SERVICE = "MULTI_SERVICE"
    MULTI_REGION = "MULTI_REGION"
    GLOBAL = "GLOBAL"
    UNKNOWN = "UNKNOWN"


class CustomerImpact(str, Enum):
    NONE = "NONE"
    LIMITED = "LIMITED"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"
    UNKNOWN = "UNKNOWN"


class RedundancyState(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class DataIntegrity(str, Enum):
    INTACT = "INTACT"
    AT_RISK = "AT_RISK"
    LOST_OR_CORRUPTED = "LOST_OR_CORRUPTED"
    UNKNOWN = "UNKNOWN"


class SecurityExposure(str, Enum):
    NONE = "NONE"
    SUSPICIOUS = "SUSPICIOUS"
    CONFIRMED = "CONFIRMED"
    ACTIVE_COMPROMISE = "ACTIVE_COMPROMISE"
    UNKNOWN = "UNKNOWN"


class EnvironmentType(str, Enum):
    PRODUCTION = "PRODUCTION"
    STAGING = "STAGING"
    DEVELOPMENT = "DEVELOPMENT"
    UNKNOWN = "UNKNOWN"


class SignalSource(str, Enum):
    EXPLICIT = "EXPLICIT"
    DERIVED = "DERIVED"
    UNKNOWN = "UNKNOWN"


class GroundedSignal(BaseModel):
    """Grounded operational impact signal linking an assessed value to exact log evidence."""

    model_config = ConfigDict(
        use_enum_values=True,
        extra="forbid",
    )

    value: str
    evidence: Optional[str] = None
    substring: Optional[str] = None
    evidence_start: Optional[int] = None
    evidence_end: Optional[int] = None
    source: SignalSource = SignalSource.UNKNOWN


class ImpactAssessment(BaseModel):
    """Structured assessment of operational impact signals extracted from logs/telemetry."""

    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        extra="forbid",
    )

    service_availability: ServiceAvailability = ServiceAvailability.UNKNOWN
    blast_radius: BlastRadius = BlastRadius.UNKNOWN
    customer_impact: CustomerImpact = CustomerImpact.UNKNOWN
    redundancy_state: RedundancyState = RedundancyState.UNKNOWN
    data_integrity: DataIntegrity = DataIntegrity.UNKNOWN
    security_exposure: SecurityExposure = SecurityExposure.NONE
    environment: EnvironmentType = EnvironmentType.PRODUCTION
    workaround_available: Optional[bool] = None
    incident_duration_minutes: Optional[float] = None
    affected_users_estimate: Optional[int] = None
    impact_evidence: List[str] = Field(default_factory=list)
    grounded_signals: Dict[str, GroundedSignal] = Field(default_factory=dict)


class SeverityDecision(BaseModel):
    """Deterministic severity policy evaluation output."""

    model_config = ConfigDict(
        use_enum_values=True,
        extra="forbid",
    )

    severity: Severity
    reason_code: str
    policy_version: str = "1.0.0"
    is_insufficient_evidence: bool = False
    evidence_signals: List[str] = Field(default_factory=list)
