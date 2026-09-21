"""
Base framework, deterministic slot fillers, structural fingerprinting,
and benign noise generators for LocalOps AI log templates.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional
import random

from src.data.models import (
    DatasetSplit,
    DiagnosticClarity,
    ImpactScenario,
    NoiseProfile,
    RecordMetadata,
)
from src.schemas.enums import IncidentFamily, Severity
from src.schemas.triage import LogTriageOutput
from src.data.family_catalog import get_incident_type_for_family


# =========================================================================
# Structural Template Fingerprinting (Amendment 2)
# =========================================================================

_RE_ISO_TIMESTAMP = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b")
_RE_SYSLOG_TIMESTAMP = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b")
_RE_IPV4 = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_RE_UUID_HEX = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b|\b[0-9a-fA-F]{16,64}\b")
_RE_PORT = re.compile(r"(?<=[:/])\b\d{2,5}\b")
_RE_NUM = re.compile(r"\b\d+(?:\.\d+)?(?:ms|s|m|MB|GB|KB|Gi|Mi|Ki|%|B)?\b")
_RE_WHITESPACE = re.compile(r"\s+")


def normalize_structural_fingerprint(text: str) -> str:
    """
    Normalizes variable slots (timestamps, IPs, UUIDs/hex, ports, metrics) into
    placeholders.
    """
    normalized = _RE_ISO_TIMESTAMP.sub("<TIMESTAMP>", text)
    normalized = _RE_SYSLOG_TIMESTAMP.sub("<TIMESTAMP>", normalized)
    normalized = _RE_IPV4.sub("<IP>", normalized)
    normalized = _RE_UUID_HEX.sub("<HEX_ID>", normalized)
    normalized = _RE_PORT.sub("<PORT>", normalized)
    normalized = _RE_NUM.sub("<NUM>", normalized)
    normalized = _RE_WHITESPACE.sub(" ", normalized).strip()
    return normalized


def compute_structural_fingerprint(text: str) -> str:
    """
    Normalizes variable slots and returns a SHA-256 hash prefix of the structural signature.
    Prevents template-level leakage across splits.
    """
    normalized = normalize_structural_fingerprint(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


# =========================================================================
# Safe Deterministic Identifiers & Value Pools (Amendments 1, 6, 7)
# =========================================================================

# Safe RFC 5737 Documentation IP ranges
SAFE_IPS = [
    "192.0.2.10", "192.0.2.15", "192.0.2.45", "192.0.2.120", "192.0.2.200",
    "198.51.100.12", "198.51.100.24", "198.51.100.58", "198.51.100.140",
    "203.0.113.8", "203.0.113.19", "203.0.113.77", "203.0.113.105"
]

SAFE_SERVICES = [
    "checkout-service", "payment-worker", "auth-gateway", "orders-service",
    "inventory-manager", "user-profile", "billing-aggregator", "shipping-router",
    "notification-dispatcher", "search-indexer", "catalog-api", "event-processor"
]

SAFE_NAMESPACES = ["production", "core-platform", "payment-mesh", "ingress-tier"]

BASE_EPOCH = datetime(2026, 9, 14, 0, 0, 0, tzinfo=timezone.utc)


def generate_deterministic_timestamp(rng: random.Random) -> str:
    """Generate a reproducible ISO-8601 timestamp with no reliance on wall-clock time."""
    offset_seconds = rng.randint(0, 86400 * 30)  # within a 30-day window
    offset_micros = rng.randint(0, 999999)
    ts = BASE_EPOCH + timedelta(seconds=offset_seconds, microseconds=offset_micros)
    return ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# =========================================================================
# Benign Noise & Distractor Pools (Amendment 3)
# =========================================================================

BENIGN_DISTRACTOR_TEMPLATES = [
    "[{ts}] [INFO] [{service}] Normal HTTP GET /healthz returned 200 in {num}ms",
    "[{ts}] [DEBUG] [{service}] Cache miss on key user_session:{hex_id}; falling back to secondary cache (resolved in {num}ms)",
    "[{ts}] [WARN] [{service}] Configuration warning: Property 'client.read-timeout-ms' is deprecated and will be removed in v3.0",
    "[{ts}] [INFO] [{service}] Optional metrics telemetry flush to {ip}:8125 succeeded after 1 transient retry",
    "[{ts}] [INFO] [{service}] Connection to downstream recommendation-engine established (pool_size=10, idle=8)",
    "[{ts}] [DEBUG] [{service}] GC completed in {num}ms. Eden: 12MB->0MB, Survivor: 2MB->2MB",
    "[{ts}] [INFO] [{service}] Successfully refreshed public JWKS key rotation cache from auth provider",
    "[{ts}] [WARN] [{service}] Non-blocking notice: Rate limit token bucket at 42% capacity on interface eth0",
    "[{ts}] [INFO] [{service}] Processed batch request id={hex_id} status=200 payload_size={num}KB",
    "[{ts}] [INFO] [{service}] Periodic heartbeat acknowledged by cluster orchestrator"
]


def generate_coherent_timestamps(
    rng: random.Random,
    base_dt: datetime,
    count_pre: int,
    count_post: int,
) -> tuple[list[str], str, list[str]]:
    """
    Generate coherent, strictly chronological timestamps relative to base_dt.
    Pre-incident: -120s to -1s (sorted ascending)
    Incident: 0s (base_dt)
    Post-incident: +31s to +180s (sorted ascending)
    """
    pre_ts = []
    if count_pre > 0:
        offsets = sorted(rng.sample(range(-120, -1), k=count_pre))
        for off in offsets:
            dt = base_dt + timedelta(seconds=off, milliseconds=rng.randint(0, 999))
            pre_ts.append(dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")

    incident_ts = base_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    post_ts = []
    if count_post > 0:
        offsets = sorted(rng.sample(range(31, 181), k=count_post))
        for off in offsets:
            dt = base_dt + timedelta(seconds=off, milliseconds=rng.randint(0, 999))
            post_ts.append(dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")

    return pre_ts, incident_ts, post_ts


# =========================================================================
# Benign Noise & Distractor Pools (Amendment 3 & 9)
# =========================================================================

BENIGN_DISTRACTOR_TEMPLATES = [
    "[{ts}] [INFO] [{service}] Normal HTTP GET /healthz returned 200 in {num}ms",
    "[{ts}] [DEBUG] [{service}] Cache miss on key user_session:{hex_id}; falling back to secondary cache (resolved in {num}ms)",
    "[{ts}] [WARN] [{service}] Configuration notice: Property 'client.read-timeout-ms' is deprecated and will be removed in v3.0",
    "[{ts}] [INFO] [{service}] Optional metrics telemetry flush to {ip}:8125 succeeded after 1 transient retry",
    "[{ts}] [INFO] [{service}] Connection to downstream recommendation-engine established (pool_size=10, idle=8)",
    "[{ts}] [DEBUG] [{service}] GC completed in {num}ms. Eden: 12MB->0MB, Survivor: 2MB->2MB",
    "[{ts}] [INFO] [{service}] Successfully refreshed public JWKS key rotation cache from auth provider",
    "[{ts}] [INFO] [{service}] Non-blocking notice: Rate limit token bucket at 42% capacity on interface eth0",
    "[{ts}] [INFO] [{service}] Processed batch request id={hex_id} status=200 payload_size={num}KB",
    "[{ts}] [INFO] [{service}] Periodic heartbeat acknowledged by cluster orchestrator",
    "[{ts}] [INFO] [{service}] TLS session resumption ticket validated for peer {ip}",
    "[{ts}] [DEBUG] [{service}] In-memory queue drain completed with 0 remaining tasks in buffer",
]


def render_noise_lines(
    rng: random.Random,
    service: str,
    profile: NoiseProfile,
    pre_timestamps: list[str],
    post_timestamps: list[str],
) -> tuple[list[str], list[str]]:
    """
    Generate leading and trailing benign distractor lines with coherent timestamps.
    Maintains invariant: zero competing incidents injected.
    """
    if profile == NoiseProfile.NONE:
        return [], []

    leading = [
        rng.choice(BENIGN_DISTRACTOR_TEMPLATES).format(
            ts=ts,
            service=service,
            ip=rng.choice(SAFE_IPS),
            hex_id=f"{rng.getrandbits(32):08x}",
            num=rng.randint(2, 85),
        )
        for ts in pre_timestamps
    ]
    trailing = [
        rng.choice(BENIGN_DISTRACTOR_TEMPLATES).format(
            ts=ts,
            service=service,
            ip=rng.choice(SAFE_IPS),
            hex_id=f"{rng.getrandbits(32):08x}",
            num=rng.randint(2, 85),
        )
        for ts in post_timestamps
    ]
    return leading, trailing


# =========================================================================
# Core LogTemplate Definition (Amendments 1, 4, 5, 6, 11)
# =========================================================================

@dataclass
class LogTemplate:
    """
    Structural log template representing a specific technology/runtime manifestation.
    Immutable to its assigned split.
    """

    template_id: str
    family: IncidentFamily
    technology: str
    runtime: str
    assigned_split: DatasetSplit

    # Log text generator: returns list of diagnostic log lines (including impact line)
    # Must accept: (rng, service, ip, ts, impact_line, hex_id, num) -> list[str]
    log_generator: Callable[..., list[str]]

    # Evidence generator: returns exact verbatim substrings that MUST appear in the generated log
    # Must accept: (service, ip, impact_line, hex_id, num) -> list[str]
    evidence_generator: Callable[..., list[str]]

    # Scenarios mapping to different operational severities & diagnostic clarity
    impact_scenarios: list[ImpactScenario]

    # Curated variant phrasing pools (Amendment 5)
    root_cause_variants: dict[str, str]
    action_variants: dict[str, str]

    # Fine-grained template manifestation (Amendment 11)
    signature_profile: str = ""

    # Semantic QA Assertions (Phase 3 Semantic QA)
    failure_mechanism: str = ""
    expected_tokens: list[str] = field(default_factory=list)
    forbidden_tokens: list[str] = field(default_factory=list)
    expected_status_code: Optional[int] = None
    observed_failure_mechanism: str = ""
    possible_hypotheses: list[str] = field(default_factory=list)

    def render_record(
        self,
        rng: random.Random,
        sample_index: int,
        seed: int,
        noise_profile: NoiseProfile,
        generator_version: str = "1.1.0",
    ) -> tuple[str, LogTriageOutput, RecordMetadata, str]:
        """
        Renders a complete, fully deterministic DatasetRecord.
        Returns: (incident_id, target, metadata, raw_log)
        """
        # 1. Deterministic Incident ID (Amendment 1)
        id_hash = hashlib.sha256(f"{seed}:{self.family.value}:{self.template_id}:{sample_index}".encode()).hexdigest()[:10]
        incident_id = f"inc_{self.family.value.lower()}_{self.template_id.lower()}_{id_hash}"

        # 2. Pick deterministic slots and base timestamp
        service = rng.choice(SAFE_SERVICES)
        ip = rng.choice(SAFE_IPS)
        hex_id = f"{rng.getrandbits(32):08x}"
        num = rng.randint(5, 500)

        base_offset_sec = rng.randint(0, 86400 * 30)
        base_offset_micro = rng.randint(0, 999999)
        base_dt = BASE_EPOCH + timedelta(seconds=base_offset_sec, microseconds=base_offset_micro)

        # Dynamic semantic timestamps relative to base_dt (Coherent historical events)
        token_expiry_dt = base_dt - timedelta(seconds=num)
        token_expiry_ts = token_expiry_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        alb_event_ts = base_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        cert_not_after_dt = base_dt - timedelta(seconds=num * 30 + 3600)
        cert_not_after_ts = cert_not_after_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        prev_exec_dt = base_dt - timedelta(seconds=num + 30)
        prev_exec_ts = prev_exec_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        semantic_slots = {
            "base_dt": base_dt,
            "token_expiry_ts": token_expiry_ts,
            "alb_event_ts": alb_event_ts,
            "cert_not_after_ts": cert_not_after_ts,
            "prev_exec_ts": prev_exec_ts,
        }

        # 3. Coherent timestamps for noise and incident (Amendment 4)
        if noise_profile == NoiseProfile.NONE:
            count_pre, count_post = 0, 0
        elif noise_profile == NoiseProfile.LIGHT:
            count_pre, count_post = 1, 1
        else:  # MEDIUM
            count_pre, count_post = rng.randint(2, 3), rng.randint(1, 3)

        pre_ts, incident_ts, post_ts = generate_coherent_timestamps(rng, base_dt, count_pre, count_post)

        # 4. Select impact scenario (determines severity) (Amendments 1 & 8)
        scenario = rng.choice(self.impact_scenarios)
        severity = scenario.severity

        # 5. Decouple Diagnostic Clarity from Severity (Amendment 2)
        clarity = rng.choice([DiagnosticClarity.EXPLICIT, DiagnosticClarity.CLEAR, DiagnosticClarity.AMBIGUOUS])

        impact_line = scenario.impact_line.format(
            service=service, ip=ip, hex_id=hex_id, num=num, ts=incident_ts
        )

        # 6. Generate core incident lines
        try:
            incident_lines = self.log_generator(
                rng=rng,
                service=service,
                ip=ip,
                ts=incident_ts,
                impact_line=impact_line,
                hex_id=hex_id,
                num=num,
                **semantic_slots,
            )
        except TypeError:
            incident_lines = self.log_generator(
                rng=rng,
                service=service,
                ip=ip,
                ts=incident_ts,
                impact_line=impact_line,
                hex_id=hex_id,
                num=num,
            )

        # 7. Generate noise lines with coherent chronological timestamps
        leading_noise, trailing_noise = render_noise_lines(
            rng=rng,
            service=service,
            profile=noise_profile,
            pre_timestamps=pre_ts,
            post_timestamps=post_ts,
        )
        full_lines = leading_noise + incident_lines + trailing_noise
        raw_log = "\n".join(full_lines)

        # 8. Extract verbatim evidence and guarantee affected_service appears
        try:
            evidence_items = self.evidence_generator(
                service=service,
                ip=ip,
                impact_line=impact_line,
                hex_id=hex_id,
                num=num,
                **semantic_slots,
            )
        except TypeError:
            evidence_items = self.evidence_generator(
                service=service,
                ip=ip,
                impact_line=impact_line,
                hex_id=hex_id,
                num=num,
            )
        for ev in evidence_items:
            assert ev in raw_log, f"Evidence '{ev}' not found in raw_log for template {self.template_id}"
        assert service in raw_log, f"Service '{service}' not found in raw_log for template {self.template_id}"

        # 9. Split-Aware Target Text Pools (Amendment 10)
        if self.assigned_split == DatasetSplit.TRAIN:
            candidate_rc = [k for k in self.root_cause_variants if k.startswith("RC_TRAIN") or k in ("RC_1", "RC_2", "RC_3")]
            candidate_act = [k for k in self.action_variants if k.startswith("ACT_TRAIN") or k in ("ACT_1", "ACT_2", "ACT_3")]
        elif self.assigned_split == DatasetSplit.VALIDATION:
            candidate_rc = [k for k in self.root_cause_variants if k.startswith("RC_VAL") or k in ("RC_4", "RC_VAL_1", "RC_VAL_2")]
            candidate_act = [k for k in self.action_variants if k.startswith("ACT_VAL") or k in ("ACT_4", "ACT_VAL_1", "ACT_VAL_2")]
        else:  # TEST
            candidate_rc = [k for k in self.root_cause_variants if k.startswith("RC_TEST") or k in ("RC_5", "RC_TEST_1", "RC_TEST_2")]
            candidate_act = [k for k in self.action_variants if k.startswith("ACT_TEST") or k in ("ACT_5", "ACT_TEST_1", "ACT_TEST_2")]

        rc_pool = candidate_rc if candidate_rc else list(self.root_cause_variants.keys())
        act_pool = candidate_act if candidate_act else list(self.action_variants.keys())

        rc_key = scenario.root_cause_key if (scenario.root_cause_key and scenario.root_cause_key in rc_pool) else rng.choice(rc_pool)
        act_key = scenario.action_key if (scenario.action_key and scenario.action_key in act_pool) else rng.choice(act_pool)

        root_cause_text = self.root_cause_variants[rc_key].format(service=service, ip=ip, num=num)
        action_text = self.action_variants[act_key].format(service=service, ip=ip, num=num)

        # 10. Semantic QA Assertions Check
        for exp in self.expected_tokens:
            assert exp in raw_log or exp in root_cause_text, (
                f"Expected token '{exp}' not found in raw_log/root_cause for template {self.template_id}"
            )
        for forb in self.forbidden_tokens:
            assert forb not in raw_log, (
                f"Forbidden token '{forb}' found in raw_log for template {self.template_id}"
            )
            assert forb not in root_cause_text, (
                f"Forbidden token '{forb}' found in root_cause for template {self.template_id}"
            )
            assert forb not in action_text, (
                f"Forbidden token '{forb}' found in suggested_action for template {self.template_id}"
            )
        if self.expected_status_code:
            code_str = str(self.expected_status_code)
            assert code_str in raw_log, (
                f"Expected status code '{code_str}' not found in raw_log for template {self.template_id}"
            )

        # 11. Deterministic Confidence Derivation (Amendment 3)
        if clarity == DiagnosticClarity.EXPLICIT:
            confidence = round(0.91 + (rng.random() * 0.07), 2)  # 0.91 - 0.98
        elif clarity == DiagnosticClarity.CLEAR:
            confidence = round(0.79 + (rng.random() * 0.09), 2)  # 0.79 - 0.88
        else:  # AMBIGUOUS
            confidence = round(0.61 + (rng.random() * 0.11), 2)  # 0.61 - 0.72

        # 12. Build and validate target LogTriageOutput
        target = LogTriageOutput(
            incident_type=get_incident_type_for_family(self.family),
            severity=severity,
            affected_service=service,
            root_cause=root_cause_text,
            suggested_action=action_text,
            confidence=confidence,
            evidence=evidence_items,
        )

        # 13. Construct metadata (Amendment 11 & Semantic QA)
        sig_profile = self.signature_profile or f"{self.template_id}_{self.family.value[:10]}"
        failure_mech = self.failure_mechanism or sig_profile
        metadata = RecordMetadata(
            incident_family=self.family,
            template_id=self.template_id,
            split=self.assigned_split.value,
            technology=self.technology,
            runtime=self.runtime,
            signature_profile=sig_profile,
            environment="production",
            noise_profile=noise_profile.value,
            diagnostic_clarity=clarity.value,
            root_cause_variant_id=rc_key,
            action_variant_id=act_key,
            failure_mechanism=failure_mech,
            generator_version=generator_version,
        )

        return incident_id, target, metadata, raw_log
