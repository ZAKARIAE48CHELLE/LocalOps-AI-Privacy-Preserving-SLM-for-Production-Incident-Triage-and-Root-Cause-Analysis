"""
Basic environment and ML stack tests for Phase 1.
"""

import torch


def test_cuda_available():
    assert torch.cuda.is_available(), "CUDA must be available for LocalOps AI"


def test_device_properties():
    assert torch.cuda.device_count() >= 1
    device_name = torch.cuda.get_device_name(0)
    assert "RTX" in device_name or "GeForce" in device_name


def test_ml_imports():
    import accelerate
    import bitsandbytes
    import datasets
    import fastapi
    import peft
    import pydantic
    import transformers
    import trl
    import uvicorn

    assert transformers.__version__ is not None
    assert bitsandbytes.__version__ is not None
