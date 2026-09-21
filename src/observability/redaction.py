"""LocalOps AI — Privacy Redaction Utilities.

Strips sensitive tokens, passwords, bearer tokens, API keys, and certificates
from text before diagnostic logging.
"""

from __future__ import annotations

import re
from typing import Dict, List, Pattern, Tuple

SECRET_PATTERNS: List[Tuple[str, Pattern]] = [
    # Passwords in URLs or JSON or logs: password=xyz, "password": "xyz"
    ("PASSWORD", re.compile(r'(?i)(password|passwd|pwd|secret|api[_-]?key|token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.!@#$%^&*()+=]{4,})["\']?')),
    # Bearer tokens
    ("BEARER_TOKEN", re.compile(r'(?i)bearer\s+[a-zA-Z0-9_\-\.]{16,}')),
    # JWT tokens
    ("JWT", re.compile(r'ey[a-zA-Z0-9_-]{10,}\.ey[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}')),
    # Private Key blocks
    ("PRIVATE_KEY", re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    # AWS Access Keys
    ("AWS_KEY", re.compile(r'\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b')),
    # Generic API Keys / Hex Hashes (32 to 64 chars)
    ("API_KEY", re.compile(r'(?i)(?:api[_-]?key|client[_-]?secret)\s*[:=]\s*["\']?([a-fA-F0-9]{32,64})["\']?')),
]


def redact_secrets(text: str) -> str:
    """Replaces detected secrets with sanitized redaction masks."""
    if not text:
        return ""

    sanitized = text

    # Handle Private Key block first
    sanitized = re.sub(
        r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        '[REDACTED_PRIVATE_KEY]',
        sanitized,
    )

    # Bearer tokens
    sanitized = re.sub(
        r'(?i)bearer\s+[a-zA-Z0-9_\-\.]{16,}',
        'Bearer [REDACTED_BEARER_TOKEN]',
        sanitized,
    )

    # JWTs
    sanitized = re.sub(
        r'ey[a-zA-Z0-9_-]{10,}\.ey[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}',
        '[REDACTED_JWT]',
        sanitized,
    )

    # AWS Keys
    sanitized = re.sub(
        r'\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b',
        '[REDACTED_AWS_KEY]',
        sanitized,
    )

    # Key-value password/secret pairs
    def kv_replacer(match):
        key = match.group(1)
        return f"{key}=[REDACTED]"

    sanitized = re.sub(
        r'(?i)(password|passwd|pwd|secret|api[_-]?key|token)\s*[:=]\s*["\']?[a-zA-Z0-9_\-\.!@#$%^&*()+=]{4,}["\']?',
        kv_replacer,
        sanitized,
    )

    return sanitized
