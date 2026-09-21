"""
Data models and definitions for LocalOps AI synthetic dataset engineering.
Strictly reuses Phase 2 LogTriageOutput, IncidentFamily, IncidentType, and Severity.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from src.schemas.enums import IncidentFamily, Severity
from src.schemas.triage import LogTriageOutput


class DiagnosticClarity(str, Enum):
    """
    Diagnostic clarity band used to derive synthetic heuristic confidence.
    Not a calibrated probability distribution.
    """

    EXPLICIT = "EXPLICIT"    # ~0.90 - 0.98: Direct stack trace / definitive error signature
    CLEAR = "CLEAR"          # ~0.78 - 0.88: Clear symptoms requiring mild inference
    AMBIGUOUS = "AMBIGUOUS"  # ~0.55 - 0.72: Partial log snippet / interleaved noise


class NoiseProfile(str, Enum):
    """Log noise profiles injected around the primary incident."""

    NONE = "NONE"      # Only primary incident log lines
    LIGHT = "LIGHT"    # 1-3 benign context lines (normal requests, routine metrics)
    MEDIUM = "MEDIUM"  # Multiple benign distractors (retries, cache misses, health checks)


class DatasetSplit(str, Enum):
    """Dataset partition assignment."""

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class RecordMetadata(BaseModel):
    """Comprehensive metadata for a synthetic incident record."""

    model_config = ConfigDict(extra="forbid")

    incident_family: IncidentFamily
    template_id: str
    split: str
    technology: str
    runtime: str
    signature_profile: str
    environment: str
    noise_profile: str
    diagnostic_clarity: str
    root_cause_variant_id: str
    action_variant_id: str
    failure_mechanism: Optional[str] = None
    generator_version: str


class DatasetRecord(BaseModel):
    """
    Top-level synthetic dataset record.
    target strictly validates against LogTriageOutput from Phase 2.
    """

    model_config = ConfigDict(extra="forbid")

    incident_id: str = Field(..., description="Deterministic incident identifier.")
    raw_log: str = Field(..., min_length=1, description="Production-style log content.")
    target: LogTriageOutput = Field(..., description="Validated triage target output.")
    metadata: RecordMetadata = Field(..., description="Traceable generation metadata.")

    @property
    def input_log(self) -> str:
        """Alias for raw_log for backward/pipeline compatibility."""
        return self.raw_log


class ImpactScenario(BaseModel):
    """
    Operational impact scenario grounding severity in observable log text.
    In accordance with Phase 2 Severity Policy, log must contain observable impact.
    """

    model_config = ConfigDict(extra="forbid")

    severity: Severity
    impact_line: str
    diagnostic_clarity: Optional[DiagnosticClarity] = None
    root_cause_key: Optional[str] = None
    action_key: Optional[str] = None
