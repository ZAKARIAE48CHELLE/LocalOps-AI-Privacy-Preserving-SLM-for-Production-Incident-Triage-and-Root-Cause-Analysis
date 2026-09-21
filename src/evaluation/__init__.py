"""
Phase 4: Baseline Evaluation package.
Provides evaluation models, prompt generators, multi-layer parsers, metrics calculators, and runners.
"""

from src.evaluation.evaluator import BaselineEvaluator
from src.evaluation.heuristics import DiagnosticHeuristics
from src.evaluation.metrics import MetricEvaluator
from src.evaluation.parser import OutputParser
from src.evaluation.prompts import PromptBuilder
from src.evaluation.schemas import EvaluationPipelineConfig, RawPredictionRecord
from src.evaluation.semantic import LocalSemanticEvaluator

__all__ = [
    "BaselineEvaluator",
    "DiagnosticHeuristics",
    "MetricEvaluator",
    "OutputParser",
    "PromptBuilder",
    "EvaluationPipelineConfig",
    "RawPredictionRecord",
    "LocalSemanticEvaluator",
]
