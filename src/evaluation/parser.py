"""
Multi-layer parsing and validation pipeline for Phase 4: Baseline Evaluation.
Separates strict raw JSON compliance from conservative JSON extraction and Pydantic validation.
Captures granular error classifications without silently repairing invalid outputs.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from src.schemas.enums import IncidentType, Severity
from src.schemas.triage import LogTriageOutput


class OutputParser:
    """
    Evaluates model outputs across three distinct layers:
    1. Strict Raw JSON Compliance (pure JSON, no conversational markdown/prose)
    2. Conservative JSON Extraction (extracts markdown ```json or outermost { ... })
    3. Pydantic Validation (enforces LogTriageOutput contract, extra="forbid", strict enums)
    """

    @staticmethod
    def check_strict_raw_json(raw_text: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if raw_text is strictly valid JSON representing an object.
        Fails if any explanatory prose, markdown fences, or comments surround the JSON.
        """
        if not raw_text or not isinstance(raw_text, str):
            return False, None
        stripped = raw_text.strip()
        # Must start with { and end with }
        if not (stripped.startswith("{") and stripped.endswith("}")):
            return False, None
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                return True, data
            return False, None
        except Exception:
            return False, None

    @staticmethod
    def extract_json(raw_text: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Conservatively extract JSON from model output.
        Inspects:
        1. Markdown code fences: ```json ... ``` or ``` ... ```
        2. Outermost balanced brace boundaries { ... }
        """
        if not raw_text or not isinstance(raw_text, str):
            return False, None, None

        # First check if strict raw JSON passes
        strict_valid, strict_data = OutputParser.check_strict_raw_json(raw_text)
        if strict_valid and strict_data is not None:
            return True, raw_text.strip(), strict_data

        # 1. Check for markdown code fences
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return True, candidate, data
            except Exception:
                pass

        # 2. Check for outermost balanced brace boundaries
        first_brace = raw_text.find("{")
        last_brace = raw_text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            candidate = raw_text[first_brace : last_brace + 1].strip()
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return True, candidate, data
            except Exception:
                pass

        return False, None, None

    @staticmethod
    def validate_pydantic(
        json_dict: Optional[Dict[str, Any]]
    ) -> Tuple[bool, Optional[Dict[str, Any]], List[str], List[str]]:
        """
        Validates an extracted JSON dictionary against LogTriageOutput.
        Returns: (is_valid, parsed_dict_or_none, error_messages, error_types)
        """
        if json_dict is None:
            return False, None, ["No JSON object extracted to validate."], ["malformed_json"]

        error_messages: List[str] = []
        error_types: List[str] = []

        try:
            validated = LogTriageOutput.model_validate(json_dict)
            return True, validated.model_dump(), [], []
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(p) for p in err.get("loc", []))
                msg = err.get("msg", "")
                err_type = err.get("type", "")
                error_messages.append(f"Field '{loc}': {msg}")

                # Granular classification of error types
                if err_type == "extra_forbidden":
                    if "extra_field" not in error_types:
                        error_types.append("extra_field")
                elif err_type in ("missing", "value_error.missing"):
                    if "missing_field" not in error_types:
                        error_types.append("missing_field")
                elif "incident_type" in loc:
                    if "invalid_incident_type" not in error_types:
                        error_types.append("invalid_incident_type")
                elif "severity" in loc:
                    if "invalid_severity" not in error_types:
                        error_types.append("invalid_severity")
                elif "confidence" in loc:
                    if "invalid_confidence" not in error_types:
                        error_types.append("invalid_confidence")
                elif "evidence" in loc:
                    if "invalid_evidence" not in error_types:
                        error_types.append("invalid_evidence")
                else:
                    if "schema_violation" not in error_types:
                        error_types.append("schema_violation")

            # In addition to Pydantic errors, check enums explicitly if not already caught
            if "incident_type" in json_dict:
                val = json_dict["incident_type"]
                valid_types = {e.value for e in IncidentType}
                if val not in valid_types and "invalid_incident_type" not in error_types:
                    error_types.append("invalid_incident_type")
            else:
                if "missing_field" not in error_types:
                    error_types.append("missing_field")

            if "severity" in json_dict:
                val = json_dict["severity"]
                valid_sevs = {e.value for e in Severity}
                if val not in valid_sevs and "invalid_severity" not in error_types:
                    error_types.append("invalid_severity")
            else:
                if "missing_field" not in error_types:
                    error_types.append("missing_field")

            return False, None, error_messages, error_types

    @classmethod
    def parse_and_validate(
        cls, raw_output: str
    ) -> Tuple[bool, bool, Optional[str], Optional[Dict[str, Any]], bool, List[str], List[str]]:
        """
        Executes full 3-layer parsing pipeline on raw model output.
        Returns:
            (
                strict_json_valid,
                json_extraction_success,
                extracted_json_str,
                parsed_output_dict,
                pydantic_valid,
                error_messages,
                error_types
            )
        """
        strict_valid, _ = cls.check_strict_raw_json(raw_output)
        extract_success, extracted_str, extracted_dict = cls.extract_json(raw_output)

        if not extract_success or extracted_dict is None:
            return (
                False,
                False,
                None,
                None,
                False,
                ["Failed to parse or extract JSON from model output."],
                ["malformed_json"],
            )

        pydantic_valid, parsed_dict, errors, err_types = cls.validate_pydantic(extracted_dict)

        return (
            strict_valid,
            extract_success,
            extracted_str,
            parsed_dict,
            pydantic_valid,
            errors,
            err_types,
        )
