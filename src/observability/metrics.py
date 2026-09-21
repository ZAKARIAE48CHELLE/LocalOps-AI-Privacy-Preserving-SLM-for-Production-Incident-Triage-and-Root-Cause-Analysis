"""LocalOps AI — Prometheus Metrics Collector & Registry.

Pure-Python, zero-dependency implementation of the Prometheus text exposition
format with low-cardinality label enforcement and live dashboard telemetry.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from src.observability.gpu_telemetry import get_gpu_telemetry

HISTOGRAM_BUCKETS = (0.5, 1.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 30.0)


class MetricsRegistry:
    """Thread-safe Prometheus metrics collector and aggregator."""

    _instance: Optional[MetricsRegistry] = None
    _lock = threading.Lock()

    def __init__(self):
        self.lock = threading.Lock()
        self.start_time = time.time()

        # Counters: (name, tuple(sorted(labels.items()))) -> float
        self.counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)

        # Gauges
        self.inflight_requests: int = 0

        # Histograms: name -> {count, sum, buckets: dict}
        self.histograms: Dict[str, Dict[str, Any]] = {
            "localops_inference_seconds": {
                "count": 0,
                "sum": 0.0,
                "buckets": {b: 0 for b in HISTOGRAM_BUCKETS},
            },
            "localops_rag_retrieval_seconds": {
                "count": 0,
                "sum": 0.0,
                "buckets": {b: 0 for b in (0.01, 0.05, 0.1, 0.25, 0.5, 1.0)},
            },
        }

        # Rolling latency buffer for dashboard p50/p95 (last 200 requests)
        self.recent_latencies: List[float] = []

    @classmethod
    def get_instance(cls) -> MetricsRegistry:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def inc_request(self, endpoint: str, status_code: int):
        with self.lock:
            labels = (("endpoint", endpoint), ("status", str(status_code)))
            self.counters[("localops_requests_total", labels)] += 1.0

    def inc_error(self, endpoint: str, error_code: str):
        with self.lock:
            labels = (("endpoint", endpoint), ("error_code", error_code))
            self.counters[("localops_request_errors_total", labels)] += 1.0

    def inc_prediction(self, incident_type: str, severity: str):
        with self.lock:
            labels = (("incident_type", incident_type), ("severity", severity))
            self.counters[("localops_predictions_total", labels)] += 1.0

    def inc_tokens(self, prompt_tokens: int, generated_tokens: int):
        with self.lock:
            self.counters[("localops_prompt_tokens_total", ())] += float(prompt_tokens)
            self.counters[("localops_inference_tokens_generated_total", ())] += float(generated_tokens)

    def inc_schema_invalid(self):
        with self.lock:
            self.counters[("localops_schema_invalid_total", ())] += 1.0

    def inc_model_output_invalid(self):
        with self.lock:
            self.counters[("localops_model_output_invalid_total", ())] += 1.0

    def inc_rag_request(self, hit: bool):
        with self.lock:
            self.counters[("localops_rag_requests_total", ())] += 1.0
            if not hit:
                self.counters[("localops_rag_no_hit_total", ())] += 1.0

    def observe_inference_duration(self, seconds: float):
        with self.lock:
            h = self.histograms["localops_inference_seconds"]
            h["count"] += 1
            h["sum"] += seconds
            for b in HISTOGRAM_BUCKETS:
                if seconds <= b:
                    h["buckets"][b] += 1

            self.recent_latencies.append(seconds * 1000.0)
            if len(self.recent_latencies) > 200:
                self.recent_latencies.pop(0)

    def observe_rag_duration(self, seconds: float):
        with self.lock:
            h = self.histograms["localops_rag_retrieval_seconds"]
            h["count"] += 1
            h["sum"] += seconds
            for b in h["buckets"]:
                if seconds <= b:
                    h["buckets"][b] += 1

    def generate_prometheus_text(self) -> str:
        """Renders collected metrics into Prometheus text format."""
        lines = []

        # GPU metrics
        gpu_telemetry = get_gpu_telemetry()

        with self.lock:
            # Counters
            lines.append("# HELP localops_requests_total Total HTTP requests processed.")
            lines.append("# TYPE localops_requests_total counter")
            for (name, labels), val in self.counters.items():
                if name == "localops_requests_total":
                    lbl_str = ",".join(f'{k}="{v}"' for k, v in labels)
                    lines.append(f"{name}{{{lbl_str}}} {val}")

            lines.append("# HELP localops_request_errors_total Total request errors by code.")
            lines.append("# TYPE localops_request_errors_total counter")
            for (name, labels), val in self.counters.items():
                if name == "localops_request_errors_total":
                    lbl_str = ",".join(f'{k}="{v}"' for k, v in labels)
                    lines.append(f"{name}{{{lbl_str}}} {val}")

            lines.append("# HELP localops_predictions_total Total predictions by IncidentType and Severity.")
            lines.append("# TYPE localops_predictions_total counter")
            for (name, labels), val in self.counters.items():
                if name == "localops_predictions_total":
                    lbl_str = ",".join(f'{k}="{v}"' for k, v in labels)
                    lines.append(f"{name}{{{lbl_str}}} {val}")

            lines.append("# HELP localops_prompt_tokens_total Total prompt tokens evaluated.")
            lines.append("# TYPE localops_prompt_tokens_total counter")
            lines.append(f"localops_prompt_tokens_total {self.counters.get(('localops_prompt_tokens_total', ()), 0.0)}")

            lines.append("# HELP localops_inference_tokens_generated_total Total tokens generated.")
            lines.append("# TYPE localops_inference_tokens_generated_total counter")
            lines.append(f"localops_inference_tokens_generated_total {self.counters.get(('localops_inference_tokens_generated_total', ()), 0.0)}")

            lines.append("# HELP localops_schema_invalid_total Count of outputs failing strict Pydantic validation.")
            lines.append("# TYPE localops_schema_invalid_total counter")
            lines.append(f"localops_schema_invalid_total {self.counters.get(('localops_schema_invalid_total', ()), 0.0)}")

            lines.append("# HELP localops_rag_requests_total Total RAG enrichment requests.")
            lines.append("# TYPE localops_rag_requests_total counter")
            lines.append(f"localops_rag_requests_total {self.counters.get(('localops_rag_requests_total', ()), 0.0)}")

            lines.append("# HELP localops_rag_no_hit_total Total RAG requests where no relevant runbook was found.")
            lines.append("# TYPE localops_rag_no_hit_total counter")
            lines.append(f"localops_rag_no_hit_total {self.counters.get(('localops_rag_no_hit_total', ()), 0.0)}")

            # Inflight Gauge
            lines.append("# HELP localops_inflight_requests Current requests executing.")
            lines.append("# TYPE localops_inflight_requests gauge")
            lines.append(f"localops_inflight_requests {self.inflight_requests}")

            # Inference Latency Histogram
            h = self.histograms["localops_inference_seconds"]
            lines.append("# HELP localops_inference_seconds Autoregressive inference duration in seconds.")
            lines.append("# TYPE localops_inference_seconds histogram")
            cum = 0
            for b in HISTOGRAM_BUCKETS:
                cum += h["buckets"][b]
                lines.append(f'localops_inference_seconds_bucket{{le="{b}"}} {cum}')
            lines.append(f'localops_inference_seconds_bucket{{le="+Inf"}} {h["count"]}')
            lines.append(f'localops_inference_seconds_sum {round(h["sum"], 4)}')
            lines.append(f'localops_inference_seconds_count {h["count"]}')

        # GPU metrics
        lines.append("# HELP localops_gpu_memory_used_bytes GPU memory used in bytes.")
        lines.append("# TYPE localops_gpu_memory_used_bytes gauge")
        lines.append(f"localops_gpu_memory_used_bytes {gpu_telemetry['memory_used_bytes']}")

        lines.append("# HELP localops_gpu_memory_total_bytes Total GPU memory in bytes.")
        lines.append("# TYPE localops_gpu_memory_total_bytes gauge")
        lines.append(f"localops_gpu_memory_total_bytes {gpu_telemetry['memory_total_bytes']}")

        lines.append("# HELP localops_gpu_utilization_percent GPU compute utilization percentage.")
        lines.append("# TYPE localops_gpu_utilization_percent gauge")
        lines.append(f"localops_gpu_utilization_percent {gpu_telemetry['utilization_percent']}")

        lines.append("# HELP localops_gpu_temperature_celsius GPU temperature in degrees Celsius.")
        lines.append("# TYPE localops_gpu_temperature_celsius gauge")
        lines.append(f"localops_gpu_temperature_celsius {gpu_telemetry['temperature_celsius']}")

        lines.append("# HELP localops_gpu_power_watts GPU power consumption in Watts.")
        lines.append("# TYPE localops_gpu_power_watts gauge")
        lines.append(f"localops_gpu_power_watts {gpu_telemetry['power_watts']}")

        return "\n".join(lines) + "\n"

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Provides consolidated operational telemetry for Mission Control dashboard."""
        import numpy as np

        gpu_telemetry = get_gpu_telemetry()

        with self.lock:
            total_reqs = sum(
                v for (name, _), v in self.counters.items() if name == "localops_requests_total"
            )
            total_errors = sum(
                v for (name, _), v in self.counters.items() if name == "localops_request_errors_total"
            )
            h = self.histograms["localops_inference_seconds"]
            mean_lat = round((h["sum"] / h["count"] * 1000.0), 1) if h["count"] > 0 else 0.0

            p50_lat = round(float(np.percentile(self.recent_latencies, 50)), 1) if self.recent_latencies else 0.0
            p95_lat = round(float(np.percentile(self.recent_latencies, 95)), 1) if self.recent_latencies else 0.0

            predictions_dist: Dict[str, int] = defaultdict(int)
            for (name, labels), count in self.counters.items():
                if name == "localops_predictions_total":
                    for k, v in labels:
                        if k == "incident_type":
                            predictions_dist[v] += int(count)

            uptime_s = round(time.time() - self.start_time, 1)

            return {
                "uptime_seconds": uptime_s,
                "total_requests": int(total_reqs),
                "total_errors": int(total_errors),
                "inflight_requests": self.inflight_requests,
                "schema_invalid_count": int(self.counters.get(("localops_schema_invalid_total", ()), 0)),
                "prompt_tokens_total": int(self.counters.get(("localops_prompt_tokens_total", ()), 0)),
                "generated_tokens_total": int(self.counters.get(("localops_inference_tokens_generated_total", ()), 0)),
                "latency_p50_ms": p50_lat,
                "latency_p95_ms": p95_lat,
                "latency_mean_ms": mean_lat,
                "predictions_by_type": dict(predictions_dist),
                "gpu": gpu_telemetry,
                "rag": {
                    "requests_total": int(self.counters.get(("localops_rag_requests_total", ()), 0)),
                    "no_hit_total": int(self.counters.get(("localops_rag_no_hit_total", ()), 0)),
                },
            }
