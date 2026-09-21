# LocalOps AI — Autonomous Execution Runbook

## Purpose

This runbook is the execution controller for the remaining LocalOps AI project phases. The project is already complete through Phase 5, while Phase 6 requires a final metrics-integrity cleanup before it can be locked.

Antigravity must execute the remaining files **in numerical order**:

1. `Phase_06_Final_Metrics_Integrity_and_Lock.md`
2. `Phase_07_FastAPI_Production_Service.md`
3. `Phase_08_Runbook_RAG.md`
4. `Phase_09_Dockerization.md`
5. `Phase_10_Monitoring_Observability.md`
6. `Phase_11_Testing_CICD_Reliability.md`
7. `Phase_12_Portfolio_Polish_Final_Benchmark.md`

## Global Rules

- Work **one phase at a time**.
- Do not skip a phase.
- Do not start the next phase until all exit criteria of the current phase pass.
- If a phase fails tests, fix it inside that phase before moving on.
- Preserve all locked artifacts from Phases 1–5.
- Never retrain the model unless a later phase explicitly requires it. The official adapter is the validation-selected Phase 5 `checkpoint-100` exported to `artifacts/phase_5/final_adapter/`.
- Never modify `data/generated/train.jsonl`, `validation.jsonl`, or `test.jsonl`.
- Do not silently change taxonomy, schema, prompt semantics, or evaluation definitions.
- Keep all execution reproducible and configuration-driven.
- Do not fabricate benchmark, latency, VRAM, energy, or quality metrics. Only report measured values.
- Keep the project fully local/private by default. No external inference APIs.
- Do not log raw production logs, secrets, or user-sensitive payloads unless an explicit debug flag is enabled.
- Prefer deterministic behavior where practical (`seed=42`, greedy decoding for benchmark paths).
- Use the existing project coding style and directory conventions where they already exist.
- All new tests must preserve existing tests. Never weaken an existing assertion just to make a phase pass.

## Locked Project Facts

### Model

- Base model: `Qwen/Qwen2.5-1.5B-Instruct`
- Fine-tuning method: QLoRA, 4-bit NF4
- Official adapter: `artifacts/phase_5/final_adapter/`
- Adapter provenance: Phase 5 `checkpoint-100`
- Hardware target: NVIDIA RTX 3070 Laptop GPU, 8 GB VRAM, 32 GB RAM

### Core Output Contract

The public triage contract remains the Phase 2 `LogTriageOutput` schema:

```json
{
  "incident_type": "...",
  "severity": "...",
  "affected_service": "...",
  "root_cause": "...",
  "suggested_action": "...",
  "confidence": 0.0,
  "evidence": ["..."]
}
```

Do not add `IncidentFamily` to this public prediction schema.

### IncidentType

- `DATABASE`
- `INFRASTRUCTURE`
- `APPLICATION`
- `SECURITY`
- `NETWORK`
- `MESSAGING`

### Severity

- `P1_CRITICAL`
- `P2_HIGH`
- `P3_MEDIUM`
- `P4_LOW`

### Phase 4 Locked Baselines

Use machine-readable locked Phase 4 artifacts as the source of truth. Key headline values:

- E2 IncidentType Macro-F1: `0.4679`
- E3 Severity Macro-F1: `0.2319`
- E2 Pydantic validity: `0.7986`
- E3 Pydantic validity: `0.9833`
- Corrected Phase 4 semantic-similarity metrics must be loaded from the locked Phase 4 artifacts, not manually retyped.

### Phase 5 Official Adapter

- Selected checkpoint: `checkpoint-100`
- Selection basis: minimum validation loss, without test access
- Test split remained sealed during Phase 5

## Autonomous Error Policy

Antigravity may autonomously fix:

- code defects
- test failures
- configuration inconsistencies
- stale documentation
- broken paths
- parser/reporting bugs
- Docker/CI syntax issues
- observability integration defects

Antigravity must **not** autonomously:

- change the official model checkpoint based on test results
- retrain the model using test data
- alter the taxonomy
- alter the Phase 2 public schema
- change locked Phase 4 baseline results
- regenerate Phase 3 data
- introduce cloud inference or external data transmission

If an external secret, missing credential, or unavailable infrastructure makes progress impossible, document the blocker clearly and continue all other work that does not depend on it.

## Required Phase Completion Pattern

At the end of every phase:

1. Run the phase-specific tests.
2. Run the full regression suite.
3. Generate/update that phase's report.
4. Create a short machine-readable phase status artifact where specified.
5. Verify every exit criterion.
6. Mark the phase `LOCKED` only if all blocking criteria pass.
7. Proceed to the next numbered phase.

## Final Definition of Done

The project is complete when:

- Phase 6 metrics are internally consistent and locked.
- Phase 7 local production API serves the QLoRA model reliably.
- Phase 8 local runbook RAG is integrated without changing the core triage schema.
- Phase 9 GPU-capable Docker packaging works.
- Phase 10 production observability and privacy-safe telemetry work.
- Phase 11 tests, CI/CD, reliability guards, and load tests pass.
- Phase 12 final benchmark, documentation, demo, model card, architecture, reproducibility guide, and portfolio materials are complete.
- Full repository regression suite is green.
