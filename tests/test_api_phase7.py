"""LocalOps AI — Phase 7 API Test Suite."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock

import pytest
import torch
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_inference_service, get_model_manager
from src.api.exceptions import ModelOutputInvalidError
from src.api.model_manager import ModelManager
from src.api.schemas import InferenceTelemetry
from src.schemas.enums import IncidentType, Severity
from src.schemas.triage import LogTriageOutput


@pytest.fixture
def mock_model_manager():
    """Mock ModelManager to avoid loading 1.5B model in standard unit tests."""
    manager = MagicMock(spec=ModelManager)
    manager.is_ready = True
    manager.is_loaded = True
    manager.warmup_completed = True
    manager.tokenizer = MagicMock()
    manager.model = MagicMock()
    manager.device = "cuda" if torch.cuda.is_available() else "cpu"
    return manager


@pytest.fixture
def sample_valid_triage_output():
    return LogTriageOutput(
        incident_type=IncidentType.DATABASE,
        severity=Severity.P1_CRITICAL,
        affected_service="user-profile",
        root_cause="Database connection pool starvation on postgres-primary.",
        suggested_action="Restart service and increase pool ceiling.",
        confidence=0.95,
        evidence=["Npgsql.NpgsqlException: The connection pool has reached its maximum size"],
    )


@pytest.fixture
def app_instance(mock_model_manager):
    app = create_app()
    app.dependency_overrides[get_model_manager] = lambda: mock_model_manager
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(app_instance):
    with TestClient(app_instance) as test_client:
        yield test_client


class TestPhase7ApiService:

    def test_health_endpoint(self, client):
        """GET /health must return 200 without triggering inference."""
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["service"] == "localops-ai"
        assert "version" in data
        assert "timestamp" in data

    def test_ready_endpoint_when_ready(self, client, mock_model_manager):
        """GET /ready returns 200 when model is loaded and ready."""
        mock_model_manager.is_ready = True
        res = client.get("/ready")
        assert res.status_code == 200
        data = res.json()
        assert data["ready"] is True
        assert data["service"] == "localops-ai"

    def test_ready_endpoint_when_not_ready(self, client, mock_model_manager):
        """GET /ready returns 503 when model is not ready."""
        mock_model_manager.is_ready = False
        res = client.get("/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["ready"] is False

    def test_model_info_no_path_leakage(self, client):
        """GET /api/v1/model-info returns metadata without absolute filesystem paths."""
        res = client.get("/api/v1/model-info")
        assert res.status_code == 200
        data = res.json()
        assert data["base_model_id"] == "Qwen/Qwen2.5-1.5B-Instruct"
        assert data["quantization_mode"] == "4-bit NF4"
        assert data["decoding_mode"] == "deterministic_greedy"
        assert "artifacts" not in data["adapter_identifier"]
        assert "/" not in data["adapter_identifier"]
        assert "\\" not in data["adapter_identifier"]

    def test_triage_single_valid(self, app_instance, client, sample_valid_triage_output):
        """POST /api/v1/triage processes valid input and returns strict Phase 2 schema."""
        telemetry = InferenceTelemetry(latency_ms=85.2, prompt_tokens=320, generated_tokens=110)

        mock_svc = MagicMock()
        mock_svc.triage_single.return_value = (sample_valid_triage_output, telemetry)
        app_instance.dependency_overrides[get_inference_service] = lambda: mock_svc

        payload = {
            "raw_log": "[2026-09-18T10:00:00Z] [ERROR] Connection pool starved on 192.0.2.1",
            "request_id": "custom_req_12345",
        }
        res = client.post("/api/v1/triage", json=payload, headers={"X-Request-ID": "custom_req_12345"})
        assert res.status_code == 200
        data = res.json()

        assert data["request_id"] == "custom_req_12345"
        assert res.headers.get("X-Request-ID") == "custom_req_12345"
        assert "X-Process-Time-Ms" in res.headers

        result = data["result"]
        assert result["incident_type"] == "DATABASE"
        assert result["severity"] == "P1_CRITICAL"
        assert result["affected_service"] == "user-profile"
        assert "evidence" in result
        assert len(result["evidence"]) == 1

        # Validate against strict Pydantic model directly
        parsed_output = LogTriageOutput(**result)
        assert parsed_output.incident_type == IncidentType.DATABASE

    def test_triage_empty_log_rejected(self, client):
        """POST /api/v1/triage rejects empty or whitespace-only raw_log with 400."""
        res = client.post("/api/v1/triage", json={"raw_log": "   \n\t  "})
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "INVALID_REQUEST"
        assert "cannot be empty" in data["error"]["message"]

    def test_triage_oversized_log_rejected(self, client):
        """POST /api/v1/triage rejects logs exceeding character limit with 400."""
        res = client.post("/api/v1/triage", json={"raw_log": "X" * 35000})
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "INVALID_REQUEST"
        assert "exceeds maximum character limit" in data["error"]["message"]

    def test_triage_invalid_model_output_handled_safely(self, app_instance, client):
        """POST /api/v1/triage returns 502 MODEL_OUTPUT_INVALID if generation fails schema."""
        mock_svc = MagicMock()
        mock_svc.triage_single.side_effect = ModelOutputInvalidError(
            "Model generated malformed JSON", request_id="req_fail_1"
        )
        app_instance.dependency_overrides[get_inference_service] = lambda: mock_svc

        res = client.post(
            "/api/v1/triage",
            json={"raw_log": "[2026-09-18T12:00:00Z] Error occurred", "request_id": "req_fail_1"},
        )
        assert res.status_code == 502
        data = res.json()
        assert data["error"]["code"] == "MODEL_OUTPUT_INVALID"
        assert "malformed JSON" in data["error"]["message"]

    def test_triage_batch_order_and_partial_failures(self, app_instance, client, sample_valid_triage_output):
        """POST /api/v1/triage/batch preserves ordering and handles individual item errors gracefully."""
        telemetry = InferenceTelemetry(latency_ms=45.0, prompt_tokens=200, generated_tokens=90)

        mock_svc = MagicMock()
        mock_svc.triage_batch.return_value = [
            (sample_valid_triage_output, telemetry, None),
            (None, None, "Empty or whitespace-only log"),
            (sample_valid_triage_output, telemetry, None),
        ]
        app_instance.dependency_overrides[get_inference_service] = lambda: mock_svc

        payload = {
            "items": [
                {"raw_log": "Valid log 1", "request_id": "b_item_1"},
                {"raw_log": "   ", "request_id": "b_item_2"},
                {"raw_log": "Valid log 3", "request_id": "b_item_3"},
            ]
        }
        res = client.post("/api/v1/triage/batch", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert data["total_items"] == 3
        assert data["successful_items"] == 2
        assert data["failed_items"] == 1

        assert len(data["items"]) == 3
        assert data["items"][0]["status"] == "success"
        assert data["items"][0]["result"]["incident_type"] == "DATABASE"
        assert data["items"][1]["status"] == "error"
        assert data["items"][1]["error"]["message"] == "Empty or whitespace-only log"
        assert data["items"][2]["status"] == "success"

    def test_triage_batch_oversized_rejected(self, client):
        """POST /api/v1/triage/batch rejects requests exceeding max batch items."""
        oversized_items = [{"raw_log": f"Log {i}"} for i in range(25)]
        res = client.post("/api/v1/triage/batch", json={"items": oversized_items})
        assert res.status_code == 413 or res.status_code == 400
        data = res.json()
        assert data["error"]["code"] in ("INPUT_TOO_LARGE", "INVALID_REQUEST")

    def test_privacy_safe_logging_does_not_leak_raw_log(self, client, caplog):
        """Verifies that raw logs are not printed to access logs under default policy."""
        secret_string = "SUPER_SECRET_INTERNAL_DB_PASSWORD_12345"
        with caplog.at_level(logging.INFO):
            _ = client.post(
                "/api/v1/triage",
                json={"raw_log": f"[ERROR] Database error with {secret_string}"},
            )
            for record in caplog.records:
                assert secret_string not in record.message

    def test_real_gpu_triage_smoke(self):
        """Real GPU integration smoke test on actual 4-bit QLoRA checkpoint-100."""
        if not torch.cuda.is_available():
            pytest.skip("CUDA GPU is not available for real hardware smoke test.")

        app = create_app()
        with TestClient(app) as live_client:
            # Check readiness
            r_res = live_client.get("/ready")
            assert r_res.status_code == 200

            # Execute real inference on synthetic production log
            test_log = (
                "[2026-10-12T13:43:42.127Z] [ERROR] [event-processor] Npgsql.NpgsqlException: "
                "The connection pool has reached its maximum size and no connections are currently available\n"
                "[2026-10-12T13:43:42.127Z] [ALERT] [event-processor] HIGH ALERT: Connection pool utilization at 98%"
            )
            res = live_client.post("/api/v1/triage", json={"raw_log": test_log})
            assert res.status_code == 200
            data = res.json()

            result = data["result"]
            assert result["incident_type"] in [e.value for e in IncidentType]
            assert result["severity"] in [e.value for e in Severity]
            assert result["confidence"] >= 0.0 and result["confidence"] <= 1.0
            assert isinstance(result["evidence"], list)
            assert len(result["evidence"]) >= 1

            # Validate with strict Pydantic model directly
            validated = LogTriageOutput(**result)
            assert validated.incident_type == IncidentType.DATABASE
            assert data["inference"]["latency_ms"] > 0.0
