"""LocalOps AI — Phase 11 Reliability, Failure Injection & Release Tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_inference_service, get_model_manager, get_runbook_retriever
from src.api.exceptions import ModelNotReadyError, ModelOutputInvalidError
from src.api.model_manager import ModelManager
from src.api.schemas import InferenceTelemetry
from src.retrieval.retriever import RunbookRetriever
from src.schemas.enums import IncidentType, Severity
from src.schemas.triage import LogTriageOutput


@pytest.fixture
def mock_model_manager():
    manager = MagicMock(spec=ModelManager)
    manager.is_ready = True
    manager.is_loaded = True
    manager.warmup_completed = True
    manager.tokenizer = MagicMock()
    manager.model = MagicMock()
    manager.device = "cuda"
    return manager


@pytest.fixture
def sample_triage_output():
    return LogTriageOutput(
        incident_type=IncidentType.DATABASE,
        severity=Severity.P1_CRITICAL,
        affected_service="user-profile",
        root_cause="Database connection pool starvation.",
        suggested_action="Restart service and increase pool ceiling.",
        confidence=0.95,
        evidence=["NpgsqlException: Connection pool reached maximum size"],
    )


class TestReliabilityAndFailureInjection:

    def test_model_not_ready_returns_503(self, mock_model_manager):
        """GET /ready must return 503 when model manager reports is_ready=False."""
        mock_model_manager.is_ready = False
        app = create_app()
        app.dependency_overrides[get_model_manager] = lambda: mock_model_manager

        with TestClient(app) as client:
            res = client.get("/ready")
            assert res.status_code == 503
            assert res.json()["ready"] is False

    def test_input_too_large_rejection(self, mock_model_manager):
        """POST /api/v1/triage rejects oversized logs with 400 Bad Request."""
        app = create_app()
        app.dependency_overrides[get_model_manager] = lambda: mock_model_manager

        with TestClient(app) as client:
            oversized_log = "FATAL ERROR OCCURRED " * 2000  # > 32k chars
            res = client.post("/api/v1/triage", json={"raw_log": oversized_log})
            assert res.status_code == 400
            data = res.json()
            assert data["error"]["code"] == "INVALID_REQUEST"
            assert "exceeds maximum character limit" in data["error"]["message"]

    def test_model_output_invalid_error_contract(self, mock_model_manager):
        """POST /api/v1/triage returns 502 with error code MODEL_OUTPUT_INVALID on parsing failure."""
        app = create_app()
        app.dependency_overrides[get_model_manager] = lambda: mock_model_manager

        mock_svc = MagicMock()
        mock_svc.triage_single.side_effect = ModelOutputInvalidError(
            "Model returned unparseable syntax", request_id="req_fail_safe"
        )
        app.dependency_overrides[get_inference_service] = lambda: mock_svc

        with TestClient(app) as client:
            res = client.post(
                "/api/v1/triage",
                json={"raw_log": "[ERROR] Something crashed", "request_id": "req_fail_safe"},
            )
            assert res.status_code == 502
            data = res.json()
            assert data["request_id"] == "req_fail_safe"
            assert data["error"]["code"] == "MODEL_OUTPUT_INVALID"
            assert "unparseable syntax" in data["error"]["message"]

    def test_missing_rag_index_fallback(self, tmp_path):
        """RunbookRetriever initializes gracefully even if index file does not pre-exist."""
        non_existent = tmp_path / "missing_index.json"
        retriever = RunbookRetriever(index_path=non_existent)
        assert retriever is not None
        assert len(retriever.chunks) > 0

    def test_release_manifest_validity(self):
        """Verify release_manifest.json exists and conforms to release metadata contract."""
        manifest_path = Path("artifacts/release/release_manifest.json")
        assert manifest_path.exists(), "Release manifest must exist in artifacts/release/"

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["project_name"] == "localops-ai"
        assert manifest["release_version"] == "1.0.0"
        assert manifest["base_model"] == "Qwen/Qwen2.5-1.5B-Instruct"
        assert manifest["quantization"] == "4-bit NF4"
        assert manifest["status"] == "PRODUCTION_READY"

        checksums = manifest["checksums"]
        assert "api_config_sha256" in checksums
        assert "adapter_config_sha256" in checksums
        assert "rag_index_sha256" in checksums

        benchmark = manifest["benchmark_summary"]
        assert benchmark["incident_type_macro_f1"] > 0.70
        assert benchmark["pydantic_schema_validity_rate"] > 0.99

    def test_version_exposed_in_model_info(self, mock_model_manager):
        """GET /api/v1/model-info must expose service_version='1.0.0'."""
        app = create_app()
        app.dependency_overrides[get_model_manager] = lambda: mock_model_manager

        with TestClient(app) as client:
            res = client.get("/api/v1/model-info")
            assert res.status_code == 200
            data = res.json()
            assert data["service_version"] == "1.0.0"
            assert data["schema_version"] in ("v1.0", "1.0.0")
