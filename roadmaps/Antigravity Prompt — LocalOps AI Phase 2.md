# LocalOps AI — Phase 2 Implementation

## Context

We are developing:

**LocalOps AI — Privacy-Preserving SLM for Production Incident Triage and Root Cause Analysis**

Phase 1 has already been completed and verified.

The existing project already has:

- Python virtual environment
- CUDA-enabled PyTorch
- NVIDIA GPU validation
- `Qwen/Qwen2.5-1.5B-Instruct`
- 4-bit NF4 local inference
- baseline telemetry
- environment tests
- initial repository structure

Do **not** modify or rebuild Phase 1 unless a change is strictly required for Phase 2 compatibility.

Existing Phase 1 tests must continue to pass.

---

# Objective

Implement only:

# Phase 2 — Incident Taxonomy & Output Schema

The purpose of this phase is to define the formal domain vocabulary and typed output contract that will later be used for:

- dataset generation
- training
- evaluation
- inference
- FastAPI responses

This phase must NOT implement dataset generation, fine-tuning, RAG, FastAPI endpoints, Docker, monitoring, or later project phases.

---

# 1. Incident Type Taxonomy

Create a strict enum representing the six high-level incident categories:

```text
DATABASE
INFRASTRUCTURE
APPLICATION
SECURITY
NETWORK
MESSAGING
```

Use Python `Enum` compatible with Pydantic v2.

Recommended class:

```python
IncidentType
```

The serialized values must exactly match the uppercase strings above.

---

# 2. Severity Taxonomy

Create a strict enum:

```text
P1_CRITICAL
P2_HIGH
P3_MEDIUM
P4_LOW
```

Recommended class:

```python
Severity
```

These values represent operational/business impact rather than simply the textual log level.

---

# 3. Severity Policy

Create:

```text
documentation/severity_policy.md
```

Document the meaning of each severity.

Use approximately the following policy:

## P1_CRITICAL

Critical production impact.

Typical situations:

- complete service outage
- critical infrastructure unavailable
- major production database unavailable
- widespread inability to serve requests
- severe failure affecting core business operations
- incident requiring immediate response

## P2_HIGH

Serious degradation or high-risk incident.

Typical situations:

- major functionality degraded
- significant security incident
- repeated failures with substantial operational impact
- important dependency unstable
- high business impact without complete outage

## P3_MEDIUM

Moderate or recoverable operational problem.

Typical situations:

- partial degradation
- intermittent dependency failure
- recoverable timeout
- limited functionality affected
- operational issue that requires investigation but not immediate emergency response

## P4_LOW

Low-impact issue.

Typical situations:

- warning
- minor isolated failure
- informational operational issue
- negligible production impact
- non-urgent issue

Explicitly document:

> Log textual level (`WARN`, `ERROR`, `FATAL`, `CRITICAL`) must not alone determine incident severity. Severity is based primarily on operational and business impact.

---

# 4. Incident Families

Create:

```text
documentation/incident_taxonomy.md
```

The document must define the six high-level categories and their initial incident families.

Do not implement dataset generation yet.

We are only defining the taxonomy.

Use at least the following initial families.

## DATABASE

```text
POSTGRES_CONNECTION_EXHAUSTION
DATABASE_DEADLOCK
DATABASE_SLOW_QUERY
DATABASE_REPLICATION_FAILURE
DATABASE_AUTH_FAILURE
DATABASE_STORAGE_EXHAUSTION
```

## INFRASTRUCTURE

```text
KUBERNETES_OOM
CPU_SATURATION
DISK_PRESSURE
CRASH_LOOP
NODE_UNAVAILABLE
CONTAINER_STARTUP_FAILURE
```

## APPLICATION

```text
APPLICATION_EXCEPTION
DEPENDENCY_TIMEOUT
THREAD_POOL_EXHAUSTION
INVALID_CONFIGURATION
API_INTERNAL_ERROR
RETRY_STORM
```

## SECURITY

```text
BRUTE_FORCE_AUTHENTICATION
SQL_INJECTION_ATTEMPT
AUTHORIZATION_FAILURE
SUSPICIOUS_TOKEN_USAGE
SUSPICIOUS_IP_ACTIVITY
CREDENTIAL_ABUSE
```

## NETWORK

```text
DNS_RESOLUTION_FAILURE
CONNECTION_REFUSED
CONNECTION_RESET
SOCKET_TIMEOUT
TLS_CERTIFICATE_FAILURE
NETWORK_UNREACHABLE
```

## MESSAGING

```text
KAFKA_CONSUMER_LAG
KAFKA_BROKER_UNAVAILABLE
QUEUE_BACKLOG
REDIS_STREAM_TIMEOUT
RABBITMQ_CONNECTION_FAILURE
MESSAGE_PROCESSING_FAILURE
```

For each family, briefly explain:

- what it represents
- which top-level category owns it
- typical observable symptoms

The taxonomy should be structured so Phase 3 can later use these families to generate diverse log templates and perform leakage-safe train/test splitting.

---

# 5. Core Pydantic Output Schema

Create:

```text
src/schemas/
```

Recommended files:

```text
src/schemas/__init__.py
src/schemas/enums.py
src/schemas/triage.py
```

## `enums.py`

Contains at least:

```python
IncidentType
Severity
```

## `triage.py`

Implement:

```python
LogTriageOutput
```

Required fields:

```text
incident_type
severity
affected_service
root_cause
suggested_action
confidence
evidence
```

Expected conceptual structure:

```python
class LogTriageOutput(BaseModel):
    incident_type: IncidentType
    severity: Severity
    affected_service: str
    root_cause: str
    suggested_action: str
    confidence: float
    evidence: list[str]
```

---

# 6. Validation Requirements

Apply appropriate Pydantic v2 validation.

## `confidence`

Must satisfy:

```text
0.0 <= confidence <= 1.0
```

Use a typed Pydantic field constraint.

Important:

Document that this field initially represents:

> model-reported confidence

It must NOT yet be described as a statistically calibrated probability.

Calibration may be evaluated in a future phase.

---

## String Fields

These fields must not accept meaningless empty strings:

```text
affected_service
root_cause
suggested_action
```

Whitespace-only values should also be rejected.

Use clean Pydantic v2 validation rather than manual ad-hoc checking where possible.

---

## Evidence

`evidence` must be:

```text
list[str]
```

It represents short excerpts or signals from the input log that support the model's diagnosis.

Example:

```json
[
  "active=50, idle=0, waiting=12",
  "remaining connection slots are reserved"
]
```

Each evidence item should be a non-empty string.

Decide whether an empty evidence list should be allowed.

Preferred behavior for this phase:

```text
at least one evidence item required
```

Document this decision.

---

# 7. Example Valid Object

The schema should accept something similar to:

```json
{
  "incident_type": "DATABASE",
  "severity": "P1_CRITICAL",
  "affected_service": "orders-service",
  "root_cause": "PostgreSQL connection capacity is exhausted.",
  "suggested_action": "Inspect application connection pool usage and PostgreSQL connection limits.",
  "confidence": 0.96,
  "evidence": [
    "active=50, idle=0, waiting=12",
    "remaining connection slots are reserved"
  ]
}
```

---

# 8. Automated Tests

Create:

```text
tests/test_schema.py
```

Use `pytest`.

Tests must cover at least:

### Valid payload

A complete valid object must pass.

### Missing required field

Example:

```text
incident_type missing
```

must fail.

### Invalid incident type

Example:

```text
"STORAGE"
```

must fail.

### Invalid severity

Example:

```text
"P5_INFO"
```

must fail.

### Confidence above range

```text
1.1
```

must fail.

### Confidence below range

```text
-0.1
```

must fail.

### Invalid confidence type

A clearly invalid non-numeric value must fail.

### Empty affected service

```text
""
```

must fail.

### Whitespace-only affected service

```text
"   "
```

must fail.

### Empty root cause

must fail.

### Empty suggested action

must fail.

### Evidence wrong type

Example:

```json
"evidence": "remaining connection slots"
```

must fail.

### Empty evidence list

must fail if the schema requires at least one item.

### Empty evidence item

Example:

```json
[""]
```

must fail.

### Serialization

Verify:

```python
model.model_dump()
```

and:

```python
model.model_dump_json()
```

produce the expected serialized enum values.

---

# 9. Regression Testing

After implementing Phase 2, run the complete test suite:

```powershell
.venv\\Scripts\\pytest.exe -v
```

All existing Phase 1 tests must remain green.

Do not remove or weaken previous tests merely to make the suite pass.

---

# 10. Architecture Principle

Keep the current core schema independent from future RAG functionality.

Do NOT add fields such as:

```text
runbook_document
runbook_section
retrieval_score
embedding_score
retrieved_context
```

Those belong to a later RAG-enriched response model in Phase 8.

Likewise, do not add FastAPI-specific response structures yet.

`LogTriageOutput` should represent the core AI triage contract.

---

# 11. Code Quality Requirements

Use:

- Python type annotations
- Pydantic v2 APIs
- clear docstrings
- modular files
- meaningful names
- no duplicated enum definitions
- no unnecessary dependencies
- no over-engineered abstractions

Keep the implementation easy to understand.

---

# 12. Documentation

Update documentation where appropriate.

Create:

```text
documentation/incident_taxonomy.md
documentation/severity_policy.md
```

Also generate:

```text
documentation/Phase_2_Report.md
```

The Phase 2 report should follow approximately the quality and structure of the existing Phase 1 report.

It must contain:

1. Executive Summary
2. Phase Objective
3. Files Created / Modified
4. Incident Type Design
5. Incident Family Taxonomy
6. Severity Policy
7. Pydantic Schema Design
8. Validation Rules
9. Test Suite
10. Test Results
11. Example Valid Payload
12. Important Design Decisions
13. Exit Criteria Checklist
14. Transition to Phase 3

Include actual test results, not fabricated results.

---

# 13. Phase 2 Exit Criteria

Phase 2 is complete only when all of the following are satisfied:

- [ ] `IncidentType` implemented
- [ ] `Severity` implemented
- [ ] six high-level incident categories documented
- [ ] incident families documented
- [ ] severity policy documented
- [ ] `LogTriageOutput` implemented
- [ ] confidence constrained to `[0, 1]`
- [ ] confidence semantics documented
- [ ] evidence implemented and validated
- [ ] empty required text fields rejected
- [ ] valid payload accepted
- [ ] invalid incident types rejected
- [ ] invalid severity rejected
- [ ] invalid confidence rejected
- [ ] invalid evidence rejected
- [ ] serialization tested
- [ ] existing Phase 1 tests still pass
- [ ] new Phase 2 tests pass
- [ ] `Phase_2_Report.md` generated

---

# 14. Explicit Scope Boundary

STOP after Phase 2.

Do NOT implement:

- Phase 3 dataset generator
- synthetic logs
- train/validation/test split
- baseline evaluation framework
- QLoRA training
- structured generation pipeline
- FastAPI serving endpoints
- RAG
- vector databases
- Docker
- Prometheus
- Grafana
- CI/CD extensions related to later phases

Do not pre-implement future architecture unless it is absolutely required for Phase 2.

At the end:

1. run all tests,
2. report the results,
3. generate `documentation/Phase_2_Report.md`,
4. stop and wait for review before Phase 3.