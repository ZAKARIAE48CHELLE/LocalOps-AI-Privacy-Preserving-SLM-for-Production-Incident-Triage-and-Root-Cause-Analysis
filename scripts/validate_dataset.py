#!/usr/bin/env python3
"""CLI script to validate an existing synthetic incident triage dataset.

Usage:
    python scripts/validate_dataset.py --data-dir data/generated
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.validation import DatasetValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("validate_dataset")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate synthetic incident triage dataset for integrity, leakage, and grounding."
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/generated",
        help="Directory containing train.jsonl, validation.jsonl, and test.jsonl.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir)

    if not data_dir.exists():
        logger.error(f"Dataset directory does not exist: {data_dir}")
        return 1

    logger.info(f"Validating dataset in {data_dir}...")
    validator = DatasetValidator(data_dir=data_dir)
    results = validator.validate_all()

    print("\n" + "=" * 60)
    print("DATASET VALIDATION RESULTS")
    print("=" * 60)
    print(f"Status: {'PASSED' if results.passed else 'FAILED'}")
    print(f"Total Records Checked: {results.total_records_checked}")
    print(f"Errors Found: {len(results.errors)}")
    print(f"Warnings Found: {len(results.warnings)}")
    print("-" * 60)

    for metric, val in results.metrics.items():
        print(f"  {metric}: {val}")

    if results.errors:
        print("\nERRORS:")
        for err in results.errors:
            print(f"  [ERROR] {err}")

    if results.warnings:
        print("\nWARNINGS:")
        for warn in results.warnings:
            print(f"  [WARN] {warn}")

    print("=" * 60 + "\n")
    return 0 if results.passed else 2


if __name__ == "__main__":
    sys.exit(main())
