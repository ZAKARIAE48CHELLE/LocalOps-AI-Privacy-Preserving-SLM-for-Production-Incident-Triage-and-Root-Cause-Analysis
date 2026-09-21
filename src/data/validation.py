"""Comprehensive dataset integrity and quality validation suite.

Enforces schema validity, evidence grounding, leakage-safe split isolation,
P4 severity coverage, severity/clarity decoupling, timestamp coherence,
and normalized metadata semantics.
"""

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Optional
from pydantic import ValidationError

from src.data.family_catalog import FAMILY_TO_CATEGORY_MAP
from src.data.models import DatasetRecord, DatasetSplit
from src.data.templates.base import compute_structural_fingerprint
from src.schemas.enums import IncidentFamily, IncidentType, Severity
from src.schemas.triage import LogTriageOutput


_TS_REGEX = re.compile(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\]")


class DatasetValidationError(Exception):
    """Raised when critical dataset integrity or quality checks fail."""
    pass


@dataclass
class ValidationResult:
    """Encapsulates outcome of a dataset validation run."""
    passed: bool
    total_records_checked: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, object] = field(default_factory=dict)


class DatasetValidator:
    """Validates on-disk or in-memory synthetic incident datasets against all Phase 3 rules."""

    def __init__(
        self,
        data_dir: Optional[Path | str] = None,
        records_by_split: Optional[dict[str, list[DatasetRecord]]] = None,
    ):
        self.data_dir = Path(data_dir) if data_dir else None
        self.records_by_split = records_by_split

    @classmethod
    def validate_file(cls, file_path: Path | str, expected_split: Optional[str] = None) -> list[DatasetRecord]:
        """Validates a single JSONL file line-by-line."""
        records: list[DatasetRecord] = []
        path = Path(file_path)
        if not path.exists():
            raise DatasetValidationError(f"Dataset file does not exist: {path}")

        with open(path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, start=1):
                line_str = line.strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                except json.JSONDecodeError as e:
                    raise DatasetValidationError(f"Invalid JSON at line {line_idx} in {path.name}: {e}")

                try:
                    record = DatasetRecord.model_validate(data)
                except ValidationError as e:
                    raise DatasetValidationError(
                        f"Schema validation error at line {line_idx} in {path.name}: {e}"
                    )

                if expected_split and record.metadata.split != expected_split:
                    raise DatasetValidationError(
                        f"Line {line_idx} in {path.name}: metadata.split '{record.metadata.split}' "
                        f"does not match expected split '{expected_split}'"
                    )

                records.append(record)

        return records

    @classmethod
    def validate_dataset_directory(cls, data_dir: Path | str) -> dict[str, object]:
        """
        Validates all three dataset files (train.jsonl, validation.jsonl, test.jsonl)
        in a target directory, ensuring cross-split isolation and zero leakage.
        """
        validator = cls(data_dir=data_dir)
        res = validator.validate_all()
        if not res.passed:
            raise DatasetValidationError(
                f"Dataset directory validation failed with {len(res.errors)} errors:\n"
                + "\n".join(f"- {e}" for e in res.errors[:10])
            )
        return res.metrics

    def validate_all(self) -> ValidationResult:
        """Runs comprehensive validation suite and returns structured ValidationResult."""
        errors: list[str] = []
        warnings: list[str] = []

        records_map = self.records_by_split
        if records_map is None:
            if self.data_dir is None:
                raise DatasetValidationError("Validator initialized without data_dir or records_by_split")

            records_map = {}
            for split_name in ["train", "validation", "test"]:
                fpath = self.data_dir / f"{split_name}.jsonl"
                if not fpath.exists():
                    errors.append(f"Missing expected split file: {fpath.name}")
                    continue
                try:
                    records_map[split_name] = self.validate_file(fpath, expected_split=split_name)
                except DatasetValidationError as e:
                    errors.append(str(e))
                    records_map[split_name] = []

        total_records = sum(len(recs) for recs in records_map.values())
        if total_records == 0:
            errors.append("Dataset is empty; 0 records loaded.")
            return ValidationResult(
                passed=False,
                total_records_checked=0,
                errors=errors,
                warnings=warnings,
                metrics={},
            )

        seen_incident_ids: set[str] = set()
        seen_raw_logs: set[str] = set()
        templates_by_split: dict[str, set[str]] = {"train": set(), "validation": set(), "test": set()}
        fingerprints_by_split: dict[str, set[str]] = {"train": set(), "validation": set(), "test": set()}
        families_seen: set[IncidentFamily] = set()
        categories_seen: set[IncidentType] = set()
        severities_seen: set[Severity] = set()
        severity_clarity_pairs: set[tuple[str, str]] = set()

        duplicate_logs = 0
        duplicate_ids = 0
        evidence_mismatches = 0
        service_mismatches = 0
        schema_failures = 0
        non_monotonic_records = 0
        excessive_span_records = 0
        missing_metadata_fields = 0

        for split_name, records in records_map.items():
            for rec in records:
                # 1. Incident ID uniqueness
                if rec.incident_id in seen_incident_ids:
                    duplicate_ids += 1
                    errors.append(f"Duplicate incident_id detected: {rec.incident_id}")
                seen_incident_ids.add(rec.incident_id)

                # 2. Raw log uniqueness
                if rec.raw_log in seen_raw_logs:
                    duplicate_logs += 1
                    errors.append(f"Duplicate raw_log detected for incident: {rec.incident_id}")
                seen_raw_logs.add(rec.raw_log)

                # 3. Target schema validity
                try:
                    LogTriageOutput.model_validate(rec.target.model_dump())
                except ValidationError as e:
                    schema_failures += 1
                    errors.append(f"Schema failure for incident {rec.incident_id}: {e}")

                # 4. Evidence Grounding
                for ev in rec.target.evidence:
                    if ev not in rec.raw_log:
                        evidence_mismatches += 1
                        errors.append(
                            f"Evidence not found as exact substring in incident {rec.incident_id}: '{ev}'"
                        )

                # 5. Affected Service Grounding
                if rec.target.affected_service not in rec.raw_log:
                    service_mismatches += 1
                    errors.append(
                        f"Affected service '{rec.target.affected_service}' not found in raw_log for {rec.incident_id}"
                    )

                # 6. Category mapping consistency
                expected_category = FAMILY_TO_CATEGORY_MAP[rec.metadata.incident_family]
                if rec.target.incident_type != expected_category:
                    errors.append(
                        f"Record {rec.incident_id}: incident_type '{rec.target.incident_type}' "
                        f"!= expected category '{expected_category}'"
                    )

                # 7. Metadata validation
                if not rec.metadata.technology or not rec.metadata.runtime or not rec.metadata.signature_profile:
                    missing_metadata_fields += 1
                    errors.append(
                        f"Record {rec.incident_id}: Missing metadata fields (tech='{rec.metadata.technology}', "
                        f"runtime='{rec.metadata.runtime}', sig='{rec.metadata.signature_profile}')"
                    )

                # 8. Timestamp coherence & monotonicity
                ts_matches = _TS_REGEX.findall(rec.raw_log)
                if ts_matches:
                    dt_list = [datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in ts_matches]
                    span = (max(dt_list) - min(dt_list)).total_seconds()
                    if span > 600:  # Spans should be realistic operational windows (<10 min)
                        excessive_span_records += 1
                        errors.append(
                            f"Record {rec.incident_id}: excessive log time span of {span:.0f}s (>600s)"
                        )
                    if any(dt_list[i] > dt_list[i + 1] for i in range(len(dt_list) - 1)):
                        non_monotonic_records += 1
                        errors.append(
                            f"Record {rec.incident_id}: non-monotonic timestamps detected in log stream"
                        )

                # 8b. Temporal semantic validation (claims vs timestamps)
                exp_ago_match = re.search(r"expired\s+(\d+)\s+seconds\s+ago", rec.raw_log, re.IGNORECASE)
                exp_at_match = re.search(r"expired\s+at\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", rec.raw_log, re.IGNORECASE)
                if exp_ago_match and exp_at_match:
                    claimed_seconds = int(exp_ago_match.group(1))
                    exp_dt = datetime.fromisoformat(exp_at_match.group(1).replace("Z", "+00:00"))
                    inc_dt = None
                    for line in rec.raw_log.split("\n"):
                        if "seconds ago" in line.lower() or "expired at" in line.lower():
                            line_ts = _TS_REGEX.search(line)
                            if line_ts:
                                inc_dt = datetime.fromisoformat(line_ts.group(1).replace("Z", "+00:00"))
                                break
                    if inc_dt:
                        actual_delta = abs((inc_dt - exp_dt).total_seconds())
                        if abs(actual_delta - claimed_seconds) > 2:
                            errors.append(
                                f"Record {rec.incident_id}: temporal inconsistency between claimed expired seconds "
                                f"({claimed_seconds}s) and timestamp delta ({actual_delta:.0f}s)"
                            )

                prev_exec_match = re.search(r"(?:was already executed at|executed at)\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", rec.raw_log, re.IGNORECASE)
                if prev_exec_match:
                    exec_dt = datetime.fromisoformat(prev_exec_match.group(1).replace("Z", "+00:00"))
                    inc_dt = None
                    for line in rec.raw_log.split("\n"):
                        if "executed at" in line.lower():
                            line_ts = _TS_REGEX.search(line)
                            if line_ts:
                                inc_dt = datetime.fromisoformat(line_ts.group(1).replace("Z", "+00:00"))
                                break
                    if inc_dt and exec_dt >= inc_dt:
                        errors.append(
                            f"Record {rec.incident_id}: historical execution timestamp {exec_dt} is not earlier than incident timestamp {inc_dt}"
                        )

                not_after_match = re.search(r"NotAfter:\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", rec.raw_log)
                if not_after_match:
                    na_dt = datetime.fromisoformat(not_after_match.group(1).replace("Z", "+00:00"))
                    inc_dt = None
                    for line in rec.raw_log.split("\n"):
                        if "NotAfter" in line:
                            line_ts = _TS_REGEX.search(line)
                            if line_ts:
                                inc_dt = datetime.fromisoformat(line_ts.group(1).replace("Z", "+00:00"))
                                break
                    if inc_dt and na_dt >= inc_dt:
                        errors.append(
                            f"Record {rec.incident_id}: certificate NotAfter timestamp {na_dt} is not earlier than incident timestamp {inc_dt}"
                        )

                # 8c. Semantic contradiction detection
                if "NotReady" in rec.raw_log and "remained Ready" in rec.raw_log:
                    errors.append(f"Record {rec.incident_id}: contradictory impact line (claims 'remained Ready' despite Node NotReady)")

                if "504" in rec.metadata.signature_profile and "502 Bad Gateway" in rec.target.root_cause:
                    errors.append(f"Record {rec.incident_id}: HTTP status mismatch (504 signature profile with 502 root cause)")
                if "502" in rec.metadata.signature_profile and "504 Gateway Timeout" in rec.target.root_cause:
                    errors.append(f"Record {rec.incident_id}: HTTP status mismatch (502 signature profile with 504 root cause)")
                if "CASSANDRA_READ_TIMEOUT" in rec.metadata.signature_profile and "unindexed" in rec.target.root_cause:
                    errors.append(f"Record {rec.incident_id}: Cassandra query timeout diagnosed with unindexed table scan instead of replica quorum timeout")

                # 9. Collect templates & structural fingerprints
                templates_by_split[split_name].add(rec.metadata.template_id)
                fp = compute_structural_fingerprint(rec.raw_log)
                fingerprints_by_split[split_name].add(fp)

                families_seen.add(rec.metadata.incident_family)
                categories_seen.add(rec.target.incident_type)
                severities_seen.add(rec.target.severity)
                severity_clarity_pairs.add(
                    (rec.target.severity.value if hasattr(rec.target.severity, "value") else str(rec.target.severity),
                     rec.metadata.diagnostic_clarity)
                )

        # 10. Template ID overlap
        train_val_id_overlap = len(templates_by_split["train"].intersection(templates_by_split["validation"]))
        train_test_id_overlap = len(templates_by_split["train"].intersection(templates_by_split["test"]))
        val_test_id_overlap = len(templates_by_split["validation"].intersection(templates_by_split["test"]))
        cross_split_templates = train_val_id_overlap + train_test_id_overlap + val_test_id_overlap
        if cross_split_templates > 0:
            errors.append(f"Cross-split template ID overlap: {cross_split_templates}")

        # 11. Normalized structural fingerprint overlap
        fp_train_val = len(fingerprints_by_split["train"].intersection(fingerprints_by_split["validation"]))
        fp_train_test = len(fingerprints_by_split["train"].intersection(fingerprints_by_split["test"]))
        fp_val_test = len(fingerprints_by_split["validation"].intersection(fingerprints_by_split["test"]))
        cross_split_fingerprints = fp_train_val + fp_train_test + fp_val_test
        if cross_split_fingerprints > 0:
            errors.append(f"Cross-split structural fingerprint overlap: {cross_split_fingerprints}")

        # 12. Completeness & Coverage Checks
        missing_families = len(IncidentFamily) - len(families_seen)
        missing_categories = len(IncidentType) - len(categories_seen)
        missing_severities = len(Severity) - len(severities_seen)

        if missing_families > 0:
            warnings.append(f"Not all 36 families present in dataset: {len(families_seen)}/36 seen")
        if missing_categories > 0:
            warnings.append(f"Not all 6 categories present in dataset: {len(categories_seen)}/6 seen")
        if Severity.P4_LOW not in severities_seen:
            errors.append("Severity P4_LOW has zero representation in the dataset.")
        if missing_severities > 0:
            errors.append(f"Missing severity classes: {missing_severities} severity classes missing from dataset.")

        # 13. Decoupling Check (severity vs clarity must not be 1:1 diagonal)
        if len(severity_clarity_pairs) <= 3 and total_records >= 100:
            errors.append(
                f"Severity and diagnostic clarity appear deterministically coupled: only {len(severity_clarity_pairs)} pairs seen."
            )

        metrics = {
            "total_records": total_records,
            "train_records": len(records_map.get("train", [])),
            "validation_records": len(records_map.get("validation", [])),
            "test_records": len(records_map.get("test", [])),
            "invalid_schemas": schema_failures,
            "duplicate_logs": duplicate_logs,
            "duplicate_ids": duplicate_ids,
            "cross_split_template_leakage": cross_split_templates,
            "cross_split_structural_fingerprint_overlap": cross_split_fingerprints,
            "evidence_mismatches": evidence_mismatches,
            "affected_service_mismatches": service_mismatches,
            "missing_families": missing_families,
            "missing_categories": missing_categories,
            "missing_severities": missing_severities,
            "severity_clarity_pairs_count": len(severity_clarity_pairs),
            "non_monotonic_records": non_monotonic_records,
            "excessive_span_records": excessive_span_records,
            "missing_metadata_fields": missing_metadata_fields,
        }

        return ValidationResult(
            passed=(len(errors) == 0),
            total_records_checked=total_records,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
        )

    @classmethod
    def validate_records_across_splits(
        cls,
        records_by_split: dict[str, list[DatasetRecord]],
    ) -> dict[str, object]:
        """Validates in-memory records across splits and returns metrics dict or raises error."""
        validator = cls(records_by_split=records_by_split)
        res = validator.validate_all()
        if not res.passed:
            raise DatasetValidationError(
                f"Validation failed with {len(res.errors)} errors:\n"
                + "\n".join(f"- {e}" for e in res.errors[:10])
            )
        return res.metrics
