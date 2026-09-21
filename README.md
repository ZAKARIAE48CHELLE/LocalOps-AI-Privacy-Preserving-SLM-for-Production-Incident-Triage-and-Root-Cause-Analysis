# LocalOps AI: Privacy-Preserving SLM for Production Incident Triage & Root Cause Analysis

[![CI Pipeline](https://github.com/zakariae48chelle/LocalOps-AI-Privacy-Preserving-SLM-for-Production-Incident-Triage-and-Root-Cause-Analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/zakariae48chelle/LocalOps-AI-Privacy-Preserving-SLM-for-Production-Incident-Triage-and-Root-Cause-Analysis/actions)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](<https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg>)](https://www.python.org/)
[![Model: Qwen2.5-1.5B-Instruct](https://img.shields.io/badge/Model-Qwen2.5--1.5B--Instruct-orange.svg)](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
[![Hardware: RTX 3070 8GB VRAM](https://img.shields.io/badge/Hardware-NVIDIA_RTX_3070_(8GB)-green.svg)](https://www.nvidia.com)
[![Pydantic v2](https://img.shields.io/badge/Schema-Pydantic_v2_(Strict)-purple.svg)](https://docs.pydantic.dev/)

> **A self-hosted, air-gapped 1.5B Small Language Model (SLM) that triages production incidents, diagnoses root causes, quotes verbatim log evidence, and retrieves remediation runbooks on consumer edge GPUs with zero cloud egress.**

---

## 1. Executive Summary & Problem

Modern Site Reliability Engineering (SRE) and DevOps workflows face a strict trade-off:

- **Cloud LLM APIs** offer high reasoning capability but introduce severe compliance, GDPR, and security hazards by egressing proprietary stack traces, database schemas, internal IP addresses, and customer tokens to external servers.
- **Traditional Rule Engines** are rigid, struggle with heterogeneous distributed multi-service logs, and fail when encountering ambiguous or noisy error cascades.

**LocalOps AI** resolves this trade-off by deploying a fine-tuned **1.5B parameter Small Language Model (`Qwen/Qwen2.5-1.5B-Instruct`)** quantized to **4-bit NF4**. It operates entirely within local GPU memory (**~1.24 GB resident VRAM**), enforcing a strict Pydantic v2 validation contract (`extra="forbid"`, `evidence: list[str]`) and retrieving verified operational runbooks via deterministic, source-grounded lexical ranking with **zero cloud dependencies**.

---

## 2. Canonical Headline Benchmark (1,440 Sealed Test Records)

Evaluated on **1,440 sealed, held-out test incident records** using template-level leakage isolation against locked Phase 4 baselines. All numbers are loaded directly from canonical machine-readable artifacts (`reports/evaluation/e4_qlora/metrics.json` and `reports/evaluation/e4_qlora/baseline_comparison.json`):

```
+------------------------------------+---------------+-----------------------+---------------+--------------------+-------------------+
| Metric                             | E1: Zero-Shot | E2: Structured Prompt | E3: Few-Shot  | E4: QLoRA (Ours)   | Delta vs Best BL  |
+------------------------------------+---------------+-----------------------+---------------+--------------------+-------------------+
| Pydantic Schema Validity           | 0.00%         | 79.86%                | 98.33%        | 99.10% (1,427/1,440| +0.77%            |
| IncidentType Accuracy              | 0.00%         | 44.72%                | 39.37%        | 98.47%             | +53.75%           |
| IncidentType Macro-F1              | 0.0000        | 0.4679                | 0.3514        | 0.9892             | +0.5213           |
| Severity Accuracy                  | 0.00%         | 18.61%                | 29.72%        | 99.10%             | +69.38%           |
| Severity Macro-F1                  | 0.0000        | 0.0895                | 0.2319        | 0.9955             | +0.7636           |
| Affected Service Exact Match       | 0.00%         | 62.08%                | 98.33%        | 99.10% (1,427/1,440| +0.77%            |
| Evidence Verbatim Rate             | 0.00%         | 97.69%                | 87.11%        | 96.75% (4,282/4,426| -0.94%            |
| Evidence Token F1                  | 0.0000        | 0.5098                | 0.7331        | 0.8599             | +0.1268           |
| Root Cause Semantic Sim (Mean)     | 0.0000        | 0.4838                | 0.5193        | 0.5781             | +0.0588           |
| Suggested Action Semantic Sim(Mean)| 0.0000        | 0.3741                | 0.4196        | 0.4755             | +0.0559           |
| Mean Offline Latency (bs=16)       | 5.5769s       | 1.7257s               | 8.1276s       | 0.9926s            | -0.7331s vs E2    |
| Peak VRAM (Batched bs=16)          | 1,585.2 MB    | 3,029.8 MB            | 5,150.8 MB    | 2,620.1 MB         | -409.7 MB vs E2   |
+------------------------------------+---------------+-----------------------+---------------+--------------------+-------------------+
```

---

## 3. Explicit Latency & Hardware Profiles

We explicitly distinguish between offline evaluation throughput and production serving latencies:

1. **Phase 6 Offline Batched Benchmark (bs=16)**:
   - Evaluated over all 1,440 test records: Mean latency **0.9926s** per sample, p50 **0.9700s**, p95 **1.1659s**, Throughput **122.42 tokens/sec**, Peak VRAM **2,620.14 MB**.
2. **Phase 7 Production Single-Request API Latency**:
   - Real-time HTTP triage via FastAPI: **9.12s** p50, **11.02s** p95 on physical NVIDIA RTX 3070 Laptop GPU (~1,243.6 MB resident VRAM).
3. **Phase 11 Concurrent Load-Test Latency (2 concurrent requests)**:
   - Mean latency **11.01s**, p50 **11.02s**, p95 **12.34s** with **0.0% error rate**.
4. **Energy & Power Telemetry**:
   - Average operational power: **72.5 W** (Total energy consumed across 1,440 test samples: 29.01 Wh / 0.029 kWh).
   - An unphysical sensor spike reading of 752.7W was rejected as hardware/driver parsing corruption and clamped to the 85.0W hardware TGP ceiling for the RTX 3070 Laptop GPU.

---

## 4. System Architecture

```mermaid
flowchart TB
    subgraph Ingress["Client / Telemetry Ingress"]
        C[Log Ingestion / Alert Webhook] --> M1[Privacy Middleware<br/>Zero Raw Payloads in Access Logs]
    end

    subgraph Service["FastAPI Microservice (Port 8000)"]
        M1 --> EP1["/api/v1/triage"]
        M1 --> EP2["/api/v1/triage/enriched"]
        M1 --> OBS["/metrics & /api/v1/telemetry/live"]

        subgraph Engine["Inference & RAG Stack"]
            IS[InferenceService]
            MM[ModelManager Singleton<br/>Warmup + Lifecycle]
            SLM[4-bit NF4 Qwen 2.5 1.5B<br/>LoRA Adapter r=16, a=32<br/>~1.24 GB VRAM Resident]
            PYD{Pydantic v2 Boundary<br/>extra='forbid', evidence: list[str]}
            RAG[RunbookRetriever<br/>Weighted Lexical Ranker]
            RB[(10 Standardized<br/>Runbooks)]
        end

        EP1 --> IS
        EP2 --> IS
        EP2 --> RAG
        IS --> MM --> SLM
        SLM --> PYD
        RAG <--> RB
    end

    subgraph Egress["Structured Diagnostic Output"]
        PYD --> OUT[IncidentType: DATABASE<br/>Severity: P2_HIGH<br/>Root Cause & Verbatim Evidence]
        RAG --> REM[Remediation Steps & Escalation]
    end
```

For comprehensive specifications covering training, inference, RAG, production serving, and CI release pipelines, see [documentation/architecture.md](documentation/architecture.md).

---

## 5. Fine-Tuning & Checkpoint Selection

- **Base Model**: `Qwen/Qwen2.5-1.5B-Instruct`
- **Technique**: 4-bit Quantized Low-Rank Adaptation (QLoRA via `bitsandbytes` NF4 double quantization).
- **Target Modules**: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj` ($r=16, \alpha=32$).
- **Checkpoint Selection Rule**: Predeclared validation-loss minimum. Validation loss reached its global minimum at `checkpoint-100` (`eval_loss = 1.0444`) and rose progressively toward ~1.56 at step 810 due to synthetic template overfit. `checkpoint-100` was officially selected and locked as `artifacts/phase_5/final_adapter/`.

![Training & Validation Loss Curves](documentation/assets/loss_curves.png)

---

## 6. Synthetic Dataset Methodology

- **Volume**: 7,200 total records (4,320 Train / 1,440 Validation / 1,440 Held-Out Test).
- **Taxonomy**: 36 Incident Families, 6 Incident Types (`APPLICATION`, `DATABASE`, `INFRASTRUCTURE`, `NETWORK`, `SECURITY`, `MESSAGING`), 4 Severities (`P1_CRITICAL` to `P4_LOW`).
- **Leakage Controls**: Template-level structural fingerprint isolation. Held-out test templates never appeared in training or validation splits.
- **Realistic Noise**: Injected background heartbeats, concurrent healthchecks (`NONE`, `LIGHT`, `MEDIUM`), and varying clarity (`EXPLICIT`, `CLEAR`, `AMBIGUOUS`).
- For full details, see [DATASET_CARD.md](DATASET_CARD.md).

---

## 7. Deterministic Runbook Retrieval (RAG)

To prevent generative hallucinations during remediation, LocalOps AI decouples **diagnostic reasoning** (handled by the SLM) from **remediation procedures** (retrieved deterministically from verified runbooks):

- **Corpus**: 10 operational markdown runbooks covering all 6 incident types (40 indexed chunks) under `runbooks/`.
- **Retrieval Engine**: Deterministic weighted lexical matching across categorical incident-type affinity, affected service matching, and keyword-signature overlap. (No dense embedding models required).
- **Performance**:
  - **Recall@1**: 85.0%
  - **Recall@3**: 100.0%
  - **Mean Reciprocal Rank (MRR)**: 0.9167
  - **Retrieval Latency**: 4.38 ms p50, 8.12 ms p95.

---

## 8. API Reference

| Endpoint                    |  Method  | Description                                                                 |
| :-------------------------- | :------: | :-------------------------------------------------------------------------- |
| `/health`                 | `GET` | Process liveness probe                                                      |
| `/ready`                  | `GET` | Model residency & CUDA warmup readiness probe                               |
| `/api/v1/model-info`      | `GET` | Active model, adapter, and quantization configuration                       |
| `/api/v1/triage`          | `POST` | Core triage: classification, severity, root cause, evidence (`list[str]`) |
| `/api/v1/triage/enriched` | `POST` | Triage output + grounded runbook remediation steps                          |
| `/api/v1/triage/batch`    | `POST` | Batched incident triage (up to 16 items)                                    |
| `/metrics`                | `GET` | Prometheus metrics exposition                                               |
| `/api/v1/telemetry/live`  | `GET` | Real-time JSON telemetry for Mission Control UI                             |

For detailed schemas and request examples, see [documentation/api.md](documentation/api.md).

---

## 9. Quickstart & Guided Demo

### Option A: 1-Click Master Launch (Web Dashboard + REST API)

Run the master launcher to verify the GPU, check frontend assets, launch the server, and automatically open the Operator Dashboard in your browser:

```bash
# Windows (Double-click or run from PowerShell/CMD):
run.bat

# Or directly with Python:
python scripts/run_all.py
```

Once running, access:
- **Operator Web Dashboard**: [`http://localhost:8000/`](http://localhost:8000/) or [`http://localhost:8000/dashboard`](http://localhost:8000/dashboard)
- **Interactive Swagger Docs**: [`http://localhost:8000/docs`](http://localhost:8000/docs)
- **Prometheus Metrics**: [`http://localhost:8000/metrics`](http://localhost:8000/metrics)

### Option B: Interactive CLI Demo (30 Seconds)

Experience end-to-end incident triage across 6 curated production scenarios without opening a browser:

```bash
python scripts/demo_localops.py
```

Or submit via CLI / curl:

```bash
curl -X POST http://localhost:8000/api/v1/triage \
  -H "Content-Type: application/json" \
  -d '{
    "raw_log": "2026-09-18 ERROR [auth-service] ConnectionTimeoutException: Connection pool exhausted after 30000ms. Active: 50, Idle: 0",
    "request_id": "test-inc-01"
  }'
```

See [documentation/dashboard.md](documentation/dashboard.md) for the complete Web UI operator guide.

### Option C: Docker Deployment

```bash
docker build -t localops-ai:1.0.0 .
docker compose up -d
```

---

## 10. Privacy, Security & Compliance

- **Zero Data Egress**: Operates 100% locally with `HF_HUB_OFFLINE=1`. No proprietary logs, tokens, or traces leave your perimeter.
- **Privacy Logging Middleware**: Automatically intercepts and strips `raw_log` payloads and generated text from access logs. Only non-sensitive request IDs, token counts, and execution latencies are logged.
- **Non-Root Execution**: Container runs under unprivileged UID `10001` (`localops`).
- **Memory Safety**: Strict input boundary caps (`max_input_characters = 32768`) prevent memory exhaustion denial-of-service attacks.

---

## 11. Reproducibility & Release Manifest

All benchmark results and baseline comparisons can be reproduced without re-running training loops:

```bash
# 1. Verify release artifact checksums (SHA-256)
python scripts/verify_release.py

# 2. Verify serving parity on live GPU
python scripts/serving_parity_benchmark.py

# 3. Run full test suite (159 tests)
pytest tests/ -v
```

See [documentation/reproducibility.md](documentation/reproducibility.md) and [artifacts/release/release_manifest.json](artifacts/release/release_manifest.json).

---

## 12. Known Limitations & Technical Honesty

1. **Synthetic Training Data**: Trained on 7,200 synthetic incident templates. While split leakage was strictly controlled via structural template isolation, enterprise deployments require domain-specific calibration on internal logs.
2. **Laptop GPU Thermal Headroom**: Sustained batched inferences on mobile GPUs should maintain batch concurrency limits to prevent thermal throttling.
3. **Advisory Scope**: LocalOps AI is an advisory diagnostic system. It does not perform autonomous write actions against production infrastructure.

---

## 13. License

Distributed under the **Apache License, Version 2.0**. See `LICENSE` for more information.
