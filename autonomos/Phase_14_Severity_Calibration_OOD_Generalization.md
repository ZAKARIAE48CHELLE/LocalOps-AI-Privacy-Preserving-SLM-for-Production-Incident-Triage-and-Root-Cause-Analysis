# LocalOps AI — Phase 14: Severity Calibration & OOD Generalization

## Objective

Correct the severity generalization weakness exposed by manually authored out-of-template logs, where the model predicted `P3_MEDIUM` for all 12 incidents despite large differences in operational impact.

This phase must improve severity reasoning WITHOUT degrading the already strong performance on IncidentType classification, affected service extraction, structured JSON compliance, evidence grounding, root cause quality, suggested-action quality, production API behavior, RAG retrieval, observability, or dashboard behavior.

Core principle:

> Severity must be derived primarily from operational impact, blast radius, recoverability, security exposure, data integrity, and redundancy — not merely from the technical failure signature.

---

## 1. Problem Statement

A manual generalization test using 12 out-of-template logs showed:

```text
12 / 12 IncidentType classifications correct
12 / 12 affected services correct
12 / 12 successful schema-valid responses
12 / 12 severity predictions = P3_MEDIUM
```

This indicates likely severity-collapse behavior under out-of-distribution inputs.

The problem is NOT necessarily class imbalance.

The model appears to have learned a fallback prior similar to:

```text
when severity impact signals are uncertain
→ predict P3_MEDIUM
```

---

## 2. Phase 14 Strategy

Implement a three-layer correction:

```text
Layer A — Formal Severity Policy
Layer B — Impact Signal Extraction
Layer C — Contrastive Severity Calibration Fine-Tuning
```

Final architecture:

```text
Raw Logs
   ↓
Fine-Tuned SLM
   ├── IncidentType
   ├── Affected Service
   ├── Root Cause
   ├── Suggested Action
   ├── Evidence
   └── Internal Impact Signals
                ↓
        Severity Policy Engine
                ↓
        P1 / P2 / P3 / P4
```

The public API continues returning the existing `LogTriageOutput` schema.

---

## 3. Scope Boundaries

Phase 14 MAY:
- add an internal impact schema
- add a severity policy engine
- create a new severity calibration dataset
- perform continuation QLoRA training
- create a new adapter derived from the current locked adapter
- add new validation and OOD test sets
- update internal API severity handling
- add tests and dashboard severity explanation

Phase 14 MUST NOT:
- modify original Phase 3 train/validation/test files
- overwrite Phase 5 final adapter
- overwrite Phase 6 benchmark artifacts
- tune against the old Phase 6 test split
- fabricate severity labels
- use the 12 manual logs as training data
- change IncidentType taxonomy
- change public severity enum names
- weaken Pydantic validation
- regress API/RAG/observability/dashboard compatibility

---

## 4. Canonical Severity Policy

Create:

```text
configs/severity_policy.yaml
```

### P1_CRITICAL
Use when:
- complete outage of a critical production service
- widespread customer-facing outage
- active security compromise with material exposure
- unrecoverable or actively progressing data loss/corruption
- global or multi-region critical path failure
- no viable workaround
- cascading outage threatening multiple critical systems

### P2_HIGH
Use when:
- major degradation of a critical service
- significant customer population affected
- partial outage with degraded capacity
- substantial backlog threatening SLA/SLO
- high-risk security event without confirmed large-scale compromise
- failover active but resilience reduced
- urgent intervention required

### P3_MEDIUM
Use when:
- localized incident
- limited service degradation
- one replica/worker failed but redundancy remains healthy
- recoverable failure
- limited customer impact
- no current security compromise
- no data loss

### P4_LOW
Use when:
- informational warning
- no user-facing impact
- non-production environment
- cosmetic issue
- low-risk transient event
- self-healed event with no continuing operational impact
- capacity warning below actionable threshold

---

## 5. Internal Impact Schema

Create:

```text
src/severity/schemas.py
```

Suggested enums:
- ServiceAvailability: AVAILABLE, DEGRADED, PARTIAL, DOWN, UNKNOWN
- BlastRadius: SINGLE_INSTANCE, SINGLE_SERVICE, MULTI_SERVICE, MULTI_REGION, GLOBAL, UNKNOWN
- CustomerImpact: NONE, LIMITED, MODERATE, HIGH, SEVERE, UNKNOWN
- RedundancyState: AVAILABLE, DEGRADED, NONE, UNKNOWN
- DataIntegrity: INTACT, AT_RISK, LOST_OR_CORRUPTED, UNKNOWN
- SecurityExposure: NONE, SUSPICIOUS, CONFIRMED, ACTIVE_COMPROMISE, UNKNOWN
- EnvironmentType: PRODUCTION, STAGING, DEVELOPMENT, UNKNOWN

Suggested model:

```python
class ImpactAssessment(BaseModel):
    service_availability: ServiceAvailability
    blast_radius: BlastRadius
    customer_impact: CustomerImpact
    redundancy_state: RedundancyState
    data_integrity: DataIntegrity
    security_exposure: SecurityExposure
    environment: EnvironmentType
    workaround_available: bool | None
    incident_duration_minutes: float | None
    affected_users_estimate: int | None
    impact_evidence: list[str]
```

Rules:
- `extra="forbid"`
- preserve UNKNOWN when evidence is absent
- never invent user counts, outage percentages, hosts, or IPs
- impact evidence should be grounded in raw logs

---

## 6. Severity Policy Engine

Create:

```text
src/severity/policy.py
```

Implement deterministic mapping from `ImpactAssessment` to severity.

Examples:

```text
IF security_exposure == ACTIVE_COMPROMISE
    → P1_CRITICAL

IF data_integrity == LOST_OR_CORRUPTED
   AND environment == PRODUCTION
    → P1_CRITICAL

IF service_availability == DOWN
   AND blast_radius in {MULTI_SERVICE, MULTI_REGION, GLOBAL}
    → P1_CRITICAL

IF service_availability in {DOWN, PARTIAL}
   AND customer_impact in {HIGH, SEVERE}
    → P2_HIGH

IF redundancy_state == DEGRADED
   AND customer_impact in {MODERATE, HIGH}
    → P2_HIGH

IF blast_radius in {SINGLE_INSTANCE, SINGLE_SERVICE}
   AND customer_impact in {NONE, LIMITED, MODERATE}
   AND redundancy_state == AVAILABLE
    → P3_MEDIUM

IF environment in {STAGING, DEVELOPMENT}
   AND customer_impact == NONE
    → P4_LOW
```

If impact evidence is insufficient, do NOT automatically return P3.

Record internally:

```text
severity_basis = INSUFFICIENT_IMPACT_EVIDENCE
```

---

## 7. Severity Reason Codes

Internally support reason codes such as:

```text
COMPLETE_OUTAGE
HIGH_CUSTOMER_IMPACT
NO_REDUNDANCY
ACTIVE_SECURITY_COMPROMISE
DATA_LOSS
NON_PRODUCTION
LIMITED_BLAST_RADIUS
INSUFFICIENT_IMPACT_EVIDENCE
```

Do not expose chain-of-thought.

---

## 8. Severity Calibration Dataset

Create:

```text
data/severity_calibration/train.jsonl
data/severity_calibration/validation.jsonl
data/severity_calibration/test_ood.jsonl
artifacts/phase_14/severity_dataset_manifest.json
```

Target:
- minimum 800 examples
- preferred 1,200–2,000
- approximately balanced P1/P2/P3/P4

Important:
Each technical failure family must appear at multiple severity levels.

---

## 9. Contrastive Severity Examples

Generate paired examples where the technical failure is held constant and only impact changes.

Example: Kubernetes OOMKilled.

### P1
```text
production checkout service
all replicas OOMKilled
100% checkout requests failing
no healthy replicas
multi-region impact
```

### P2
```text
6 of 10 replicas OOMKilled
error rate 35%
remaining capacity saturated
```

### P3
```text
1 of 12 worker replicas OOMKilled
healthy replicas absorbed traffic
no customer-visible errors
```

### P4
```text
staging worker OOMKilled
production unaffected
pod restarted automatically
```

Repeat across:
- DB connection exhaustion
- deadlocks
- replication lag
- storage pressure
- OOMKilled
- CrashLoopBackOff
- DNS failure
- TLS expiry
- brute force
- RBAC denial
- Kafka lag
- poison-pill messages
- broker partition issues
- socket timeouts
- gateway 502/504
- application exceptions

---

## 10. Leakage Prevention

Group split by scenario/template family.

Use fields:

```text
scenario_group_id
template_id
severity_variant
```

Do not allow near-duplicate contrastive variants across train and OOD test.

Add automated overlap checks.

---

## 11. Preserve Manual Logs as OOD Evaluation

The 12 manual logs must remain evaluation-only.

Store:

```text
reports/manual_validation/manual_logs_v1.jsonl
reports/manual_validation/manual_results_before_phase14.json
```

After Phase 14:

```text
reports/manual_validation/manual_results_after_phase14.json
```

This provides a clean before/after comparison.

---

## 12. Fine-Tuning Strategy

Preferred:

```text
continue QLoRA from current selected adapter
```

Create a NEW artifact:

```text
artifacts/phase_14/final_adapter/
```

Never overwrite:

```text
artifacts/phase_5/final_adapter/
```

Use:
- 4-bit NF4
- LoRA
- gradient checkpointing
- assistant-only loss

Target hardware remains RTX 3070 Laptop 8GB VRAM.

Suggested conservative starting range:

```text
learning_rate: 5e-5 to 1e-4
epochs: 1–2
LoRA rank: 16
LoRA alpha: 32
dropout: 0.05
```

Select final values using validation only.

---

## 13. Validation Metrics

Track:
- Severity Accuracy
- Severity Macro-F1
- Per-class precision
- Per-class recall
- Per-class F1
- confusion matrix
- prediction distribution
- severity entropy
- P3 dominance ratio

Define:

```text
P3 dominance ratio =
count(P3 predictions) / total predictions
```

This should not collapse toward 1.0 on a balanced OOD set.

---

## 14. OOD Severity Benchmark

Create a new OOD test:
- minimum 120 records
- preferred 240–400
- balanced P1–P4
- unseen wording
- unseen service names
- unseen numeric values
- same technical family at multiple severities
- ambiguous/incomplete-impact cases
- no training templates

---

## 15. Manual Expected Labels

Create:

```text
reports/manual_validation/manual_expected_labels_v1.json
```

Do not automatically force severity labels.

If insufficient impact context exists:

```text
severity_expected = null
severity_review_status = "INSUFFICIENT_IMPACT_CONTEXT"
```

This is preferable to inventing a definitive severity.

---

## 16. API Integration

Internal flow:

```text
raw_log
↓
model diagnosis
↓
impact extraction
↓
severity policy engine
↓
final LogTriageOutput
```

Keep public API backward-compatible.

Optional telemetry:

```text
severity_source = "POLICY_ENGINE"
severity_policy_version = "1.0"
```

Do not add these to the frozen core result schema unless explicitly versioned.

---

## 17. Dashboard Integration

Update dashboard to show:
- Severity
- Severity source
- Impact-context warning when evidence is insufficient

Tooltip:

```text
Severity is based on operational impact, blast radius,
redundancy, security exposure, and data integrity.
```

Do not expose internal reasoning traces.

---

## 18. Hallucination Reduction

The manual OOD test also revealed unsupported IP/host insertion.

Add checks/objectives for:

```text
hallucinated_ip_rate
hallucinated_hostname_rate
hallucinated_numeric_detail_rate
```

The root cause must not invent:
- IP addresses
- hostnames
- ports
- counts
- services

unless supported by the raw log.

---

## 19. E5 Evaluation

Create:

```text
E5 — Severity-Calibrated QLoRA
```

Evaluate on:
1. Phase 14 OOD test
2. manual OOD v1
3. optionally the already-consumed Phase 6 test for regression only

Do not use the Phase 6 test for checkpoint selection.

Primary model selection must use only Phase 14 validation.

---

## 20. Model Selection Criteria

Primary:

```text
Severity Macro-F1
```

Constraints:

```text
IncidentType Macro-F1 degradation <= 0.01
Pydantic validity >= previous production threshold
Affected-service accuracy degradation <= 0.01
Unsupported-detail rate must not increase
```

Tie-breaker:

```text
lower P3 dominance ratio on balanced validation
```

---

## 21. Tests

Create:

```text
tests/test_severity_phase14.py
```

Required tests:
- severity policy loads
- deterministic P1/P2/P3/P4 mapping
- unknown-context handling
- public schema unchanged
- Phase 3 data unchanged
- manual OOD logs excluded from training
- contrastive groups split safely
- no train/OOD template leakage
- P3 collapse detector
- hallucinated IP detector
- hallucinated hostname detector
- Phase 5 adapter unchanged
- API backward compatibility
- dashboard compatibility

---

## 22. Artifacts

Create:

```text
configs/severity_policy.yaml

src/severity/
├── __init__.py
├── schemas.py
├── policy.py
├── extractor.py
└── evaluator.py

data/severity_calibration/
├── train.jsonl
├── validation.jsonl
└── test_ood.jsonl

artifacts/phase_14/
├── severity_dataset_manifest.json
├── training_manifest.json
├── validation_metrics.json
├── final_adapter/
└── severity_policy_metrics.json

reports/manual_validation/
├── manual_logs_v1.jsonl
├── manual_expected_labels_v1.json
├── manual_results_before_phase14.json
├── manual_results_after_phase14.json
└── manual_ood_comparison_phase14.json

reports/evaluation/e5_severity_calibrated/
├── predictions.jsonl
├── metrics.json
├── confusion_matrices.json
└── error_analysis.json

documentation/phase_14/
├── Phase_14_Report.md
└── Manual_OOD_Comparison.md
```

---

## 23. Exit Criteria

Phase 14 is complete when:
- severity policy implemented
- impact schema implemented
- severity calibration dataset created
- contrastive examples verified
- no train/OOD leakage
- manual test set untouched by training
- Phase 14 adapter trained
- validation-only checkpoint selected
- OOD evaluation completed
- manual before/after comparison completed
- P3 collapse eliminated or materially reduced
- all four severity classes predicted on balanced OOD benchmark
- unsupported IP/host hallucinations reduced
- IncidentType performance preserved
- schema validity preserved
- API backward compatibility preserved
- dashboard remains functional
- full tests pass
- Phase_14_Report.md generated

---

## 24. Success Targets

Preferred targets only; never fabricate values:

```text
Severity Macro-F1 >= 0.85
Each severity recall >= 0.75
P3 dominance ratio between 0.15 and 0.40 on balanced OOD
Pydantic validity >= 0.98
IncidentType Macro-F1 degradation <= 0.01
Unsupported IP/hostname insertion rate < 1%
```

For the 12 manual logs:

```text
predictions must not collapse to one severity class
```

Do not force diversity artificially. Diversity must follow actual impact evidence.

---

## 25. Autonomous Execution Instructions

Proceed without waiting for user approval.

Execution order:

```text
1. Audit current severity behavior
2. Implement canonical policy
3. Implement impact schema
4. Build calibration dataset
5. Run leakage checks
6. Build validation/OOD benchmark
7. Run training smoke test
8. Fine-tune Phase 14 adapter
9. Select checkpoint using validation only
10. Evaluate E5
11. Re-run 12 manual OOD logs
12. Compare before vs after
13. Integrate calibrated severity into API
14. Integrate dashboard severity explanation
15. Run full regression suite
16. Fix failures automatically
17. Generate Phase 14 report
18. Lock Phase 14
```

Do NOT pause for plan approval.

Only stop if hardware failure, corrupted artifacts, missing required files, destructive repository action, or a decision impossible under the locked constraints prevents safe continuation.

---

## 26. Final Scientific Principle

The purpose is NOT to make severity scores merely look better.

The purpose is to teach and enforce:

> A technical failure signature does not uniquely determine incident severity.

Severity must reflect:

```text
impact
blast radius
service criticality
redundancy
security exposure
data integrity
recoverability
environment
```

The corrected system should distinguish:

```text
same failure + low impact   → P3/P4
same failure + major impact → P1/P2
```

without collapsing toward a single default class.

---

# Phase 14 — Severity Calibration & OOD Generalization
