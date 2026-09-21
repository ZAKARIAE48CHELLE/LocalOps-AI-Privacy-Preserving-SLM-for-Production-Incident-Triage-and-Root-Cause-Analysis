# LocalOps AI — Phase 9: Dockerization & Reproducible Packaging

## Objective

Package the LocalOps AI service into a reproducible GPU-capable container deployment while preserving local model privacy, configuration portability, health checks, and data/model separation.

The image must serve the Phase 7 API with optional Phase 8 RAG support.

Do not bake large model weights or private runbooks into the image unless explicitly required. Prefer mounted/cache volumes.

## 1. Required Artifacts

Create:

```text
Dockerfile
.dockerignore
docker-compose.yml
configs/docker.env.example
scripts/docker_smoke_test.py
documentation/phase_9/Phase_9_Report.md
tests/test_docker_phase9.py
```

Optionally create:

```text
Dockerfile.cpu-smoke
```

only if useful for CI syntax/smoke checks. Production target remains NVIDIA GPU.

## 2. Base Image Strategy

Use a CUDA runtime/base compatible with the installed PyTorch/bitsandbytes stack.

The Dockerfile must explicitly document:

- CUDA runtime version
- Python version
- PyTorch version
- bitsandbytes compatibility

Do not use an unnecessarily huge CUDA development image unless compilation requires it.

## 3. Multi-Stage Build

Use a multi-stage build where practical:

### Builder stage

- install build tools only if needed
- install Python dependencies
- build wheels/cache when useful

### Runtime stage

- minimal CUDA runtime
- non-root user
- application source
- installed dependencies
- no compilers unless required at runtime

## 4. Dependency Locking

Create or use an existing locked dependency specification.

Acceptable forms:

- pinned `requirements.txt`
- `requirements.lock`
- `uv.lock`
- equivalent deterministic lock

Record important versions for:

- torch
- transformers
- peft
- bitsandbytes
- trl if runtime imports it
- fastapi
- uvicorn
- pydantic
- sentence-transformers
- FAISS/fallback packages
- prometheus client if already introduced later only as optional

## 5. Model & Adapter Mounts

Do not copy Hugging Face base-model cache into the Docker image by default.

Support mounted volumes for:

```text
Hugging Face cache
artifacts/phase_5/final_adapter
data/runbooks
artifacts/rag
```

Use environment/config paths inside the container.

Do not expose host absolute Windows paths in runtime responses.

## 6. Docker Compose

Create `docker-compose.yml` with at least:

### `localops-api`

- NVIDIA GPU reservation/device access
- API port
- mounted model cache
- adapter mount
- config mount
- optional RAG artifacts mount
- restart policy
- healthcheck

Do not require internet after model/cache artifacts are available locally.

If Mission Control dashboard is a separate process, either:

- include it as a second service, or
- serve it from the API service if that is already the architecture

Avoid needless duplication.

## 7. Environment Variables

Support environment overrides for:

```text
LOCALOPS_MODEL_ID
LOCALOPS_ADAPTER_PATH
LOCALOPS_CONFIG_PATH
LOCALOPS_RAG_ENABLED
LOCALOPS_RAG_INDEX_PATH
LOCALOPS_HOST
LOCALOPS_PORT
LOCALOPS_LOG_LEVEL
LOCALOPS_LOG_RAW_PAYLOADS
HF_HOME / cache path
```

Provide `.env.example` with non-secret placeholders.

Never commit actual credentials/tokens.

## 8. Non-Root Runtime

Run application as a non-root user.

Ensure mounted volume permissions are compatible.

Do not grant privileged container mode.

## 9. Healthcheck

Docker healthcheck should call:

```text
GET /health
```

Readiness can be separately monitored through `/ready`.

Do not make the container healthcheck perform inference.

## 10. Startup Behavior

Container startup must:

1. validate configuration
2. validate adapter files
3. load model
4. load optional RAG index
5. warm up if enabled
6. become ready

Failures should result in clear logs and non-ready state.

## 11. Offline/Local Mode

Support an offline deployment flag/environment configuration where:

- Hugging Face network access is disabled
- all required artifacts must already exist in mounted cache

Document exact offline start command.

## 12. Image Size

Measure final image size.

Avoid accidental inclusion of:

- test datasets
- `.git`
- checkpoints not needed for serving
- full training artifacts
- raw evaluation predictions
- local caches
- virtual environments

Use `.dockerignore` aggressively.

## 13. GPU Verification

Inside container verify:

- CUDA visible
- torch CUDA available
- expected GPU name
- bitsandbytes 4-bit loading works
- adapter loads
- one real inference succeeds

Create an automated smoke script.

## 14. RAG Verification

When RAG is enabled:

- index loads from mounted artifact
- runbook endpoint works
- no index rebuild is required on every startup unless explicitly configured

When disabled:

- core triage API still starts and works

## 15. Container Security

Add:

- non-root user
- read-only mounts where possible
- no Docker socket mount
- no privileged mode
- minimal exposed ports
- no secrets baked into layers
- dependency vulnerability scan hook for Phase 11

## 16. Docker Tests

Add tests for:

- Dockerfile parses/builds
- required files excluded by `.dockerignore`
- compose config validates
- container health endpoint
- readiness after model load
- model-info endpoint
- real GPU inference smoke when GPU runner exists
- offline mode failure is explicit if cache absent
- RAG enabled/disabled behavior

CI may skip GPU-required tests but local Phase 9 completion requires a GPU container smoke on the target machine if Docker/NVIDIA Container Toolkit are available.

## 17. Docker Benchmark

Compare native vs container service on a small validation fixture set:

- startup time
- p50 inference latency
- p95 inference latency
- peak VRAM
- throughput

Container overhead should be documented, not assumed.

## 18. Reproducibility Documentation

Document exact commands:

```bash
docker compose build
docker compose up
```

and offline equivalents.

Document prerequisites:

- Docker Desktop / Docker Engine
- NVIDIA driver
- NVIDIA Container Toolkit / Docker GPU support
- mounted model cache

## 19. Phase 9 Report

Generate:

```text
documentation/phase_9/Phase_9_Report.md
```

Include:

- image architecture
- base image
- dependency locking
- GPU setup
- mounts
- offline mode
- security
- image size
- native vs Docker telemetry
- smoke results
- known limitations
- Phase 10 transition

## 20. Phase 9 Exit Criteria

Lock Phase 9 only if:

- Docker image builds
- compose configuration validates
- non-root runtime works
- model cache/adapter mounts work
- `/health` works in container
- `/ready` becomes ready after load
- real GPU inference succeeds in container when local GPU Docker support exists
- RAG can be toggled on/off
- offline mode documented
- image size measured
- no secrets/model caches accidentally baked in
- all Phase 1–9 tests pass or clearly marked GPU-only tests pass locally
- Phase 9 report exists

When locked, proceed to Phase 10.
