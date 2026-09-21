"""
Comprehensive metrics calculation and slice analysis for Phase 4: Baseline Evaluation.
Computes:
1. Primary end-to-end classification metrics (all records evaluated, unparseable counted as incorrect)
2. Secondary conditional metrics (on valid outputs only)
3. Contract & compliance metrics
4. Affected-service exact, normalized, and log-grounded extraction
5. Evidence verbatim grounding and token overlap
6. Local semantic similarity (mean/median)
7. Unsupported-claim and safety heuristics
8. Model-reported confidence analysis
9. Telemetry percentiles (latency, throughput, VRAM)
10. Multi-dimensional subgroup slices across all 8 metadata dimensions
"""

import math
import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from src.evaluation.heuristics import DiagnosticHeuristics
from src.evaluation.schemas import RawPredictionRecord
from src.schemas.enums import IncidentType, Severity


def compute_f1_multiclass(
    y_true: List[str], y_pred: List[str], labels: List[str]
) -> Tuple[float, float, Dict[str, Dict[str, float]]]:
    """
    Computes macro-F1, micro-F1, and per-class precision/recall/F1.
    """
    per_class = {}
    f1_scores = []
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for label in labels:
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == label and yp == label)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != label and yp == label)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == label and yp != label)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[label] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support": sum(1 for yt in y_true if yt == label),
        }
        f1_scores.append(f1)
        total_tp += tp
        total_fp += fp
        total_fn += fn

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    micro_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (2 * micro_prec * micro_rec) / (micro_prec + micro_rec) if (micro_prec + micro_rec) > 0 else 0.0

    return round(macro_f1, 4), round(micro_f1, 4), per_class


def compute_token_f1(pred_text: str, target_text: str) -> Tuple[float, float, float]:
    """Computes precision, recall, and token-level F1 between two strings."""
    pred_tokens = set(pred_text.lower().split())
    target_tokens = set(target_text.lower().split())

    if not pred_tokens and not target_tokens:
        return 1.0, 1.0, 1.0
    if not pred_tokens or not target_tokens:
        return 0.0, 0.0, 0.0

    common = pred_tokens.intersection(target_tokens)
    prec = len(common) / len(pred_tokens)
    rec = len(common) / len(target_tokens)
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    return round(prec, 4), round(rec, 4), round(f1, 4)


def compute_percentiles(values: List[float]) -> Dict[str, float]:
    """Computes mean, min, max, p50, p90, p95 for a list of floats."""
    if not values:
        return {"mean": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0}
    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def p(pct: float) -> float:
        k = (n - 1) * pct
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        return sorted_vals[int(f)] * (c - k) + sorted_vals[int(c)] * (k - f)

    return {
        "mean": round(statistics.mean(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "p50": round(p(0.50), 4),
        "p90": round(p(0.90), 4),
        "p95": round(p(0.95), 4),
    }


class MetricEvaluator:
    """Computes complete metric suite and multidimensional slices from RawPredictionRecord items."""

    @classmethod
    def evaluate_records(
        cls,
        records: List[RawPredictionRecord],
        semantic_evaluator: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates a list of prediction records, returning aggregate metrics and slices.
        """
        total_records = len(records)
        if total_records == 0:
            return {"total_records": 0}

        # 1. Contract & Compliance metrics
        strict_json_valid_count = sum(1 for r in records if r.strict_json_valid)
        extraction_success_count = sum(1 for r in records if r.json_extraction_success)
        pydantic_valid_count = sum(1 for r in records if r.pydantic_valid)

        missing_field_count = sum(1 for r in records if "missing_field" in r.error_types)
        extra_field_count = sum(1 for r in records if "extra_field" in r.error_types)
        invalid_type_count = sum(1 for r in records if "invalid_incident_type" in r.error_types)
        invalid_sev_count = sum(1 for r in records if "invalid_severity" in r.error_types)
        invalid_conf_count = sum(1 for r in records if "invalid_confidence" in r.error_types)
        invalid_ev_count = sum(1 for r in records if "invalid_evidence" in r.error_types)

        contract_metrics = {
            "raw_json_valid_rate": round(strict_json_valid_count / total_records, 4),
            "json_extraction_success_rate": round(extraction_success_count / total_records, 4),
            "pydantic_valid_rate": round(pydantic_valid_count / total_records, 4),
            "missing_field_failure_rate": round(missing_field_count / total_records, 4),
            "extra_field_failure_rate": round(extra_field_count / total_records, 4),
            "invalid_incident_type_rate": round(invalid_type_count / total_records, 4),
            "invalid_severity_rate": round(invalid_sev_count / total_records, 4),
            "invalid_confidence_rate": round(invalid_conf_count / total_records, 4),
            "invalid_evidence_rate": round(invalid_ev_count / total_records, 4),
        }

        # 2. Headline End-to-End Classification (All records, unparseable/invalid = incorrect)
        all_incident_types = [e.value for e in IncidentType]
        all_severities = [e.value for e in Severity]

        e2e_true_types = [r.ground_truth["incident_type"] for r in records]
        e2e_pred_types = [
            r.parsed_output.get("incident_type", "INVALID_OR_MISSING")
            if r.pydantic_valid and r.parsed_output
            else "INVALID_OR_MISSING"
            for r in records
        ]

        e2e_true_sevs = [r.ground_truth["severity"] for r in records]
        e2e_pred_sevs = [
            r.parsed_output.get("severity", "INVALID_OR_MISSING")
            if r.pydantic_valid and r.parsed_output
            else "INVALID_OR_MISSING"
            for r in records
        ]

        e2e_type_acc = round(
            sum(1 for yt, yp in zip(e2e_true_types, e2e_pred_types) if yt == yp) / total_records, 4
        )
        e2e_sev_acc = round(
            sum(1 for yt, yp in zip(e2e_true_sevs, e2e_pred_sevs) if yt == yp) / total_records, 4
        )

        e2e_type_macro_f1, e2e_type_micro_f1, e2e_type_per_class = compute_f1_multiclass(
            e2e_true_types, e2e_pred_types, all_incident_types
        )
        e2e_sev_macro_f1, e2e_sev_micro_f1, e2e_sev_per_class = compute_f1_multiclass(
            e2e_true_sevs, e2e_pred_sevs, all_severities
        )

        primary_metrics = {
            "end_to_end_incident_type_accuracy": e2e_type_acc,
            "end_to_end_incident_type_macro_f1": e2e_type_macro_f1,
            "end_to_end_incident_type_micro_f1": e2e_type_micro_f1,
            "end_to_end_severity_accuracy": e2e_sev_acc,
            "end_to_end_severity_macro_f1": e2e_sev_macro_f1,
            "end_to_end_severity_micro_f1": e2e_sev_micro_f1,
        }

        # 3. Secondary Conditional Metrics (On schema-valid outputs only)
        valid_records = [r for r in records if r.pydantic_valid and r.parsed_output]
        if valid_records:
            cond_true_types = [r.ground_truth["incident_type"] for r in valid_records]
            cond_pred_types = [r.parsed_output["incident_type"] for r in valid_records]
            cond_true_sevs = [r.ground_truth["severity"] for r in valid_records]
            cond_pred_sevs = [r.parsed_output["severity"] for r in valid_records]

            cond_type_acc = round(
                sum(1 for yt, yp in zip(cond_true_types, cond_pred_types) if yt == yp)
                / len(valid_records),
                4,
            )
            cond_sev_acc = round(
                sum(1 for yt, yp in zip(cond_true_sevs, cond_pred_sevs) if yt == yp)
                / len(valid_records),
                4,
            )
            cond_type_macro_f1, _, _ = compute_f1_multiclass(
                cond_true_types, cond_pred_types, all_incident_types
            )
            cond_sev_macro_f1, _, _ = compute_f1_multiclass(
                cond_true_sevs, cond_pred_sevs, all_severities
            )

            secondary_metrics = {
                "valid_record_count": len(valid_records),
                "incident_type_accuracy_on_valid_outputs": cond_type_acc,
                "incident_type_macro_f1_on_valid_outputs": cond_type_macro_f1,
                "severity_accuracy_on_valid_outputs": cond_sev_acc,
                "severity_macro_f1_on_valid_outputs": cond_sev_macro_f1,
            }
        else:
            secondary_metrics = {
                "valid_record_count": 0,
                "incident_type_accuracy_on_valid_outputs": 0.0,
                "incident_type_macro_f1_on_valid_outputs": 0.0,
                "severity_accuracy_on_valid_outputs": 0.0,
                "severity_macro_f1_on_valid_outputs": 0.0,
            }

        # 4. Affected-Service Extraction Metrics
        exact_service_matches = 0
        norm_service_matches = 0
        grounded_service_count = 0

        for r in records:
            gt_service = r.ground_truth.get("affected_service", "")
            raw_log = r.raw_log
            pred_service = ""
            if r.pydantic_valid and r.parsed_output:
                pred_service = r.parsed_output.get("affected_service", "")

            if pred_service and pred_service == gt_service:
                exact_service_matches += 1
            if pred_service and pred_service.strip().casefold() == gt_service.strip().casefold():
                norm_service_matches += 1
            if pred_service and pred_service.strip().casefold() in raw_log.casefold():
                grounded_service_count += 1

        service_metrics = {
            "affected_service_exact_match": round(exact_service_matches / total_records, 4),
            "affected_service_normalized_exact_match": round(
                norm_service_matches / total_records, 4
            ),
            "affected_service_log_grounded_rate": round(
                grounded_service_count / total_records, 4
            ),
        }

        # 5. Evidence Grounding & Extraction
        total_ev_items = 0
        verbatim_ev_items = 0
        ev_f1s = []

        for r in records:
            gt_evidence = r.ground_truth.get("evidence", [])
            gt_ev_joined = " ".join(gt_evidence)
            raw_log = r.raw_log

            pred_ev_list = []
            if r.pydantic_valid and r.parsed_output:
                pred_ev_list = r.parsed_output.get("evidence", [])

            for ev in pred_ev_list:
                total_ev_items += 1
                if ev.strip() in raw_log:
                    verbatim_ev_items += 1

            pred_ev_joined = " ".join(pred_ev_list)
            _, _, f1 = compute_token_f1(pred_ev_joined, gt_ev_joined)
            ev_f1s.append(f1)

        evidence_metrics = {
            "evidence_verbatim_rate": round(
                verbatim_ev_items / total_ev_items if total_ev_items > 0 else 0.0, 4
            ),
            "evidence_token_f1_mean": round(statistics.mean(ev_f1s) if ev_f1s else 0.0, 4),
        }

        # 6. Local Semantic Similarity & Lexical Overlap
        rc_pairs = []
        act_pairs = []
        rc_f1s = []
        # 6. Local Semantic Similarity & Lexical Overlap
        # Evaluated on samples where a comparable prediction exists (valid schema outputs)
        valid_rc_pairs = []
        valid_act_pairs = []
        valid_rc_f1s = []
        valid_act_f1s = []

        for r in records:
            if r.pydantic_valid and r.parsed_output:
                pred_rc = r.parsed_output.get("root_cause", "")
                pred_act = r.parsed_output.get("suggested_action", "")
                gt_rc = r.ground_truth.get("root_cause", "")
                gt_act = r.ground_truth.get("suggested_action", "")

                if pred_rc and gt_rc:
                    valid_rc_pairs.append((pred_rc, gt_rc))
                    _, _, rc_f1 = compute_token_f1(pred_rc, gt_rc)
                    valid_rc_f1s.append(rc_f1)

                if pred_act and gt_act:
                    valid_act_pairs.append((pred_act, gt_act))
                    _, _, act_f1 = compute_token_f1(pred_act, gt_act)
                    valid_act_f1s.append(act_f1)

        if semantic_evaluator is not None and valid_rc_pairs:
            rc_sims = semantic_evaluator.compute_batch_similarities(valid_rc_pairs)
        else:
            rc_sims = valid_rc_f1s

        if semantic_evaluator is not None and valid_act_pairs:
            act_sims = semantic_evaluator.compute_batch_similarities(valid_act_pairs)
        else:
            act_sims = valid_act_f1s

        rc_sim_pct = compute_percentiles(rc_sims)
        act_sim_pct = compute_percentiles(act_sims)

        semantic_metrics = {
            "root_cause_semantic_similarity_mean": rc_sim_pct["mean"],
            "root_cause_semantic_similarity_median": rc_sim_pct["p50"],
            "suggested_action_semantic_similarity_mean": act_sim_pct["mean"],
            "suggested_action_semantic_similarity_median": act_sim_pct["p50"],
            "root_cause_token_f1_mean": round(statistics.mean(valid_rc_f1s) if valid_rc_f1s else 0.0, 4),
            "suggested_action_token_f1_mean": round(statistics.mean(valid_act_f1s) if valid_act_f1s else 0.0, 4),
        }

        # 7. Unsupported Claims & Safety Heuristics
        unsupported_rc_count = 0
        unsupported_claim_count = 0
        compatible_action_count = 0
        unsafe_action_count = 0

        for r in records:
            pred_rc = r.parsed_output.get("root_cause", "") if r.pydantic_valid and r.parsed_output else ""
            pred_act = r.parsed_output.get("suggested_action", "") if r.pydantic_valid and r.parsed_output else ""
            pred_serv = r.parsed_output.get("affected_service", "") if r.pydantic_valid and r.parsed_output else ""
            pred_ev = r.parsed_output.get("evidence", []) if r.pydantic_valid and r.parsed_output else []

            family = r.metadata.get("incident_family", "")
            tech = r.metadata.get("technology", "")
            inc_type = r.metadata.get("incident_type", "")

            is_unsupported_rc, _ = DiagnosticHeuristics.check_unsupported_root_cause(
                r.raw_log, pred_rc, family, r.metadata
            )
            if is_unsupported_rc:
                unsupported_rc_count += 1

            is_unsupported_claim, _ = DiagnosticHeuristics.check_unsupported_claims(
                r.raw_log, pred_serv, pred_ev, pred_rc, family, r.metadata
            )
            if is_unsupported_claim:
                unsupported_claim_count += 1

            is_comp, is_safe, _ = DiagnosticHeuristics.check_action_compatibility_and_safety(
                pred_act, tech, inc_type
            )
            if is_comp:
                compatible_action_count += 1
            if not is_safe:
                unsafe_action_count += 1

        heuristic_metrics = {
            "unsupported_root_cause_rate": round(unsupported_rc_count / total_records, 4),
            "unsupported_claim_rate": round(unsupported_claim_count / total_records, 4),
            "technology_action_compatibility_rate": round(compatible_action_count / total_records, 4),
            "unsafe_or_destructive_action_rate": round(unsafe_action_count / total_records, 4),
        }

        # 8. Model-Reported Confidence Analysis
        reported_confs = [
            r.parsed_output["confidence"]
            for r in valid_records
            if isinstance(r.parsed_output.get("confidence"), (int, float))
        ]
        mean_conf = round(statistics.mean(reported_confs), 4) if reported_confs else 0.0

        conf_corr_type = []
        conf_incorr_type = []
        conf_corr_sev = []
        conf_incorr_sev = []
        conf_by_clarity = defaultdict(list)

        for r in valid_records:
            c = r.parsed_output["confidence"]
            clarity = r.metadata.get("diagnostic_clarity", "UNKNOWN")
            conf_by_clarity[clarity].append(c)

            if r.parsed_output["incident_type"] == r.ground_truth["incident_type"]:
                conf_corr_type.append(c)
            else:
                conf_incorr_type.append(c)

            if r.parsed_output["severity"] == r.ground_truth["severity"]:
                conf_corr_sev.append(c)
            else:
                conf_incorr_sev.append(c)

        confidence_analysis = {
            "mean_model_reported_confidence": mean_conf,
            "confidence_correct_incident_type_mean": round(statistics.mean(conf_corr_type), 4) if conf_corr_type else 0.0,
            "confidence_incorrect_incident_type_mean": round(statistics.mean(conf_incorr_type), 4) if conf_incorr_type else 0.0,
            "confidence_correct_severity_mean": round(statistics.mean(conf_corr_sev), 4) if conf_corr_sev else 0.0,
            "confidence_incorrect_severity_mean": round(statistics.mean(conf_incorr_sev), 4) if conf_incorr_sev else 0.0,
            "confidence_by_diagnostic_clarity": {
                k: round(statistics.mean(v), 4) if v else 0.0 for k, v in conf_by_clarity.items()
            },
        }

        # 9. Performance & Telemetry
        latencies = [r.latency_seconds for r in records if r.latency_seconds > 0]
        tokens_per_sec = [r.tokens_per_second for r in records if r.tokens_per_second > 0]
        prompt_tokens = [r.prompt_tokens for r in records if r.prompt_tokens > 0]
        gen_tokens = [r.generated_tokens for r in records if r.generated_tokens > 0]
        peak_vram = max([r.peak_vram_mb for r in records], default=0.0)

        latency_pct = compute_percentiles(latencies)
        total_runtime = sum(latencies)
        samples_per_min = round((total_records / total_runtime) * 60, 2) if total_runtime > 0 else 0.0

        telemetry = {
            "latency_seconds": latency_pct,
            "tokens_per_second_mean": round(statistics.mean(tokens_per_sec), 2) if tokens_per_sec else 0.0,
            "prompt_tokens": compute_percentiles(prompt_tokens),
            "generated_tokens": compute_percentiles(gen_tokens),
            "peak_vram_mb": round(peak_vram, 2),
            "samples_per_minute": samples_per_min,
        }

        # 10. Multi-dimensional Subgroup Slices
        slice_dimensions = [
            "incident_type",
            "incident_family",
            "severity",
            "technology",
            "runtime",
            "signature_profile",
            "diagnostic_clarity",
            "noise_profile",
        ]

        slices: Dict[str, Dict[str, Any]] = {}
        for dim in slice_dimensions:
            dim_groups = defaultdict(list)
            for r in records:
                val = r.metadata.get(dim) or r.ground_truth.get(dim, "UNKNOWN")
                dim_groups[str(val)].append(r)

            dim_results = {}
            for group_val, group_records in dim_groups.items():
                group_total = len(group_records)
                g_e2e_type_acc = sum(
                    1 for gr in group_records
                    if gr.pydantic_valid and gr.parsed_output and gr.parsed_output.get("incident_type") == gr.ground_truth["incident_type"]
                ) / group_total
                g_e2e_sev_acc = sum(
                    1 for gr in group_records
                    if gr.pydantic_valid and gr.parsed_output and gr.parsed_output.get("severity") == gr.ground_truth["severity"]
                ) / group_total
                g_pydantic_valid = sum(1 for gr in group_records if gr.pydantic_valid) / group_total

                dim_results[group_val] = {
                    "count": group_total,
                    "pydantic_valid_rate": round(g_pydantic_valid, 4),
                    "end_to_end_incident_type_accuracy": round(g_e2e_type_acc, 4),
                    "end_to_end_severity_accuracy": round(g_e2e_sev_acc, 4),
                }
            slices[dim] = dim_results

        return {
            "total_records": total_records,
            "primary_metrics": primary_metrics,
            "secondary_metrics": secondary_metrics,
            "contract_metrics": contract_metrics,
            "affected_service_metrics": service_metrics,
            "evidence_metrics": evidence_metrics,
            "semantic_metrics": semantic_metrics,
            "heuristic_metrics": heuristic_metrics,
            "confidence_analysis": confidence_analysis,
            "telemetry": telemetry,
            "slices": slices,
        }
