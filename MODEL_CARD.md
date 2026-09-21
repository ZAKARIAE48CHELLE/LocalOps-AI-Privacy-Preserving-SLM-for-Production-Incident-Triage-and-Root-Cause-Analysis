# Model Card: LocalOps AI Incident Triage SLM (v1.0.0)

## Model Details

- **Model Name**: LocalOps AI Incident Triage SLM
- **Version**: 1.0.0 (Release Candidate 1)
- **Base Architecture**: [Qwen/Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
- **Fine-Tuning Technique**: 4-bit Quantized Low-Rank Adaptation (QLoRA)
  - Quantization: `bitsandbytes` 4-bit NF4 (`bnb_4bit_quant_type="nf4"`, `bnb_4bit_use_double_quant=True`)
  - Target Modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
  - Rank ($r$): 16
  - Alpha ($\alpha$): 32
  - Dropout: 0.05
  - Checkpoint Source: `checkpoint-100` (selected via validation loss minimum of 1.0444)
- **Primary Task**: Autonomous parsing, classification, severity scoring, root cause diagnosis, and verbatim evidence extraction from multi-line raw production logs and stack traces.
- **Output Boundary**: Enforced JSON schema validated strictly by Pydantic v2 (`extra="forbid"`, `evidence: list[str]`).

---

## Intended Use & Target Users

### Primary Intended Use
- **Local Incident Triage**: Real-time analysis of production logs within enterprise on-premises networks, air-gapped VPCs, or edge developer workstations where data confidentiality prevents sending telemetry to third-party proprietary LLM APIs.
- **Root Cause Suggestion**: Accelerating SRE and DevOps incident response workflows by generating hypothesized root causes and suggested immediate actions directly alongside relevant runbooks.
- **Evidence Extraction**: Verbatim quoting of log snippets justifying severity and incident classification.

### Out-of-Scope & Prohibited Uses
- **Autonomous Remediation Execution**: The model is a triage and advisory assistant. It must NEVER be granted direct autonomous write/execution authority on production infrastructure without human-in-the-loop review.
- **Arbitrary Open-Ended Chat**: Not designed for conversational dialogue, coding assistance, or non-log natural language tasks.
- **Medical, Legal, or Safety-Critical Diagnostics**: Strictly scoped to IT infrastructure, microservices, and distributed cloud computing environments.

---

## Dataset Description & Synthetic Caveat

- **Training Corpus**: 4,320 synthetic log records generated across 36 distinct IncidentFamilies, 6 IncidentTypes, and 4 Severities.
- **Validation Corpus**: 1,440 synthetic log records (used exclusively for checkpoint selection).
- **Test Corpus**: 1,440 synthetic log records sealed under template-level structural fingerprint isolation.
- **IMPORTANT SYNTHETIC-DATA CAVEAT**: All training, validation, and testing records were synthetically generated using parameterized log templates and noise models. While structural fingerprints were strictly isolated between train and test splits to prevent verbatim memorization, the model was NOT trained on real-world enterprise log dumps. Generalization to novel, highly corrupted, or proprietary log formats requires domain-specific calibration.

---

## Domain Taxonomy & Incident Ontology

The model classifies incidents into 6 mutually exclusive types and 4 severity levels:

### Incident Types
1. `APPLICATION`: Memory leaks, unhandled exceptions, deadlock, null pointer exceptions, thread starvation.
2. `DATABASE`: Connection pool exhaustion, lock contention, slow query pileups, replication lag, disk quota exhaustion.
3. `INFRASTRUCTURE`: Pod OOMKilled, CPU throttling, disk I/O bottlenecks, node kernel panics, systemd service crashes.
4. `NETWORK`: DNS resolution failures, upstream timeouts, TLS handshake errors, network partition/reset.
5. `SECURITY`: Brute-force authentication floods, expired tokens/certificates, unauthorized role assumption, rate limit breach.
6. `MESSAGING`: Kafka/RabbitMQ consumer lag accumulation, dead letter queue overflows, partition rebalance loops.

### Severity Levels
- `P1_CRITICAL`: Catastrophic customer-facing outage, complete service unavailability, or critical security breach.
- `P2_HIGH`: Severe degradation, major functionality broken, or downstream cascade risk.
- `P3_MEDIUM`: Impaired non-critical feature, localized failure with active redundant failover.
- `P4_LOW`: Transient glitch, background batch warning, or minor cosmetic anomaly.

---

## Canonical Benchmark Metrics & Evaluation (1,440 Sealed Test Records)

All values below are loaded from canonical locked machine-readable artifacts (`reports/evaluation/e4_qlora/metrics.json` and `reports/evaluation/e4_qlora/baseline_comparison.json`):

| Evaluation Metric | E1 (Zero-Shot) | E2 (Structured Prompt) | E3 (Few-Shot) | **LocalOps AI E4 (QLoRA)** | Delta vs Best Baseline |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Pydantic Schema Validity** | 0.00% | 79.86% | 98.33% | **99.10%** (1,427/1,440) | **+0.77%** |
| **IncidentType Accuracy** | 0.00% | 44.72% | 39.37% | **98.47%** | **+53.75%** |
| **IncidentType Macro-F1** | 0.0000 | 0.4679 | 0.3514 | **0.9892** | **+0.5213** |
| **Severity Accuracy** | 0.00% | 18.61% | 29.72% | **99.10%** | **+69.38%** |
| **Severity Macro-F1** | 0.0000 | 0.0895 | 0.2319 | **0.9955** | **+0.7636** |
| **Affected Service Exact Match** | 0.00% | 62.08% | 98.33% | **99.10%** (1,427/1,440) | **+0.77%** |
| **Evidence Verbatim Rate** | 0.00% | 97.69% | 87.11% | **96.75%** (4,282/4,426) | **-0.94%** |
| **Evidence Token F1** | 0.0000 | 0.5098 | 0.7331 | **0.8599** | **+0.1268** |
| **Root Cause Semantic Sim** | 0.0000 | 0.4838 | 0.5193 | **0.5781** | **+0.0588** |
| **Action Semantic Sim** | 0.0000 | 0.3741 | 0.4196 | **0.4755** | **+0.0559** |
| **Mean Offline Latency (bs=16)**| 5.5769s | 1.7257s | 8.1276s | **0.9926s** | **-0.7331s** |
| **Peak VRAM (Batched bs=16)** | 1,585.2 MB | 3,029.8 MB | 5,150.8 MB | **2,620.1 MB** | **-409.7 MB** vs E2 |

---

## Latency Profiles & Hardware Resource Constraints

- **Offline Batched Inference (bs=16)**:
  - Mean Latency: **0.9926s** per sample
  - p50 Latency: **0.9700s**
  - p95 Latency: **1.1659s**
  - Throughput: **122.42 tokens/second**
  - Peak VRAM: **2,620.14 MB**
- **Production Single-Request API**:
  - p50 Latency: **9.12s**
  - p95 Latency: **11.02s**
  - Resident VRAM Footprint: **~1,243.6 MB**
- **Concurrent Load Test (2 concurrent)**:
  - Mean Latency: **11.01s**
  - p50 Latency: **11.02s**
  - Error Rate: **0.0%**
- **Hardware Envelope**: Tested on NVIDIA GeForce RTX 3070 Laptop GPU (8GB VRAM, 85W Max TGP). Mean power draw: **72.5W** (Total energy: 29.01 Wh). Raw sensor reading spike of 752.7W was rejected as sensor/parsing corruption and clamped to the 85.0W hardware ceiling.

---

## Privacy & Security Considerations

- **100% Local Inference**: Zero telemetry egress, zero external API keys required. Operates with `HF_HUB_OFFLINE=1`.
- **Privacy-Safe Ingress**: Middleware strictly redacts raw incident logs from standard access and error logs.
- **Defense in Depth**: Non-root container runtime (`localops:10001`), immutable volumes, bounded input payload sizes (max 32KB).

---

## License & Attribution

- Base Model: Licensed by the Qwen team under the **Qwen Research / Apache 2.0** terms.
- LocalOps AI Implementation & Adapter Weights: Open-source under the **Apache License, Version 2.0**.
