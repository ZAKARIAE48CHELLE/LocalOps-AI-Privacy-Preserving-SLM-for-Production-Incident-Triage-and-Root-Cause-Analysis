"""LocalOps AI — API Middleware (Privacy-Safe Telemetry & Request Tracking)."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.settings import settings
from src.observability.metrics import MetricsRegistry

logger = logging.getLogger("localops.api.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Generates request_id, tracks latency, updates metrics, and provides privacy-safe logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        metrics = MetricsRegistry.get_instance()
        metrics.inflight_requests += 1

        req_id = request.headers.get("X-Request-ID")
        if not req_id:
            req_id = f"req_{uuid.uuid4().hex[:12]}"

        # Store in request state for downstream handlers
        request.state.request_id = req_id
        start_time = time.time()

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000.0

            metrics.inc_request(request.url.path, response.status_code)

            final_req_id = getattr(request.state, "request_id", req_id)
            response.headers["X-Request-ID"] = final_req_id
            response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

            # Privacy-safe access log: NEVER logs raw request payload or triage details
            logger.info(
                f"method={request.method} path={request.url.path} "
                f"status={response.status_code} latency_ms={duration_ms:.2f} "
                f"request_id={final_req_id}"
            )
            return response

        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000.0
            metrics.inc_error(request.url.path, exc.__class__.__name__)
            logger.error(
                f"method={request.method} path={request.url.path} "
                f"error={exc} latency_ms={duration_ms:.2f} request_id={req_id}"
            )
            raise exc
        finally:
            metrics.inflight_requests -= 1
