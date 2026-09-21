"""LocalOps AI — Phase 7 API Micro-Benchmark."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch
from fastapi.testclient import TestClient

from src.api.app import create_app


def run_benchmark(num_samples: int = 10):
    val_path = Path("data/generated/validation.jsonl")
    if not val_path.exists():
        print(f"Validation dataset {val_path} not found.")
        return

    records = []
    with open(val_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
            if len(records) >= num_samples:
                break

    print(f"Loaded {len(records)} validation samples for API micro-benchmark.")

    start_init = time.time()
    app = create_app()
    init_time_s = round(time.time() - start_init, 2)
    print(f"App creation & model initialization time: {init_time_s}s")

    latencies_ms: List[float] = []
    tokens_generated: List[int] = []

    with TestClient(app) as client:
        # Check readiness
        ready_res = client.get("/ready")
        assert ready_res.status_code == 200, "Service is not ready"

        print("Executing benchmark requests...")
        for i, rec in enumerate(records):
            req_payload = {
                "raw_log": rec["raw_log"],
                "request_id": f"bench_{i:03d}",
            }
            t0 = time.time()
            res = client.post("/api/v1/triage", json=req_payload)
            t1 = time.time()
            assert res.status_code == 200, f"Failed at sample {i}: {res.text}"
            data = res.json()
            latencies_ms.append((t1 - t0) * 1000.0)
            tokens_generated.append(data["inference"]["generated_tokens"])
            print(f"Sample {i+1}/{len(records)}: latency={latencies_ms[-1]:.1f}ms, tokens={tokens_generated[-1]}")

    vram_mb = 0.0
    if torch.cuda.is_available():
        vram_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 1)

    p50 = round(float(np.percentile(latencies_ms, 50)), 1)
    p95 = round(float(np.percentile(latencies_ms, 95)), 1)
    avg_lat = round(float(np.mean(latencies_ms)), 1)
    req_per_min = round(60000.0 / avg_lat, 1)

    benchmark_results = {
        "num_samples": len(records),
        "initialization_time_seconds": init_time_s,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "mean_latency_ms": avg_lat,
        "estimated_rpm_single_stream": req_per_min,
        "peak_vram_mb": vram_mb,
    }

    out_path = Path("reports/api_benchmark.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_results, f, indent=2)

    print("\nAPI Micro-Benchmark Results:")
    print(json.dumps(benchmark_results, indent=2))


if __name__ == "__main__":
    run_benchmark(10)
