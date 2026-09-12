"""Unit tests for LocalOps AI Incident Taxonomy and Output Schema."""

import json
import pytest
from pydantic import ValidationError

from src.schemas.enums import IncidentFamily, IncidentType, Severity
from src.schemas.triage import LogTriageOutput


@pytest.fixture
def valid_payload():
    """Returns a dictionary representing a valid triage output."""
    return {
        "incident_type": "DATABASE",
        "severity": "P1_CRITICAL",
        "confidence": 0.95,
        "affected_service": "payment-postgres-cluster",
        "root_cause": "Connection pool exhaustion due to unclosed client sessions in payment-worker.",
        "suggested_action": "Restart payment-worker pods and scale up max_connections on primary node.",
        "evidence": [
            "FATAL: remaining connection slots are reserved",
            "Timeout: Pool empty, max pool size 100 reached",
        ],
    }


# =========================================================================
# Enum Tests
# =========================================================================

def test_incident_type_enum_members():
    """Verify all 6 required incident types are defined with correct values."""
    expected = {
        "DATABASE",
        "INFRASTRUCTURE",
        "APPLICATION",
        "SECURITY",
        "NETWORK",
        "MESSAGING",
    }
    actual = {item.value for item in IncidentType}
    assert actual == expected
    assert len(IncidentType) == 6


def test_severity_enum_members():
    """Verify all 4 required severity tiers are defined with correct values."""
    expected = {
        "P1_CRITICAL",
        "P2_HIGH",
        "P3_MEDIUM",
        "P4_LOW",
    }
    actual = {item.value for item in Severity}
    assert actual == expected
    assert len(Severity) == 4


def test_incident_family_count_and_uniqueness():
    """Verify exactly 36 expected enum members exist and all values are unique."""
    assert len(IncidentFamily) == 36
    values = [member.value for member in IncidentFamily]
    assert len(values) == len(set(values)), "IncidentFamily values must be unique"
    # Ensure all values are uppercase strings
    assert all(val.isupper() and isinstance(val, str) for val in values)


def test_incident_family_serialization():
    """Verify representative family values serialize correctly as strings and JSON."""
    assert IncidentFamily.DB_CONNECTION_POOL_STARVATION == "DB_CONNECTION_POOL_STARVATION"
    assert IncidentFamily.INFRA_POD_OOMKILLED.value == "INFRA_POD_OOMKILLED"
    assert json.dumps(IncidentFamily.NET_DNS_RESOLUTION_FAILURE) == '"NET_DNS_RESOLUTION_FAILURE"'


def test_incident_family_unknown_value_rejected():
    """Verify unknown family value raises ValueError when validating IncidentFamily."""
    with pytest.raises(ValueError):
        IncidentFamily("NON_EXISTENT_FAILURE_FAMILY")


# =========================================================================
# Valid Instantiation & Serialization Tests
# =========================================================================

def test_valid_payload_parsing(valid_payload):
    """Verify valid payload instantiates LogTriageOutput with exact types and values."""
    triage = LogTriageOutput(**valid_payload)
    assert triage.incident_type == IncidentType.DATABASE
    assert triage.severity == Severity.P1_CRITICAL
    assert triage.confidence == 0.95
    assert triage.affected_service == valid_payload["affected_service"]
    assert triage.root_cause == valid_payload["root_cause"]
    assert triage.suggested_action == valid_payload["suggested_action"]
    assert triage.evidence == valid_payload["evidence"]


def test_instantiation_with_enum_instances(valid_payload):
    """Verify model accepts explicit enum instances as well as string values."""
    payload = valid_payload.copy()
    payload["incident_type"] = IncidentType.INFRASTRUCTURE
    payload["severity"] = Severity.P2_HIGH

    triage = LogTriageOutput(**payload)
    assert triage.incident_type == IncidentType.INFRASTRUCTURE
    assert triage.severity == Severity.P2_HIGH


def test_serialization_dict_and_json(valid_payload):
    """Verify model_dump and model_dump_json produce valid, conformant output."""
    triage = LogTriageOutput(**valid_payload)

    # model_dump()
    data_dict = triage.model_dump()
    assert isinstance(data_dict, dict)
    assert data_dict["incident_type"] == "DATABASE"
    assert data_dict["severity"] == "P1_CRITICAL"
    assert data_dict["confidence"] == 0.95
    assert data_dict["affected_service"] == valid_payload["affected_service"]
    assert data_dict["root_cause"] == valid_payload["root_cause"]
    assert data_dict["suggested_action"] == valid_payload["suggested_action"]
    assert len(data_dict["evidence"]) == 2

    # model_dump_json()
    json_str = triage.model_dump_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["incident_type"] == "DATABASE"
    assert parsed["severity"] == "P1_CRITICAL"
    assert parsed["confidence"] == 0.95
    assert parsed["affected_service"] == valid_payload["affected_service"]

    # round-trip parse from JSON
    reconstructed = LogTriageOutput.model_validate_json(json_str)
    assert reconstructed == triage


# =========================================================================
# Missing Required Fields Tests
# =========================================================================

@pytest.mark.parametrize(
    "missing_field",
    [
        "incident_type",
        "severity",
        "confidence",
        "affected_service",
        "root_cause",
        "suggested_action",
        "evidence",
    ],
)
def test_missing_required_fields_raise_validation_error(valid_payload, missing_field):
    """Verify omitting any required field raises a Pydantic ValidationError."""
    payload = valid_payload.copy()
    del payload[missing_field]
    with pytest.raises(ValidationError) as exc_info:
        LogTriageOutput(**payload)
    errors = exc_info.value.errors()
    assert any(err["loc"] == (missing_field,) for err in errors)


# =========================================================================
# Forbidden Extra Fields Tests
# =========================================================================

def test_unexpected_fields_raise_validation_error(valid_payload):
    """Verify unexpected extra fields are rejected via ConfigDict(extra='forbid')."""
    payload = valid_payload.copy()
    payload["unexpected_field"] = "unexpected_value"
    with pytest.raises(ValidationError) as exc_info:
        LogTriageOutput(**payload)
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("unexpected_field",) for err in errors)


# =========================================================================
# Invalid Enum Values Tests
# =========================================================================

def test_invalid_incident_type_raises(valid_payload):
    """Verify invalid incident type fails validation."""
    payload = valid_payload.copy()
    payload["incident_type"] = "STORAGE"  # not in taxonomy
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload)


def test_invalid_severity_raises(valid_payload):
    """Verify invalid severity fails validation."""
    payload = valid_payload.copy()
    payload["severity"] = "CRITICAL"  # must be P1_CRITICAL
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload)

    payload["severity"] = "P5_NEGLIGIBLE"
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload)


# =========================================================================
# Confidence Bounds & Types Tests
# =========================================================================

def test_confidence_boundary_values(valid_payload):
    """Verify 0.0 and 1.0 are valid boundary values for confidence."""
    payload = valid_payload.copy()
    payload["confidence"] = 0.0
    triage_min = LogTriageOutput(**payload)
    assert triage_min.confidence == 0.0

    payload["confidence"] = 1.0
    triage_max = LogTriageOutput(**payload)
    assert triage_max.confidence == 1.0


@pytest.mark.parametrize("invalid_confidence", [-0.01, -1.0, 1.01, 1.5, 100.0])
def test_confidence_out_of_bounds_raises(valid_payload, invalid_confidence):
    """Verify confidence outside [0.0, 1.0] raises ValidationError."""
    payload = valid_payload.copy()
    payload["confidence"] = invalid_confidence
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload)


def test_confidence_invalid_type_raises(valid_payload):
    """Verify non-numeric confidence raises ValidationError."""
    payload = valid_payload.copy()
    payload["confidence"] = "not-a-float"
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload)


def test_confidence_rejects_string_coercion(valid_payload):
    """Verify string numbers like '0.95' are rejected rather than coerced."""
    payload = valid_payload.copy()
    payload["confidence"] = "0.95"
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload)


def test_confidence_rejects_booleans(valid_payload):
    """Verify booleans (True/False) are strictly rejected for confidence."""
    payload_true = valid_payload.copy()
    payload_true["confidence"] = True
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload_true)

    payload_false = valid_payload.copy()
    payload_false["confidence"] = False
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload_false)


# =========================================================================
# Non-Empty & Whitespace String Validation Tests
# =========================================================================

@pytest.mark.parametrize(
    "field",
    ["affected_service", "root_cause", "suggested_action"],
)
@pytest.mark.parametrize("empty_val", ["", "   ", "\t\n  "])
def test_empty_or_whitespace_strings_raise(valid_payload, field, empty_val):
    """Verify empty or whitespace-only strings for text fields raise ValidationError."""
    payload = valid_payload.copy()
    payload[field] = empty_val
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload)


def test_whitespace_stripping(valid_payload):
    """Verify leading and trailing whitespace is stripped from string fields."""
    payload = valid_payload.copy()
    payload["affected_service"] = "  payment-gateway  "
    triage = LogTriageOutput(**payload)
    assert triage.affected_service == "payment-gateway"


def test_explicit_whitespace_normalization_and_evidence_stripping(valid_payload):
    """Verify '   orders-service   ' is normalized and evidence items are stripped."""
    payload = valid_payload.copy()
    payload["affected_service"] = "   orders-service   "
    payload["evidence"] = [
        "  FATAL: connection terminated  ",
        "\tPool saturated\n",
    ]
    triage = LogTriageOutput(**payload)
    assert triage.affected_service == "orders-service"
    assert triage.evidence == [
        "FATAL: connection terminated",
        "Pool saturated",
    ]


# =========================================================================
# Evidence List Validation Tests
# =========================================================================

def test_empty_evidence_list_raises(valid_payload):
    """Verify empty evidence list raises ValidationError."""
    payload = valid_payload.copy()
    payload["evidence"] = []
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload)


@pytest.mark.parametrize("bad_item", ["", "   ", "\t"])
def test_empty_or_whitespace_evidence_item_raises(valid_payload, bad_item):
    """Verify evidence list containing blank/whitespace strings raises ValidationError."""
    payload = valid_payload.copy()
    payload["evidence"] = ["Valid log snippet", bad_item]
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload)


def test_non_string_evidence_item_raises(valid_payload):
    """Verify evidence items must be valid strings."""
    payload = valid_payload.copy()
    payload["evidence"] = [12345]
    with pytest.raises(ValidationError):
        LogTriageOutput(**payload)
