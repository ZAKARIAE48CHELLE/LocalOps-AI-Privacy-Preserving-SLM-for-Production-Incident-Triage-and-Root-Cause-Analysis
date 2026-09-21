# LocalOps AI — Phase 10: Monitoring, Observability & Privacy-Safe Operations

## Objective

Add production observability to LocalOps AI without compromising privacy.

The system must expose operational health, model inference telemetry, structured logs, GPU metrics, RAG metrics, and service-level indicators while keeping raw user logs private by default.

## 1. Observability Architecture

Implement three layers:

1. **Structured application logs**
2. **Prometheus-compatible metrics**
3. **Mission Control dashboard integration**

Optional Grafana dashboards may be included if they add value and remain easy to run locally.

## 2. Required Metrics Endpoint

Add:

```text
GET /metrics
```

Prometheus text format.

Do not expose raw logs or generated text in labels.

## 3. Core Service Metrics

Expose counters/gauges/histograms such as:

```text
localops_requests_total
localops_request_errors_total
localops_inference_seconds
localops_inference_tokens_generated_total
localops_prompt_tokens_total
localops_schema_invalid_total
localops_model_output_invalid_total
localops_batch_size
localops_inflight_requests
```

Use low-cardinality labels only, e.g.:

- endpoint
- status
- incident_type
- severity

Do not use request ID, service name, raw log text, or user-controlled strings as metric labels.

## 4. Model Metrics

Track:

- prediction counts by IncidentType
- prediction counts by Severity
- schema-valid rate over rolling/service lifetime
- model-output-invalid count
- mean/p50/p95 inference latency through histogram buckets
- generated-token counts

Do not interpret live production distributions as accuracy because no ground truth exists at runtime.

## 5. GPU Metrics

Using NVML where available expose:

```text
localops_gpu_utilization_percent
localops_gpu_memory_used_bytes
localops_gpu_memory_total_bytes
localops_gpu_temperature_celsius
localops_gpu_power_watts
```

Handle NVML unavailable state gracefully.

Do not crash the API if GPU telemetry cannot be collected.

## 6. RAG Metrics

When Phase 8 RAG is enabled, expose:

```text
localops_rag_requests_total
localops_rag_no_hit_total
localops_rag_retrieval_seconds
localops_rag_top_similarity
localops_rag_chunks_returned
```

Do not use runbook content as metric labels.

## 7. Structured Logging

Use JSON logs in production mode.

Each request log event may include:

```text
timestamp
level
event
request_id
endpoint
status_code
latency_ms
prompt_tokens
generated_tokens
incident_type
severity
schema_valid
rag_enabled
```

Default must exclude:

- raw_log
- full model output
- evidence strings
- root cause text
- suggested action text

## 8. Redaction

Implement privacy redaction utilities for any optional debug logging.

Patterns should cover common secret forms:

- API keys
- bearer tokens
- JWT-like tokens
- passwords
- private-key blocks
- common cloud credentials

Redaction is defense-in-depth and not a guarantee.

Debug raw-payload logging remains disabled by default.

## 9. Request Tracing

Use request IDs from Phase 7 consistently across:

- API logs
- error logs
- RAG logs
- dashboard events

Optional OpenTelemetry tracing can be added if it stays local and does not create unnecessary complexity.

Do not export telemetry to external SaaS by default.

## 10. Mission Control Dashboard

Extend the existing LocalOps AI Mission Control to show live production telemetry:

- service health/readiness
- model loaded state
- requests/minute
- p50/p95 latency
- inflight requests
- schema failures
- predicted category/severity distribution
- GPU utilization
- VRAM usage
- temperature
- RAG hit/no-hit rates

Do not display raw production logs by default.

Add clear separation between:

- historical benchmark pages
- live serving telemetry

## 11. Alert Rules

Create local Prometheus-style alert examples/config for:

- API not ready
- high 5xx rate
- p95 inference latency above threshold
- schema invalid rate above threshold
- GPU VRAM > 90%
- GPU temperature above safe threshold
- repeated CUDA OOM
- RAG no-hit rate abnormally high

Thresholds must be configurable and documented as operational defaults, not universal truths.

## 12. Metrics Persistence

If Prometheus is included through Docker Compose, configure local retention suitable for development/demo.

Do not require long-term cloud storage.

## 13. Observability Security

By default:

- `/metrics` is intended for local/internal access
- do not expose the dashboard publicly without authentication/reverse-proxy controls
- avoid sensitive labels
- no raw logs in Prometheus

Document network exposure risk.

## 14. Tests

Add:

```text
tests/test_observability_phase10.py
```

Cover:

- metrics endpoint works
- counters increment
- latency histogram records
- invalid schema counter increments
- GPU metrics degrade gracefully without NVML
- RAG metrics conditional behavior
- no high-cardinality request ID labels
- default structured logs exclude raw payload
- redaction utility catches representative secret patterns
- dashboard API endpoints return valid telemetry

## 15. Load/Telemetry Smoke

Generate controlled local traffic and verify:

- metrics update correctly
- no memory leak over short run
- logs remain privacy-safe
- dashboard updates
- p50/p95 calculations align with observed traffic

## 16. Phase 10 Report

Generate:

```text
documentation/phase_10/Phase_10_Report.md
```

Include:

- observability architecture
- metric catalog
- logging policy
- privacy/redaction
- dashboard screenshots/description
- GPU telemetry
- RAG telemetry
- alert rules
- load smoke results
- limitations
- Phase 11 transition

## 17. Phase 10 Exit Criteria

Lock Phase 10 only if:

- `/metrics` works
- core service metrics are correct
- GPU telemetry works or gracefully degrades
- RAG metrics work when enabled
- production logs are structured
- raw payloads are absent by default
- redaction tests pass
- dashboard shows live serving metrics
- alert rules exist
- all Phase 1–10 tests pass
- Phase 10 report exists

When locked, proceed to Phase 11.
