"""
Pydantic data models and schemas for Phase 4: Baseline Evaluation.
Covers configuration, raw predictions, evaluation records, manifests, and metrics.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ModelConfig(BaseModel):
    """Configuration for base SLM loading and quantization."""
    model_config = ConfigDict(extra="ignore")

    model_id: str = "Qwen/Qwen2.5-1.5B-Instruct"
    quantization: str = "nf4"
    bnb_quant_type: str = "nf4"
    bnb_compute_dtype: str = "bfloat16"
    bnb_use_double_quant: bool = True
    device: str = "cuda"


class GenerationConfig(BaseModel):
    """Decoding parameters for deterministic baseline inference."""
    model_config = ConfigDict(extra="ignore")

    seed: int = 42
    max_new_tokens: int = 384
    do_sample: bool = False
    temperature: float = 0.0


class EvaluationConfig(BaseModel):
    """Evaluation runner execution settings."""
    model_config = ConfigDict(extra="ignore")

    batch_size: int = 1
    checkpoint_frequency: int = 25
    semantic_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    train_path: str = "data/generated/train.jsonl"
    validation_path: str = "data/generated/validation.jsonl"
    test_path: str = "data/generated/test.jsonl"
    results_dir: str = "reports/evaluation"
    smoke_records_per_family: int = 1


class EvaluationPipelineConfig(BaseModel):
    """Full evaluation configuration combining model, generation, and eval specs."""
    model_config = ConfigDict(extra="ignore")

    model: ModelConfig = Field(default_factory=ModelConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "EvaluationPipelineConfig":
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)


class RawPredictionRecord(BaseModel):
    """
    Complete audit record for a single inference evaluation sample.
    Stores raw model output unchanged alongside structured extraction & validation results.
    """
    model_config = ConfigDict(extra="ignore")

    incident_id: str
    experiment_id: str
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    raw_log: str
    raw_model_output: str

    strict_json_valid: bool = False
    json_extraction_success: bool = False
    extracted_json: Optional[str] = None
    parsed_output: Optional[Dict[str, Any]] = None
    pydantic_valid: bool = False

    validation_errors: List[str] = Field(default_factory=list)
    error_types: List[str] = Field(default_factory=list)

    latency_seconds: float = 0.0
    prompt_tokens: int = 0
    generated_tokens: int = 0
    tokens_per_second: float = 0.0
    peak_vram_mb: float = 0.0

    ground_truth: Dict[str, Any]
    metadata: Dict[str, Any]


class PromptManifestEntry(BaseModel):
    """Metadata for a frozen prompt template."""
    prompt_id: str
    prompt_version: str
    prompt_sha256: str
    generation_config_sha256: str
    frozen_at: str
    demonstration_ids: List[str] = Field(default_factory=list)


class FewShotDemonstrationRecord(BaseModel):
    """Metadata and content for a frozen few-shot demonstration."""
    incident_id: str
    incident_type: str
    incident_family: str
    severity: str
    technology: str
    template_id: str
    record_hash: str
    raw_log: str
    target: Dict[str, Any]
