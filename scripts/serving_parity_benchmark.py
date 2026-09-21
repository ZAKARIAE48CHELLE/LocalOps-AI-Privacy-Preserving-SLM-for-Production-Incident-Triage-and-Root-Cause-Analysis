"""Serving parity benchmark.

Verifies that the production InferenceService running the locked release
configuration on real hardware reproduces the offline E4 model behavior on a
stratified subset of test records spanning all 6 IncidentTypes and multiple severities.
"""
import json
import time
import torch
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from src.api.inference_service import InferenceService
from src.api.schemas import TriageRequest

def run_serving_parity():
    root = Path(__file__).resolve().parent.parent
    predictions_path = root / "reports" / "evaluation" / "e4_qlora" / "predictions.jsonl"
    
    # Stratified selection across the 6 IncidentTypes
    target_types = ["APPLICATION", "DATABASE", "INFRASTRUCTURE", "NETWORK", "SECURITY", "MESSAGING"]
    selected_records = {}

    with open(predictions_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            gt_type = rec.get("ground_truth", {}).get("incident_type")
            if gt_type in target_types and gt_type not in selected_records:
                selected_records[gt_type] = rec
            if len(selected_records) == len(target_types):
                break

    print(f"Selected {len(selected_records)} stratified records for serving parity verification:")
    for itype, rec in selected_records.items():
        print(f" - {itype}: id={rec['incident_id']}, severity={rec['ground_truth'].get('severity')}")

    # Initialize and load production service
    print("\nInitializing production InferenceService...")
    service = InferenceService()
    service.model_manager.load_model()

    results = []
    parity_matches = 0
    schema_valid_count = 0
    total_latency = 0.0

    print("\nExecuting Serving Parity Evaluations...")
    for itype, rec in selected_records.items():
        raw_log = rec["raw_log"]
        e4_output = rec["parsed_output"]
        
        t0 = time.perf_counter()
        out, telemetry = service.triage_single(raw_log=raw_log, request_id=rec["incident_id"])
        latency = time.perf_counter() - t0
        total_latency += latency
        schema_valid = (out is not None)
        if schema_valid:
            schema_valid_count += 1

        out_type = out.incident_type.value if hasattr(out.incident_type, "value") else str(out.incident_type)
        out_sev = out.severity.value if hasattr(out.severity, "value") else str(out.severity)
        
        e4_type = e4_output.get("incident_type")
        e4_sev = e4_output.get("severity")

        type_match = (out_type == e4_type)
        sev_match = (out_sev == e4_sev)
        exact_parity = type_match and sev_match

        if exact_parity:
            parity_matches += 1

        print(f"[{itype}] Latency: {latency:.2f}s | SchemaValid: {schema_valid} | "
              f"TypeMatch: {type_match} ({out_type} vs {e4_type}) | "
              f"SevMatch: {sev_match} ({out_sev} vs {e4_sev})")

        results.append({
            "incident_id": rec["incident_id"],
            "target_incident_type": itype,
            "e4_incident_type": e4_type,
            "serving_incident_type": out_type,
            "e4_severity": e4_sev,
            "serving_severity": out_sev,
            "incident_type_match": type_match,
            "severity_match": sev_match,
            "exact_parity": exact_parity,
            "latency_seconds": round(latency, 3),
            "schema_valid": schema_valid
        })

    n = len(selected_records)
    vram_peak = torch.cuda.max_memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0

    summary = {
        "status": "PASSED" if parity_matches == n and schema_valid_count == n else "FAILED",
        "sample_count": n,
        "schema_validity_rate": round(schema_valid_count / n, 4),
        "exact_parity_rate": round(parity_matches / n, 4),
        "mean_latency_seconds": round(total_latency / n, 3),
        "peak_vram_mb": round(vram_peak, 2),
        "records": results
    }

    out_file = root / "artifacts" / "release" / "serving_parity.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nServing Parity Result: {summary['status']}")
    print(f"Parity Rate: {summary['exact_parity_rate']*100:.1f}% | Schema Validity: {summary['schema_validity_rate']*100:.1f}%")
    print(f"Mean Latency: {summary['mean_latency_seconds']}s | Peak VRAM: {summary['peak_vram_mb']} MB")
    print(f"Report saved to {out_file}")

if __name__ == "__main__":
    run_serving_parity()
