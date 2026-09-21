"""
Template split isolation and leakage verification module.
Guarantees template IDs and normalized structural fingerprints never cross splits.
"""

from src.data.models import DatasetSplit
from src.data.templates import ALL_TEMPLATES, LogTemplate
from src.data.templates.base import compute_structural_fingerprint
import random


class SplitManager:
    """Manages template-to-split assignments and verifies leakage-safe partitioning."""

    def __init__(self, templates: list[LogTemplate] = ALL_TEMPLATES):
        self.templates = templates
        self._split_map: dict[DatasetSplit, list[LogTemplate]] = {
            DatasetSplit.TRAIN: [],
            DatasetSplit.VALIDATION: [],
            DatasetSplit.TEST: [],
        }
        for tpl in self.templates:
            self._split_map[tpl.assigned_split].append(tpl)

    def get_templates_for_split(self, split: DatasetSplit) -> list[LogTemplate]:
        """Return all structural templates assigned to a specific split."""
        return self._split_map[split]

    def verify_split_isolation(self) -> dict[str, int]:
        """
        Validates:
        1. No template_id crosses any split.
        2. Zero normalized structural fingerprint overlap across splits (Amendment 2).
        Returns isolation statistics dictionary.
        """
        train_ids = {t.template_id for t in self._split_map[DatasetSplit.TRAIN]}
        val_ids = {t.template_id for t in self._split_map[DatasetSplit.VALIDATION]}
        test_ids = {t.template_id for t in self._split_map[DatasetSplit.TEST]}

        # ID overlap checks
        train_val_overlap = len(train_ids.intersection(val_ids))
        train_test_overlap = len(train_ids.intersection(test_ids))
        val_test_overlap = len(val_ids.intersection(test_ids))
        total_id_overlap = train_val_overlap + train_test_overlap + val_test_overlap

        assert total_id_overlap == 0, (
            f"Cross-split template ID overlap detected! "
            f"Train/Val: {train_val_overlap}, Train/Test: {train_test_overlap}, Val/Test: {val_test_overlap}"
        )

        # Normalized structural fingerprint checks (Amendment 2)
        # We sample a mock rendering of each template to extract its normalized structural signature
        mock_rng = random.Random(9999)
        fingerprints: dict[DatasetSplit, set[str]] = {
            DatasetSplit.TRAIN: set(),
            DatasetSplit.VALIDATION: set(),
            DatasetSplit.TEST: set(),
        }

        for split, tpls in self._split_map.items():
            for tpl in tpls:
                # Render core incident lines with mock parameters
                lines = tpl.log_generator(
                    rng=mock_rng,
                    service="mock-service",
                    ip="192.0.2.1",
                    ts="2026-09-14T00:00:00.000Z",
                    impact_line=tpl.impact_scenarios[0].impact_line.format(
                        service="mock-service", ip="192.0.2.1", hex_id="deadbeef", num=100, ts="2026-09-14T00:00:00.000Z"
                    ),
                    hex_id="deadbeef",
                    num=100,
                )
                raw_text = "\n".join(lines)
                fp = compute_structural_fingerprint(raw_text)
                fingerprints[split].add(fp)

        fp_train_val = len(fingerprints[DatasetSplit.TRAIN].intersection(fingerprints[DatasetSplit.VALIDATION]))
        fp_train_test = len(fingerprints[DatasetSplit.TRAIN].intersection(fingerprints[DatasetSplit.TEST]))
        fp_val_test = len(fingerprints[DatasetSplit.VALIDATION].intersection(fingerprints[DatasetSplit.TEST]))
        total_fp_overlap = fp_train_val + fp_train_test + fp_val_test

        assert total_fp_overlap == 0, (
            f"Cross-split structural fingerprint overlap detected! "
            f"Train/Val: {fp_train_val}, Train/Test: {fp_train_test}, Val/Test: {fp_val_test}"
        )

        return {
            "train_template_count": len(train_ids),
            "val_template_count": len(val_ids),
            "test_template_count": len(test_ids),
            "cross_split_id_overlap": total_id_overlap,
            "cross_split_fingerprint_overlap": total_fp_overlap,
        }

    def split_templates(
        self, templates: list[LogTemplate] | None = None
    ) -> tuple[list[LogTemplate], list[LogTemplate], list[LogTemplate]]:
        """Return (train_templates, val_templates, test_templates) tuple."""
        target_templates = templates if templates is not None else self.templates
        train = [t for t in target_templates if t.assigned_split == DatasetSplit.TRAIN]
        val = [t for t in target_templates if t.assigned_split == DatasetSplit.VALIDATION]
        test = [t for t in target_templates if t.assigned_split == DatasetSplit.TEST]
        return train, val, test

    def verify_structural_isolation(self, templates: list[LogTemplate] | None = None) -> int:
        """Verify structural isolation and return the cross_split_fingerprint_overlap count."""
        if templates is not None:
            manager = SplitManager(templates)
            stats = manager.verify_split_isolation()
        else:
            stats = self.verify_split_isolation()
        return stats["cross_split_fingerprint_overlap"]
