# LocalOps AI: Privacy-Preserving SLM for Production Incident Triage and Root Cause Analysis

A production-grade, local, privacy-preserving SLM system designed to triage raw production logs, predict incident category & severity, infer root causes, and provide runbook-grounded remediation recommendations on edge/local GPU infrastructure without transmitting sensitive telemetry data to external cloud APIs.

---

## Phase 1 Status: COMPLETED

### Baseline Benchmark Results (`Qwen/Qwen2.5-1.5B-Instruct`)
- **Hardware**: NVIDIA GeForce RTX 3070 Laptop GPU (8.0 GB VRAM, Compute Capability 8.6)
- **Quantization**: 4-bit NF4 (Double Quantization enabled via `bitsandbytes`)
- **VRAM Usage**: 1,099.9 MB post-load / 1,149.7 MB peak during inference (~1.15 GB total)
- **Generation Latency**: 13.09 seconds (175 generated tokens)
- **Throughput**: 13.37 tokens/second
- **Telemetry Report**: `reports/smoke_test_baseline.json`

---

## Quickstart

### 1. Environment Setup
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run verification suite
python scripts/verify_environment.py
pytest -v
```

### 2. Run Local Baseline Inference
```powershell
python scripts/smoke_test_model.py
```