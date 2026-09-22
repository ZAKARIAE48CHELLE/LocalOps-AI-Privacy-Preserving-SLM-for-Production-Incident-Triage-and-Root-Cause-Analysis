"""LocalOps AI — API Pydantic Schemas."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from src.schemas.triage import LogTriageOutput


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "localops-ai"
    version: str = "1.0.0"
    timestamp: float = Field(default_factory=time.time)


class ReadinessResponse(BaseModel):
    ready: bool
    service: str = "localops-ai"
    tokenizer_loaded: bool
    base_model_loaded: bool
    adapter_loaded: bool
    cuda_available: bool
    warmup_completed: bool
    message: str = "Service ready for inference"


class ModelInfoResponse(BaseModel):
    base_model_id: str
    adapter_identifier: str
    adapter_source_checkpoint: str
    quantization_mode: str
    device: str
    schema_version: str = "1.0.0"
    service_version: str = "1.0.0"
    max_input_tokens: int
    max_new_tokens: int
    decoding_mode: str = "deterministic_greedy"


class TriageRequest(BaseModel):
    raw_log: str = Field(..., description="Raw production log text to analyze")
    request_id: Optional[str] = Field(None, description="Optional caller-provided request tracking ID")

    @field_validator("raw_log")
    @classmethod
    def validate_raw_log(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("raw_log cannot be empty or whitespace only.")
        if len(s) > 32768:
            raise ValueError("raw_log exceeds maximum character limit of 32768.")
        return v


class InferenceTelemetry(BaseModel):
    latency_ms: float
    prompt_tokens: int
    generated_tokens: int
    severity_source: Optional[str] = "POLICY_ENGINE"
    severity_reason_code: Optional[str] = None
    grounding_corrections_count: int = 0
    unsupported_ip_removed: int = 0
    unsupported_hostname_removed: int = 0
    unsupported_numeric_claim_removed: int = 0


class TriageResponse(BaseModel):
    request_id: str
    result: LogTriageOutput
    inference: InferenceTelemetry


class BatchTriageItem(BaseModel):
    raw_log: str
    request_id: Optional[str] = None


class BatchTriageRequest(BaseModel):
    items: List[BatchTriageItem] = Field(..., min_length=1, max_length=32)


class BatchTriageItemResult(BaseModel):
    request_id: str
    status: str  # "success" or "error"
    result: Optional[LogTriageOutput] = None
    error: Optional[Dict[str, str]] = None
    inference: Optional[InferenceTelemetry] = None


class BatchTriageResponse(BaseModel):
    request_id: str
    total_items: int
    successful_items: int
    failed_items: int
    items: List[BatchTriageItemResult]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    request_id: str
    error: ErrorDetail
