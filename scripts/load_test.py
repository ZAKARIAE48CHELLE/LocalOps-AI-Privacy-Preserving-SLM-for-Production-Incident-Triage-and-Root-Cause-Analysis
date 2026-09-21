"""LocalOps AI — Local Load Testing Script.

Executes bounded load tests across single-stream, concurrent burst, and RAG endpoints,
measuring p50, p95, p99 latency, error rates, and throughput.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from fastapi.testclient import TestClient

from src.api.app import create_app

logger = logging.getLogger("localops.load_test")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

SAMPLE_LOGS = [
    "[ERROR] [event-processor] Npgsql.NpgsqlException: The connection pool has reached its maximum size",
    "[FATAL] [auth-service] CrashLoopBackOff: back-off restarting failed container exit code 1",
    "[ERROR] [kubelet] NodeHasDiskPressure: eviction manager triggering on /var/lib/docker",
    "[ALERT] [ingress-nginx] SSL handshake failed: CERT_HAS_EXPIRED on gateway",
    "[WARN] [stream-processor] CommitFailedException: Offset commit cannot be completed",
]


def run_load_test(total_requests: int = 15, concurrency: int = 2) -> dict:
    logger.info(f"Starting load test: total_requests={total_requests}, concurrency={concurrency}...")

    app = create_app()
    with TestClient(app) as client:
        # Verify readiness
        ready_res = client.get("/ready")
        assert ready_res.status_code == 200, "Service is not ready"

        latencies_ms: List[float] = []
        successes = 0
        failures = 0

        def make_request(idx: int) -> tuple[int, float]:
            raw_log = SAMPLE_LOGS[idx % len(SAMPLE_LOGS)]
            payload = {"raw_log": raw_log, "request_id": f"load_{idx:04d}"}
            endpoint = "/api/v1/triage/enriched" if idx % 2 == 0 else "/api/v1/triage"

            t0 = time.time()
            try:
                res = client.post(endpoint, json=payload, headers={"X-Request-ID": f"load_{idx:04d}"})
                lat = (time.time() - t0) * 1000.0
                return res.status_code, lat
            except Exception as e:
                return 500, (time.time() - t0) * 1000.0

        t_start = time.time()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(make_request, i) for i in range(total_requests)]
            for fut in as_completed(futures):
                code, lat = fut.result()
                latencies_ms.append(lat)
                if code == 200:
                    successes += 1
                else:
                    failures += 1

    total_duration_s = round(time.time() - t_start, 2)
    rps = round(total_requests / total_duration_s, 2)

    p50 = round(float(np.percentile(latencies_ms, 50)), 1)
    p95 = round(float(np.percentile(latencies_ms, 95)), 1)
    p99 = round(float(np.percentile(latencies_ms, 99)), 1)
    mean_lat = round(float(np.mean(latencies_ms)), 1)

    results = {
        "total_requests": total_requests,
        "concurrency": concurrency,
        "total_duration_seconds": total_duration_s,
        "throughput_req_per_sec": rps,
        "successful_requests": successes,
        "failed_requests": failures,
        "error_rate_percent": round((failures / total_requests) * 100.0, 2),
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "latency_p99_ms": p99,
        "latency_mean_ms": mean_lat,
    }

    out_path = Path("reports/load_test_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Load test complete. Results saved to {out_path}")
    logger.info(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    run_load_test(10, concurrency=2)
