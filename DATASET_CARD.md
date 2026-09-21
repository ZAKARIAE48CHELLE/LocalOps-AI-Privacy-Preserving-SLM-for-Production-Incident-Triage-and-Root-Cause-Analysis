# Dataset Card: LocalOps AI Production Incident Triage Corpus (v1.0.0)

## Dataset Summary

The **LocalOps AI Production Incident Triage Corpus** is a curated, high-entropy synthetic benchmark dataset comprising **7,200 incident records** designed to evaluate and fine-tune Small Language Models (SLMs) on IT infrastructure incident triage, severity estimation, root cause analysis, and evidence extraction.

- **Total Records**: 7,200
- **Splits**:
  - `train.jsonl`: 4,320 records (60%)
  - `val.jsonl`: 1,440 records (20%) — used strictly for checkpoint selection
  - `test.jsonl`: 1,440 records (20%) — held-out, sealed benchmark split
- **Taxonomy Dimensions**:
  - 36 Incident Families
  - 6 Incident Types (`APPLICATION`, `DATABASE`, `INFRASTRUCTURE`, `NETWORK`, `SECURITY`, `MESSAGING`)
  - 4 Severity Classes (`P1_CRITICAL`, `P2_HIGH`, `P3_MEDIUM`, `P4_LOW`)
  - 3 Clarity Levels (`EXPLICIT`, `CLEAR`, `AMBIGUOUS`)
  - 3 Noise Levels (`NONE`, `LIGHT`, `MEDIUM`)

---

## Dataset Architecture & Generation Methodology

### 1. Parametric Log Generation
Each incident record is synthesized using parametric log templates representing realistic distributed microservice traces:
- Standard log formats: JSON structured logs, log4j patterns, syslog entries, Nginx error logs, Kubernetes event streams.
- Dynamically sampled attributes: Timestamp ISO-8601 strings, UUID request/trace IDs, cluster/node names, service identifiers, container IDs, and IP addresses.
- Realistic stack traces: Java exceptions (`java.lang.OutOfMemoryError`, `NullPointerException`), Python tracebacks, Go runtime panics, SQL error codes (`ORA-00060`, `PGRES_FATAL_ERROR`), and kernel OOM invocation dumps.

### 2. Leakage Isolation & Template Fingerprinting
To prevent trivial memorization and data contamination:
- **Structural Fingerprints**: Each template variant is assigned a distinct structural hash.
- **Strict Split Isolation**: Templates assigned to `test.jsonl` are held out completely from `train.jsonl`. The test split measures genuine architectural understanding of system failure modes rather than verbatim template memorization.

### 3. Noise & Clarity Injection
To simulate messy production environments:
- **Clarity Levels**:
  - `EXPLICIT`: Contains definitive root cause statements and explicit error signatures.
  - `CLEAR`: Contains descriptive error cascades without an explicit root cause declaration.
  - `AMBIGUOUS`: Features multi-component warnings, intermittent errors, or concurrent symptoms requiring inference across multiple log lines.
- **Noise Levels**:
  - `NONE`: Pristine stack trace and error logs only.
  - `LIGHT`: Interspersed standard `INFO` / `DEBUG` heartbeats and unrelated request logs.
  - `MEDIUM`: Heavy background noise, concurrent healthcheck pings, and misleading warning logs.

### 4. Grounded Evidence Annotation
Every record includes:
- `evidence`: An array of verbatim strings extracted directly from the raw log text justifying the diagnosis.
- `affected_service`: The exact microservice or component undergoing distress.
- `root_cause`: A concise diagnostic explanation.
- `suggested_action`: The immediate recommended mitigation.

---

## Data Fields

Each JSONL record adheres strictly to the following schema:

```json
{
  "incident_id": "string (unique identifier)",
  "incident_family": "string (one of 36 incident families)",
  "incident_type": "string (APPLICATION | DATABASE | INFRASTRUCTURE | NETWORK | SECURITY | MESSAGING)",
  "severity": "string (P1_CRITICAL | P2_HIGH | P3_MEDIUM | P4_LOW)",
  "clarity": "string (EXPLICIT | CLEAR | AMBIGUOUS)",
  "noise": "string (NONE | LIGHT | MEDIUM)",
  "affected_service": "string (e.g. auth-service, payment-gateway)",
  "raw_log": "string (raw multi-line production log text)",
  "evidence": ["string (verbatim substrings from raw_log)"],
  "root_cause": "string (concise root cause summary)",
  "suggested_action": "string (immediate operational mitigation action)"
}
```

---

## Known Limitations & Synthetic Data Disclaimers

1. **Synthetic Generation Caveat**: This corpus was created via controlled synthetic generators. While it incorporates real-world architecture patterns, realistic error codes, and distributed tracing artifacts, it does not represent an actual dump of private enterprise production systems.
2. **Distributional Shift**: Real-world proprietary enterprise systems may generate novel, undocumented stack formats, custom proprietary error codes, or distributed traces spanning dozens of disparate microservices not represented in this dataset.
3. **No Real PII or Credentials**: All usernames, IP addresses, credentials, tokens, and domain names are synthetic or simulated RFC-5737 / RFC-1918 test vectors. No real personal identifiable information (PII) or secrets are present.

---

## Intended Use & Ethical Considerations

- **Intended Use**: Benchmarking and fine-tuning Small Language Models for automated incident triage, root cause hypothesis generation, and structured telemetry extraction.
- **Prohibited Overclaims**: This dataset must not be claimed as an empirical measure of real-world zero-day exploit detection or proprietary enterprise log triage performance without downstream on-premises domain calibration.
