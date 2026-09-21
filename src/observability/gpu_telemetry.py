"""LocalOps AI — GPU Telemetry Provider.

Collects real-time GPU memory, utilization, temperature, and power metrics
using PyTorch CUDA runtime and NVML when available, with graceful degradation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import torch

logger = logging.getLogger("localops.observability.gpu")

_nvml_initialized = False
_pynvml = None

try:
    import pynvml
    pynvml.nvmlInit()
    _pynvml = pynvml
    _nvml_initialized = True
except Exception:
    _nvml_initialized = False


def get_gpu_telemetry() -> Dict[str, Any]:
    """Retrieves current GPU metrics with graceful degradation for CPU environments."""
    telemetry = {
        "cuda_available": torch.cuda.is_available(),
        "device_name": "CPU" if not torch.cuda.is_available() else torch.cuda.get_device_name(0),
        "memory_used_bytes": 0,
        "memory_total_bytes": 0,
        "memory_allocated_bytes": 0,
        "utilization_percent": 0.0,
        "temperature_celsius": 0.0,
        "power_watts": 0.0,
    }

    if not torch.cuda.is_available():
        return telemetry

    # PyTorch memory allocation
    try:
        telemetry["memory_allocated_bytes"] = int(torch.cuda.memory_allocated(0))
        telemetry["memory_used_bytes"] = int(torch.cuda.memory_reserved(0))
        # Total device memory
        props = torch.cuda.get_device_properties(0)
        telemetry["memory_total_bytes"] = int(props.total_memory)
    except Exception as e:
        logger.debug(f"PyTorch CUDA property query failed: {e}")

    # NVML telemetry (temperatures, utilization, power)
    if _nvml_initialized and _pynvml:
        try:
            handle = _pynvml.nvmlDeviceGetHandleByIndex(0)
            mem_info = _pynvml.nvmlDeviceGetMemoryInfo(handle)
            telemetry["memory_used_bytes"] = int(mem_info.used)
            telemetry["memory_total_bytes"] = int(mem_info.total)

            rates = _pynvml.nvmlDeviceGetUtilizationRates(handle)
            telemetry["utilization_percent"] = float(rates.gpu)

            temp = _pynvml.nvmlDeviceGetTemperature(handle, _pynvml.NVML_TEMPERATURE_GPU)
            telemetry["temperature_celsius"] = float(temp)

            power_mw = _pynvml.nvmlDeviceGetPowerUsage(handle)
            telemetry["power_watts"] = round(float(power_mw) / 1000.0, 2)
        except Exception as e:
            logger.debug(f"NVML metric collection failed: {e}")

    return telemetry
