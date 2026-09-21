"""LocalOps AI — API Server CLI Runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from src.api.settings import settings


def main():
    parser = argparse.ArgumentParser(description="Run LocalOps AI FastAPI Production Service")
    parser.add_argument("--host", type=str, default=settings.service.host, help="Bind host")
    parser.add_argument("--port", type=int, default=settings.service.port, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for dev")
    parser.add_argument("--log-level", type=str, default=settings.service.log_level.lower(), help="Log level")
    args = parser.parse_args()

    print(f"Starting LocalOps AI Production API on {args.host}:{args.port}...")
    uvicorn.run(
        "src.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
