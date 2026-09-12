"""
Core domain enums for LocalOps AI incident triage.
Compatible with Pydantic v2.
"""

from enum import Enum


class IncidentType(str, Enum):
    """
    High-level incident taxonomy categories.
    Serialized values exactly match the uppercase strings.
    """

    DATABASE = "DATABASE"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    APPLICATION = "APPLICATION"
    SECURITY = "SECURITY"
    NETWORK = "NETWORK"
    MESSAGING = "MESSAGING"


class Severity(str, Enum):
    """
    Operational and business impact severity levels.
    Represents actual operational impact rather than raw log level.
    """

    P1_CRITICAL = "P1_CRITICAL"
    P2_HIGH = "P2_HIGH"
    P3_MEDIUM = "P3_MEDIUM"
    P4_LOW = "P4_LOW"
