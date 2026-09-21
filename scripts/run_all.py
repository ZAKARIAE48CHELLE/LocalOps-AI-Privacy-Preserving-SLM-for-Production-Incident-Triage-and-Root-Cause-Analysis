"""LocalOps AI — Master Runner & System Launcher.

Starts the full production stack:
  1. Verifies local GPU, PyTorch, CUDA, and fine-tuned QLoRA adapter
  2. Ensures frontend Operator Dashboard assets are compiled
  3. Launches the FastAPI production server (API + Web Dashboard + Metrics)
  4. Polls health probe and opens the Operator Dashboard in the default browser
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Auto-switch to virtual environment python if available
if os.name == "nt":
    venv_py = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
else:
    venv_py = PROJECT_ROOT / ".venv" / "bin" / "python"

if venv_py.exists():
    try:
        if Path(sys.executable).resolve() != venv_py.resolve():
            sys.exit(subprocess.call([str(venv_py)] + sys.argv))
    except Exception:
        pass


def print_banner(host: str, port: int) -> None:
    display_host = "localhost" if host in ("0.0.0.0", "127.0.0.1") else host
    base_url = f"http://{display_host}:{port}"

    print("\n" + "=" * 72)
    print("           🛡️  LOCALOPS AI — AIR-GAPPED SLM INCIDENT TRIAGE  🛡️")
    print("=" * 72)
    print(f"  Web Operator Dashboard :  {base_url}/")
    print(f"  Dashboard Alternate URL:  {base_url}/dashboard")
    print(f"  Interactive OpenAPI UI :  {base_url}/docs")
    print(f"  Prometheus Metrics     :  {base_url}/metrics")
    print(f"  Live Health Endpoint   :  {base_url}/health")
    print(f"  Model Readiness Check  :  {base_url}/ready")
    print("=" * 72)
    print("  Privacy Guarantee: 100% Local GPU Execution (Zero Cloud Egress)")
    print("  Press Ctrl+C to gracefully terminate.")
    print("=" * 72 + "\n")


def check_and_build_dashboard() -> None:
    dashboard_dir = PROJECT_ROOT / "dashboard"
    dist_dir = dashboard_dir / "dist"
    index_html = dist_dir / "index.html"

    if index_html.exists():
        print("✓ Operator Dashboard static assets verified in dashboard/dist.")
        return

    print("! Compiled dashboard assets not found. Compiling dashboard now...")
    if not dashboard_dir.exists():
        print("! Warning: dashboard directory not found. Skipping frontend compilation.")
        return

    try:
        # Check npm
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        subprocess.run([npm_cmd, "run", "build"], cwd=dashboard_dir, check=True)
        print("✓ Frontend compiled successfully.")
    except Exception as e:
        print(f"! Warning: Frontend compilation failed ({e}). Running in headless API mode.")


def check_hardware_and_environment() -> None:
    print("Checking local runtime environment...")
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"✓ CUDA Accelerator detected: {gpu_name} ({vram_gb:.1f} GB VRAM)")
        else:
            print("! Notice: CUDA not available; running on CPU.")
    except ImportError:
        print("! Warning: torch not imported.")

    adapter_dir = PROJECT_ROOT / "artifacts" / "phase_5" / "final_adapter"
    if adapter_dir.exists():
        print(f"✓ QLoRA Adapter verified: {adapter_dir.name}")
    else:
        print(f"! Notice: Custom adapter path not at default ({adapter_dir}). Using configured path.")

    runbook_index = PROJECT_ROOT / "artifacts" / "phase_8" / "runbooks_index.json"
    if runbook_index.exists():
        print("✓ Operational Runbook Index verified.")


def wait_and_open_browser(url: str, timeout_seconds: float = 45.0) -> None:
    import threading

    def _poll_and_open():
        health_url = f"{url}/health"
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            try:
                with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                    if resp.status == 200:
                        print(f"\n✓ LocalOps AI is live! Opening browser at {url}...")
                        webbrowser.open(url)
                        return
            except Exception:
                pass
            time.sleep(0.5)

    thread = threading.Thread(target=_poll_and_open, daemon=True)
    thread.start()


def main():
    parser = argparse.ArgumentParser(description="LocalOps AI Master Runner")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port number (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn hot-reloading for development")
    args = parser.parse_args()

    # UTF-8 stdout for Windows consoles
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    check_hardware_and_environment()
    check_and_build_dashboard()
    print_banner(args.host, args.port)

    display_host = "localhost" if args.host in ("0.0.0.0", "127.0.0.1") else args.host
    target_url = f"http://{display_host}:{args.port}"

    if not args.no_browser:
        wait_and_open_browser(target_url)

    import uvicorn
    uvicorn.run(
        "src.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
