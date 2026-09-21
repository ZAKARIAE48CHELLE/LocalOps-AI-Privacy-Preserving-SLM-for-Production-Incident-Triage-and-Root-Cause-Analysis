
# LocalOps AI — Build Roadmap by Phases

> **Goal:** Build a production-grade private SLM system for log triage, root-cause analysis, and runbook-grounded remediation.
>
> This roadmap is intentionally phased. Each phase should end with something concrete that you can test, measure, or demo.

---

# Phase 1 — Project Setup & Local Model Baseline

## Objective

Get the repository running and confirm that your machine can load and execute the base SLM correctly.

## Tasks

- Create the GitHub repository
- Create a Python virtual environment
- Install the ML stack:
  - PyTorch
  - Transformers
  - PEFT
  - TRL
  - bitsandbytes
  - datasets
  - Pydantic
  - FastAPI
  - Uvicorn
  - pytest
- Verify CUDA and GPU detection
- Create the initial repository structure
- Load `Qwen/Qwen2.5-1.5B-Instruct`
- Run one local inference
- Measure:
  - model load time
  - VRAM usage
  - generation latency
  - token throughput

## Initial Structure

```text
localops-ai/
├── src/
├── scripts/
├── data/
├── configs/
├── tests/
├── reports/
├── models/
├── runbooks/
├── requirements.txt
├── .env.example
└── README.md
```

## Deliverable

```text
scripts/smoke_test_model.py
```

Running it should successfully produce a model response.

## What You Should Understand

- What an SLM is
- Tokens
- Context window
- Inference
- Quantization
- FP16 vs 4-bit
- CUDA and VRAM

## Exit Criteria

- [ ] Environment works
- [ ] GPU is detected
- [ ] Model loads successfully
- [ ] One inference works
- [ ] VRAM and latency are measured

---

# Phase 2 — Incident Taxonomy & Output Schema

## Objective

Define exactly what the system must predict before generating data or fine-tuning anything.

## Step 1 — Define High-Level Incident Types

Recommended categories:

```text
DATABASE
INFRASTRUCTURE
APPLICATION
SECURITY
NETWORK
MESSAGING
```

## Step 2 — Define Incident Families

Example:

```text
DATABASE
├── PostgreSQL connection exhaustion
├── deadlock
├── slow query
├── replication failure
└── authentication error
```

```text
INFRASTRUCTURE
├── OOMKilled
├── CPU saturation
├── disk pressure
├── CrashLoopBackOff
└── node unavailable
```

```text
SECURITY
├── brute-force authentication
├── SQL injection
├── suspicious token usage
├── repeated authorization failure
└── unusual IP activity
```

## Step 3 — Define Severity Rules

Recommended levels:

```text
P1_CRITICAL
P2_HIGH
P3_MEDIUM
P4_LOW
```

Example rules:

```text
P1_CRITICAL
Major outage, critical dependency failure, or complete production unavailability.

P2_HIGH
Serious service degradation, major security event, or high business impact.

P3_MEDIUM
Partial degradation, recoverable dependency issue, or limited operational impact.

P4_LOW
Minor warning, informational problem, or low-impact issue.
```

## Step 4 — Build the Pydantic Contract

Recommended output:

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

## Step 5 — Create Schema Tests

Test cases should include:

- valid response
- missing field
- invalid severity
- invalid incident type
- wrong confidence type
- confidence outside expected range

## Deliverables

```text
src/schemas/triage.py
tests/test_schema.py
docs/incident_taxonomy.md
```

## Exit Criteria

- [ ] Incident categories defined
- [ ] Incident families defined
- [ ] Severity policy documented
- [ ] Pydantic schema implemented
- [ ] Validation tests pass

---

# Phase 3 — Dataset Engineering

## Objective

Create a diverse and realistic dataset without train/test leakage.

This is one of the most important phases of the project.

## Step 1 — Create Incident Templates

Start with around 10–15 families.

Examples:

```text
postgres_connection_exhaustion
postgres_deadlock
kubernetes_oom
kubernetes_disk_pressure
redis_timeout
api_dependency_timeout
sql_injection
brute_force_login
dns_failure
kafka_consumer_lag
tls_certificate_expired
connection_refused
```

Later grow toward:

```text
30–50 incident families
```

## Step 2 — Generate Meaningful Variation

For every family, vary:

- service name
- timestamp
- hostname
- pod name
- namespace
- IP address
- port
- request ID
- stack trace wording
- memory limits
- timeout values
- database names
- cloud/container environment
- HTTP status code

### Example

Same root cause:

```text
[checkout-api]
HikariPool-1 - Connection is not available...
```

```text
[payment-worker]
FATAL: remaining connection slots are reserved...
```

```text
[orders-service]
Unable to acquire JDBC connection...
```

All can belong to:

```text
postgres_connection_exhaustion
```

## Step 3 — Store Ground Truth Metadata

Example record:

```json
{
  "incident_id": "db_0042",
  "family": "postgres_connection_exhaustion",
  "incident_type": "DATABASE",
  "severity": "P1_CRITICAL",
  "affected_service": "checkout-api",
  "raw_log": "...",
  "root_cause": "PostgreSQL connection capacity is exhausted.",
  "suggested_action": "Inspect the connection pool and database connection limits."
}
```

## Step 4 — Prevent Leakage

Do not just randomly shuffle duplicated templates.

Prefer template-aware splits.

Example:

```text
TRAIN
postgres variants A–F
redis variants A–F
oom variants A–F

TEST
postgres variants G–H
redis variants G–H
oom variants G–H
```

The final test set must contain genuinely unseen log variations.

## Step 5 — Scale Progressively

Recommended progression:

```text
Prototype: 100–200 examples
↓
Validation dataset: ~1,000 examples
↓
Final training dataset: 5,000–10,000 examples
```

## Deliverables

```text
data/train.jsonl
data/validation.jsonl
data/test.jsonl
reports/dataset_statistics.json
```

## What You Should Understand

- synthetic data generation
- class balance
- train / validation / test design
- leakage
- template variation
- domain taxonomy

## Exit Criteria

- [ ] At least 10 incident families exist
- [ ] Logs have meaningful variation
- [ ] Metadata is complete
- [ ] Dataset split is leakage-safe
- [ ] Dataset statistics are generated

---

# Phase 4 — Baseline Evaluation

## Objective

Measure the base model before fine-tuning.

Without this phase, you cannot prove that QLoRA actually improved anything.

## Systems to Evaluate

### Experiment E1 — Zero-Shot

The model receives:

- the log
- the schema requirement

No examples.

### Experiment E2 — Prompt-Engineered

Add:

- severity rules
- output rules
- stronger system prompt
- JSON-only instructions

### Experiment E3 — Few-Shot

Add 2–4 representative examples in the prompt.

## Metrics

Measure:

### Classification

- incident type accuracy
- incident type macro-F1
- severity accuracy
- severity macro-F1

### Structured Output

- valid JSON rate
- Pydantic-valid rate
- missing-field rate
- invalid-enum rate

### System

- average latency
- p50 latency
- p95 latency
- tokens/second
- VRAM usage

## Deliverables

```text
src/evaluation/baseline.py
src/evaluation/metrics.py
reports/baseline_results.json
reports/baseline_results.csv
```

## Exit Criteria

- [ ] Zero-shot evaluated
- [ ] Prompted baseline evaluated
- [ ] Few-shot baseline evaluated
- [ ] Metrics stored
- [ ] Weaknesses of the base model are documented

---

# Phase 5 — QLoRA Fine-Tuning

## Objective

Fine-tune the compact SLM for domain-specific incident triage.

## Initial Strategy

Use:

```text
Base model: Qwen/Qwen2.5-1.5B-Instruct
Quantization: 4-bit NF4
LoRA rank: 16
LoRA alpha: 32
LoRA dropout: 0.05
Epochs: 2–4
Optimizer: paged AdamW 8-bit
Gradient checkpointing: enabled
```

These values are starting points, not permanent truths.

## Training Flow

```text
Base Model
↓
4-bit Quantization
↓
Prepare for k-bit Training
↓
Attach LoRA Adapters
↓
Supervised Fine-Tuning
↓
Validation
↓
Save Adapter
```

## Keep Configuration External

Example:

```text
configs/
├── model.yaml
├── training.yaml
└── lora.yaml
```

Avoid hard-coding everything inside `train.py`.

## Save Experiment Metadata

Track:

- model ID
- dataset version
- LoRA parameters
- learning rate
- epochs
- loss
- training time
- GPU
- VRAM usage

## Deliverables

```text
src/training/train_qlora.py
models/lora_adapter/
reports/training_summary.json
```

## Exit Criteria

- [ ] Training completes successfully
- [ ] Adapter is saved
- [ ] Validation loss is recorded
- [ ] Training configuration is reproducible
- [ ] Training resource usage is documented

---

# Phase 6 — Fine-Tuned Evaluation & Structured Output

## Objective

Prove whether the fine-tuned model is better and make its outputs reliable enough for software integration.

## Experiment E4 — Fine-Tuned QLoRA Model

Evaluate on the exact same held-out test set used for the baselines.

Compare:

```text
Zero-shot
vs
Prompted
vs
Few-shot
vs
QLoRA
```

## Add Structured Output Reliability

Evaluate three approaches.

### A — Prompt-Only JSON

```text
Return only valid JSON.
```

### B — Parsing + Pydantic

```text
generation
↓
JSON parsing
↓
Pydantic validation
```

### C — Constrained Generation

Optional advanced improvement.

Use grammar/schema-constrained generation so the model is restricted to valid structures.

## Reliability Flow

```text
Model Output
↓
Valid JSON?
├── Yes → Pydantic
└── No  → Repair / Retry
            ↓
          Pydantic
```

## Final Metrics

Compare:

| System                    | Schema Validity |  Type F1 | Severity F1 | p95 Latency |
| ------------------------- | --------------: | -------: | ----------: | ----------: |
| Zero-shot                 |        measured | measured |    measured |    measured |
| Prompted                  |        measured | measured |    measured |    measured |
| Few-shot                  |        measured | measured |    measured |    measured |
| QLoRA                     |        measured | measured |    measured |    measured |
| QLoRA + structured output |        measured | measured |    measured |    measured |

## Deliverables

```text
src/inference/model.py
src/inference/generation.py
src/inference/structured_output.py
reports/final_benchmark.csv
```

## Exit Criteria

- [ ] QLoRA evaluated on held-out data
- [ ] Baseline comparison completed
- [ ] JSON/schema reliability measured
- [ ] Latency measured
- [ ] VRAM measured
- [ ] Real results are stored

---

# Phase 7 — FastAPI Production Service

## Objective

Expose the model as a clean and testable AI service.

## Recommended Endpoints

```text
POST /api/v1/triage
POST /api/v1/triage/batch
GET  /api/v1/model-info
GET  /health
```

## `/triage`

Input:

```json
{
  "raw_log": "..."
}
```

Output:

```json
{
  "incident_type": "DATABASE",
  "severity": "P1_CRITICAL",
  "affected_service": "payment-api",
  "root_cause": "...",
  "suggested_action": "...",
  "confidence": 0.95,
  "evidence": ["..."],
  "model_version": "localops-qwen-v1"
}
```

## `/triage/batch`

Allow multiple logs in one request.

## `/model-info`

Return:

```json
{
  "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
  "adapter": "localops-v1",
  "quantization": "4bit-nf4",
  "schema_version": "1.0"
}
```

## Reliability Controls

Add:

- request validation
- maximum input size
- request ID
- safe exception handling
- generation timeout
- retry on malformed model output
- schema validation
- model version in response

## Deliverables

```text
src/api/main.py
tests/test_api.py
```

## Exit Criteria

- [ ] `/triage` works
- [ ] `/triage/batch` works
- [ ] `/health` works
- [ ] `/model-info` works
- [ ] API tests pass

---

# Phase 8 — Runbook RAG

## Objective

Ground remediation recommendations in trusted operational documentation.

The fine-tuned model should learn **behavior**.

The runbooks should provide **knowledge**.

```text
Fine-tuning = behavior
RAG = knowledge
```

## Create Runbooks

Example:

```text
runbooks/
├── postgres_connection_exhaustion.md
├── redis_timeout.md
├── kubernetes_oom.md
├── disk_pressure.md
├── kafka_consumer_lag.md
└── tls_certificate_expired.md
```

## RAG Flow

```text
Incoming Log
↓
SLM Triage
↓
Predicted Incident / Root Cause
↓
Retriever
↓
Relevant Runbook Sections
↓
Grounded Remediation Recommendation
↓
Validated JSON
```

## Vector Store

Start simple.

Use one of:

- FAISS
- Chroma
- Qdrant

Do not over-engineer this part initially.

## Add Traceability

Example:

```json
{
  "suggested_action": "Inspect HikariCP and PgBouncer before increasing max_connections.",
  "runbook": {
    "document": "postgres_connection_exhaustion.md",
    "section": "Immediate Mitigation"
  }
}
```

## Deliverables

```text
src/retrieval/index_runbooks.py
src/retrieval/retriever.py
runbooks/
```

## Exit Criteria

- [ ] Runbooks indexed
- [ ] Relevant runbook retrieval works
- [ ] Final response is grounded
- [ ] Source document is included in output

---

# Phase 9 — Dockerization & Reproducible Deployment

## Objective

Make the system reproducible outside your development environment.

## Build

```text
docker/
├── Dockerfile.api
└── docker-compose.yml
```

## Initial Docker Services

Start with:

```text
localops-api
```

Later optionally add:

```text
vector-db
prometheus
grafana
```

## Test

The final system should start with:

```bash
docker compose up
```

Then:

```bash
curl http://localhost:8000/health
```

## Exit Criteria

- [ ] Docker image builds
- [ ] API starts in container
- [ ] GPU access works where applicable
- [ ] Health endpoint works
- [ ] Inference works from container

---

# Phase 10 — Monitoring & Observability

## Objective

Treat the model like a production service rather than a notebook experiment.

## Track

```text
request_id
timestamp
model_version
incident_type
severity
latency_ms
input_tokens
output_tokens
schema_valid
retrieval_used
```

## Metrics

Recommended:

```text
requests_total
requests_failed_total
schema_validation_failures_total
inference_latency_seconds
tokens_generated_total
```

## Optional Stack

```text
Prometheus
+
Grafana
```

## Privacy Rule

Do not store raw production logs by default.

Prefer metadata and sanitized samples.

## Exit Criteria

- [ ] Request metrics collected
- [ ] Latency tracked
- [ ] Model failures tracked
- [ ] Schema failures tracked
- [ ] Sensitive input logging avoided

---

# Phase 11 — Testing, CI/CD & Reliability

## Objective

Make the repository look like serious engineering work.

## Tests

Create:

```text
tests/
├── test_schema.py
├── test_dataset.py
├── test_api.py
├── test_retrieval.py
└── test_inference.py
```

## CI Pipeline

Example GitHub Actions flow:

```text
Push / Pull Request
↓
Install Dependencies
↓
Lint
↓
Unit Tests
↓
Schema Tests
↓
API Tests
```

Do not run expensive GPU fine-tuning on every commit.

## Optional

Add:

- Ruff
- Black
- mypy
- pre-commit

## Exit Criteria

- [ ] Unit tests pass
- [ ] API tests pass
- [ ] CI works
- [ ] Repository is reproducible

---

# Phase 12 — Portfolio Polish & Final Benchmark

## Objective

Make a recruiter understand the project quickly.

## Final Experiment Matrix

| ID | System                          |
| -- | ------------------------------- |
| E1 | Base zero-shot                  |
| E2 | Base + strong prompt            |
| E3 | Base + few-shot                 |
| E4 | QLoRA                           |
| E5 | QLoRA + structured output       |
| E6 | QLoRA + structured output + RAG |

## Final README Structure

Your README should contain:

1. Problem statement
2. Why local/private SLM
3. Architecture
4. Dataset methodology
5. Leakage prevention
6. Baselines
7. QLoRA fine-tuning
8. Evaluation
9. RAG
10. API
11. Docker deployment
12. Benchmark results
13. Limitations
14. Future work

## Final Portfolio Story

```text
AuraMarket
Data Engineering + Microservices + AI Agents

OSMOS
Applied AI + Digital Twins + Local LLMs + Multi-Agent Systems

LocalOps AI
SLM Fine-Tuning + Evaluation + RAG + Production LLM Engineering
```

## Exit Criteria

- [ ] README is polished
- [ ] Architecture diagram exists
- [ ] Real benchmark results included
- [ ] Demo request/response included
- [ ] Limitations documented
- [ ] Repository is ready to show

---

# Recommended Build Order

```text
PHASE 1
Environment + Base Model
↓
PHASE 2
Taxonomy + Schema
↓
PHASE 3
Dataset
↓
PHASE 4
Baselines
↓
PHASE 5
QLoRA Training
↓
PHASE 6
Evaluation + Structured Output
↓
PHASE 7
FastAPI
↓
PHASE 8
Runbook RAG
↓
PHASE 9
Docker
↓
PHASE 10
Monitoring
↓
PHASE 11
CI/CD + Testing
↓
PHASE 12
Portfolio Polish
```

---

# MVP Boundary

A strong MVP is:

```text
Phase 1
+
Phase 2
+
Phase 3
+
Phase 4
+
Phase 5
+
Phase 6
+
Phase 7
+
Phase 9
```

That already gives you:

- dataset engineering
- SLM inference
- proper baselines
- QLoRA fine-tuning
- rigorous evaluation
- structured output
- API serving
- Docker deployment

---

# Advanced Version

After the MVP, add:

```text
Runbook RAG
+
Batch inference
+
Constrained generation
+
Prometheus
+
Grafana
+
CI/CD
+
Load testing
```

---

# First 7 Concrete Tasks

1. Create the repository.
2. Create the Python environment.
3. Verify CUDA.
4. Load Qwen locally.
5. Run one inference.
6. Implement the Pydantic schema.
7. Design the first incident taxonomy.

Do **not** start QLoRA training yet.

The first major milestone is:

> **Build a trustworthy dataset and baseline evaluation pipeline before adapting the model.**
