"""
Launch script for the LocalOps AI Baseline Evaluation Mission Control Dashboard.
Runs a lightweight Uvicorn server on port 8080.
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    port = 8080
    host = "0.0.0.0"
    print("=" * 60)
    print(" LocalOps AI — Evaluation Mission Control Dashboard")
    print(f" Local Access:   http://localhost:{port}")
    print(f" Network Access: http://192.168.1.8:{port}")
    print("=" * 60)

    uvicorn.run(
        "src.dashboard.server:app",
        host=host,
        port=port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
