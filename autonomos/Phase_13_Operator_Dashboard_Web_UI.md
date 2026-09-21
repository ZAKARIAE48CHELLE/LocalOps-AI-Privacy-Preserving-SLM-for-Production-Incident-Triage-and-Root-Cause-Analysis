# LocalOps AI — Phase 13: Operator Dashboard & Web User Experience

## Objective

Build a production-ready web dashboard so LocalOps AI can be used by DevOps, SRE, platform engineering, and technical operations users without requiring terminal commands, curl requests, or direct interaction with the REST API.

The dashboard must sit on top of the already locked LocalOps AI backend and MUST NOT modify the fine-tuned model, benchmark artifacts, Phase 6 results, retrieval logic, or public inference semantics.

The dashboard is an operational UI layer only.

---

## 1. Phase Scope

Phase 13 must provide a complete browser-based interface for:

- single incident triage
- enriched triage with runbook remediation
- batch incident analysis
- health and readiness inspection
- live model/GPU telemetry
- Prometheus-style operational metrics visualization
- recent local request history
- result export
- runbook inspection
- operator-friendly error messages
- privacy-safe operation

The dashboard must consume the existing LocalOps AI API rather than reimplement inference logic.

Existing backend endpoints are expected to remain the source of truth:

- `GET /health`
- `GET /ready`
- `GET /api/v1/model-info`
- `POST /api/v1/triage`
- `POST /api/v1/triage/enriched`
- `POST /api/v1/triage/batch`
- `GET /metrics`
- `GET /api/v1/telemetry/live`

---

## 2. Architectural Rule

The dashboard MUST NOT load the SLM itself.

Correct architecture:

```text
Browser Dashboard
        |
        v
FastAPI REST API
        |
        +--> InferenceService
        |
        +--> Pydantic Validation
        |
        +--> Runbook Retriever
        |
        +--> Observability / Telemetry
        |
        v
Qwen2.5-1.5B + QLoRA Adapter
```

The UI is a client of the backend.

This prevents duplicated GPU memory, duplicated inference code, benchmark drift, schema inconsistency, and accidental model loading in frontend processes.

---

## 3. Technology Choice

Prefer a lightweight frontend that is easy to maintain and portfolio-friendly.

Recommended default:

```text
React
Vite
TypeScript
Tailwind CSS
Recharts
Axios or native fetch
```

Alternative frontend frameworks may only be used if already present in the repository.

Do NOT replace the existing FastAPI backend.

Recommended structure:

```text
dashboard/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   └── localopsClient.ts
│   ├── components/
│   │   ├── Layout.tsx
│   │   ├── Sidebar.tsx
│   │   ├── StatusBadge.tsx
│   │   ├── IncidentForm.tsx
│   │   ├── TriageResult.tsx
│   │   ├── RemediationPanel.tsx
│   │   ├── EvidencePanel.tsx
│   │   ├── TelemetryCard.tsx
│   │   ├── MetricsChart.tsx
│   │   ├── BatchUploader.tsx
│   │   └── ErrorBanner.tsx
│   ├── pages/
│   │   ├── OverviewPage.tsx
│   │   ├── TriagePage.tsx
│   │   ├── BatchPage.tsx
│   │   ├── RunbooksPage.tsx
│   │   ├── MonitoringPage.tsx
│   │   └── SystemPage.tsx
│   ├── types/
│   │   └── api.ts
│   └── utils/
│       ├── formatting.ts
│       └── export.ts
└── tests/
```

---

## 4. Dashboard Pages

### 4.1 Overview / Mission Control

Create a landing page providing immediate operational status.

Display:

- API health
- model readiness
- loaded model ID
- adapter status
- quantization mode
- GPU device
- GPU VRAM usage
- GPU utilization
- GPU temperature
- current power draw
- total processed requests
- request error count
- schema-invalid count
- average inference latency
- p50 latency
- p95 latency
- RAG request count
- RAG no-hit count

Status must refresh automatically every 2–5 seconds.

Use:

```text
GET /health
GET /ready
GET /api/v1/model-info
GET /api/v1/telemetry/live
```

---

### 4.2 Incident Triage Page

Provide a large multiline input area for raw production logs.

Required controls:

- raw log textarea
- optional request ID
- Analyze Incident button
- Analyze + Runbook button
- clear/reset button
- sample incident selector
- character count
- maximum input warning

Use:

```text
POST /api/v1/triage
```

or:

```text
POST /api/v1/triage/enriched
```

Display a loading indicator while inference runs and disable repeated submission while the request is pending.

---

## 5. Triage Result Presentation

Do NOT display the model result as raw JSON only.

Create operator-friendly cards.

### Incident Summary Card

Display:

- Incident Type
- Severity
- Affected Service
- Confidence
- Latency

Use clear severity badges for:

```text
P1_CRITICAL
P2_HIGH
P3_MEDIUM
P4_LOW
```

Do not alter model output values.

### Root Cause Panel

Display `root_cause` as a readable diagnostic explanation.

### Suggested Action Panel

Display `suggested_action` clearly separated from root cause.

Add:

```text
Advisory only — LocalOps AI does not execute production changes.
```

### Evidence Panel

Render every evidence item clearly, preferably in monospace for log excerpts.

Do not expose hidden chain-of-thought.

Only display schema fields actually returned by the API.

---

## 6. Enriched Runbook Result

For `/api/v1/triage/enriched`, display a dedicated remediation section.

Show:

- runbook title
- runbook/document ID
- relevance score
- matched section
- matched keywords if returned
- immediate mitigation steps
- escalation guidance
- source runbook reference

Clearly distinguish:

```text
Model diagnosis
```

from:

```text
Retrieved runbook guidance
```

Do not present retrieved text as model-generated reasoning.

---

## 7. Batch Analysis Page

Support:

- multiple pasted log blocks
- JSON input if supported
- optional `.txt`, `.log`, `.json`, or `.jsonl` upload
- maximum 16 incidents per API batch request unless backend configuration says otherwise

Use:

```text
POST /api/v1/triage/batch
```

Display results in a table with Request, Incident Type, Severity, Service, Status, and Latency.

Allow expanding each row to inspect root cause, suggested action, evidence, and errors.

Batch errors must be isolated per item.

---

## 8. Result Export

Support at minimum:

- JSON
- CSV for batch results

Optional:

- Markdown incident report

Generate exports client-side where practical.

Never write uploaded raw logs to server disk just to generate exports.

---

## 9. Monitoring Page

Visualize:

- inference latency over time
- request throughput
- error count/rate
- schema-invalid count
- generated-token count
- prompt-token count
- predictions by IncidentType
- predictions by Severity
- GPU utilization
- GPU memory usage
- GPU temperature
- GPU power

Do not introduce high-cardinality telemetry.

Never put raw logs, request IDs, user text, or root-cause text inside metrics labels.

---

## 10. System Page

Display:

- service version
- base model
- adapter
- quantization
- device
- maximum input size
- maximum generated tokens
- decoding mode
- RAG enabled/disabled
- runbook count
- API status
- uptime

Do not expose absolute filesystem paths, secrets, environment credentials, or private tokens.

---

## 11. Runbooks Page

Provide a read-only browser for available operational runbooks.

Display:

- title
- IncidentType
- affected services
- severity default
- keywords
- symptoms
- diagnosis
- immediate mitigation
- long-term remediation

If no runbook-list API exists, add safe read-only endpoints:

```text
GET /api/v1/runbooks
GET /api/v1/runbooks/{runbook_id}
```

Do NOT implement runbook editing in Phase 13.

---

## 12. API Client Layer

Create a typed API client with methods like:

```text
getHealth()
getReadiness()
getModelInfo()
getTelemetry()
triage(log)
triageEnriched(log)
triageBatch(logs)
getRunbooks()
```

Frontend types should mirror backend Pydantic contracts.

Avoid duplicating or inventing fields.

---

## 13. Error Handling UX

Handle:

- 400 invalid request
- 413 payload too large
- 422/502 model output invalid
- 503 model not ready
- 507 GPU resource exhausted
- network failure
- request timeout

Never expose Python stack traces to browser users.

---

## 14. Privacy Requirements

Mandatory:

- no third-party analytics
- no Google Analytics
- no remote error telemetry
- no external CDN dependency in production
- no cloud model API calls
- no raw-log persistence by default
- no browser localStorage persistence of incident logs unless explicitly enabled
- no raw payload in URLs/query strings

Use in-memory UI state by default.

---

## 15. Security Controls

Implement:

- safe HTML escaping
- no `dangerouslySetInnerHTML` for model/log content
- payload-size awareness
- API timeout handling
- same-origin deployment where possible
- configurable CORS only when intentionally separated

Do not expose backend administrative filesystem operations to the dashboard.

---

## 16. Production Integration

Preferred deployment model:

```text
FastAPI backend
+
compiled dashboard static assets
```

Option A: serve frontend separately through Nginx.

Option B: FastAPI serves built dashboard static assets.

For local/portfolio deployment, Option B is preferred:

```text
http://localhost:8000/
```

Keep:

```text
/api/v1/*
/docs
/redoc
/metrics
```

unchanged.

---

## 17. Docker Integration

Update Docker build to compile the frontend and include static assets in the runtime image.

Recommended multi-stage structure:

```text
Stage 1: frontend-builder
Node.js
npm ci
npm run build

Stage 2: Python/backend builder
Python dependencies

Stage 3: CUDA runtime
FastAPI
SLM adapter
compiled dashboard assets
```

Do not run a Node dev server in production.

---

## 18. Dashboard Tests

Create:

```text
tests/test_dashboard_phase13.py
```

Verify:

- dashboard root route reachable
- static assets served
- health/readiness available
- telemetry remains privacy-safe
- runbook listing safe if added
- no raw-log persistence endpoint exists
- dashboard does not alter Phase 2 output schema
- existing API routes behave identically

Frontend tests should cover:

- triage submission
- loading state
- result rendering
- enriched remediation rendering
- batch rendering
- API error rendering
- severity badge mapping
- telemetry cards

---

## 19. End-to-End Browser Smoke Test

If Playwright is already available, add a lightweight E2E smoke test:

```text
open dashboard
→ verify API health
→ paste known synthetic incident
→ click Analyze Incident
→ wait for result
→ verify IncidentType
→ verify Severity
→ verify Root Cause
→ verify Evidence
→ navigate to Monitoring
→ verify GPU telemetry cards
```

Do not add a heavy browser framework if it creates unnecessary complexity.

---

## 20. Accessibility & UX

Requirements:

- responsive layout
- readable monospace log viewer
- keyboard-accessible controls
- visible focus states
- sufficient contrast
- loading indicators
- empty states
- clear error states
- copy-to-clipboard actions

Prefer a professional operations-dashboard visual style.

---

## 21. Dashboard Performance

Target:

```text
initial UI load < 2 seconds locally
telemetry refresh without page reload
no frontend memory leak
```

The dashboard must remain responsive during long inference requests.

---

## 22. Phase 13 Documentation

Create:

```text
documentation/phase_13/Phase_13_Report.md
documentation/dashboard.md
```

Update:

```text
README.md
architecture.md
operations.md
api.md
Docker documentation
FINAL_PROJECT_AUDIT.md
final completion report
```

Do not rewrite benchmark numbers.

Phase 13 is a UX/serving layer and must not change scientific evaluation results.

---

## 23. Dashboard Screenshots

Capture portfolio screenshots for:

- Mission Control / Overview
- Incident Triage
- Enriched Runbook Result
- Batch Analysis
- Monitoring
- System Information

Store under:

```text
documentation/assets/dashboard/
```

Use synthetic samples only.

---

## 24. Phase 13 Exit Criteria

Phase 13 is complete when:

- browser dashboard launches successfully
- user can triage a single incident without terminal
- user can request enriched runbook remediation
- user can submit batch incidents
- results are displayed in operator-friendly cards
- evidence is visible and readable
- remediation source is clearly distinguished from model diagnosis
- health/readiness shown
- GPU/live telemetry shown
- monitoring charts function
- runbook browser works
- JSON/CSV export works
- privacy guarantees preserved
- no third-party telemetry added
- compiled frontend integrated into production deployment
- Docker configuration updated
- tests pass
- existing Phase 1–12 tests remain green
- dashboard documentation generated
- portfolio screenshots generated
- Phase 13 report generated

---

## 25. Autonomous Execution Rules

This phase may proceed without waiting for user approval.

Execution order:

```text
inspect current repository
→ choose compatible frontend stack
→ create implementation plan internally
→ implement dashboard
→ integrate API client
→ add monitoring UI
→ add batch UI
→ add runbook UI
→ integrate production build
→ integrate Docker
→ run frontend tests
→ run backend Phase 13 tests
→ run full repository regression suite
→ fix failures automatically
→ generate documentation
→ generate screenshots
→ lock Phase 13
```

Do NOT pause for plan approval.

Do not modify the model, datasets, adapter, or benchmark predictions.

---

## 26. Final Project Declaration

The project should receive its final public completion declaration only after both:

```text
Final Release Consistency Audit = PASS
Phase 13 Dashboard = LOCKED
```

Then update project status to:

# LOCALOPS AI — PROJECT COMPLETE ✅

The final system must be usable through either:

```text
Web Dashboard
```

or:

```text
REST API / CLI
```

so operators are never forced to interact only through terminal commands.
