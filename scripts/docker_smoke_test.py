"""LocalOps AI — Docker Smoke Test Script.

Validates that the LocalOps AI service running inside a container responds
correctly to health, readiness, model-info, and triage endpoints.
"""

from __future__ import annotations

import json
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def check_endpoint(url: str, method: str = "GET", payload: dict | None = None, timeout: int = 15) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = Request(url, data=data, headers=headers, method=method)

    try:
        with urlopen(req, timeout=timeout) as response:
            status = response.status
            body = json.loads(response.read().decode("utf-8"))
            return status, body
    except URLError as e:
        if hasattr(e, "code"):
            body = json.loads(e.read().decode("utf-8")) if e.fp else {}
            return e.code, body
        return 0, {"error": str(e)}


def run_smoke_test(base_url: str = "http://localhost:8000"):
    print(f"Executing Docker smoke tests against {base_url}...")

    # 1. Healthcheck
    print("Testing GET /health...")
    status, body = check_endpoint(f"{base_url}/health")
    if status != 200 or body.get("status") != "ok":
        print(f"FAILED: /health returned status {status}: {body}")
        sys.exit(1)
    print("  PASSED: /health is OK.")

    # 2. Readiness
    print("Testing GET /ready...")
    status, body = check_endpoint(f"{base_url}/ready")
    if status != 200 or not body.get("ready"):
        print(f"FAILED: /ready returned status {status}: {body}")
        sys.exit(1)
    print("  PASSED: /ready confirms model is memory-resident.")

    # 3. Model Info
    print("Testing GET /api/v1/model-info...")
    status, body = check_endpoint(f"{base_url}/api/v1/model-info")
    if status != 200:
        print(f"FAILED: /api/v1/model-info returned status {status}")
        sys.exit(1)
    if "artifacts" in body.get("adapter_identifier", "") or "\\" in body.get("adapter_identifier", ""):
        print(f"FAILED: /api/v1/model-info disclosed local paths: {body}")
        sys.exit(1)
    print(f"  PASSED: model={body.get('base_model_id')}, quant={body.get('quantization_mode')}.")

    # 4. Standard Triage
    print("Testing POST /api/v1/triage...")
    log_sample = {
        "raw_log": "[2026-10-12T13:43:42.127Z] [ERROR] [event-processor] Npgsql.NpgsqlException: The connection pool has reached its maximum size and no connections are currently available",
        "request_id": "docker_smoke_001",
    }
    status, body = check_endpoint(f"{base_url}/api/v1/triage", method="POST", payload=log_sample, timeout=30)
    if status != 200:
        print(f"FAILED: /api/v1/triage returned status {status}: {body}")
        sys.exit(1)
    res = body.get("result", {})
    if res.get("incident_type") != "DATABASE" or not res.get("evidence"):
        print(f"FAILED: /api/v1/triage returned unexpected payload: {res}")
        sys.exit(1)
    print(f"  PASSED: incident_type={res.get('incident_type')}, severity={res.get('severity')}.")

    # 5. Enriched RAG Triage
    print("Testing POST /api/v1/triage/enriched...")
    status, body = check_endpoint(f"{base_url}/api/v1/triage/enriched", method="POST", payload=log_sample, timeout=30)
    if status != 200:
        print(f"FAILED: /api/v1/triage/enriched returned status {status}: {body}")
        sys.exit(1)
    remediation = body.get("remediation")
    if not remediation or "postgres" not in remediation.get("runbook_document", "").lower():
        print(f"FAILED: /api/v1/triage/enriched missing valid runbook remediation: {body}")
        sys.exit(1)
    print(f"  PASSED: runbook={remediation.get('runbook_document')}, score={remediation.get('relevance_score')}.")

    print("\nALL DOCKER SMOKE TESTS PASSED SUCCESSFULLY! ✅")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    run_smoke_test(url)
