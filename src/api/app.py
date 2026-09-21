"""LocalOps AI — FastAPI Production Application."""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import List

from pathlib import Path
import json

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from src.api.dependencies import (
    get_concurrency_limiter,
    get_inference_service,
    get_model_manager,
    get_runbook_retriever,
)
from src.observability.metrics import MetricsRegistry
from src.retrieval.retriever import RunbookRetriever
from src.retrieval.schemas import EnrichedTriageResponse
from src.api.exceptions import (
    InputTooLargeError,
    InvalidRequestError,
    LocalOpsApiException,
    ModelNotReadyError,
)
from src.api.inference_service import InferenceService
from src.api.middleware import RequestContextMiddleware
from src.api.model_manager import ModelManager
from src.api.schemas import (
    BatchTriageItemResult,
    BatchTriageRequest,
    BatchTriageResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    ModelInfoResponse,
    ReadinessResponse,
    TriageRequest,
    TriageResponse,
)
from src.api.settings import settings

logger = logging.getLogger("localops.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for model loading, warmup, and graceful cleanup."""
    logger.info("Initializing LocalOps AI application lifecycle...")
    manager = get_model_manager()
    try:
        # Load model during startup
        manager.load_model()
    except Exception as e:
        logger.error(f"Startup model loading failed: {e}. API will start in unready state.")

    yield

    logger.info("Shutting down LocalOps AI application lifecycle...")
    manager.unload_model()


def create_app() -> FastAPI:
    """Factory creating configured FastAPI instance."""
    app = FastAPI(
        title="LocalOps AI — Production Incident Triage API",
        description="Privacy-preserving, edge-deployable Small Language Model API for incident root-cause triage.",
        version=settings.service.version,
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(RequestContextMiddleware)

    if settings.service.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.service.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # -------------------------------------------------------------------------
    # Exception Handlers
    # -------------------------------------------------------------------------
    @app.exception_handler(LocalOpsApiException)
    async def localops_exception_handler(request: Request, exc: LocalOpsApiException):
        req_id = getattr(request.state, "request_id", None) or exc.request_id or f"req_{uuid.uuid4().hex[:12]}"
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                request_id=req_id,
                error=ErrorDetail(code=exc.error_code, message=exc.message),
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
        err_msg = "; ".join([f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()])
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                request_id=req_id,
                error=ErrorDetail(code="INVALID_REQUEST", message=err_msg),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
        logger.error(f"Unhandled server error on request {req_id}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                request_id=req_id,
                error=ErrorDetail(code="INTERNAL_ERROR", message="An unexpected internal service error occurred."),
            ).model_dump(),
        )

    # -------------------------------------------------------------------------
    # Endpoints
    # -------------------------------------------------------------------------
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def get_health():
        """Process liveness probe; does not invoke inference."""
        return HealthResponse(
            status="ok",
            service=settings.service.name,
            version=settings.service.version,
        )

    @app.get("/ready", response_model=ReadinessResponse, tags=["Health"])
    async def get_readiness(manager: ModelManager = Depends(get_model_manager)):
        """Readiness probe indicating whether model is resident and ready for inference."""
        is_ready = manager.is_ready
        status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

        resp = ReadinessResponse(
            ready=is_ready,
            service=settings.service.name,
            tokenizer_loaded=manager.tokenizer is not None,
            base_model_loaded=manager.is_loaded,
            adapter_loaded=manager.model is not None,
            cuda_available=manager.device == "cuda",
            warmup_completed=manager.warmup_completed,
            message="Service ready for inference" if is_ready else "Model not loaded or warming up",
        )
        return JSONResponse(status_code=status_code, content=resp.model_dump())

    @app.get("/api/v1/model-info", response_model=ModelInfoResponse, tags=["Metadata"])
    async def get_model_info(manager: ModelManager = Depends(get_model_manager)):
        """Returns non-sensitive model metadata without leaking local file paths."""
        return ModelInfoResponse(
            base_model_id=settings.model.base_model_id,
            adapter_identifier="localops-qlora-adapter",
            adapter_source_checkpoint=settings.model.adapter_source_checkpoint,
            quantization_mode="4-bit NF4",
            device="cuda" if manager.device == "cuda" else "cpu",
            schema_version="1.0.0",
            service_version=settings.service.version,
            max_input_tokens=settings.inference.max_input_tokens,
            max_new_tokens=settings.inference.max_new_tokens,
            decoding_mode="deterministic_greedy",
        )

    @app.post("/api/v1/triage", response_model=TriageResponse, tags=["Triage"])
    async def triage_log(
        req: TriageRequest,
        request: Request,
        response: Response,
        service: InferenceService = Depends(get_inference_service),
        semaphore: asyncio.Semaphore = Depends(get_concurrency_limiter),
    ):
        """Analyzes a single production log line and returns strictly validated root cause triage."""
        req_id = req.request_id or getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id
        response.headers["X-Request-ID"] = req_id

        # Acquire concurrency semaphore to protect shared GPU resource
        async with semaphore:
            result, telem = await asyncio.to_thread(service.triage_single, req.raw_log, req_id)

        # Record telemetry in Prometheus metrics registry
        metrics = MetricsRegistry.get_instance()
        metrics.observe_inference_duration(telem.latency_ms / 1000.0)
        metrics.inc_tokens(telem.prompt_tokens, telem.generated_tokens)
        inc_type_str = result.incident_type.value if hasattr(result.incident_type, "value") else str(result.incident_type)
        sev_str = result.severity.value if hasattr(result.severity, "value") else str(result.severity)
        metrics.inc_prediction(inc_type_str, sev_str)

        return TriageResponse(
            request_id=req_id,
            result=result,
            inference=telem,
        )

    @app.post("/api/v1/triage/enriched", response_model=EnrichedTriageResponse, tags=["Triage", "RAG"])
    async def triage_log_enriched(
        req: TriageRequest,
        request: Request,
        response: Response,
        service: InferenceService = Depends(get_inference_service),
        retriever: RunbookRetriever = Depends(get_runbook_retriever),
        semaphore: asyncio.Semaphore = Depends(get_concurrency_limiter),
    ):
        """Analyzes a log line and grounds remediation recommendations in indexed runbooks."""
        req_id = req.request_id or getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id
        response.headers["X-Request-ID"] = req_id

        async with semaphore:
            result, telem = await asyncio.to_thread(service.triage_single, req.raw_log, req_id)

        remediation = retriever.retrieve(
            incident_type=result.incident_type,
            affected_service=result.affected_service,
            root_cause=result.root_cause,
            raw_log=req.raw_log,
        )

        metrics = MetricsRegistry.get_instance()
        metrics.observe_inference_duration(telem.latency_ms / 1000.0)
        metrics.inc_tokens(telem.prompt_tokens, telem.generated_tokens)
        inc_type_str = result.incident_type.value if hasattr(result.incident_type, "value") else str(result.incident_type)
        sev_str = result.severity.value if hasattr(result.severity, "value") else str(result.severity)
        metrics.inc_prediction(inc_type_str, sev_str)
        metrics.inc_rag_request(hit=bool(remediation))

        return EnrichedTriageResponse(
            request_id=req_id,
            result=result,
            remediation=remediation,
            inference=telem,
        )

    @app.get("/metrics", tags=["Observability"])
    async def get_prometheus_metrics():
        """Exposes Prometheus text exposition format metrics."""
        content = MetricsRegistry.get_instance().generate_prometheus_text()
        return PlainTextResponse(content=content, media_type="text/plain; version=0.0.4")

    @app.get("/api/v1/telemetry/live", tags=["Observability"])
    async def get_live_telemetry():
        """Provides real-time aggregated service telemetry for Mission Control dashboard."""
        return MetricsRegistry.get_instance().get_dashboard_summary()



    @app.post("/api/v1/triage/batch", response_model=BatchTriageResponse, tags=["Triage"])
    async def triage_logs_batch(
        req: BatchTriageRequest,
        request: Request,
        response: Response,
        service: InferenceService = Depends(get_inference_service),
        semaphore: asyncio.Semaphore = Depends(get_concurrency_limiter),
    ):
        """Analyzes a batch of production logs with micro-batching to prevent OOM."""
        batch_req_id = getattr(request.state, "request_id", None) or f"batch_{uuid.uuid4().hex[:12]}"
        response.headers["X-Request-ID"] = batch_req_id

        if len(req.items) > settings.inference.batch_max_items:
            raise InputTooLargeError(
                f"Batch size {len(req.items)} exceeds maximum allowed limit of {settings.inference.batch_max_items}.",
                request_id=batch_req_id,
            )

        logs = [item.raw_log for item in req.items]
        item_req_ids = [
            item.request_id or f"{batch_req_id}_{idx}"
            for idx, item in enumerate(req.items)
        ]

        async with semaphore:
            batch_results = await asyncio.to_thread(service.triage_batch, logs, item_req_ids)

        items_out: List[BatchTriageItemResult] = []
        successful_count = 0
        failed_count = 0

        for idx, (out, telem, err) in enumerate(batch_results):
            sub_id = item_req_ids[idx]
            if out is not None and telem is not None:
                successful_count += 1
                items_out.append(
                    BatchTriageItemResult(
                        request_id=sub_id,
                        status="success",
                        result=out,
                        error=None,
                        inference=telem,
                    )
                )
            else:
                failed_count += 1
                items_out.append(
                    BatchTriageItemResult(
                        request_id=sub_id,
                        status="error",
                        result=None,
                        error={"code": "ITEM_ERROR", "message": err or "Failed to process item"},
                        inference=None,
                    )
                )

        return BatchTriageResponse(
            request_id=batch_req_id,
            total_items=len(req.items),
            successful_items=successful_count,
            failed_items=failed_count,
            items=items_out,
        )

    # -------------------------------------------------------------------------
    # Runbook Inspection Endpoints (Phase 13 Read-Only)
    # -------------------------------------------------------------------------
    @app.get("/api/v1/runbooks", tags=["Runbooks"])
    async def list_runbooks():
        """Lists all indexed operational runbooks with categorical metadata."""
        root_dir = Path(__file__).resolve().parent.parent.parent
        index_path = root_dir / "artifacts" / "phase_8" / "runbooks_index.json"
        if not index_path.exists():
            return JSONResponse(content=[], status_code=200)

        try:
            with open(index_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
        except Exception:
            return JSONResponse(content=[], status_code=200)

        runbooks_map = {}
        for c in chunks:
            doc = c.get("document", "")
            if not doc:
                continue
            rb_id = doc.replace(".md", "")
            if rb_id not in runbooks_map:
                runbooks_map[rb_id] = {
                    "runbook_id": rb_id,
                    "document": doc,
                    "title": c.get("title", rb_id),
                    "incident_type": c.get("incident_type", "GENERAL"),
                    "affected_services": c.get("affected_services", []),
                    "keywords": c.get("keywords", []),
                    "sections": [],
                }
            runbooks_map[rb_id]["sections"].append({
                "section": c.get("section", ""),
                "chunk_id": c.get("chunk_id", ""),
                "content": c.get("content", ""),
            })

        return JSONResponse(content=list(runbooks_map.values()), status_code=200)

    @app.get("/api/v1/runbooks/{runbook_id}", tags=["Runbooks"])
    async def get_runbook_detail(runbook_id: str):
        """Retrieves an operational runbook by ID or document name."""
        root_dir = Path(__file__).resolve().parent.parent.parent
        index_path = root_dir / "artifacts" / "phase_8" / "runbooks_index.json"
        if not index_path.exists():
            return JSONResponse(content={"error": "Runbook index not found"}, status_code=404)

        try:
            with open(index_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
        except Exception:
            return JSONResponse(content={"error": "Failed to read runbook index"}, status_code=500)

        clean_id = runbook_id.replace(".md", "").strip().lower()
        matched_chunks = [
            c for c in chunks
            if c.get("document", "").replace(".md", "").strip().lower() == clean_id
        ]

        if not matched_chunks:
            return JSONResponse(content={"error": f"Runbook '{runbook_id}' not found"}, status_code=404)

        doc_name = matched_chunks[0].get("document", "")
        runbook_file = root_dir / "runbooks" / doc_name
        raw_markdown = runbook_file.read_text(encoding="utf-8") if runbook_file.exists() else ""

        return JSONResponse(content={
            "runbook_id": doc_name.replace(".md", ""),
            "document": doc_name,
            "title": matched_chunks[0].get("title", ""),
            "incident_type": matched_chunks[0].get("incident_type", ""),
            "affected_services": matched_chunks[0].get("affected_services", []),
            "keywords": matched_chunks[0].get("keywords", []),
            "raw_markdown": raw_markdown,
            "sections": [
                {
                    "section": c.get("section", ""),
                    "chunk_id": c.get("chunk_id", ""),
                    "content": c.get("content", ""),
                }
                for c in matched_chunks
            ],
        }, status_code=200)

    # -------------------------------------------------------------------------
    # Dashboard Static Files Mounting
    # -------------------------------------------------------------------------
    root_dir = Path(__file__).resolve().parent.parent.parent
    dist_dir = root_dir / "dashboard" / "dist"
    fallback_static_dir = root_dir / "src" / "dashboard" / "static"

    target_index = None
    if dist_dir.exists() and (dist_dir / "index.html").exists():
        target_index = dist_dir / "index.html"
    elif fallback_static_dir.exists() and (fallback_static_dir / "index.html").exists():
        target_index = fallback_static_dir / "index.html"

    if target_index is not None:
        @app.get("/dashboard", include_in_schema=False)
        async def serve_dashboard_page():
            return FileResponse(target_index, media_type="text/html")

    if dist_dir.exists() and (dist_dir / "index.html").exists():
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
        app.mount("/dashboard", StaticFiles(directory=str(dist_dir), html=True), name="dashboard_static")
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="root_dashboard")
    elif fallback_static_dir.exists() and (fallback_static_dir / "index.html").exists():
        app.mount("/dashboard", StaticFiles(directory=str(fallback_static_dir), html=True), name="dashboard_static")
        app.mount("/", StaticFiles(directory=str(fallback_static_dir), html=True), name="root_dashboard")

    return app


app = create_app()
