"""LocalOps AI — Phase 6: E4 QLoRA Fine-Tuned Evaluation CLI Driver.

Evaluates the validation-selected Phase 5 adapter (checkpoint-100) on the
sealed held-out test split (1,440 records).
Features:
- Checksum verification of data/generated/test.jsonl
- Smoke test with automatic batch size & VRAM safety testing
- Frozen execution manifest and prompt hashing
- Atomic checkpointing and zero-duplicate crash resumption
- Per-sample and batched telemetry (latency, tokens/s, peak VRAM)
- Physical NVML energy tracking
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch
import yaml

from src.evaluation.evaluator import BaselineEvaluator, load_stratified_smoke_records
from src.evaluation.metrics import MetricEvaluator
from src.evaluation.prompts import PromptBuilder
from src.evaluation.schemas import EvaluationPipelineConfig, RawPredictionRecord
from src.dashboard.energy_tracker import EnergyTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("localops.run_e4_evaluation")


def compute_file_sha256(file_path: str | Path) -> str:
    """Computes SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def update_live_status(
    status_file: Path,
    experiment_id: str,
    completed: int,
    total: int,
    vram_mb: float,
    latency_avg: float,
    phase_detail: str,
    recent_records: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Writes atomic live status for dashboard consumption."""
    status_file.parent.mkdir(parents=True, exist_ok=True)
    pct = round((completed / max(1, total)) * 100, 1)
    eta_sec = round((total - completed) * latency_avg, 1) if latency_avg > 0 else 0.0

    payload = {
        "timestamp": time.time(),
        "experiment_id": experiment_id,
        "completed": completed,
        "total": total,
        "progress_pct": pct,
        "peak_vram_mb": vram_mb,
        "avg_sample_latency": round(latency_avg, 4),
        "eta_seconds": eta_sec,
        "phase_detail": phase_detail,
        "recent_predictions": (recent_records or [])[-5:],
    }
    tmp_file = status_file.with_suffix(".tmp")
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp_file.replace(status_file)
    except Exception as e:
        logger.warning(f"Could not update live status file: {e}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run Phase 6 E4 QLoRA Evaluation.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/evaluation_e4.yaml",
        help="Path to evaluation_e4 YAML configuration.",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        choices=["test", "validation"],
        help="Dataset split to evaluate.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run pre-flight smoke test (36 stratified validation records) to test batch hypothesis.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override batch size (default: from config).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of samples to evaluate (for quick verification).",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable resume from existing predictions.",
    )

    args = parser.parse_args()

    print("=" * 65)
    print(" LocalOps AI — Phase 6: Fine-Tuned Model Evaluation (E4 QLoRA)")
    print("=" * 65)

    # 1. Load Configuration
    config_path = PROJECT_ROOT / args.config
    logger.info(f"Loading configuration from: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)

    eval_config = EvaluationPipelineConfig.from_yaml(str(config_path))

    adapter_path = PROJECT_ROOT / config_dict["model"]["adapter_path"]
    adapter_source = config_dict["model"].get("adapter_source_checkpoint", "checkpoint-100")
    results_dir = PROJECT_ROOT / config_dict["evaluation"]["results_dir"]
    results_dir.mkdir(parents=True, exist_ok=True)

    live_status_path = PROJECT_ROOT / "artifacts" / "phase_6" / "live_evaluation_status.json"

    # 2. Verify Integrity of Components
    logger.info(f"Verifying adapter path: {adapter_path} (Source: {adapter_source})")
    if not adapter_path.exists():
        raise FileNotFoundError(f"Adapter not found at: {adapter_path}")

    adapter_weights_path = adapter_path / "adapter_model.safetensors"
    if not adapter_weights_path.exists():
        raise FileNotFoundError(f"Adapter weights not found at: {adapter_weights_path}")
    adapter_weights_sha256 = compute_file_sha256(adapter_weights_path)
    logger.info(f"Adapter weights SHA-256: {adapter_weights_sha256}")

    # 3. Check Dataset Checksum
    target_path = PROJECT_ROOT / (
        config_dict["evaluation"]["test_path"]
        if args.split == "test" and not args.smoke
        else config_dict["evaluation"]["validation_path"]
    )
    logger.info(f"Target dataset path: {target_path}")
    if not target_path.exists():
        raise FileNotFoundError(f"Dataset not found at: {target_path}")

    dataset_sha256 = compute_file_sha256(target_path)
    logger.info(f"Dataset SHA-256: {dataset_sha256}")

    if args.split == "test" and not args.smoke:
        expected_test_sha = config_dict["evaluation"].get(
            "test_split_sha256",
            "a1c79a8beb9ca4868d358aa9bba1dd3c762466bd58249d460987a1e692f817b9",
        )
        if dataset_sha256.lower() != expected_test_sha.lower():
            raise ValueError(
                f"Test dataset checksum mismatch! Expected: {expected_test_sha}, Got: {dataset_sha256}"
            )
        logger.info("[OK] Held-out test set integrity verified via SHA-256.")

    # 4. Prompt Manifest & Freeze Hash
    prompt_hash = PromptBuilder.get_prompt_hash("E4")
    prompt_manifest = PromptBuilder.create_prompt_manifest(config_dict["generation"])
    manifest_path = results_dir / "e4_prompt_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(prompt_manifest, f, indent=2)
    logger.info(f"E4 Prompt frozen with SHA-256: {prompt_hash}")

    # 5. Load Target Dataset Records
    if args.smoke:
        logger.info("[*] Running SMOKE evaluation on validation split (36 records)...")
        records = load_stratified_smoke_records(
            validation_path=str(PROJECT_ROOT / config_dict["evaluation"]["validation_path"]),
            records_per_family=config_dict["evaluation"].get("smoke_records_per_family", 1),
        )
        output_dir = results_dir / "smoke"
    else:
        records = []
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        output_dir = results_dir

    if args.limit:
        records = records[: args.limit]
        logger.info(f"[!] Applied limit: evaluating {len(records)} records.")

    total_records = len(records)
    logger.info(f"[+] Total target evaluation records: {total_records}")

    # 6. Batch Size & VRAM Safety Hypothesis Verification
    initial_batch_size = args.batch_size or config_dict["evaluation"].get("batch_size", 16)
    vram_ceiling_mb = config_dict["evaluation"].get("vram_safety_ceiling_mb", 6800.0)
    current_batch_size = initial_batch_size

    # 7. Initialize Evaluator with LoRA Adapter
    logger.info("Initializing BaselineEvaluator with LoRA adapter...")
    evaluator = BaselineEvaluator(
        config=eval_config,
        demonstrations=[],
        adapter_path=str(adapter_path),
    )
    evaluator.load_model()

    # If smoke test, verify batch size hypothesis and measure peak VRAM
    if args.smoke:
        logger.info(f"Testing batch size {current_batch_size} hypothesis in smoke mode...")
        test_sample = records[:current_batch_size]
        test_msgs = [PromptBuilder.build_e4_messages(r["raw_log"]) for r in test_sample]

        batch_success = False
        while not batch_success and current_batch_size >= 4:
            try:
                res = evaluator.run_inference_batch(test_msgs[:current_batch_size])
                peak_vram = res[0][5]
                logger.info(f"Smoke batch size {current_batch_size} test: Peak VRAM = {peak_vram:.2f} MB")

                if peak_vram > vram_ceiling_mb:
                    logger.warning(
                        f"Peak VRAM {peak_vram:.2f} MB exceeded ceiling {vram_ceiling_mb} MB! "
                        f"Reducing batch size: {current_batch_size} -> {max(4, current_batch_size - 4)}"
                    )
                    current_batch_size = max(4, current_batch_size - 4)
                else:
                    batch_success = True
                    logger.info(f"[OK] Batch size {current_batch_size} verified and frozen.")
            except torch.cuda.OutOfMemoryError:
                logger.warning(f"CUDA OOM with batch size {current_batch_size}! Reducing to {current_batch_size // 2}")
                torch.cuda.empty_cache()
                current_batch_size = max(4, current_batch_size // 2)

    # Freeze verified execution configuration
    exec_manifest = {
        "experiment_id": "E4",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "base_model": config_dict["model"]["model_id"],
        "adapter_path": str(adapter_path),
        "adapter_source_checkpoint": adapter_source,
        "adapter_weights_sha256": adapter_weights_sha256,
        "dataset_path": str(target_path),
        "dataset_sha256": dataset_sha256,
        "dataset_record_count": total_records,
        "frozen_batch_size": current_batch_size,
        "prompt_sha256": prompt_hash,
        "generation_config": config_dict["generation"],
    }
    manifest_out = output_dir / "execution_manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(manifest_out, "w", encoding="utf-8") as f:
        json.dump(exec_manifest, f, indent=2)
    logger.info(f"[+] Execution manifest frozen at: {manifest_out}")

    # 8. Start Energy Tracking
    energy_tracker = EnergyTracker()
    start_energy_wh = energy_tracker.energy_wh
    start_sample_count = energy_tracker.sample_count
    start_power_sum = energy_tracker.total_power_sum
    energy_tracker.start()

    # 9. Execute Evaluation
    logger.info(f"Starting E4 evaluation on {total_records} records with batch_size={current_batch_size}...")
    start_time = time.time()

    # Setup live status
    update_live_status(
        live_status_path,
        "E4",
        completed=0,
        total=total_records,
        vram_mb=0.0,
        latency_avg=0.0,
        phase_detail="Inference started",
    )

    results = evaluator.evaluate_dataset(
        experiment_id="E4",
        records=records,
        output_dir=str(output_dir),
        resume=not args.no_resume,
        batch_size=current_batch_size,
    )

    total_time = time.time() - start_time
    energy_tracker.stop()
    raw_telemetry = energy_tracker.get_telemetry(completed_records=total_records, total_records=total_records)

    # Isolate run-specific telemetry
    run_wh = max(0.0, energy_tracker.energy_wh - start_energy_wh)
    run_samples = max(1, energy_tracker.sample_count - start_sample_count)
    run_power_sum = max(0.0, energy_tracker.total_power_sum - start_power_sum)
    run_avg_power = run_power_sum / run_samples if run_samples > 0 else raw_telemetry.get("average_power_w", 0.0)
    run_kwh = run_wh / 1000.0

    energy_info = {
        "run_energy_wh": round(run_wh, 4),
        "run_energy_kwh": round(run_kwh, 6),
        "run_average_power_w": round(run_avg_power, 2),
        "run_peak_power_w": round(raw_telemetry.get("peak_power_w", 0.0), 2),
        "run_duration_seconds": round(total_time, 2),
        "carbon_co2_g": round(run_kwh * 385.0, 3),
        "estimated_cost_usd": round(run_kwh * 0.15, 4),
        "cumulative_lifetime_telemetry": raw_telemetry,
    }

    logger.info("=" * 65)
    logger.info(f"[OK] Evaluation finished in {total_time:.2f} seconds ({total_time / 60:.2f} min).")
    logger.info(f"Run energy consumed: {run_wh:.2f} Wh (Avg power: {run_avg_power:.1f} W)")
    logger.info("=" * 65)

    # Save energy info alongside metrics
    results["energy_telemetry"] = energy_info
    results["execution_manifest"] = exec_manifest
    metrics_path = output_dir / "metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Update final live status
    update_live_status(
        live_status_path,
        "E4",
        completed=total_records,
        total=total_records,
        vram_mb=results.get("telemetry", {}).get("peak_vram_mb", 0.0),
        latency_avg=results.get("telemetry", {}).get("latency_seconds", {}).get("mean", 0.0),
        phase_detail="E4 evaluation complete. Metrics compiled.",
    )

    print("\n" + "=" * 65)
    print(" E4 QLoRA Evaluation Summary:")
    print("=" * 65)
    p_met = results.get("primary_metrics", {})
    c_met = results.get("contract_metrics", {})
    print(f"  Pydantic Validity Rate:          {c_met.get('pydantic_valid_rate', 0.0) * 100:.2f}%")
    print(f"  IncidentType Accuracy (E2E):      {p_met.get('end_to_end_incident_type_accuracy', 0.0):.4f}")
    print(f"  IncidentType Macro-F1 (E2E):      {p_met.get('end_to_end_incident_type_macro_f1', 0.0):.4f}")
    print(f"  Severity Accuracy (E2E):          {p_met.get('end_to_end_severity_accuracy', 0.0):.4f}")
    print(f"  Severity Macro-F1 (E2E):          {p_met.get('end_to_end_severity_macro_f1', 0.0):.4f}")
    print(f"  Peak VRAM:                       {results.get('telemetry', {}).get('peak_vram_mb', 0.0):.2f} MB")
    print(f"  Metrics saved to:                {metrics_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()
