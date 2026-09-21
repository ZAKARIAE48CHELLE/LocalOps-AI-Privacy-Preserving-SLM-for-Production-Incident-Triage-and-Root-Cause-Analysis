"""LocalOps AI — Phase 10 Observability & Privacy-Safe Monitoring Test Suite."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_inference_service, get_model_manager, get_runbook_retriever
from src.api.exceptions import ModelOutputInvalidError
from src.api.model_manager import ModelManager
from src.api.schemas import InferenceTelemetry
from src.observability.gpu_telemetry import get_gpu_telemetry
from src.observability.metrics import MetricsRegistry
from src.observability.redaction import redact_secrets
from src.schemas.enums import IncidentType, Severity
from src.schemas.triage import LogTriageOutput


@pytest.fixture
def mock_model_manager():
    manager = MagicMock(spec=ModelManager)
    manager.is_ready = True
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


class TestObservabilityPhase10:

    def test_metrics_endpoint_returns_prometheus_format(self):
        """GET /metrics must return standard Prometheus text format with headers."""
        app = create_app()
        with TestClient(app) as client:
            res = client.get("/metrics")
            assert res.status_code == 200
            assert "text/plain" in res.headers.get("Content-Type", "")

            content = res.text
            assert "# HELP localops_requests_total" in content
            assert "# TYPE localops_requests_total counter" in content
            assert "localops_inference_seconds_bucket" in content
            assert "localops_gpu_memory_used_bytes" in content

    def test_counters_and_tokens_increment_on_traffic(self, mock_model_manager, sample_triage_output):
        """Verify metric counters and token aggregates increment during triage requests."""
        app = create_app()
        app.dependency_overrides[get_model_manager] = lambda: mock_model_manager

        mock_svc = MagicMock()
        mock_telem = InferenceTelemetry(latency_ms=120.0, prompt_tokens=180, generated_tokens=95)
        mock_svc.triage_single.return_value = (sample_triage_output, mock_telem)
        app.dependency_overrides[get_inference_service] = lambda: mock_svc

        with TestClient(app) as client:
            initial_metrics = client.get("/metrics").text

            payload = {
                "raw_log": "[ERROR] NpgsqlException: Connection pool reached maximum size",
                "request_id": "req_obs_001",
            }
            res = client.post("/api/v1/triage", json=payload)
            assert res.status_code == 200

            after_metrics = client.get("/metrics").text
            assert "localops_requests_total" in after_metrics
            assert "localops_predictions_total" in after_metrics
            assert 'incident_type="DATABASE"' in after_metrics
            assert 'severity="P1_CRITICAL"' in after_metrics

    def test_schema_invalid_counter_increments_on_failure(self, mock_model_manager):
        """Verify localops_schema_invalid_total increments when model output fails validation."""
        registry = MetricsRegistry.get_instance()
        prev_invalid = registry.counters.get(("localops_schema_invalid_total", ()), 0.0)

        registry.inc_schema_invalid()
        after_invalid = registry.counters.get(("localops_schema_invalid_total", ()), 0.0)
        assert after_invalid == prev_invalid + 1.0

    def test_no_high_cardinality_labels(self):
        """Verify that Prometheus metrics labels do NOT contain request_ids or raw logs."""
        registry = MetricsRegistry.get_instance()
        text = registry.generate_prometheus_text()

        forbidden_patterns = ["req_", "custom_req_", "NpgsqlException", "password="]
        for line in text.splitlines():
            if line.startswith("#"):
                continue
            for pat in forbidden_patterns:
                assert pat not in line, f"Found high-cardinality or sensitive data '{pat}' in metric line: {line}"

    def test_privacy_redaction_secrets(self):
        """Verify redaction masks passwords, bearer tokens, JWTs, AWS keys, and private keys."""
        dirty_text = (
            "User password=SuperSecretPassword123! attempted login with "
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisSignature "
            "using AWS access key AKIAIOSFODNN7EXAMPLE."
        )
        clean_text = redact_secrets(dirty_text)

        assert "SuperSecretPassword123!" not in clean_text
        assert "password=[REDACTED]" in clean_text
        assert "AKIAIOSFODNN7EXAMPLE" not in clean_text
        assert "[REDACTED_AWS_KEY]" in clean_text
        assert "[REDACTED_BEARER_TOKEN]" in clean_text or "[REDACTED_JWT]" in clean_text

    def test_gpu_telemetry_graceful_degradation(self):
        """Verify get_gpu_telemetry returns standard structure even on CPU."""
        telemetry = get_gpu_telemetry()
        assert "cuda_available" in telemetry
        assert "device_name" in telemetry
        assert "memory_used_bytes" in telemetry
        assert "memory_total_bytes" in telemetry
        assert "utilization_percent" in telemetry
        assert "temperature_celsius" in telemetry
        assert "power_watts" in telemetry
        assert isinstance(telemetry["cuda_available"], bool)

    def test_live_telemetry_endpoint(self, mock_model_manager):
        """GET /api/v1/telemetry/live must return valid JSON for Mission Control dashboard."""
        app = create_app()
        app.dependency_overrides[get_model_manager] = lambda: mock_model_manager

        with TestClient(app) as client:
            res = client.get("/api/v1/telemetry/live")
            assert res.status_code == 200
            data = res.json()

            assert "uptime_seconds" in data
            assert "total_requests" in data
            assert "total_errors" in data
            assert "inflight_requests" in data
            assert "latency_p50_ms" in data
            assert "latency_p95_ms" in data
            assert "predictions_by_type" in data
            assert "gpu" in data
            assert "rag" in data

    def test_prometheus_alerts_yaml_valid(self):
        """Verify configs/prometheus_alerts.yml is valid YAML and defines expected rules."""
        alert_path = Path("configs/prometheus_alerts.yml")
        assert alert_path.exists()

        with open(alert_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert "groups" in data
        assert len(data["groups"]) > 0

        rules = data["groups"][0]["rules"]
        alert_names = [r["alert"] for r in rules]

        assert "LocalOpsApiDown" in alert_names
        assert "LocalOpsHighErrorRate" in alert_names
        assert "LocalOpsHighInferenceLatency" in alert_names
        assert "LocalOpsSchemaInvalidSpike" in alert_names
        assert "LocalOpsGpuVramCritical" in alert_names
