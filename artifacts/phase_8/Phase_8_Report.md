# LocalOps AI — Phase 8: Runbook Retrieval-Augmented Generation (RAG) Report

## Executive Summary

Phase 8 integrates local, privacy-preserving Retrieval-Augmented Generation (RAG) into LocalOps AI to ground remediation recommendations in trusted operational engineering documentation. 

As specified in the project roadmap, the fine-tuned Small Language Model (SLM) provides specialized **behavior** (rapidly classifying incident types, determining severity, pinpointing the affected microservice, extracting verbatim evidence, and diagnosing root cause), while the retrieval engine provides operational **knowledge** (concrete step-by-step mitigation commands, configuration flags, and long-term architectural remediations from version-controlled runbooks).

All Phase 8 exit criteria have been satisfied without altering the frozen Phase 2 public `LogTriageOutput` schema (`extra="forbid"`).

---

## 1. Operational Runbooks Catalog

Ten standardized operational markdown runbooks have been established under `runbooks/`, directly covering all 6 core `IncidentType` taxonomy categories:

| Runbook File | Title | Incident Type | Target Microservices |
|---|---|---|---|
| `postgres_connection_exhaustion.md` | PostgreSQL Connection Pool Exhaustion | `DATABASE` | event-processor, user-service, order-service, api-gateway |
| `redis_timeout_eviction.md` | Redis Timeout and Key Eviction | `DATABASE` | cache-service, session-service, rate-limiter, product-catalog |
| `kubernetes_container_oom.md` | Kubernetes Container OOMKilled | `INFRASTRUCTURE` | data-ingest, ml-worker, report-generator, search-indexer |
| `kubernetes_disk_pressure.md` | Kubernetes Node Disk Pressure | `INFRASTRUCTURE` | kubelet, node-exporter, logging-agent, cluster-nodes |
| `application_crashloop_backoff.md` | Application CrashLoopBackOff | `APPLICATION` | payment-processor, auth-service, order-api, user-management |
| `application_jvm_thread_deadlock.md` | Application Thread Deadlock and CPU Starvation | `APPLICATION` | billing-engine, inventory-service, workflow-orchestrator |
| `tls_certificate_expiration.md` | TLS Certificate Expiration and Handshake Failure | `SECURITY` | ingress-nginx, edge-proxy, api-gateway, payment-gateway |
| `network_dns_resolution_failure.md` | DNS Resolution and CoreDNS Failure | `NETWORK` | coredns, kube-dns, egress-proxy, api-clients |
| `kafka_consumer_lag.md` | Apache Kafka Consumer Group Lag and Partition Starvation | `MESSAGING` | stream-processor, telemetry-ingest, notification-service, event-hub |
| `nats_jetstream_storage_limit.md` | NATS JetStream Storage Limit and Stream Starvation | `MESSAGING` | event-router, telemetry-collector, async-dispatcher |

Each runbook follows a strict structural schema consisting of:
- Metadata Header (`Incident Type`, `Affected Services`, `Severity Default`, `Keywords`)
- `## Symptoms` (Observable metrics, error messages, client impacts)
- `## Root Cause Diagnosis` (Diagnostic commands, log inspection queries, profiling techniques)
- `## Immediate Mitigation` (Actionable shell commands, SQL statements, and rollback actions to stop the bleeding)
- `## Long-Term Remediation` (Architectural fixes, timeout tuning, alert thresholds, and autoscaling configurations)

---

## 2. Retrieval Architecture & Hybrid Scoring

The retrieval module is encapsulated in `src/retrieval/`:

```text
src/retrieval/
├── __init__.py
├── schemas.py           # RunbookChunk, RemediationRecommendation, EnrichedTriageResponse
├── index_runbooks.py    # Markdown parser and structured JSON index generator
└── retriever.py         # Hybrid incident-type, keyword, and semantic retriever
```

### Hybrid Scoring Function:
To guarantee zero hallucinations and zero external API dependencies, `RunbookRetriever` computes a composite relevance score $S \in [0.0, 1.0]$:

$$S = S_{\text{type}} + S_{\text{section}} + S_{\text{service}} + S_{\text{keywords}} + S_{\text{tokens}}$$

1. **IncidentType Alignment ($S_{\text{type}} = 0.35$)**: Categorical alignment between the model-predicted `incident_type` and the runbook's registered type.
2. **Actionable Section Priority ($S_{\text{section}} = 0.15$)**: Gives highest operational precedence to `Immediate Mitigation` sections for active incidents.
3. **Service Affinity ($S_{\text{service}} = 0.15$)**: Matches the diagnosed microservice against the runbook's targeted service list.
4. **Signature Keyword Matching ($S_{\text{keywords}} \le 0.25$)**: Matches error signatures and keywords (e.g. `NpgsqlException`, `exit code 137`, `OOMKilled`, `CERT_HAS_EXPIRED`) directly in the incoming log.
5. **Token Overlap ($S_{\text{tokens}} \le 0.10$)**: Normalized term frequency overlap between query and runbook content.

---

## 3. API Integration: `POST /api/v1/triage/enriched`

To preserve full backwards-compatibility with existing clients of `POST /api/v1/triage` (which strictly return `LogTriageOutput`), an enriched endpoint was added:

### Endpoint Contract:
- **URL**: `POST /api/v1/triage/enriched`
- **Request**:
  ```json
  {
    "raw_log": "[2026-10-12T13:43:42.127Z] [ERROR] [event-processor] Npgsql.NpgsqlException: The connection pool has reached its maximum size and no connections are currently available",
    "request_id": "req_enriched_001"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "request_id": "req_enriched_001",
    "result": {
      "incident_type": "DATABASE",
      "severity": "P1_CRITICAL",
      "affected_service": "event-processor",
      "root_cause": "Npgsql database connection pool exhaustion under high concurrency.",
      "suggested_action": "Increase connection pool ceiling or tune connection lifetime timeouts.",
      "confidence": 0.95,
      "evidence": [
        "The connection pool has reached its maximum size and no connections are currently available"
      ]
    },
    "remediation": {
      "runbook_document": "postgres_connection_exhaustion.md",
      "runbook_title": "PostgreSQL Connection Pool Exhaustion",
      "section": "Immediate Mitigation",
      "content": "1. Terminate hanging idle-in-transaction connections:\n   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND now() - state_change > interval '5 minutes';\n2. Rate-limit or restart offending application pods consuming excessive connections.\n3. If PgBouncer is deployed, reload pool configurations or temporarily route non-critical traffic away from the primary instance.",
      "relevance_score": 0.825,
      "matched_keywords": [
        "Npgsql",
        "NpgsqlException",
        "connection pool has reached its maximum size"
      ]
    },
    "inference": {
      "latency_ms": 10528.7,
      "prompt_tokens": 142,
      "generated_tokens": 116
    }
  }
  ```

---

## 4. Test Suite Verification

The Phase 8 test suite (`tests/test_retrieval_phase8.py`) was executed:
- `test_runbooks_exist_and_cover_all_incident_types`: **PASSED** (100% taxonomy coverage).
- `test_runbook_parsing_and_chunking`: **PASSED** (40 structured chunks parsed from 10 runbooks).
- `test_index_generation_and_persistence`: **PASSED** (`artifacts/phase_8/runbooks_index.json` validated).
- `test_retrieval_postgres_connection_exhaustion`: **PASSED** (Score 0.825, matched PostgreSQL mitigation).
- `test_retrieval_kubernetes_oom`: **PASSED** (Score 0.775, matched Container OOM mitigation).
- `test_retrieval_tls_certificate`: **PASSED** (Score 0.800, matched TLS cert renewal runbook).
- `test_retrieval_kafka_lag`: **PASSED** (Score 0.800, matched Kafka consumer lag runbook).
- `test_retrieval_dns_failure`: **PASSED** (Score 0.750, matched CoreDNS mitigation runbook).
- `test_retrieval_crashloop_backoff`: **PASSED** (Score 0.775, matched Application CrashLoop runbook).
- `test_enriched_api_endpoint`: **PASSED** (Validated combined SLM triage + RAG output).
- `test_remediation_schema_forbids_extra_fields`: **PASSED** (Strict schema enforcement).

**Total Repository Test Suite**: **133 passed, 0 failed** (Phases 1–8).

---

## 5. Phase 8 Exit Criteria Checklist

- [x] Operational runbooks authored and cataloged across all 6 incident types.
- [x] Runbooks parsed into structured chunks and persisted in `artifacts/phase_8/runbooks_index.json`.
- [x] Local hybrid retrieval engine implemented in `src/retrieval/retriever.py`.
- [x] Remediation recommendations grounded in source operational documentation.
- [x] Source document, title, and section metadata included in enriched output.
- [x] Public `LogTriageOutput` core schema preserved with zero schema changes.
- [x] Enriched endpoint `/api/v1/triage/enriched` active and verified.
- [x] Phase 8 test suite (`tests/test_retrieval_phase8.py`) passed.
- [x] Full regression suite (133 tests) passed with 100% green status.
- [x] Phase 8 report generated and locked.

**Phase 8 Status: LOCKED ✅**
