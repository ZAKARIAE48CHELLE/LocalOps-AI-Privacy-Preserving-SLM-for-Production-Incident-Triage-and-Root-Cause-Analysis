# LocalOps AI — Phase 7: FastAPI Production Service

## Objective

Package the locked LocalOps AI fine-tuned model into a reliable local production API.

The service must expose the official QLoRA model through a stable HTTP contract while preserving privacy, strict schema validation, deterministic inference defaults, and observability hooks for later phases.

Official inference stack:

- Base model: `Qwen/Qwen2.5-1.5B-Instruct`
- Adapter: `artifacts/phase_5/final_adapter/`
- Quantization: 4-bit NF4
- GPU target: RTX 3070 Laptop 8 GB
- Core response schema: Phase 2 `LogTriageOutput`

Do not modify model weights or Phase 2 schema.

## 1. Required API Endpoints

Implement exactly these public endpoints:

### `GET /health`

Purpose: process/liveness health.

Return fields such as:

```json
{
  "status": "ok",
  "service": "localops-ai",
  "version": "..."
}
```

Must not trigger model inference.

### `GET /ready`

Purpose: readiness/model-loaded status.

Return whether:

- tokenizer loaded
- base model loaded
- adapter loaded
- CUDA available when configured
- warmup completed

Return non-2xx if the service cannot accept inference traffic.

### `GET /api/v1/model-info`

Return non-sensitive model metadata:

- base model ID
- adapter version/path identifier
- quantization mode
- device type
- schema version
- service version
- max input tokens
- decoding mode

Do not expose local absolute filesystem paths.

### `POST /api/v1/triage`

Request:

```json
{
  "raw_log": "..."
}
```

Optional request metadata may include:

```json
{
  "request_id": "..."
}
```

Response must contain:

```json
{
  "request_id": "...",
  "result": {
    "incident_type": "...",
    "severity": "...",
    "affected_service": "...",
    "root_cause": "...",
    "suggested_action": "...",
    "confidence": 0.0,
    "evidence": ["..."]
  },
  "inference": {
    "latency_ms": 0.0,
    "prompt_tokens": 0,
    "generated_tokens": 0
  }
}
```

The `result` object must strictly validate using the locked Phase 2 Pydantic model.

### `POST /api/v1/triage/batch`

Request:

```json
{
  "items": [
    {"raw_log": "..."},
    {"raw_log": "..."}
  ]
}
```

Implement bounded batch size through configuration.

The endpoint must:

- preserve input ordering
- return per-item status/result/error
- not fail the entire batch because one input is invalid
- enforce maximum batch size
- avoid GPU OOM through controlled batching/micro-batching

## 2. API Project Structure

Create or adapt:

```text
src/api/
├── __init__.py
├── app.py
├── schemas.py
├── dependencies.py
├── inference_service.py
├── model_manager.py
├── exceptions.py
├── middleware.py
└── settings.py
```

Scripts:

```text
scripts/run_api.py
```

Configuration:

```text
configs/api.yaml
```

Tests:

```text
tests/test_api_phase7.py
```

Documentation:

```text
documentation/phase_7/Phase_7_Report.md
```

## 3. Configuration

`configs/api.yaml` must be the source of truth for:

```text
service host
service port
base model ID
adapter path
quantization config
max input characters
max input tokens
max_new_tokens
batch size limits
concurrency limit
request timeout
warmup enabled
CORS policy
log level
raw-log logging policy
```

Environment variables may override deployment-specific values, but config precedence must be documented.

Never commit secrets.

## 4. Model Manager

Implement a singleton/lifecycle-managed model manager that:

1. Loads tokenizer once.
2. Loads the 4-bit base model once.
3. Loads the locked PEFT adapter once.
4. Puts model in evaluation mode.
5. Performs optional warmup inference.
6. Exposes readiness state.
7. Cleans up CUDA resources on graceful shutdown.

Do not reload the model per request.

Model provenance must be validated against the Phase 5 manifest when practical.

## 5. Inference Service

Create a dedicated inference service responsible for:

- input validation
- prompt construction matching Phase 6 E4
- tokenization
- GPU inference under `torch.inference_mode()`
- deterministic decoding by default
- raw generation capture internally
- JSON parsing
- strict Pydantic validation
- inference telemetry

Prompt:

```text
SYSTEM:
You are a production incident triage assistant.
Return only valid JSON following the required schema.

USER:
<raw production log>
```

Do not use Phase 4 few-shot demonstrations.

## 6. Structured-Output Failure Handling

Do not silently invent fields.

If generation cannot be validated:

- preserve the raw generation in internal debug state/log only when debug policy permits
- return a controlled API error object
- use an explicit error code such as `MODEL_OUTPUT_INVALID`
- include request ID
- never return an invalid `result` object as if successful

Do not expose stack traces to clients.

## 7. Input Validation & Abuse Protection

Reject:

- empty logs
- logs above configured character/token limits
- malformed request bodies
- oversized batches

Normalize line endings only if needed.

Do not alter semantic log content.

Add configurable concurrency control using an `asyncio.Semaphore` or equivalent because the GPU is a shared scarce resource.

## 8. Request IDs

Every request must have a request ID.

If a valid user-provided request ID is absent, generate a UUID.

Return it in:

- API response
- structured logs
- error responses

This will be used for observability in Phase 10.

## 9. Privacy-Safe Logging

Default behavior:

- do not log raw logs
- do not log full generated root-cause text unless debug is explicitly enabled
- log only metadata such as request ID, latency, token counts, status, predicted category/severity when permitted

Add a configuration flag:

```text
log_raw_payloads: false
```

Default must remain `false`.

## 10. Concurrency & GPU Safety

Use bounded inference concurrency.

Start conservatively with configurable:

```text
max_concurrent_inference = 1
```

Then smoke-test 2 if VRAM permits.

Do not assume that higher API concurrency improves autoregressive generation throughput.

For batch endpoint, use micro-batching based on measured Phase 6 VRAM behavior.

If CUDA OOM occurs:

- catch it at service boundary
- clear recoverable CUDA cache
- return controlled `GPU_RESOURCE_EXHAUSTED`
- keep service alive if possible

## 11. Timeouts

Implement:

- request-level timeout
- inference timeout
- graceful cancellation semantics where safe

Do not leave GPU work orphaned unnecessarily.

## 12. Error Contract

Use a consistent error model:

```json
{
  "request_id": "...",
  "error": {
    "code": "...",
    "message": "..."
  }
}
```

Codes should include at least:

- `INVALID_REQUEST`
- `INPUT_TOO_LARGE`
- `MODEL_NOT_READY`
- `MODEL_OUTPUT_INVALID`
- `GPU_RESOURCE_EXHAUSTED`
- `INFERENCE_TIMEOUT`
- `INTERNAL_ERROR`

## 13. Security Basics

Phase 7 is local/private by default.

Implement:

- no arbitrary file reads from request payloads
- no shell execution
- bounded payload size
- CORS disabled or restricted by default
- safe exception handling
- no model-path leakage
- no debug stack traces in production mode

Authentication can remain optional/configurable for now but design middleware boundaries so it can be added later without rewriting endpoints.

## 14. Warmup

On startup, optionally run one tiny synthetic inference request.

Warmup must:

- not use the held-out test set
- not alter model state
- record warmup duration
- set readiness only after successful completion when warmup is enabled

## 15. API Tests

Add tests covering:

### Schema/API

- `/health`
- `/ready`
- `/model-info`
- valid single triage request
- invalid empty request
- oversized request
- valid batch request
- oversized batch
- per-item batch errors

### Model behavior

Use mocked inference for most CI tests.

Add one local integration smoke test, optionally marked `gpu`, that loads the real adapter and verifies one response validates Phase 2 schema.

### Reliability

- request ID propagation
- timeout handling
- concurrency semaphore behavior
- invalid model output error handling
- no raw-log leakage in default logs

## 16. API Benchmark

Run a local API benchmark on a small non-test fixture set or validation samples.

Measure:

- p50 latency
- p95 latency
- requests/minute
- peak VRAM
- startup/load time

This is service benchmark data, not a replacement for Phase 6 scientific evaluation.

## 17. Phase 7 Report

Generate:

```text
documentation/phase_7/Phase_7_Report.md
```

Include:

- service architecture
- endpoints
- request/response examples
- model lifecycle
- concurrency design
- privacy controls
- failure handling
- measured service telemetry
- tests
- known limitations
- Phase 8 transition

## 18. Phase 7 Exit Criteria

Lock Phase 7 only if:

- model loads once and remains resident
- `/health` works
- `/ready` reflects model readiness accurately
- `/model-info` works without sensitive path leakage
- `/api/v1/triage` works with strict schema
- `/api/v1/triage/batch` works with bounded size
- request IDs propagate
- invalid model outputs are handled safely
- default logs do not contain raw logs
- concurrency is bounded
- real local GPU integration smoke test passes
- all Phase 1–7 tests pass
- Phase 7 report is generated

## 19. Scope Boundary

Do not add RAG yet.
Do not Dockerize yet.
Do not add Prometheus/Grafana yet except minimal hooks needed for later phases.
Do not alter model weights.

When all exit criteria pass, mark Phase 7 `LOCKED` and proceed to Phase 8.
