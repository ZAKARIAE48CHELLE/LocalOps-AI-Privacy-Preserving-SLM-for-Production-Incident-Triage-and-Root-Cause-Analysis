"""
Core Pydantic contract for incident triage outputs.
Strictly validates model predictions against domain rules.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.enums import IncidentType, Severity


class LogTriageOutput(BaseModel):
    """
    Structured prediction contract for local SLM incident triage.

    Attributes:
        incident_type: High-level category of the incident.
        severity: Operational and business impact tier (P1_CRITICAL to P4_LOW).
        affected_service: Identifier of the impacted service, component, or resource.
        root_cause: Concise technical diagnosis of the underlying cause.
        suggested_action: Immediate recommended mitigation or investigation step.
        confidence: Model-reported prediction confidence score in [0.0, 1.0].
            Note: This initially represents raw model-reported confidence,
            not a statistically calibrated probability distribution.
        evidence: Verifiable excerpts, quotes, or metric signals from the log
            substantiating the triage assessment. At least one non-empty
            evidence item is required.
    """

    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    incident_type: IncidentType = Field(
        ...,
        description="High-level category of the incident.",
    )
    severity: Severity = Field(
        ...,
        description="Operational severity level based on business impact.",
    )
    affected_service: str = Field(
        ...,
        min_length=1,
        description="Name of the affected service or infrastructure component.",
    )
    root_cause: str = Field(
        ...,
        min_length=1,
        description="Concise description of the likely root cause.",
    )
    suggested_action: str = Field(
        ...,
        min_length=1,
        description="Recommended immediate remediation or troubleshooting action.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model-reported confidence score between 0.0 and 1.0.",
    )
    evidence: list[str] = Field(
        ...,
        min_length=1,
        description="Log excerpts or signals directly supporting the diagnosis.",
    )

    @field_validator("affected_service", "root_cause", "suggested_action", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, v: object, info) -> str:
        if not isinstance(v, str):
            raise ValueError(f"{info.field_name} must be a string.")
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError(f"{info.field_name} must not be empty or whitespace-only.")
        return v_stripped

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence_list(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            raise ValueError("evidence must be a list of non-empty strings.")
        if len(v) == 0:
            raise ValueError("evidence must contain at least one supporting excerpt.")

        cleaned: list[str] = []
        for idx, item in enumerate(v):
            if not isinstance(item, str):
                raise ValueError(f"evidence item at index {idx} must be a string.")
            item_stripped = item.strip()
            if not item_stripped:
                raise ValueError(
                    f"evidence item at index {idx} must not be empty or whitespace-only."
                )
            cleaned.append(item_stripped)

        return cleaned
