"""
Dataset generator orchestrator for LocalOps AI synthetic incident logs.
Enforces deterministic RNG seeding, template-level split isolation, and strict validation.
"""

import json
from pathlib import Path
import random
from typing import Optional
import yaml

from src.data.models import DatasetRecord, DatasetSplit, NoiseProfile
from src.data.splitter import SplitManager
from src.data.templates import ALL_TEMPLATES, LogTemplate


class DatasetGenerator:
    """Orchestrates deterministic dataset generation across train, validation, and test splits."""

    def __init__(
        self,
        seed: int = 42,
        examples_per_template: int = 20,
        noise_distribution: Optional[dict[str, float]] = None,
        generator_version: str = "1.0.0",
        templates: list[LogTemplate] = ALL_TEMPLATES,
        config_path: Optional[str | Path] = None,
    ):
        self.config: dict = {}
        if config_path is not None:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
            seed = self.config.get("seed", seed)
            examples_per_template = self.config.get("examples_per_template", examples_per_template)
            noise_distribution = self.config.get("noise", noise_distribution)
            generator_version = self.config.get("generator_version", generator_version)

        self.seed = seed
        self.examples_per_template = examples_per_template
        self.generator_version = generator_version
        self.templates = templates
        self.split_manager = SplitManager(templates)

        if noise_distribution is None:
            self.noise_distribution = {
                NoiseProfile.NONE: 0.20,
                NoiseProfile.LIGHT: 0.40,
                NoiseProfile.MEDIUM: 0.40,
            }
        else:
            self.noise_distribution = {
                NoiseProfile(k.upper()): v for k, v in noise_distribution.items()
            }

        # Initialize deterministic RNG (Amendment 7, 20)
        self.rng = random.Random(self.seed)

    @classmethod
    def from_config_file(cls, config_path: str | Path, smoke: bool = False) -> "DatasetGenerator":
        """Factory method to load parameters from a YAML configuration file."""
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        examples_count = (
            cfg.get("smoke_examples_per_template", 2)
            if smoke
            else cfg.get("examples_per_template", 20)
        )

        return cls(
            seed=cfg.get("seed", 42),
            examples_per_template=examples_count,
            noise_distribution=cfg.get("noise"),
            generator_version=cfg.get("generator_version", "1.0.0"),
            config_path=config_path,
        )

    def _choose_noise_profile(self, rng: Optional[random.Random] = None) -> NoiseProfile:
        """Deterministically choose noise profile according to configured weights."""
        active_rng = rng or self.rng
        profiles = list(self.noise_distribution.keys())
        weights = list(self.noise_distribution.values())
        return active_rng.choices(profiles, weights=weights, k=1)[0]

    def _generate_incident_id(self, template: LogTemplate, sample_index: int) -> str:
        """Derive canonical deterministic incident identifier."""
        import hashlib
        id_hash = hashlib.sha256(f"{self.seed}:{template.family.value}:{template.template_id}:{sample_index}".encode()).hexdigest()[:10]
        return f"inc_{template.family.value.lower()}_{template.template_id.lower()}_{id_hash}"

    def generate_record(
        self,
        template: LogTemplate,
        split: DatasetSplit,
        sample_index: int = 0,
        noise_profile: Optional[NoiseProfile] = None,
    ) -> DatasetRecord:
        """Render a single record deterministically using the generator's state or a localized seed."""
        # Create a deterministic sub-RNG seeded by base seed, template ID, and sample index
        sub_seed = (self.seed * 10007) + (sample_index * 37) + sum(ord(c) for c in template.template_id)
        local_rng = random.Random(sub_seed)

        profile = noise_profile or self._choose_noise_profile(local_rng)
        inc_id, target, metadata, raw_log = template.render_record(
            rng=local_rng,
            sample_index=sample_index,
            seed=self.seed,
            noise_profile=profile,
            generator_version=self.generator_version,
        )

        return DatasetRecord(
            incident_id=inc_id,
            raw_log=raw_log,
            target=target,
            metadata=metadata,
        )

    def generate(self) -> dict[DatasetSplit, list[DatasetRecord]]:
        """
        Generates all records across train, validation, and test splits.
        Returns: {DatasetSplit.TRAIN: [...], DatasetSplit.VALIDATION: [...], DatasetSplit.TEST: [...]}
        """
        # First verify isolation before generation
        self.split_manager.verify_split_isolation()

        records_by_split: dict[DatasetSplit, list[DatasetRecord]] = {
            DatasetSplit.TRAIN: [],
            DatasetSplit.VALIDATION: [],
            DatasetSplit.TEST: [],
        }

        seen_incident_ids: set[str] = set()
        seen_raw_logs: set[str] = set()

        for split in [DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST]:
            templates_for_split = self.split_manager.get_templates_for_split(split)

            for tpl in templates_for_split:
                for sample_idx in range(self.examples_per_template):
                    noise_profile = self._choose_noise_profile()

                    # Render deterministic record
                    inc_id, target, metadata, raw_log = tpl.render_record(
                        rng=self.rng,
                        sample_index=sample_idx,
                        seed=self.seed,
                        noise_profile=noise_profile,
                        generator_version=self.generator_version,
                    )

                    # Assertions for deterministic ID and duplicate prevention (Amendment 1 & 19)
                    assert inc_id not in seen_incident_ids, f"Duplicate incident_id detected: {inc_id}"
                    assert raw_log not in seen_raw_logs, f"Exact duplicate raw_log detected for template {tpl.template_id}"

                    seen_incident_ids.add(inc_id)
                    seen_raw_logs.add(raw_log)

                    record = DatasetRecord(
                        incident_id=inc_id,
                        raw_log=raw_log,
                        target=target,
                        metadata=metadata,
                    )
                    records_by_split[split].append(record)

        return records_by_split

    def write_jsonl_splits(
        self,
        records_by_split: dict[DatasetSplit, list[DatasetRecord]],
        output_dir: str | Path,
    ) -> dict[DatasetSplit, Path]:
        """Writes the generated records to separate train.jsonl, validation.jsonl, test.jsonl files."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        file_paths: dict[DatasetSplit, Path] = {}

        filename_map = {
            DatasetSplit.TRAIN: "train.jsonl",
            DatasetSplit.VALIDATION: "validation.jsonl",
            DatasetSplit.TEST: "test.jsonl",
        }

        for split, records in records_by_split.items():
            dest_file = out_path / filename_map[split]
            with open(dest_file, "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(rec.model_dump_json() + "\n")
            file_paths[split] = dest_file

        return file_paths

    def generate_all(
        self,
        output_dir: str | Path,
        examples_per_template: Optional[int] = None,
    ) -> dict[DatasetSplit, Path]:
        """Convenience workflow to generate all splits and write them directly to JSONL files."""
        orig_examples = self.examples_per_template
        if examples_per_template is not None:
            self.examples_per_template = examples_per_template

        # Reset RNG seed to ensure determinism across invocations
        self.rng = random.Random(self.seed)

        try:
            records = self.generate()
            return self.write_jsonl_splits(records, output_dir)
        finally:
            self.examples_per_template = orig_examples
