#!/usr/bin/env python3
"""CLI script to generate synthetic incident triage dataset.

Usage:
    python scripts/generate_dataset.py --smoke
    python scripts/generate_dataset.py --examples-per-template 20
    python scripts/generate_dataset.py --output-dir data/generated
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.generator import DatasetGenerator
from src.data.statistics import DatasetStatistics
from src.data.validation import DatasetValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("generate_dataset")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic incident triage dataset for LocalOps AI."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/dataset.yaml",
        help="Path to dataset configuration YAML file.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/generated",
        help="Target directory for generated JSONL files.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run smoke generation (2 examples per template = 720 records total).",
    )
    parser.add_argument(
        "--examples-per-template",
        type=int,
        default=None,
        help="Override examples per template (default 20 for full, 2 for smoke).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Override random seed for deterministic generation.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip post-generation validation checks.",
    )
    parser.add_argument(
        "--reports-dir",
        type=str,
        default="reports",
        help="Directory to save manifest and statistics reports.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger.info("Starting dataset generation pipeline...")

    try:
        generator = DatasetGenerator(config_path=args.config)
    except Exception as exc:
        logger.error(f"Failed to initialize DatasetGenerator: {exc}")
        return 1

    # Overrides
    if args.seed is not None:
        generator.seed = args.seed
        logger.info(f"Using CLI seed override: {args.seed}")

    if args.examples_per_template is not None:
        examples = args.examples_per_template
    elif args.smoke:
        examples = 2
    else:
        examples = generator.config.get("examples_per_template", 20)

    logger.info(f"Target examples per template: {examples} across 360 templates.")
    logger.info(f"Output directory: {args.output_dir}")

    output_dir = Path(args.output_dir)
    generated_files = generator.generate_all(
        output_dir=output_dir,
        examples_per_template=examples,
    )

    for split, path in generated_files.items():
        logger.info(f"Generated {split.value}: {path}")

    # Validation
    if not args.no_validate:
        logger.info("Executing comprehensive dataset validation...")
        validator = DatasetValidator(data_dir=output_dir)
        results = validator.validate_all()

        if not results.passed:
            logger.error(f"Validation FAILED with {len(results.errors)} errors:")
            for err in results.errors:
                logger.error(f"  - {err}")
            return 2
        else:
            logger.info("Validation PASSED! All integrity constraints satisfied.")
            if results.warnings:
                for warn in results.warnings:
                    logger.warning(f"  - {warn}")

    # Statistics and Manifest
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Computing dataset statistics and generating manifest...")

    stats_calc = DatasetStatistics(data_dir=output_dir)
    stats_data = stats_calc.compute_all()
    stats_path = stats_calc.save_statistics(reports_dir / "dataset_statistics.json")
    logger.info(f"Saved dataset statistics to {stats_path}")

    manifest_config = {
        "noise_distribution": {
            (k.value if hasattr(k, "value") else str(k)): v
            for k, v in generator.noise_distribution.items()
        }
    }
    manifest_path = stats_calc.save_manifest(reports_dir / "dataset_manifest.json", config=manifest_config)
    logger.info(f"Saved dataset manifest to {manifest_path}")

    records_map = stats_calc._load_records()
    samples_path = DatasetStatistics.export_quality_samples(records_map, reports_dir)
    logger.info(f"Saved dataset quality review samples to {samples_path}")

    print("\n" + "=" * 60)
    print("DATASET GENERATION SUMMARY")
    print("=" * 60)
    print(f"Total Records: {stats_data['total_records']}")
    for split, count in stats_data["split_distribution"].items():
        print(f"  - {split}: {count} records")
    print("-" * 60)
    print("Severity Breakdown:")
    for sev, count in stats_data["severity_distribution"].items():
        print(f"  - {sev}: {count}")
    print("-" * 60)
    print("Diagnostic Clarity Breakdown:")
    for clarity, count in stats_data["diagnostic_clarity_distribution"].items():
        print(f"  - {clarity}: {count}")
    print("-" * 60)
    print("Noise Profile Breakdown:")
    for noise, count in stats_data["noise_profile_distribution"].items():
        print(f"  - {noise}: {count}")
    print("=" * 60 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
