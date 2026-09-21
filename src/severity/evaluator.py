"""LocalOps AI — Severity & OOD Evaluator (Phase 14).

Computes comprehensive calibration and generalization metrics:
  - Severity Accuracy & Macro-F1
  - Per-class Precision, Recall, and F1
  - Confusion Matrix & Prediction Distribution
  - P3 Dominance Ratio (detects default-prior collapse)
  - Hallucination Detectors (unsupported IP and hostname insertions)
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple


class SeverityEvaluator:
    """Evaluates severity predictions and hallucination metrics on incident datasets."""

    CLASSES = ["P1_CRITICAL", "P2_HIGH", "P3_MEDIUM", "P4_LOW"]
    IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    HOSTNAME_REGEX = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+(?:internal|cluster\.local|com|net|org|io)\b")

    def evaluate(
        self,
        predictions: List[Dict[str, Any]],
        ground_truth: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluates predictions against ground truth records."""
        assert len(predictions) == len(ground_truth), "Length mismatch between predictions and ground truth"

        total = len(predictions)
        if total == 0:
            return {}

        correct_severity = 0
        correct_type = 0
        correct_service = 0

        y_true_sev: List[str] = []
        y_pred_sev: List[str] = []

        hallucinated_ips = 0
        hallucinated_hosts = 0

        pred_dist: Dict[str, int] = defaultdict(int)

        for pred, gt in zip(predictions, ground_truth):
            p_res = pred.get("result", pred)
            gt_res = gt.get("target", gt)

            p_sev = str(p_res.get("severity", "UNKNOWN"))
            gt_sev = str(gt_res.get("severity", "UNKNOWN"))
            p_type = str(p_res.get("incident_type", "UNKNOWN"))
            gt_type = str(gt_res.get("incident_type", "UNKNOWN"))
            p_svc = str(p_res.get("affected_service", "")).strip().lower()
            gt_svc = str(gt_res.get("affected_service", "")).strip().lower()

            y_true_sev.append(gt_sev)
            y_pred_sev.append(p_sev)
            pred_dist[p_sev] += 1

            if p_sev == gt_sev:
                correct_severity += 1
            if p_type == gt_type:
                correct_type += 1
            if p_svc == gt_svc:
                correct_service += 1

            # Hallucination checks: check if root_cause mentions IPs or hostnames absent from raw_log
            raw_log = pred.get("raw_log", gt.get("raw_log", ""))
            root_cause = p_res.get("root_cause", "")

            raw_ips = set(self.IP_REGEX.findall(raw_log))
            rc_ips = set(self.IP_REGEX.findall(root_cause))
            if rc_ips - raw_ips:
                hallucinated_ips += 1

            raw_hosts = set(self.HOSTNAME_REGEX.findall(raw_log))
            rc_hosts = set(self.HOSTNAME_REGEX.findall(root_cause))
            if rc_hosts - raw_hosts:
                hallucinated_hosts += 1

        # Calculate Per-Class Precision, Recall, F1
        per_class: Dict[str, Dict[str, float]] = {}
        f1_sum = 0.0

        for cls in self.CLASSES:
            tp = sum(1 for yt, yp in zip(y_true_sev, y_pred_sev) if yt == cls and yp == cls)
            fp = sum(1 for yt, yp in zip(y_true_sev, y_pred_sev) if yt != cls and yp == cls)
            fn = sum(1 for yt, yp in zip(y_true_sev, y_pred_sev) if yt == cls and yp != cls)

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

            per_class[cls] = {
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
                "support": sum(1 for yt in y_true_sev if yt == cls),
            }
            f1_sum += f1

        macro_f1 = round(f1_sum / len(self.CLASSES), 4)
        sev_acc = round(correct_severity / total, 4)
        p3_count = pred_dist.get("P3_MEDIUM", 0)
        p3_dominance = round(p3_count / total, 4)

        # Confusion Matrix (4x4)
        matrix: Dict[str, Dict[str, int]] = {
            true_cls: {pred_cls: 0 for pred_cls in self.CLASSES}
            for true_cls in self.CLASSES
        }
        for yt, yp in zip(y_true_sev, y_pred_sev):
            if yt in matrix and yp in matrix[yt]:
                matrix[yt][yp] += 1

        return {
            "total_evaluated": total,
            "severity_accuracy": sev_acc,
            "severity_macro_f1": macro_f1,
            "incident_type_accuracy": round(correct_type / total, 4),
            "affected_service_accuracy": round(correct_service / total, 4),
            "p3_dominance_ratio": p3_dominance,
            "hallucinated_ip_rate": round(hallucinated_ips / total, 4),
            "hallucinated_hostname_rate": round(hallucinated_hosts / total, 4),
            "per_class_metrics": per_class,
            "prediction_distribution": dict(pred_dist),
            "confusion_matrix": matrix,
        }

    def compute_metrics(
        self,
        y_true_sev: List[str],
        y_pred_sev: List[str],
    ) -> Dict[str, Any]:
        """Directly computes severity evaluation metrics on true vs predicted labels."""
        total = len(y_true_sev)
        if total == 0:
            return {}

        correct = sum(1 for yt, yp in zip(y_true_sev, y_pred_sev) if yt == yp)
        sev_acc = round(correct / total, 4)

        pred_dist: Dict[str, int] = defaultdict(int)
        for p in y_pred_sev:
            pred_dist[p] += 1

        per_class: Dict[str, Dict[str, float]] = {}
        f1_sum = 0.0

        for cls in self.CLASSES:
            tp = sum(1 for yt, yp in zip(y_true_sev, y_pred_sev) if yt == cls and yp == cls)
            fp = sum(1 for yt, yp in zip(y_true_sev, y_pred_sev) if yt != cls and yp == cls)
            fn = sum(1 for yt, yp in zip(y_true_sev, y_pred_sev) if yt == cls and yp != cls)

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

            per_class[cls] = {
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
                "support": sum(1 for yt in y_true_sev if yt == cls),
            }
            f1_sum += f1

        macro_f1 = round(f1_sum / len(self.CLASSES), 4)
        p3_count = pred_dist.get("P3_MEDIUM", 0)
        p3_dominance = round(p3_count / total, 4)

        matrix: Dict[str, Dict[str, int]] = {
            true_cls: {pred_cls: 0 for pred_cls in self.CLASSES}
            for true_cls in self.CLASSES
        }
        for yt, yp in zip(y_true_sev, y_pred_sev):
            if yt in matrix and yp in matrix[yt]:
                matrix[yt][yp] += 1

        return {
            "total_evaluated": total,
            "severity_accuracy": sev_acc,
            "severity_macro_f1": macro_f1,
            "p3_dominance_ratio": p3_dominance,
            "per_class_metrics": per_class,
            "prediction_distribution": dict(pred_dist),
            "confusion_matrix": matrix,
        }
