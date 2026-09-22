"""LocalOps AI — Grounding Validators.

Validators to detect unsupported IP addresses, hostnames, and numeric claims
in SLM-generated output against the original raw log.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set, Tuple

# Standard IPv4 regex pattern
IPV4_REGEX = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")

# Hostname / FQDN pattern (e.g., prod-db-01.us-east.internal, cluster.local, domain.com)
HOSTNAME_REGEX = re.compile(
    r"\b(?:[a-zA-Z0-9][-a-zA-Z0-9]*\.)+(?:internal|svc|cluster\.local|local|corp|net|org|com|io|gov)\b",
    re.IGNORECASE,
)

# Numeric impact claim patterns (percentages, replicas, users, failure counts)
NUMERIC_CLAIM_PATTERNS = [
    re.compile(r"\b(\d+%\s+(?:traffic|requests|users|failures|errors|packet loss|capacity|load))\b", re.IGNORECASE),
    re.compile(r"\b(\d+\s+replicas(?:\s+(?:failed|unavailable|oomkilled|down|crashed))?)\b", re.IGNORECASE),
    re.compile(r"\b(\d+\s+users(?:\s+(?:impacted|affected|unable|blocked))?)\b", re.IGNORECASE),
    re.compile(r"\b(\d+\s+(?:nodes|pods|instances|containers)(?:\s+(?:failed|crashed|evicted|down))?)\b", re.IGNORECASE),
]

# Trusted static vocabulary that does not constitute an invented hostname
TRUSTED_STATIC_VOCABULARY: Set[str] = {
    "localhost",
    "cluster.local",
    "internal",
    "svc",
    "svc.cluster.local",
    "127.0.0.1",
    "0.0.0.0",
}


def extract_ips(text: str) -> List[str]:
    """Extracts all IPv4 addresses found in the text."""
    if not text:
        return []
    return IPV4_REGEX.findall(text)


def detect_unsupported_ips(generated_text: str, raw_log: str) -> List[str]:
    """Returns all IP addresses present in generated_text that do NOT appear verbatim in raw_log."""
    if not generated_text:
        return []
    gen_ips = extract_ips(generated_text)
    raw_log_ips = set(extract_ips(raw_log))
    # Also check literal presence in raw_log in case formatting varies
    unsupported = [ip for ip in gen_ips if ip not in raw_log_ips and ip not in raw_log]
    return unsupported


def extract_hostnames(text: str) -> List[str]:
    """Extracts candidate hostnames and FQDNs from text."""
    if not text:
        return []
    return HOSTNAME_REGEX.findall(text)


def detect_unsupported_hostnames(
    generated_text: str,
    raw_log: str,
    affected_service: Optional[str] = None,
    extra_trusted: Optional[Set[str]] = None,
) -> List[str]:
    """Returns hostnames appearing in generated_text that are unsupported."""
    if not generated_text:
        return []
    
    trusted = set(TRUSTED_STATIC_VOCABULARY)
    if extra_trusted:
        trusted.update(extra_trusted)
    if affected_service:
        trusted.add(affected_service.lower())
        # Also add service name subparts
        for part in affected_service.lower().split("-"):
            trusted.add(part)

    gen_hosts = extract_hostnames(generated_text)
    raw_log_lower = raw_log.lower()
    unsupported: List[str] = []

    for host in gen_hosts:
        h_lower = host.lower()
        if h_lower in trusted:
            continue
        if h_lower in raw_log_lower or host in raw_log:
            continue
        unsupported.append(host)

    return unsupported


def detect_unsupported_numeric_claims(generated_text: str, raw_log: str) -> List[Tuple[str, str]]:
    """Detects unsupported numeric impact claims (e.g., '80% traffic affected', '500 users impacted').
    
    Returns list of (full_claim_match, number_part).
    """
    if not generated_text:
        return []
    
    unsupported: List[Tuple[str, str]] = []
    for pattern in NUMERIC_CLAIM_PATTERNS:
        for match in pattern.finditer(generated_text):
            full_match = match.group(1)
            digits = re.search(r"\d+", full_match)
            if not digits:
                continue
            num_str = digits.group(0)

            # 1. Percentage claims: must have matching percentage in raw_log
            if "%" in full_match:
                if not re.search(rf"\b{re.escape(num_str)}\s*%", raw_log):
                    unsupported.append((full_match, num_str))
            else:
                # 2. Entity count claims (e.g. 500 users, 12 replicas):
                # The number must exist in raw_log in a count/metric context,
                # NOT solely as an HTTP status code (e.g. status=500), port, or exitCode.
                if num_str not in raw_log:
                    unsupported.append((full_match, num_str))
                else:
                    # Check if the number only appears as an HTTP status code, port, or exit code
                    is_status_or_port_only = bool(
                        re.search(rf"(?:status|response_status|port|exitcode|code)=?{re.escape(num_str)}\b", raw_log, re.IGNORECASE)
                    ) and not bool(
                        re.search(rf"\b{re.escape(num_str)}\s*(?:users|clients|replicas|pods|nodes|records|messages|attempts|requests|fail)\b", raw_log, re.IGNORECASE)
                    ) and not bool(
                        re.search(rf"(?:total|active|idle|waiting|lag|count)=\d*", raw_log, re.IGNORECASE) and re.search(rf"={re.escape(num_str)}\b", raw_log)
                    )

                    if is_status_or_port_only:
                        unsupported.append((full_match, num_str))

    return unsupported
