"""LocalOps AI — Retrieval Schemas & Models."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.api.schemas import InferenceTelemetry
from src.schemas.enums import IncidentType, Severity
from src.schemas.triage import LogTriageOutput


class RunbookChunk(BaseModel):
    """Represents an atomic, searchable section within an operational runbook."""
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(..., description="Unique chunk identifier, e.g. doc_section")
    document: str = Field(..., description="Runbook markdown file basename")
    title: str = Field(..., description="Runbook human-readable title")
    section: str = Field(..., description="Section title (e.g. Symptoms, Immediate Mitigation)")
    incident_type: IncidentType = Field(..., description="Associated IncidentType enum")
    affected_services: List[str] = Field(default_factory=list, description="Target microservices")
    keywords: List[str] = Field(default_factory=list, description="Key technical terms & error signatures")
    content: str = Field(..., description="Raw text content of the runbook section")


class RemediationRecommendation(BaseModel):
    """Structured remediation recommendation grounded in an indexed runbook."""
    model_config = ConfigDict(extra="forbid")

    runbook_document: str = Field(..., description="Referenced runbook filename")
    runbook_title: str = Field(..., description="Referenced runbook title")
    section: str = Field(..., description="Referenced section, e.g. Immediate Mitigation")
    content: str = Field(..., description="Specific remediation steps extracted from the runbook")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Confidence/similarity score of the match")
    matched_keywords: List[str] = Field(default_factory=list, description="Keywords matching the incident log")


class EnrichedTriageResponse(BaseModel):
    """Enriched triage response wrapping LogTriageOutput with grounded remediation."""
    model_config = ConfigDict(extra="forbid")

    request_id: str
    result: LogTriageOutput = Field(..., description="Strict Phase 2 model-predicted triage output")
    remediation: Optional[RemediationRecommendation] = Field(
        None, description="Grounded operational runbook recommendation, if retrieved"
    )
    inference: InferenceTelemetry
