"""LocalOps AI - Training Dataset & Chat Formatting Module.

Converts raw production incident JSONL records into ChatML conversational
representation for Qwen2.5-1.5B-Instruct, enforcing strict dataset isolation
and canonical LogTriageOutput JSON serialization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from datasets import Dataset

from src.schemas import LogTriageOutput


DEFAULT_SYSTEM_PROMPT = (
    "You are a production incident triage assistant.\n"
    "Return only valid JSON following the required schema."
)


def serialize_target_to_canonical_json(target_dict: Dict[str, Any]) -> str:
    """Serializes a target dictionary into canonical LogTriageOutput JSON.

    Validates schema against LogTriageOutput Pydantic model and ensures
    strictly deterministic field ordering and absence of internal metadata.
    """
    # Validate structure using strict Pydantic model
    validated = LogTriageOutput(**target_dict)

    # Construct canonical dictionary with fixed key order
    inc_type = validated.incident_type.value if hasattr(validated.incident_type, "value") else str(validated.incident_type)
    sev = validated.severity.value if hasattr(validated.severity, "value") else str(validated.severity)

    canonical = {
        "incident_type": inc_type,
        "severity": sev,
        "affected_service": validated.affected_service,
        "root_cause": validated.root_cause,
        "suggested_action": validated.suggested_action,
        "confidence": round(validated.confidence, 4),
        "evidence": validated.evidence,
    }

    return json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))


def format_training_messages(
    raw_log: str,
    target: Dict[str, Any],
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> List[Dict[str, str]]:
    """Converts a raw log and target dictionary into ChatML messages.

    Assistant target contains ONLY the canonical LogTriageOutput JSON.
    No metadata fields (e.g. incident_family, template_id) are included.
    """
    target_json_str = serialize_target_to_canonical_json(target)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": raw_log},
        {"role": "assistant", "content": target_json_str},
    ]


class LocalOpsChatDataset:
    """Loader and manager for Phase 5 supervised fine-tuning dataset."""

    @staticmethod
    def assert_not_test_split(file_path: str | Path) -> None:
        """Enforces dataset isolation boundary.

        The test split (test.jsonl) must remain sealed until Phase 6.
        """
        path_str = str(file_path).replace("\\", "/").lower()
        if "test.jsonl" in path_str or "test_dataset" in path_str:
            raise ValueError(
                f"Dataset isolation boundary violation: '{file_path}' contains test split! "
                "test.jsonl must remain strictly sealed until Phase 6 evaluation."
            )

    @classmethod
    def load_records(
        cls,
        file_path: str | Path,
        max_samples: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Loads JSONL records while enforcing split isolation."""
        cls.assert_not_test_split(file_path)

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found at: {path}")

        records = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                records.append(json.loads(line_str))
                if max_samples and len(records) >= max_samples:
                    break

        return records

    @classmethod
    def create_hf_dataset(
        cls,
        file_path: str | Path,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_samples: Optional[int] = None,
    ) -> Dataset:
        """Loads records and wraps them in a Hugging Face Dataset with 'messages'."""
        records = cls.load_records(file_path, max_samples=max_samples)

        formatted_samples = []
        for rec in records:
            messages = format_training_messages(
                raw_log=rec["raw_log"],
                target=rec["target"],
                system_prompt=system_prompt,
            )
            formatted_samples.append({
                "incident_id": rec.get("incident_id", ""),
                "messages": messages,
            })

        return Dataset.from_list(formatted_samples)
