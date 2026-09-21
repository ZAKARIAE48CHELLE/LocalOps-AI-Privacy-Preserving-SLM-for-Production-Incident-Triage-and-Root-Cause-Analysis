"""LocalOps AI — Phase 13 Operator Dashboard & Web UI Test Suite."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_model_manager, get_inference_service
from src.api.model_manager import ModelManager
from src.schemas.enums import IncidentType, Severity
from src.schemas.triage import LogTriageOutput
from src.api.schemas import InferenceTelemetry


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
def mock_inference_service():
    service = MagicMock()
    triage_out = LogTriageOutput(
        incident_type=IncidentType.DATABASE,
        severity=Severity.P1_CRITICAL,
        affected_service="billing-db",
        root_cause="PostgreSQL connection pool exhaustion",
        suggested_action="Increase connection pool size and restart billing workers",
        confidence=0.98,
        evidence=["HikariCP: Connection pool exhausted, 50/50 connections active"],
    )
    telem = InferenceTelemetry(latency_ms=142.5, prompt_tokens=120, generated_tokens=85)
    service.triage_single.return_value = (triage_out, telem)
    service.triage_batch.return_value = [(triage_out, telem, None)]
    return service


@pytest.fixture
def app_instance(mock_model_manager, mock_inference_service):
    app = create_app()
    app.dependency_overrides[get_model_manager] = lambda: mock_model_manager
    app.dependency_overrides[get_inference_service] = lambda: mock_inference_service
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(app_instance):
    with TestClient(app_instance) as test_client:
        yield test_client


def test_dashboard_root_serves_html(client: TestClient):
    """Verify that root endpoint / serves the compiled dashboard index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "<title>LocalOps AI — Operator Dashboard</title>" in response.text
    assert '<div id="root">' in response.text


def test_dashboard_route_serves_html(client: TestClient):
    """Verify that /dashboard route serves the compiled dashboard."""
    response = client.get("/dashboard")
    assert response.status_code in (200, 307)
    if response.status_code == 307:
        redirected = client.get(response.headers["location"])
        assert redirected.status_code == 200
        assert "<title>LocalOps AI — Operator Dashboard</title>" in redirected.text
    else:
        assert "<title>LocalOps AI — Operator Dashboard</title>" in response.text


def test_health_and_readiness_probes(client: TestClient):
    """Verify that liveness and readiness remain responsive and valid."""
    h_resp = client.get("/health")
    assert h_resp.status_code == 200
    h_data = h_resp.json()
    assert h_data["status"] == "ok"
    assert h_data["service"] == "localops-ai"

    r_resp = client.get("/ready")
    assert r_resp.status_code == 200
    r_data = r_resp.json()
    assert r_data["ready"] is True
    assert r_data["tokenizer_loaded"] is True


def test_model_info_endpoint(client: TestClient):
    """Verify model-info provides non-sensitive metadata for dashboard display."""
    resp = client.get("/api/v1/model-info")
    assert resp.status_code == 200
    data = resp.json()
    assert "base_model_id" in data
    assert "adapter_identifier" in data
    assert "quantization_mode" in data
    assert "max_input_tokens" in data
    assert "decoding_mode" in data


def test_runbooks_catalog_listing(client: TestClient):
    """Verify that read-only runbook listing returns operational playbooks."""
    resp = client.get("/api/v1/runbooks")
    assert resp.status_code == 200
    runbooks = resp.json()
    assert isinstance(runbooks, list)
    assert len(runbooks) >= 10

    first_rb = runbooks[0]
    assert "runbook_id" in first_rb
    assert "title" in first_rb
    assert "incident_type" in first_rb
    assert "affected_services" in first_rb
    assert "keywords" in first_rb
    assert "sections" in first_rb


def test_runbook_detail_endpoint(client: TestClient):
    """Verify detail retrieval for a specific operational runbook."""
    resp = client.get("/api/v1/runbooks/postgres_connection_exhaustion")
    assert resp.status_code == 200
    data = resp.json()
    assert data["runbook_id"] == "postgres_connection_exhaustion"
    assert "document" in data
    assert "sections" in data
    assert len(data["sections"]) > 0
    assert "content" in data["sections"][0]


def test_runbook_detail_not_found(client: TestClient):
    """Verify 404 behavior for unknown runbook ID."""
    resp = client.get("/api/v1/runbooks/non_existent_runbook_xyz")
    assert resp.status_code == 404
    assert "Runbook 'non_existent_runbook_xyz' not found" in resp.text


def test_telemetry_privacy_guarantee(client: TestClient):
    """Verify live telemetry does not expose raw logs or unredacted user text."""
    resp = client.get("/api/v1/telemetry/live")
    assert resp.status_code == 200
    data = resp.json()

    # Ensure counters and performance metrics exist
    assert "total_requests" in data
    assert "latency_p50_ms" in data
    assert "gpu" in data
    assert "rag" in data

    # Verify no raw user log keys exist in telemetry summary
    assert "raw_log" not in data
    assert "log" not in data
    assert "user_prompt" not in data


def test_no_raw_log_persistence_endpoint_exists(client: TestClient):
    """Verify no backdoor exists for persisting raw incident logs to server storage."""
    assert client.post("/api/v1/logs/save", json={"log": "secret"}).status_code in (404, 405)
    assert client.post("/api/v1/store", json={"log": "secret"}).status_code in (404, 405)
    assert client.get("/api/v1/logs").status_code in (404, 405)


def test_triage_contract_invariance(client: TestClient):
    """Verify that Phase 13 frontend integration does not alter the Phase 2/7 output contract."""
    resp = client.post(
        "/api/v1/triage",
        json={"raw_log": "2026-09-18 [ERROR] HikariCP Connection pool exhausted"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "request_id" in body
    assert "result" in body
    assert "inference" in body

    res = body["result"]
    assert res["incident_type"] == "DATABASE"
    assert res["severity"] == "P1_CRITICAL"
    assert res["affected_service"] == "billing-db"
    assert isinstance(res["evidence"], list)
    assert len(res["evidence"]) >= 1
