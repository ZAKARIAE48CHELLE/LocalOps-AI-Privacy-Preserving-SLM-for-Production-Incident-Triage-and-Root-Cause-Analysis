"""
CLI driver for Phase 4: Baseline Evaluation.
Executes E1 (Zero-Shot), E2 (Structured Prompt), and E3 (Few-Shot) evaluations.
Supports crash-safe resume, stratified smoke benchmarking, and multi-experiment execution.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.evaluator import BaselineEvaluator, load_stratified_smoke_records
from src.evaluation.prompts import PromptBuilder
from src.evaluation.schemas import EvaluationPipelineConfig


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run Phase 4 Baseline Evaluations.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/evaluation.yaml",
        help="Path to evaluation YAML configuration.",
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default="all",
        choices=["E1", "E2", "E3", "all"],
        help="Experiment to evaluate: E1, E2, E3, or all.",
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
        help="Run deterministic stratified smoke evaluation (36 records from validation split).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of samples to evaluate (for debugging).",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable resume from existing checkpoints.",
    )

    args = parser.parse_args()

    print("=" * 60)
    print(" LocalOps AI — Phase 4: Baseline Evaluation Engine")
    print("=" * 60)

    # 1. Load Configuration
    print(f"[*] Loading configuration from: {args.config}")
    config = EvaluationPipelineConfig.from_yaml(args.config)

    # 2. Load Few-Shot Demonstrations
    few_shot_manifest_path = "reports/evaluation/few_shot_manifest.json"
    demonstrations = []
    if os.path.exists(few_shot_manifest_path):
        with open(few_shot_manifest_path, "r", encoding="utf-8") as f:
            demonstrations = json.load(f).get("demonstrations", [])
        print(f"[+] Loaded {len(demonstrations)} frozen few-shot demonstrations.")
    else:
        print(f"[-] WARNING: Few-shot manifest not found at {few_shot_manifest_path}")

    # 3. Load Target Records
    if args.smoke:
        print("[*] Running STRATIFIED SMOKE evaluation on validation split (36 records)...")
        records = load_stratified_smoke_records(
            validation_path=config.evaluation.validation_path,
            records_per_family=config.evaluation.smoke_records_per_family,
        )
        base_output_dir = os.path.join(config.evaluation.results_dir, "smoke")
    else:
        target_path = (
            config.evaluation.test_path
            if args.split == "test"
            else config.evaluation.validation_path
        )
        print(f"[*] Loading evaluation dataset from: {target_path}")
        records = []
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        base_output_dir = config.evaluation.results_dir

    if args.limit is not None and args.limit > 0:
        print(f"[!] Applying sample limit: {args.limit} records.")
        records = records[: args.limit]

    print(f"[+] Prepared {len(records)} records for evaluation.")

    # 4. Determine Experiments
    if args.experiment == "all":
        experiments = ["E1", "E2", "E3"]
    else:
        experiments = [args.experiment]

    # 5. Initialize Evaluator
    evaluator = BaselineEvaluator(config=config, demonstrations=demonstrations)

    exp_folder_map = {
        "E1": "e1_zero_shot",
        "E2": "e2_structured",
        "E3": "e3_few_shot",
    }

    # 6. Execute Experiments
    for exp_id in experiments:
        print("\n" + "#" * 60)
        print(f" EXECUTING EXPERIMENT {exp_id}")
        print("#" * 60)

        folder_name = exp_folder_map.get(exp_id, exp_id.lower())
        exp_output_dir = os.path.join(base_output_dir, folder_name)
        evaluator.evaluate_dataset(
            experiment_id=exp_id,
            records=records,
            output_dir=exp_output_dir,
            resume=not args.no_resume,
        )

    print("\n" + "=" * 60)
    print(" [OK] All requested baseline evaluations completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
