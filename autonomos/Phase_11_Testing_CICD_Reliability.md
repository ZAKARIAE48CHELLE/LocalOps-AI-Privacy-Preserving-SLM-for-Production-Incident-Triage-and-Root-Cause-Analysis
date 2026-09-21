# LocalOps AI — Phase 11: Testing, CI/CD, Reliability & Release Engineering

## Objective

Turn LocalOps AI from a successful local prototype into a maintainable software project with strong regression protection, CI/CD, reliability safeguards, load testing, release metadata, and documented failure behavior.

Do not retrain the model.

## 1. Testing Pyramid

Organize tests into explicit groups:

### Unit

- schemas
- parsers
- metrics
- config loading
- prompt building
- RAG chunking/retrieval
- redaction
- helpers

### Integration

- FastAPI endpoint tests
- mocked inference service
- RAG service integration
- metrics/logging integration

### Local GPU integration

- real adapter load
- one real inference
- API end-to-end inference
- Docker GPU smoke

### Benchmark/regression

- locked Phase 4 baseline artifacts immutable
- Phase 6 E4 metrics artifact integrity
- serving parity checks

CI should not download or execute the full 1.5B model on every normal commit.

## 2. Test Markers

Introduce pytest markers such as:

```text
unit
integration
gpu
slow
docker
benchmark
```

Default CI should run non-GPU deterministic tests.

GPU/slow tests should have explicit local/manual commands.

## 3. Static Quality

Add/configure:

- Ruff (lint/format)
- type checking (mypy or pyright, choose one)
- import sorting if not covered by Ruff

Do not force type strictness so high that the ML stack becomes impractical; document ignored third-party typing boundaries.

## 4. Security Checks

Add CI-compatible security checks such as:

- dependency vulnerability scan (`pip-audit` or equivalent)
- secret scan (`gitleaks` if available, or a lightweight repository scanner)
- Bandit for Python security linting where useful

Do not fail on irrelevant false positives without documented suppressions.

## 5. GitHub Actions / CI

Create a CI workflow, for example:

```text
.github/workflows/ci.yml
```

Stages:

1. checkout
2. set up supported Python version
3. install locked lightweight/CI dependencies
4. lint
5. type check
6. unit tests
7. integration tests with mocked model
8. security scans
9. Dockerfile/compose validation

Do not require NVIDIA GPU in standard hosted CI.

## 6. GPU Validation Workflow

Create a documented manual/self-hosted workflow or script for GPU verification:

```text
scripts/run_gpu_release_checks.py
```

It should run:

- model/adaptor load
- real schema-valid inference
- API inference
- RAG inference
- Docker GPU smoke when available

Produce a machine-readable result artifact.

## 7. Load Testing

Add a local load-test tool.

Use Locust, k6, or a lightweight Python/httpx runner. Choose one and document it.

Test scenarios:

### Single request

- steady low QPS

### Burst

- short concurrent burst

### Batch endpoint

- varying batch sizes

### RAG endpoint

- triage + retrieval

Measure:

- throughput
- p50/p95/p99 latency
- error rate
- timeout rate
- GPU utilization
- VRAM
- queue/inflight depth

Do not overload the laptop indefinitely. Use bounded tests.

## 8. Reliability Guards

Ensure production service has:

- bounded concurrency
- request timeouts
- graceful shutdown
- readiness transition on model failure
- controlled CUDA OOM handling
- batch-size limits
- input-size limits
- exception normalization
- RAG no-hit behavior
- startup failure clarity

Test each.

## 9. Graceful Shutdown

On SIGTERM/CTRL-C:

- stop accepting new requests
- allow in-flight inference to finish within grace period where practical
- flush logs/metrics
- release resources

Document Windows/Linux behavior where different.

## 10. Failure Injection Tests

Simulate:

- model not found
- adapter not found
- CUDA unavailable
- CUDA OOM mocked path
- invalid model generation
- RAG index missing
- corrupt RAG index metadata
- embedding model unavailable
- timeout

Service should fail safely and predictably.

## 11. Serving Parity Regression

Select a small frozen set of non-sensitive benchmark records with known Phase 6 outputs.

Verify that API serving with the same model/prompt/decoding produces semantically/structurally equivalent outputs.

Do not require exact text equality for every free-text field if tokenizer/runtime variation can occur, but strict enum/schema fields should match under deterministic local execution.

Document parity rule.

## 12. Versioning

Introduce project versioning.

Use semantic versioning, starting from a reasonable current pre-release or `1.0.0` if all release gates pass.

Expose version through:

- package metadata
- `/model-info`
- reports
- Docker image tag

## 13. Release Manifest

Generate:

```text
artifacts/release/release_manifest.json
```

Include:

- project version
- git commit if available
- base model ID
- adapter checksum
- RAG index checksum
- config checksums
- Phase 6 benchmark summary
- Docker image tag/hash if available
- test-suite result summary
- build timestamp

Do not include secrets or machine-specific absolute paths.

## 14. Reproducibility Script

Create a top-level or scripts-based validation command, e.g.:

```text
scripts/verify_release.py
```

It should check:

- expected artifacts present
- checksums match
- configs load
- API schema imports
- RAG index metadata valid
- locked benchmark artifacts present

## 15. CI Artifacts

CI should preserve lightweight artifacts such as:

- test report
- coverage report
- lint result
- security scan summary

Do not upload model weights to public CI artifacts.

## 16. Code Coverage

Measure coverage for application code.

Set a realistic threshold based on current codebase, then document it.

Do not game coverage with meaningless tests.

Focus on:

- API validation
- error handling
- RAG retrieval
- observability
- configuration
- reliability guards

## 17. Documentation Quality Checks

Add automated checks for broken internal file references where practical.

Ensure commands in README/report remain synchronized with real scripts/config files.

## 18. Phase 11 Report

Generate:

```text
documentation/phase_11/Phase_11_Report.md
```

Include:

- testing strategy
- CI workflow
- security scans
- load test methodology/results
- reliability tests
- failure injection
- graceful shutdown
- versioning
- release manifest
- coverage
- limitations
- Phase 12 transition

## 19. Phase 11 Exit Criteria

Lock Phase 11 only if:

- unit/integration suites pass
- full existing regression suite passes
- lint passes
- type checks pass under documented configuration
- security scans execute
- CI workflow validates
- GPU release checks pass locally where hardware exists
- load test results are recorded
- failure injection cases behave safely
- graceful shutdown is validated
- release manifest is generated
- version is exposed consistently
- Phase 11 report exists

When locked, proceed to Phase 12.
