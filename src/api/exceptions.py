"""LocalOps AI — API Exception Hierarchy."""

from __future__ import annotations
from typing import Optional


class LocalOpsApiException(Exception):
    """Base exception for all LocalOps AI API errors."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, request_id: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.request_id = request_id


class InvalidRequestError(LocalOpsApiException):
    status_code = 400
    error_code = "INVALID_REQUEST"


class InputTooLargeError(LocalOpsApiException):
    status_code = 413
    error_code = "INPUT_TOO_LARGE"


class ModelNotReadyError(LocalOpsApiException):
    status_code = 503
    error_code = "MODEL_NOT_READY"


class ModelOutputInvalidError(LocalOpsApiException):
    status_code = 502
    error_code = "MODEL_OUTPUT_INVALID"


class GpuResourceExhaustedError(LocalOpsApiException):
    status_code = 503
    error_code = "GPU_RESOURCE_EXHAUSTED"


class InferenceTimeoutError(LocalOpsApiException):
    status_code = 504
    error_code = "INFERENCE_TIMEOUT"


class InternalServiceError(LocalOpsApiException):
    status_code = 500
    error_code = "INTERNAL_ERROR"
