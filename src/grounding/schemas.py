"""LocalOps AI — Grounding Schemas.

Data structures and telemetry for output grounding and validation.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GroundingTelemetry(BaseModel):
    """Internal telemetry tracking grounding sanitizations and corrections."""

    model_config = ConfigDict(
        extra="forbid",
    )

    grounding_corrections_count: int = 0
    unsupported_ip_removed: int = 0
    unsupported_hostname_removed: int = 0
    unsupported_numeric_claim_removed: int = 0
    rewritten_fields: List[str] = Field(default_factory=list)
    corrections_applied: List[str] = Field(default_factory=list)


class SanitizedOutput(BaseModel):
    """Result of grounding sanitization."""

    model_config = ConfigDict(
        extra="forbid",
    )

    root_cause: str
    suggested_action: str
    telemetry: GroundingTelemetry
