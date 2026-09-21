# LocalOps AI — Phase 6 Final Metrics Integrity & Lock

## Objective

Phase 6 inference has already been completed on all 1,440 held-out test records using:

- Base model: `Qwen/Qwen2.5-1.5B-Instruct`
- Official adapter: `artifacts/phase_5/final_adapter/`
- Source checkpoint: Phase 5 `checkpoint-100`
- Deterministic greedy decoding

Do **not** rerun model inference unless the existing prediction artifact is corrupt or incomplete. This phase is a **post-processing, metrics-integrity, and reporting correction** only.

Do not begin Phase 7 until this phase is locked.

## 1. Preserve E4 Predictions

Use the existing:

```text
reports/evaluation/e4_qlora/predictions.jsonl
```

Verify before any analytics work:

- exactly 1,440 rows
- exactly 1,440 unique `incident_id` values
- zero duplicates
- zero missing test incident IDs
- raw model outputs are preserved
- test checksum matches the Phase 3 locked checksum

If any of these fail, stop and document the failure before doing analytics.

## 2. Restore Locked Phase 4 Baselines

Load Phase 4 baselines directly from the locked machine-readable Phase 4 artifacts. Do not hard-code or manually reinterpret the values.

Known locked headline values include:

```text
E2 IncidentType Accuracy = 0.4472
E2 IncidentType Macro-F1 = 0.4679
E2 Severity Accuracy = 0.1861
E2 Severity Macro-F1 = 0.0895

E3 IncidentType Accuracy = 0.3937
E3 IncidentType Macro-F1 = 0.3514
E3 Severity Accuracy = 0.2972
E3 Severity Macro-F1 = 0.2319
```

Load corrected Phase 4 semantic metrics from the final Phase 4 artifact as well. Do not reuse stale pre-fix semantic values.

Add a regression assertion that Phase 6 reporting never changes locked Phase 4 metrics.

## 3. Recompute E4 Headline Metrics from Predictions

From the same 1,440 E4 prediction rows, recompute:

### Contract

- `raw_json_valid_rate`
- `json_extraction_success_rate`
- `pydantic_valid_rate`
- `missing_field_failure_rate`
- `extra_field_failure_rate`
- `invalid_incident_type_rate`
- `invalid_severity_rate`
- `invalid_confidence_rate`
- `invalid_evidence_rate`

### IncidentType

- accuracy
- macro precision
- macro recall
- macro F1
- micro F1
- per-class precision/recall/F1

### Severity

- accuracy
- macro precision
- macro recall
- macro F1
- micro F1
- per-class precision/recall/F1

All end-to-end metrics must include invalid/unparseable predictions as incorrect.

## 4. Confusion Matrix Consistency

Use end-to-end matrices including invalid predictions:

- IncidentType: 7×7 with `INVALID_OR_MISSING`
- Severity: 5×5 with `INVALID_OR_MISSING`

Programmatically assert:

```text
IncidentType matrix sum = 1440
Severity matrix sum = 1440
```

Also assert:

```text
IncidentType correct count = valid-class diagonal sum
Severity correct count = valid-class diagonal sum
```

Metrics must be generated from the same prediction set and matrix counts.

## 5. Fix Affected-Service Metrics

Recompute directly from prediction rows:

- `affected_service_exact_match`
- `affected_service_normalized_exact_match`
- `affected_service_log_grounded_rate`

Normalization is limited to:

- `strip()`
- `casefold()`

Do not use fuzzy matching as the main metric.

Resolve the prior contradiction where the report showed `0.00%` exact match while error analysis reported zero mismatches.

Add a test verifying aggregate affected-service metrics equal the prediction-level truth table.

## 6. Fix Evidence Grounding Metrics

Recompute:

- `evidence_verbatim_rate`
- `record_level_full_evidence_grounding_rate`
- `evidence_token_precision`
- `evidence_token_recall`
- `evidence_token_f1`
- `ungrounded_evidence_count`

Definitions:

### `evidence_verbatim_rate`

Fraction of individual predicted evidence strings appearing verbatim in the corresponding raw log.

### `record_level_full_evidence_grounding_rate`

Fraction of records where every predicted evidence item is grounded in the raw log.

Ensure these values agree with `error_analysis.json`.

## 7. Semantic Metrics

Use the corrected Phase 4 semantic implementation:

- model: `sentence-transformers/all-MiniLM-L6-v2`
- attention-mask-aware mean pooling
- L2 normalization
- cosine similarity

Recompute E4:

- `root_cause_semantic_similarity_mean`
- `root_cause_semantic_similarity_median`
- `root_cause_token_f1_mean`
- `suggested_action_semantic_similarity_mean`
- `suggested_action_semantic_similarity_median`
- `suggested_action_token_f1_mean`

Compare E4 only against the corrected locked Phase 4 semantic values.

## 8. Unsupported-Claim & Action Safety Metrics

Recompute using the same Phase 4 heuristic implementation:

- `unsupported_root_cause_rate`
- `unsupported_claim_rate`
- `technology_action_compatibility_rate`
- `unsafe_or_destructive_action_rate`

Document heuristic limitations explicitly. These are lower-bound proxy indicators, not complete hallucination detectors.

## 9. Statistical Confidence

Use deterministic paired bootstrap on the same common test-record indices.

Seed: `42`

Recommended resamples: `1000` or more if runtime remains reasonable.

Compute 95% paired bootstrap confidence intervals for:

- E4 IncidentType accuracy
- E4 IncidentType Macro-F1
- E4 Severity accuracy
- E4 Severity Macro-F1
- E4 − E2 IncidentType accuracy
- E4 − E2 IncidentType Macro-F1
- E4 − E3 Severity accuracy
- E4 − E3 Severity Macro-F1

Do not write `p < 0.01` unless an actual p-value procedure is implemented and saved.

Preferred wording when only CIs are computed:

> The paired 95% bootstrap confidence interval for the improvement excludes zero.

## 10. Validate Telemetry

Recompute telemetry summaries from raw E4 telemetry:

- mean latency
- p50 latency
- p90 latency
- p95 latency
- mean tokens/sec
- prompt-token distribution
- generated-token distribution
- peak VRAM
- samples/minute

### Power/Energy

Validate raw NVML power samples.

Reject only clearly corrupt/out-of-domain sensor values using a documented deterministic rule. Do not silently clip valid data.

Report:

- `average_power_w`
- `validated_peak_power_w`
- `energy_Wh`
- `energy_kWh`

Any carbon intensity or electricity price is an **assumption**, not a measured property.

## 11. Generalization Gap

Compare Phase 5 validation-slice metrics with the full E4 test metrics.

Report honestly:

- schema validity gap
- IncidentType Macro-F1 gap
- Severity Macro-F1 gap
- MESSAGING recall gap
- P4_LOW recall gap

Do not describe the 48-sample validation slice as equivalent to the full held-out test benchmark.

## 12. Slice Analysis

Use actual Phase 3 metadata values:

### Diagnostic clarity

- `EXPLICIT`
- `CLEAR`
- `AMBIGUOUS`

### Noise profile

- `NONE`
- `LIGHT`
- `MEDIUM`

Also analyze:

- IncidentType
- IncidentFamily
- Severity
- technology
- runtime
- signature_profile

Avoid over-interpreting very small slices.

## 13. Final Phase 6 Artifacts

Regenerate analytics only:

```text
reports/evaluation/e4_qlora/metrics.json
reports/evaluation/e4_qlora/confusion_matrices.json
reports/evaluation/e4_qlora/bootstrap_confidence_intervals.json
reports/evaluation/e4_qlora/error_analysis.json
reports/evaluation/e4_qlora/baseline_comparison.json
reports/evaluation/e4_qlora/human_review_samples.json
reports/evaluation/e4_qlora/execution_manifest.json
documentation/phase_6/Phase_6_Report.md
```

Do not overwrite raw predictions.

## 14. Phase 6 Tests

Add/update tests for:

- prediction count = 1,440
- zero duplicate IDs
- no missing IDs
- baseline metric immutability
- confusion-matrix sums
- aggregate metric consistency
- affected-service metric consistency
- evidence grounding consistency
- semantic metric parity with Phase 4 implementation
- paired bootstrap reproducibility
- raw output preservation
- telemetry outlier-handling determinism

Then run the full repository test suite.

## 15. Phase 6 Exit Criteria

Phase 6 can be marked `LOCKED` only if:

- 1,440 E4 predictions are intact
- all headline metrics are derived from the same prediction set
- Phase 4 baseline values match locked artifacts exactly
- affected-service metrics are internally consistent
- evidence-grounding metrics are internally consistent
- semantic metrics use corrected implementation
- confusion matrices sum to 1,440
- bootstrap comparison is paired and reproducible
- telemetry is physically plausible or documented when filtered
- full regression suite passes
- Phase 6 report contains no contradictory claims

## 16. Scope Boundary

Do not retrain.
Do not change the adapter.
Do not alter the E4 prompt or decoding configuration.
Do not begin Phase 7 until this phase is locked.
