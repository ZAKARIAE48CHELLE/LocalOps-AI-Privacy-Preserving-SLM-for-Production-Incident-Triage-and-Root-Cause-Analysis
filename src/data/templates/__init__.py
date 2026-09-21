"""
Aggregate registry for all 360 structural incident templates.
6 categories * 6 families * 10 templates = 360 templates.
"""

from src.data.templates.application import APPLICATION_TEMPLATES
from src.data.templates.base import LogTemplate, compute_structural_fingerprint
from src.data.templates.database import DATABASE_TEMPLATES
from src.data.templates.infrastructure import INFRASTRUCTURE_TEMPLATES
from src.data.templates.messaging import MESSAGING_TEMPLATES
from src.data.templates.network import NETWORK_TEMPLATES
from src.data.templates.security import SECURITY_TEMPLATES
from src.schemas.enums import IncidentFamily

ALL_TEMPLATES: list[LogTemplate] = (
    DATABASE_TEMPLATES +
    INFRASTRUCTURE_TEMPLATES +
    APPLICATION_TEMPLATES +
    SECURITY_TEMPLATES +
    NETWORK_TEMPLATES +
    MESSAGING_TEMPLATES
)

# Registry assertions: Total templates must equal 360
assert len(ALL_TEMPLATES) == 360, f"Expected 360 templates across all categories, got {len(ALL_TEMPLATES)}"

# Validate that each of the 36 families has exactly 10 templates
_family_counts: dict[IncidentFamily, int] = {}
for tpl in ALL_TEMPLATES:
    _family_counts[tpl.family] = _family_counts.get(tpl.family, 0) + 1

for fam in IncidentFamily:
    assert _family_counts.get(fam, 0) == 10, f"Family {fam} has {_family_counts.get(fam, 0)} templates (expected 10)"

# Validate that template IDs are globally unique
_all_ids = [t.template_id for t in ALL_TEMPLATES]
assert len(_all_ids) == len(set(_all_ids)), "All 360 template IDs must be unique"


TEMPLATES_BY_FAMILY: dict[IncidentFamily, list[LogTemplate]] = {
    fam: [t for t in ALL_TEMPLATES if t.family == fam]
    for fam in IncidentFamily
}

TEMPLATES_BY_ID: dict[str, LogTemplate] = {
    t.template_id: t for t in ALL_TEMPLATES
}


def get_all_templates() -> list[LogTemplate]:
    """Return all 360 registered structural log templates."""
    return ALL_TEMPLATES


def get_templates_by_family(family: IncidentFamily) -> list[LogTemplate]:
    """Return the 10 structural templates for a specific IncidentFamily."""
    return TEMPLATES_BY_FAMILY.get(family, [])
