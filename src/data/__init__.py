"""Dataset engineering package for LocalOps AI.

Provides models, templates, generators, validation, and statistics
for synthetic incident triage dataset generation.
"""

from src.data.family_catalog import (
    FAMILY_TO_INCIDENT_TYPE,
    CATEGORY_TO_FAMILIES,
    get_incident_type_for_family,
    get_category_for_family,
)
from src.data.models import (
    DatasetRecord,
    DatasetSplit,
    DiagnosticClarity,
    ImpactScenario,
    NoiseProfile,
    RecordMetadata,
)
from src.data.generator import DatasetGenerator
from src.data.splitter import SplitManager
from src.data.statistics import DatasetStatistics
from src.data.validation import DatasetValidator

__all__ = [
    "FAMILY_TO_INCIDENT_TYPE",
    "CATEGORY_TO_FAMILIES",
    "get_incident_type_for_family",
    "get_category_for_family",
    "DatasetRecord",
    "DatasetSplit",
    "DiagnosticClarity",
    "ImpactScenario",
    "NoiseProfile",
    "RecordMetadata",
    "DatasetGenerator",
    "SplitManager",
    "DatasetStatistics",
    "DatasetValidator",
]
