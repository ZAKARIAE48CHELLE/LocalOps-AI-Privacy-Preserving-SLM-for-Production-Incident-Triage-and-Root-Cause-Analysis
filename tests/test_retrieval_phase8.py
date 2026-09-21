"""LocalOps AI — Phase 8 Runbook RAG Test Suite."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_inference_service, get_model_manager, get_runbook_retriever
from src.api.model_manager import ModelManager
from src.api.schemas import InferenceTelemetry
from src.retrieval.index_runbooks import build_runbook_index, parse_runbook_markdown
from src.retrieval.retriever import RunbookRetriever
from src.retrieval.schemas import EnrichedTriageResponse, RemediationRecommendation, RunbookChunk
from src.schemas.enums import IncidentType, Severity
from src.schemas.triage import LogTriageOutput


@pytest.fixture
def runbooks_dir():
    return Path("runbooks")


@pytest.fixture
def retriever():
    return RunbookRetriever()


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
        affected_service="event-processor",
        root_cause="PostgreSQL connection pool exhaustion under load.",
        suggested_action="Restart service and increase pool ceiling.",
        confidence=0.95,
        evidence=["Npgsql.NpgsqlException: The connection pool has reached its maximum size"],
    )


class TestRunbookRAGSuite:

    def test_runbooks_exist_and_cover_all_incident_types(self, runbooks_dir):
        """Verify that runbooks exist and cover all 6 core IncidentTypes."""
        assert runbooks_dir.exists()
        md_files = list(runbooks_dir.glob("*.md"))
        assert len(md_files) >= 6, f"Expected at least 6 runbooks, found {len(md_files)}"

        covered_types = set()
        for md_file in md_files:
            chunks = parse_runbook_markdown(md_file)
            for c in chunks:
                covered_types.add(c.incident_type)

        for expected in IncidentType:
            assert expected in covered_types, f"IncidentType {expected} not covered by any runbook"

    def test_runbook_parsing_and_chunking(self, runbooks_dir):
        """Verify structured extraction of sections, title, services, and keywords."""
        sample_file = runbooks_dir / "postgres_connection_exhaustion.md"
        assert sample_file.exists()

        chunks = parse_runbook_markdown(sample_file)
        assert len(chunks) >= 3

        sections = [c.section for c in chunks]
        assert "Symptoms" in sections
        assert "Immediate Mitigation" in sections
        assert "Long-Term Remediation" in sections

        for chunk in chunks:
            assert chunk.incident_type == IncidentType.DATABASE
            assert "event-processor" in chunk.affected_services
            assert len(chunk.keywords) > 0
            assert len(chunk.content) > 20

    def test_index_generation_and_persistence(self, tmp_path, runbooks_dir):
        """Verify that index generation creates a valid JSON artifact."""
        out_index = tmp_path / "test_runbooks_index.json"
        chunks = build_runbook_index(runbooks_dir, out_index)
        assert len(chunks) >= 20
        assert out_index.exists()

        with open(out_index, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == len(chunks)
        assert data[0]["chunk_id"]

    def test_retrieval_postgres_connection_exhaustion(self, retriever):
        """Query for postgres connection pool starvation matches postgres runbook."""
        res = retriever.retrieve(
            incident_type=IncidentType.DATABASE,
            affected_service="event-processor",
            root_cause="Npgsql connection pool exhausted",
            raw_log="[ERROR] Npgsql.NpgsqlException: The connection pool has reached its maximum size",
        )
        assert res is not None
        assert "postgres" in res.runbook_document.lower()
        assert res.section == "Immediate Mitigation"
        assert "pg_terminate_backend" in res.content or "PgBouncer" in res.content
        assert res.relevance_score >= 0.50
        assert len(res.matched_keywords) >= 1

    def test_retrieval_kubernetes_oom(self, retriever):
        """Query for OOMKilled container matches kubernetes container OOM runbook."""
        res = retriever.retrieve(
            incident_type=IncidentType.INFRASTRUCTURE,
            affected_service="data-ingest",
            root_cause="Container killed due to cgroup memory limit",
            raw_log="Pod terminated with exit code 137 Reason: OOMKilled",
        )
        assert res is not None
        assert "oom" in res.runbook_document.lower()
        assert "kubectl set resources" in res.content or "limits=memory" in res.content
        assert res.relevance_score >= 0.50

    def test_retrieval_tls_certificate(self, retriever):
        """Query for SSL handshake failure matches TLS certificate runbook."""
        res = retriever.retrieve(
            incident_type=IncidentType.SECURITY,
            affected_service="ingress-nginx",
            root_cause="TLS certificate expired on ingress endpoint",
            raw_log="SSL handshake failed: CERT_HAS_EXPIRED on payment gateway",
        )
        assert res is not None
        assert "tls" in res.runbook_document.lower() or "cert" in res.runbook_document.lower()
        assert res.relevance_score >= 0.50

    def test_retrieval_kafka_lag(self, retriever):
        """Query for Kafka lag matches Kafka consumer lag runbook."""
        res = retriever.retrieve(
            incident_type=IncidentType.MESSAGING,
            affected_service="stream-processor",
            root_cause="Consumer group rebalance timeout and offset commit failure",
            raw_log="CommitFailedException: Offset commit cannot be completed since the group has rebalanced",
        )
        assert res is not None
        assert "kafka" in res.runbook_document.lower()
        assert "max.poll.interval.ms" in res.content or "kafka-consumer-groups" in res.content
        assert res.relevance_score >= 0.50

    def test_retrieval_dns_failure(self, retriever):
        """Query for DNS resolution timeout matches CoreDNS runbook."""
        res = retriever.retrieve(
            incident_type=IncidentType.NETWORK,
            affected_service="coredns",
            root_cause="CoreDNS query upstream timeout",
            raw_log="dial tcp: lookup auth-service: no such host",
        )
        assert res is not None
        assert "dns" in res.runbook_document.lower()
        assert res.relevance_score >= 0.50

    def test_retrieval_crashloop_backoff(self, retriever):
        """Query for CrashLoopBackOff matches application crashloop runbook."""
        res = retriever.retrieve(
            incident_type=IncidentType.APPLICATION,
            affected_service="order-api",
            root_cause="Application panic on startup due to missing environment variable",
            raw_log="CrashLoopBackOff: back-off restarting failed container exit code 1",
        )
        assert res is not None
        assert "crashloop" in res.runbook_document.lower()
        assert res.relevance_score >= 0.50

    def test_enriched_api_endpoint(self, mock_model_manager, sample_triage_output):
        """POST /api/v1/triage/enriched returns strict LogTriageOutput + grounded remediation."""
        app = create_app()
        app.dependency_overrides[get_model_manager] = lambda: mock_model_manager

        mock_svc = MagicMock()
        mock_telem = InferenceTelemetry(latency_ms=90.0, prompt_tokens=250, generated_tokens=120)
        mock_svc.triage_single.return_value = (sample_triage_output, mock_telem)
        app.dependency_overrides[get_inference_service] = lambda: mock_svc

        with TestClient(app) as client:
            payload = {
                "raw_log": "[ERROR] Npgsql.NpgsqlException: The connection pool has reached its maximum size",
                "request_id": "rag_test_1001",
            }
            res = client.post("/api/v1/triage/enriched", json=payload, headers={"X-Request-ID": "rag_test_1001"})
            assert res.status_code == 200
            data = res.json()

            assert data["request_id"] == "rag_test_1001"
            assert res.headers.get("X-Request-ID") == "rag_test_1001"

            # Check strict LogTriageOutput preservation
            result = data["result"]
            parsed_triage = LogTriageOutput(**result)
            assert parsed_triage.incident_type == IncidentType.DATABASE
            assert parsed_triage.affected_service == "event-processor"

            # Check grounded remediation
            remediation = data["remediation"]
            assert remediation is not None
            assert "postgres" in remediation["runbook_document"].lower()
            assert remediation["section"] == "Immediate Mitigation"
            assert remediation["relevance_score"] >= 0.50
            assert len(remediation["content"]) > 20

            # Validate entire response structure against EnrichedTriageResponse
            parsed_full = EnrichedTriageResponse(**data)
            assert parsed_full.result.incident_type == IncidentType.DATABASE

    def test_remediation_schema_forbids_extra_fields(self):
        """Verify strict Pydantic extra='forbid' constraint on RAG models."""
        with pytest.raises(Exception):
            RemediationRecommendation(
                runbook_document="test.md",
                runbook_title="Test",
                section="Mitigation",
                content="Do something",
                relevance_score=0.9,
                unexpected_extra_field="should_fail",
            )
