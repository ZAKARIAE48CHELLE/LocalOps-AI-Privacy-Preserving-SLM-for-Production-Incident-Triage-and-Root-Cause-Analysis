"""
Prompt engineering, hashing, and freezing module for Phase 4: Baseline Evaluation.
Builds standardized chat message prompts for:
- E1: Zero-Shot Baseline
- E2: Strong Structured Prompt
- E3: Few-Shot Baseline (with 6 frozen demonstrations)
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.schemas.enums import IncidentType, Severity


PROMPT_VERSION = "1.0.0"

# E1 System & User instructions
E1_SYSTEM_PROMPT = (
    "You are an expert site reliability and production incident triage assistant. "
    "Analyze the provided production logs and diagnose the incident."
)

E1_USER_TEMPLATE = (
    "Analyze the following production logs.\n"
    "Identify the incident type, severity, affected service, root cause, recommended action, "
    "confidence, and supporting evidence.\n\n"
    "Production Incident Log:\n"
    "```\n{raw_log}\n```"
)

# E2 Structured System Prompt
E2_SYSTEM_PROMPT = (
    "You are an expert production incident triage engine. "
    "Analyze the provided production log and return a strictly validated JSON object.\n\n"
    "CRITICAL CONSTRAINTS:\n"
    "1. You must respond with valid JSON ONLY. Do not prepend or append markdown explanations, "
    "notes, conversational greetings, or closing text outside the JSON.\n"
    "2. Do NOT add extra or invented fields outside the specified schema.\n"
    "3. Do NOT speculate or diagnose root causes beyond what is directly substantiated by log signals.\n"
    "4. Every evidence item must be copied verbatim directly from the raw log text.\n"
    "5. Confidence must be a numeric float between 0.0 and 1.0 reflecting certainty in the diagnosis.\n\n"
    "ALLOWED ENUM VALUES:\n"
    f"- incident_type MUST be one of: {[e.value for e in IncidentType]}\n"
    f"- severity MUST be one of: {[e.value for e in Severity]}\n\n"
    "REQUIRED JSON SCHEMA:\n"
    "{\n"
    '  "incident_type": "...",\n'
    '  "severity": "...",\n'
    '  "affected_service": "...",\n'
    '  "root_cause": "...",\n'
    '  "suggested_action": "...",\n'
    '  "confidence": 0.0,\n'
    '  "evidence": ["..."]\n'
    "}"
)

E2_USER_TEMPLATE = (
    "Analyze the following production log and provide the incident triage assessment in the required JSON format.\n\n"
    "Production Incident Log:\n"
    "```\n{raw_log}\n```"
)

# E4 Fine-Tuned System Prompt (Matches Phase 5 training format)
E4_SYSTEM_PROMPT = (
    "You are a production incident triage assistant.\n"
    "Return only valid JSON following the required schema."
)



def compute_sha256(content: str) -> str:
    """Computes SHA-256 hash of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_dict_sha256(data: Dict[str, Any]) -> str:
    """Computes canonical deterministic SHA-256 hash of a dictionary."""
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class PromptBuilder:
    """Constructs reproducible, versioned chat messages for baseline experiments."""

    @staticmethod
    def build_e1_messages(raw_log: str) -> List[Dict[str, str]]:
        """Builds zero-shot E1 chat messages."""
        return [
            {"role": "system", "content": E1_SYSTEM_PROMPT},
            {"role": "user", "content": E1_USER_TEMPLATE.format(raw_log=raw_log)},
        ]

    @staticmethod
    def build_e2_messages(raw_log: str) -> List[Dict[str, str]]:
        """Builds strong structured E2 chat messages."""
        return [
            {"role": "system", "content": E2_SYSTEM_PROMPT},
            {"role": "user", "content": E2_USER_TEMPLATE.format(raw_log=raw_log)},
        ]

    @staticmethod
    def build_e3_messages(
        raw_log: str, demonstrations: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Builds few-shot E3 chat messages.
        Includes E2 system prompt followed by demonstration pairs (User / Assistant)
        and finally the target evaluation query.
        """
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": E2_SYSTEM_PROMPT}
        ]

        for demo in demonstrations:
            demo_raw_log = demo["raw_log"]
            demo_target = demo["target"]
            demo_json_str = json.dumps(demo_target, indent=2)

            messages.append(
                {
                    "role": "user",
                    "content": E2_USER_TEMPLATE.format(raw_log=demo_raw_log),
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": demo_json_str,
                }
            )

        messages.append(
            {"role": "user", "content": E2_USER_TEMPLATE.format(raw_log=raw_log)}
        )
        return messages

    @staticmethod
    def build_e4_messages(raw_log: str) -> List[Dict[str, str]]:
        """
        Builds fine-tuned E4 chat messages matching Phase 5 training format.
        Consists of concise system instruction and verbatim raw log.
        No few-shot demonstrations.
        """
        return [
            {"role": "system", "content": E4_SYSTEM_PROMPT},
            {"role": "user", "content": raw_log},
        ]

    @classmethod
    def get_prompt_hash(
        cls, experiment_id: str, demonstrations: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Returns stable SHA-256 hash representing the prompt template and any demos."""
        sample_log = "[TEST_LOG]"
        if experiment_id == "E1":
            msgs = cls.build_e1_messages(sample_log)
        elif experiment_id == "E2":
            msgs = cls.build_e2_messages(sample_log)
        elif experiment_id == "E3":
            msgs = cls.build_e3_messages(sample_log, demonstrations or [])
        elif experiment_id == "E4":
            msgs = cls.build_e4_messages(sample_log)
        else:
            raise ValueError(f"Unknown experiment_id: {experiment_id}")

        canonical_repr = json.dumps(msgs, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    @classmethod
    def create_prompt_manifest(
        cls,
        gen_config_dict: Dict[str, Any],
        demonstrations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Creates the frozen prompt manifest for auditability."""
        now_utc = datetime.now(timezone.utc).isoformat()
        gen_hash = compute_dict_sha256(gen_config_dict)

        demo_ids = [d["incident_id"] for d in demonstrations] if demonstrations else []

        manifest = {
            "version": PROMPT_VERSION,
            "created_at": now_utc,
            "generation_config_sha256": gen_hash,
            "experiments": {
                "E1": {
                    "prompt_id": "prompt_e1_zero_shot",
                    "prompt_version": PROMPT_VERSION,
                    "prompt_sha256": cls.get_prompt_hash("E1"),
                    "demonstration_count": 0,
                    "demonstration_ids": [],
                },
                "E2": {
                    "prompt_id": "prompt_e2_structured",
                    "prompt_version": PROMPT_VERSION,
                    "prompt_sha256": cls.get_prompt_hash("E2"),
                    "demonstration_count": 0,
                    "demonstration_ids": [],
                },
                "E3": {
                    "prompt_id": "prompt_e3_few_shot",
                    "prompt_version": PROMPT_VERSION,
                    "prompt_sha256": cls.get_prompt_hash("E3", demonstrations),
                    "demonstration_count": len(demo_ids),
                    "demonstration_ids": demo_ids,
                },
                "E4": {
                    "prompt_id": "prompt_e4_qlora",
                    "prompt_version": PROMPT_VERSION,
                    "prompt_sha256": cls.get_prompt_hash("E4"),
                    "demonstration_count": 0,
                    "demonstration_ids": [],
                },
            },
        }
        return manifest
