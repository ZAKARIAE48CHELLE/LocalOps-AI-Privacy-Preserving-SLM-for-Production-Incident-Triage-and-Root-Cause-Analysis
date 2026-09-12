"""
Quick environment verification script for LocalOps AI.
Checks Python version, PyTorch, CUDA, and key library imports.
"""

import sys


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("[*] Verifying LocalOps AI Environment...")
    print(f"Python: {sys.version}")

    try:
        import torch

        print(f"PyTorch Version: {torch.__version__}")
        cuda_ok = torch.cuda.is_available()
        print(f"CUDA Available: {cuda_ok}")
        if cuda_ok:
            print(f"Device Name: {torch.cuda.get_device_name(0)}")
            print(f"Device Capability: {torch.cuda.get_device_capability(0)}")
            print(f"Total VRAM: {round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)} GB")
        else:
            print("WARNING: CUDA is NOT available to PyTorch!")
    except ImportError:
        print("ERROR: torch is not installed!")

    modules = [
        "transformers",
        "accelerate",
        "peft",
        "trl",
        "bitsandbytes",
        "datasets",
        "pydantic",
        "fastapi",
        "uvicorn",
        "pytest",
    ]

    for mod in modules:
        try:
            __import__(mod)
            print(f"  [OK] {mod}")
        except ImportError as e:
            print(f"  [FAIL] {mod} ({e})")


if __name__ == "__main__":
    main()
