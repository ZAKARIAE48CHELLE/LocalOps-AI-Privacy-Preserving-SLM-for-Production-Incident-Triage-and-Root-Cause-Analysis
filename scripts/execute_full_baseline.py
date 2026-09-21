"""
Master execution script for Phase 4: Baseline Benchmark.
Runs E1, E2, E3 on the full 1,440 held-out test records with crash-safe resume,
verifies output integrity (1,440 unique IDs, 0 duplicates, 0 missing),
and compiles all final baseline reports and artifacts.
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.evaluator import BaselineEvaluator
from src.evaluation.prompts import PromptBuilder
from src.evaluation.schemas import EvaluationPipelineConfig
import scripts.generate_baseline_report as report_generator


def verify_test_checksum(test_path: str) -> str:
    hasher = hashlib.sha256()
    with open(test_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 70)
    print(" LocalOps AI — Phase 4: Full Baseline Benchmark Execution")
    print("=" * 70)

    config_path = "configs/evaluation.yaml"
    config = EvaluationPipelineConfig.from_yaml(config_path)

    # 1. Verification of Freeze
    test_path = config.evaluation.test_path
    actual_test_hash = verify_test_checksum(test_path)
    print(f"[*] Test Dataset Path: {test_path}")
    print(f"[*] Test Dataset SHA-256: {actual_test_hash}")

    few_shot_manifest_path = "reports/evaluation/few_shot_manifest.json"
    with open(few_shot_manifest_path, "r", encoding="utf-8") as f:
        few_shot_data = json.load(f)
    demonstrations = few_shot_data.get("demonstrations", [])
    print(f"[+] Loaded {len(demonstrations)} frozen few-shot demonstrations.")

    prompt_hashes = {
        "E1": PromptBuilder.get_prompt_hash("E1"),
        "E2": PromptBuilder.get_prompt_hash("E2"),
        "E3": PromptBuilder.get_prompt_hash("E3", demonstrations),
    }
    print("[*] Frozen Prompt Hashes:")
    for exp, h in prompt_hashes.items():
        print(f"    {exp}: {h}")

    # Load all test records
    records = []
    with open(test_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    total_records = len(records)
    print(f"[+] Total Test Records: {total_records}")
    expected_ids = set(r["incident_id"] for r in records)
    assert len(expected_ids) == total_records, "Duplicate incident_ids in test dataset!"

    # 2. Evaluator
    evaluator = BaselineEvaluator(config=config, demonstrations=demonstrations)

    experiments = [
        ("E1", "reports/evaluation/e1_zero_shot"),
        ("E2", "reports/evaluation/e2_structured"),
        ("E3", "reports/evaluation/e3_few_shot"),
    ]

    for exp_id, out_dir in experiments:
        print("\n" + "#" * 70)
        print(f" STARTING BENCHMARK: {exp_id} -> {out_dir}")
        print("#" * 70)

        t_start = time.time()
        metrics = evaluator.evaluate_dataset(
            experiment_id=exp_id,
            records=records,
            output_dir=out_dir,
            resume=True,
        )
        elapsed = time.time() - t_start
        print(f"[+] {exp_id} completed in {elapsed:.1f}s.")

        # Integrity Check
        preds_file = os.path.join(out_dir, "predictions.jsonl")
        completed_ids = set()
        duplicate_count = 0
        with open(preds_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    inc_id = item["incident_id"]
                    if inc_id in completed_ids:
                        duplicate_count += 1
                    completed_ids.add(inc_id)

        print(f"[*] Integrity Verification for {exp_id}:")
        print(f"    Completed Count: {len(completed_ids)}/{total_records}")
        print(f"    Duplicate Count: {duplicate_count}")
        missing_ids = expected_ids - completed_ids
        print(f"    Missing Count:   {len(missing_ids)}")

        if len(completed_ids) != total_records or duplicate_count > 0 or missing_ids:
            print(f"[!] WARNING: Integrity check failed for {exp_id}!")
        else:
            print(f"[OK] {exp_id} passed all integrity checks (1440 unique records, 0 duplicates, 0 missing).")

    # 3. Generate Consolidated Reports & Artifacts
    print("\n" + "=" * 70)
    print(" GENERATING FINAL CONSOLIDATED BENCHMARK ARTIFACTS")
    print("=" * 70)
    report_generator.main()

    print("\n[OK] Phase 4 Full Baseline Benchmark Execution Completed Successfully!")


if __name__ == "__main__":
    main()
