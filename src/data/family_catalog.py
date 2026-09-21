"""
Canonical mapping and catalog utilities for IncidentFamily to IncidentType.
Guarantees 1-to-1 deterministic relationship across the 36 families and 6 categories.
"""

from src.schemas.enums import IncidentFamily, IncidentType

FAMILY_TO_CATEGORY_MAP: dict[IncidentFamily, IncidentType] = {
    # DATABASE (6 families)
    IncidentFamily.DB_CONNECTION_POOL_STARVATION: IncidentType.DATABASE,
    IncidentFamily.DB_DEADLOCK_OR_CONTENTION: IncidentType.DATABASE,
    IncidentFamily.DB_REPLICATION_LAG: IncidentType.DATABASE,
    IncidentFamily.DB_QUERY_TIMEOUT: IncidentType.DATABASE,
    IncidentFamily.DB_STORAGE_EXHAUSTION: IncidentType.DATABASE,
    IncidentFamily.DB_INDEX_OR_DATA_CORRUPTION: IncidentType.DATABASE,

    # INFRASTRUCTURE (6 families)
    IncidentFamily.INFRA_POD_OOMKILLED: IncidentType.INFRASTRUCTURE,
    IncidentFamily.INFRA_CPU_THROTTLING: IncidentType.INFRASTRUCTURE,
    IncidentFamily.INFRA_INODE_EXHAUSTION: IncidentType.INFRASTRUCTURE,
    IncidentFamily.INFRA_NODE_NOT_READY: IncidentType.INFRASTRUCTURE,
    IncidentFamily.INFRA_CRASHLOOP_BACKOFF: IncidentType.INFRASTRUCTURE,
    IncidentFamily.INFRA_STORAGE_EVICTION: IncidentType.INFRASTRUCTURE,

    # APPLICATION (6 families)
    IncidentFamily.APP_MEMORY_LEAK: IncidentType.APPLICATION,
    IncidentFamily.APP_THREAD_POOL_EXHAUSTION: IncidentType.APPLICATION,
    IncidentFamily.APP_UNHANDLED_EXCEPTION: IncidentType.APPLICATION,
    IncidentFamily.APP_SERIALIZATION_FAILURE: IncidentType.APPLICATION,
    IncidentFamily.APP_STACK_OVERFLOW: IncidentType.APPLICATION,
    IncidentFamily.APP_DEPENDENCY_INJECTION_FAILURE: IncidentType.APPLICATION,

    # SECURITY (6 families)
    IncidentFamily.SEC_CREDENTIAL_OR_TOKEN_EXPIRATION: IncidentType.SECURITY,
    IncidentFamily.SEC_PERMISSION_OR_RBAC_DENIED: IncidentType.SECURITY,
    IncidentFamily.SEC_SECRET_LEAKAGE: IncidentType.SECURITY,
    IncidentFamily.SEC_BRUTE_FORCE_ATTACK: IncidentType.SECURITY,
    IncidentFamily.SEC_CORS_POLICY_BLOCK: IncidentType.SECURITY,
    IncidentFamily.SEC_SSRF_OR_EGRESS_VIOLATION: IncidentType.SECURITY,

    # NETWORK (6 families)
    IncidentFamily.NET_DNS_RESOLUTION_FAILURE: IncidentType.NETWORK,
    IncidentFamily.NET_CONNECTION_REFUSED: IncidentType.NETWORK,
    IncidentFamily.NET_SOCKET_TIMEOUT: IncidentType.NETWORK,
    IncidentFamily.NET_TLS_HANDSHAKE_FAILURE: IncidentType.NETWORK,
    IncidentFamily.NET_INGRESS_GATEWAY_TIMEOUT: IncidentType.NETWORK,
    IncidentFamily.NET_PARTITION_OR_BLACKHOLE: IncidentType.NETWORK,

    # MESSAGING (6 families)
    IncidentFamily.MSG_CONSUMER_LAG_ACCUMULATION: IncidentType.MESSAGING,
    IncidentFamily.MSG_DEAD_LETTER_QUEUE_OVERFLOW: IncidentType.MESSAGING,
    IncidentFamily.MSG_PARTITION_LEADER_OFFLINE: IncidentType.MESSAGING,
    IncidentFamily.MSG_POISON_PILL_FAILURE: IncidentType.MESSAGING,
    IncidentFamily.MSG_QUEUE_STORAGE_BACKPRESSURE: IncidentType.MESSAGING,
    IncidentFamily.MSG_DUPLICATE_DELIVERY_OR_IDEMPOTENCY: IncidentType.MESSAGING,
}

# Compile-time validation: Ensure all 36 IncidentFamily members are present in the map
assert len(FAMILY_TO_CATEGORY_MAP) == len(IncidentFamily), (
    f"Expected {len(IncidentFamily)} families in mapping, got {len(FAMILY_TO_CATEGORY_MAP)}"
)
assert len(FAMILY_TO_CATEGORY_MAP) == 36, "Taxonomy must define exactly 36 families."


FAMILY_TO_INCIDENT_TYPE = FAMILY_TO_CATEGORY_MAP

CATEGORY_TO_FAMILIES: dict[IncidentType, list[IncidentFamily]] = {
    cat: [fam for fam, c in FAMILY_TO_CATEGORY_MAP.items() if c == cat]
    for cat in IncidentType
}


def get_incident_type_for_family(family: IncidentFamily) -> IncidentType:
    """Return the canonical IncidentType for a given IncidentFamily."""
    return FAMILY_TO_CATEGORY_MAP[family]


def get_category_for_family(family: IncidentFamily) -> IncidentType:
    """Alias for get_incident_type_for_family."""
    return get_incident_type_for_family(family)


def get_families_for_category(category: IncidentType) -> list[IncidentFamily]:
    """Return all 6 IncidentFamily members associated with a given IncidentType."""
    return CATEGORY_TO_FAMILIES[category]
