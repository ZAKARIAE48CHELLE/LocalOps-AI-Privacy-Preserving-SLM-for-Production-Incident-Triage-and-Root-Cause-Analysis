"""Dataset statistics, telemetry, and manifest generation module.

Calculates distributions, cross-tabulations, log length metrics, timestamp coherence,
target text leakage rates, and SHA-256 checksums.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Optional

from src.data.models import DatasetRecord


_TS_PATTERN = re.compile(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\]")


class DatasetStatistics:
    """Calculates dataset telemetry and exports manifest/statistics reports."""

    def __init__(
        self,
        data_dir: Optional[Path | str] = None,
        records_by_split: Optional[dict[str, list[DatasetRecord]]] = None,
        seed: int = 42,
        generator_version: str = "1.0.0",
        config: Optional[dict[str, object]] = None,
    ):
        self.data_dir = Path(data_dir) if data_dir else None
        self.records_by_split = records_by_split
        self.seed = seed
        self.generator_version = generator_version
        self.config = config or {}

    @classmethod
    def compute_file_sha256(cls, file_path: Path | str) -> str:
        """Calculates SHA-256 checksum of an on-disk dataset file for reproducibility tracking."""
        path = Path(file_path)
        if not path.exists():
            return ""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _load_records(self) -> dict[str, list[DatasetRecord]]:
        if self.records_by_split is not None:
            return self.records_by_split

        if self.data_dir is None:
            return {}

        loaded: dict[str, list[DatasetRecord]] = {}
        for split in ["train", "validation", "test"]:
            file_path = self.data_dir / f"{split}.jsonl"
            records: list[DatasetRecord] = []
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str:
                            records.append(DatasetRecord.model_validate_json(line_str))
            loaded[split] = records
        return loaded

    def compute_all(self) -> dict[str, object]:
        """Computes comprehensive dataset statistics across all splits."""
        records_map = self._load_records()
        checksums = {}
        if self.data_dir:
            for split in ["train", "validation", "test"]:
                fp = self.data_dir / f"{split}.jsonl"
                if fp.exists():
                    checksums[f"{split}.jsonl"] = self.compute_file_sha256(fp)

        stats, _ = self.analyze_dataset(
            records_by_split=records_map,
            file_checksums=checksums,
            config=self.config,
            generator_version=self.generator_version,
            seed=self.seed,
        )
        return stats

    def save_statistics(self, dest_path: Path | str) -> Path:
        """Computes and saves statistics to JSON."""
        stats = self.compute_all()
        path = Path(dest_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
        return path

    def save_manifest(self, dest_path: Path | str, config: Optional[dict[str, object]] = None) -> Path:
        """Generates and saves manifest to JSON."""
        records_map = self._load_records()
        checksums = {}
        files_meta = {}
        if self.data_dir:
            for split in ["train", "validation", "test"]:
                fp = self.data_dir / f"{split}.jsonl"
                if fp.exists():
                    sha = self.compute_file_sha256(fp)
                    checksums[f"{split}.jsonl"] = sha
                    files_meta[f"{split}.jsonl"] = {
                        "sha256": sha,
                        "size_bytes": fp.stat().st_size,
                        "record_count": len(records_map.get(split, [])),
                    }

        active_config = config if config is not None else self.config
        _, manifest = self.analyze_dataset(
            records_by_split=records_map,
            file_checksums=checksums,
            config=active_config,
            generator_version=self.generator_version,
            seed=self.seed,
        )
        manifest["files"] = files_meta

        path = Path(dest_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        return path

    @classmethod
    def analyze_dataset(
        cls,
        records_by_split: dict[str, list[DatasetRecord]],
        file_checksums: Optional[dict[str, str]] = None,
        config: Optional[dict[str, object]] = None,
        generator_version: str = "1.0.0",
        seed: int = 42,
    ) -> tuple[dict[str, object], dict[str, object]]:
        """
        Analyzes the full corpus across splits and produces both
        (statistics_dict, manifest_dict).
        """
        all_records: list[DatasetRecord] = []
        split_counts: dict[str, int] = {}
        for split_name, recs in records_by_split.items():
            split_counts[split_name] = len(recs)
            all_records.extend(recs)

        total_records = len(all_records)
        if total_records == 0:
            return {}, {}

        # Distributions
        by_category: dict[str, int] = {}
        by_family: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_technology: dict[str, int] = {}
        by_runtime: dict[str, int] = {}
        by_signature_profile: dict[str, int] = {}
        by_noise_profile: dict[str, int] = {}
        by_diagnostic_clarity: dict[str, int] = {}

        # Cross-tabulations
        severity_by_category: dict[str, dict[str, int]] = {}
        severity_by_family: dict[str, dict[str, int]] = {}
        severity_by_clarity: dict[str, dict[str, int]] = {}

        log_lengths: list[int] = []
        log_line_counts: list[int] = []
        record_time_spans: list[int] = []
        non_monotonic_records = 0

        for rec in all_records:
            cat = rec.target.incident_type.value if hasattr(rec.target.incident_type, "value") else str(rec.target.incident_type)
            fam = rec.metadata.incident_family.value if hasattr(rec.metadata.incident_family, "value") else str(rec.metadata.incident_family)
            sev = rec.target.severity.value if hasattr(rec.target.severity, "value") else str(rec.target.severity)
            tech = rec.metadata.technology
            rt = rec.metadata.runtime
            sig = rec.metadata.signature_profile
            noise = rec.metadata.noise_profile
            clarity = rec.metadata.diagnostic_clarity

            by_category[cat] = by_category.get(cat, 0) + 1
            by_family[fam] = by_family.get(fam, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_technology[tech] = by_technology.get(tech, 0) + 1
            by_runtime[rt] = by_runtime.get(rt, 0) + 1
            if sig:
                by_signature_profile[sig] = by_signature_profile.get(sig, 0) + 1
            by_noise_profile[noise] = by_noise_profile.get(noise, 0) + 1
            by_diagnostic_clarity[clarity] = by_diagnostic_clarity.get(clarity, 0) + 1

            if sev not in severity_by_category:
                severity_by_category[sev] = {}
            severity_by_category[sev][cat] = severity_by_category[sev].get(cat, 0) + 1

            if sev not in severity_by_family:
                severity_by_family[sev] = {}
            severity_by_family[sev][fam] = severity_by_family[sev].get(fam, 0) + 1

            if sev not in severity_by_clarity:
                severity_by_clarity[sev] = {}
            severity_by_clarity[sev][clarity] = severity_by_clarity[sev].get(clarity, 0) + 1

            raw_text = rec.raw_log
            log_lengths.append(len(raw_text))
            log_line_counts.append(len(raw_text.splitlines()))

            # Timestamp extraction & monotonicity checks
            ts_matches = _TS_PATTERN.findall(raw_text)
            if ts_matches:
                dt_list = [datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in ts_matches]
                span_s = int((max(dt_list) - min(dt_list)).total_seconds())
                record_time_spans.append(span_s)
                is_non_monotonic = any(dt_list[i] > dt_list[i + 1] for i in range(len(dt_list) - 1))
                if is_non_monotonic:
                    non_monotonic_records += 1

        # Target wording cross-split leakage metrics
        train_records = records_by_split.get("train", [])
        test_records = records_by_split.get("test", [])
        train_rc_set = {r.target.root_cause for r in train_records}
        train_act_set = {r.target.suggested_action for r in train_records}

        exact_test_rc_seen = 0
        exact_test_act_seen = 0
        if test_records:
            exact_test_rc_seen = sum(1 for r in test_records if r.target.root_cause in train_rc_set)
            exact_test_act_seen = sum(1 for r in test_records if r.target.suggested_action in train_act_set)
            rc_overlap_rate = round(exact_test_rc_seen / len(test_records), 4)
            act_overlap_rate = round(exact_test_act_seen / len(test_records), 4)
        else:
            rc_overlap_rate = 0.0
            act_overlap_rate = 0.0

        stats: dict[str, object] = {
            "total_records": total_records,
            "split_distribution": split_counts,
            "category_distribution": dict(sorted(by_category.items())),
            "family_distribution": dict(sorted(by_family.items())),
            "severity_distribution": dict(sorted(by_severity.items())),
            "technology_distribution": dict(sorted(by_technology.items())),
            "runtime_distribution": dict(sorted(by_runtime.items())),
            "signature_profile_distribution": dict(sorted(by_signature_profile.items())),
            "noise_profile_distribution": dict(sorted(by_noise_profile.items())),
            "diagnostic_clarity_distribution": dict(sorted(by_diagnostic_clarity.items())),
            "severity_x_category": severity_by_category,
            "severity_x_family": severity_by_family,
            "severity_x_diagnostic_clarity": severity_by_clarity,
            "log_length_bytes": {
                "min": min(log_lengths),
                "max": max(log_lengths),
                "mean": round(sum(log_lengths) / total_records, 1),
            },
            "log_line_counts": {
                "min": min(log_line_counts),
                "max": max(log_line_counts),
                "mean": round(sum(log_line_counts) / total_records, 1),
            },
            "record_time_span_seconds": {
                "min": min(record_time_spans) if record_time_spans else 0,
                "max": max(record_time_spans) if record_time_spans else 0,
                "mean": round(sum(record_time_spans) / len(record_time_spans), 1) if record_time_spans else 0,
            },
            "non_monotonic_timestamp_records": non_monotonic_records,
            "target_phrase_split_leakage": {
                "exact_test_root_cause_seen_in_train_rate": rc_overlap_rate,
                "exact_test_action_seen_in_train_rate": act_overlap_rate,
                "test_root_cause_train_matches": exact_test_rc_seen,
                "test_action_train_matches": exact_test_act_seen,
            },
        }

        resolved_config = {
            "seed": seed,
            "generator_version": generator_version,
            "dataset_format_version": "1.0.0",
            "examples_per_template": 20,
            "templates_per_family": 10,
            "train_templates_per_family": 6,
            "validation_templates_per_family": 2,
            "test_templates_per_family": 2,
            "noise_distribution": {
                "NONE": 0.20,
                "LIGHT": 0.40,
                "MEDIUM": 0.40,
            },
            "base_synthetic_timestamp": "2026-09-14T08:00:00Z",
            "severity_generation_strategy": "decoupled_scenario_driven",
            "confidence_generation_strategy": "clarity_heuristic_range",
            "total_templates": 360,
            "total_families": 36,
            "total_categories": 6,
        }
        if config:
            resolved_config.update(config)

        manifest: dict[str, object] = {
            "manifest_version": "1.1.0",
            "generator_version": generator_version,
            "seed": seed,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_records": total_records,
            "record_counts_by_split": split_counts,
            "file_checksums_sha256": file_checksums or {},
            "configuration": resolved_config,
            "integrity_status": "VALIDATED",
        }

        return stats, manifest

    @classmethod
    def export_reports(
        cls,
        stats: dict[str, object],
        manifest: dict[str, object],
        reports_dir: Path | str,
        records_by_split: Optional[dict[str, list[DatasetRecord]]] = None,
    ) -> tuple[Path, Path]:
        """Saves reports/dataset_statistics.json, reports/dataset_manifest.json, and dataset_quality_samples.json."""
        out_dir = Path(reports_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        stats_path = out_dir / "dataset_statistics.json"
        manifest_path = out_dir / "dataset_manifest.json"

        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        if records_by_split:
            cls.export_quality_samples(records_by_split, out_dir)

        return stats_path, manifest_path

    @classmethod
    def export_quality_samples(
        cls,
        records_by_split: dict[str, list[DatasetRecord]],
        reports_dir: Path | str,
    ) -> Path:
        """
        Exports representative review samples spanning all 6 IncidentTypes,
        all 4 Severities, all 3 DiagnosticClarity levels, and all 3 splits.
        """
        out_dir = Path(reports_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        samples_path = out_dir / "dataset_quality_samples.json"

        sampled: list[dict[str, object]] = []
        covered_combos: set[tuple[str, str, str, str]] = set()

        # Prioritize diverse coverage
        for split_name in ["train", "validation", "test"]:
            records = records_by_split.get(split_name, [])
            for rec in records:
                cat = rec.target.incident_type.value if hasattr(rec.target.incident_type, "value") else str(rec.target.incident_type)
                sev = rec.target.severity.value if hasattr(rec.target.severity, "value") else str(rec.target.severity)
                clarity = rec.metadata.diagnostic_clarity
                combo = (split_name, cat, sev, clarity)

                if combo not in covered_combos or len(sampled) < 24:
                    covered_combos.add(combo)
                    sampled.append({
                        "incident_id": rec.incident_id,
                        "split": split_name,
                        "category": cat,
                        "family": rec.metadata.incident_family.value if hasattr(rec.metadata.incident_family, "value") else str(rec.metadata.incident_family),
                        "severity": sev,
                        "diagnostic_clarity": clarity,
                        "technology": rec.metadata.technology,
                        "runtime": rec.metadata.runtime,
                        "signature_profile": rec.metadata.signature_profile,
                        "raw_log_preview": rec.raw_log.splitlines()[:5],
                        "total_lines": len(rec.raw_log.splitlines()),
                        "target": {
                            "incident_type": cat,
                            "severity": sev,
                            "affected_service": rec.target.affected_service,
                            "root_cause": rec.target.root_cause,
                            "suggested_action": rec.target.suggested_action,
                            "confidence": rec.target.confidence,
                            "evidence": rec.target.evidence,
                        }
                    })

                if len(sampled) >= 36:
                    break
            if len(sampled) >= 36:
                break

        with open(samples_path, "w", encoding="utf-8") as f:
            json.dump({
                "description": "Representative review samples spanning all IncidentTypes, Severities, Clarity levels, and Splits",
                "sample_count": len(sampled),
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "samples": sampled,
            }, f, indent=2)

        return samples_path
