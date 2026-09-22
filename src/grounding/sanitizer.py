"""LocalOps AI — Grounding Output Sanitizer.

Inspects generated fields (root_cause, suggested_action) against the original raw log
and sanitizes unsupported IP addresses, hostnames, and numeric claims via minimal rewriting.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, Union

from src.grounding.schemas import GroundingTelemetry, SanitizedOutput
from src.grounding.validators import (
    detect_unsupported_hostnames,
    detect_unsupported_ips,
    detect_unsupported_numeric_claims,
)


class GroundingSanitizer:
    """Sanitizes SLM generation by removing or rewriting unsupported hallucinated facts."""

    def __init__(self, extra_trusted_hosts: Optional[set] = None):
        self.extra_trusted_hosts = extra_trusted_hosts or set()

    def sanitize(
        self,
        output_dict_or_obj: Union[Dict[str, Any], Any],
        raw_log: str,
    ) -> Tuple[Dict[str, Any], GroundingTelemetry]:
        """Sanitizes output dictionary or model object against the raw log.
        
        Returns (sanitized_dict, telemetry).
        """
        # Convert to dictionary if necessary
        if hasattr(output_dict_or_obj, "model_dump"):
            data = output_dict_or_obj.model_dump()
        elif isinstance(output_dict_or_obj, dict):
            data = dict(output_dict_or_obj)
        else:
            raise ValueError("output_dict_or_obj must be a dict or Pydantic model")

        telemetry = GroundingTelemetry()
        affected_service = data.get("affected_service")

        for field_name in ("root_cause", "suggested_action"):
            if field_name not in data or not isinstance(data[field_name], str):
                continue

            orig_text = data[field_name]
            sanitized_text, field_corrections = self.sanitize_text(
                text=orig_text,
                raw_log=raw_log,
                affected_service=affected_service,
            )

            if orig_text != sanitized_text:
                data[field_name] = sanitized_text
                telemetry.rewritten_fields.append(field_name)
                telemetry.grounding_corrections_count += field_corrections["total"]
                telemetry.unsupported_ip_removed += field_corrections["ips"]
                telemetry.unsupported_hostname_removed += field_corrections["hostnames"]
                telemetry.unsupported_numeric_claim_removed += field_corrections["numbers"]
                telemetry.corrections_applied.extend(field_corrections["details"])

        return data, telemetry

    def sanitize_text(
        self,
        text: str,
        raw_log: str,
        affected_service: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Sanitizes a single text string against the raw log."""
        if not text:
            return text, {"total": 0, "ips": 0, "hostnames": 0, "numbers": 0, "details": []}

        corrections = {"total": 0, "ips": 0, "hostnames": 0, "numbers": 0, "details": []}
        current = text

        # ---------------------------------------------------------------------
        # 1. Detect and rewrite unsupported IPs
        # ---------------------------------------------------------------------
        unsupported_ips = detect_unsupported_ips(current, raw_log)
        for ip in unsupported_ips:
            # Canonical specific rewrites requested by policy
            if "database lock" in current.lower() and ip in current:
                # Example: "Database lock timeout on 203.0.113.1." -> "Database lock contention caused the transaction to abort."
                current = re.sub(
                    rf"(?i)database lock [^.]*?(?:on|at|from)\s+{re.escape(ip)}\.?",
                    "Database lock contention caused the transaction to abort.",
                    current,
                )
            elif "exceeded memory on host" in current.lower() and ip in current:
                # Example: "Process exceeded memory on host 203.0.113.5, triggering OOM." -> "Process memory exceeded the container limit, triggering OOM termination."
                current = re.sub(
                    rf"(?i)process exceeded memory on host\s+{re.escape(ip)},\s*triggering oom\.?",
                    "Process memory exceeded the container limit, triggering OOM termination.",
                    current,
                )
            elif "filesystem filled on host" in current.lower() and ip in current:
                # Example: "Filesystem filled on host 192.0.2.1." -> "Filesystem capacity became critically low, triggering DiskPressure and pod eviction."
                current = re.sub(
                    rf"(?i)filesystem filled on host\s+{re.escape(ip)}\.?",
                    "Filesystem capacity became critically low, triggering DiskPressure and pod eviction.",
                    current,
                )

            # General IP removal / cleanup if the IP is still present in current
            if ip in current:
                # Pattern: (on|at|from|to|host|node|server|ip)\s+(host\s+|node\s+|server\s+)?IP
                pattern_prefix = rf"(?i)\b(?:on|at|from|to|server|host|node|ip)\s+(?:host\s+|node\s+|server\s+)?{re.escape(ip)}\b"
                if re.search(pattern_prefix, current):
                    current = re.sub(pattern_prefix, "", current)
                else:
                    current = current.replace(ip, "")

            corrections["ips"] += 1
            corrections["total"] += 1
            corrections["details"].append(f"Removed unsupported IP: {ip}")

        # ---------------------------------------------------------------------
        # 2. Detect and rewrite unsupported Hostnames
        # ---------------------------------------------------------------------
        unsupported_hosts = detect_unsupported_hostnames(
            current,
            raw_log,
            affected_service=affected_service,
            extra_trusted=self.extra_trusted_hosts,
        )
        for host in unsupported_hosts:
            pattern_prefix = rf"(?i)\b(?:on|at|from|to|server|host|node)\s+(?:host\s+|node\s+|server\s+)?{re.escape(host)}\b"
            if re.search(pattern_prefix, current):
                current = re.sub(pattern_prefix, "", current)
            else:
                current = current.replace(host, "")

            corrections["hostnames"] += 1
            corrections["total"] += 1
            corrections["details"].append(f"Removed unsupported hostname: {host}")

        # ---------------------------------------------------------------------
        # 3. Detect and rewrite unsupported Numeric Claims
        # ---------------------------------------------------------------------
        unsupported_nums = detect_unsupported_numeric_claims(current, raw_log)
        for full_match, num_str in unsupported_nums:
            # E.g. "80% traffic affected" -> "traffic affected"
            # E.g. "12 replicas failed" -> "replicas failed"
            # E.g. "500 users impacted" -> "users impacted"
            cleaned_claim = re.sub(rf"\b{re.escape(num_str)}%?\s*", "", full_match).strip()
            current = current.replace(full_match, cleaned_claim)

            corrections["numbers"] += 1
            corrections["total"] += 1
            corrections["details"].append(f"Removed unsupported numeric claim: {full_match} -> {cleaned_claim}")

        # ---------------------------------------------------------------------
        # 4. Clean up punctuation and whitespace after removals
        # ---------------------------------------------------------------------
        current = re.sub(r"[ \t]+", " ", current)
        current = re.sub(r"\s+([,.:;])", r"\1", current)
        current = re.sub(r"\.{2,}", ".", current)
        current = re.sub(r",\s*,", ",", current)
        current = current.strip()

        return current, corrections
