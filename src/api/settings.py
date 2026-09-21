"""LocalOps AI — API Service Settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class ServiceConfig(BaseModel):
    name: str = "localops-ai"
    version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    log_raw_payloads: bool = False
    cors_origins: List[str] = Field(default_factory=list)


class ModelConfig(BaseModel):
    base_model_id: str = "Qwen/Qwen2.5-1.5B-Instruct"
    adapter_path: str = "artifacts/phase_5/final_adapter"
    adapter_source_checkpoint: str = "checkpoint-100"
    device: str = "cuda"
    load_in_4bit: bool = True
    bnb_4bit_compute_dtype: str = "bfloat16"
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_use_double_quant: bool = True
    warmup_enabled: bool = True
    warmup_sample_log: str = (
        "[2026-09-18T12:00:00Z] [WARN] [service-discovery] Keepalive ping delayed by 120ms; re-establishing socket."
    )


class InferenceConfig(BaseModel):
    max_input_characters: int = 16384
    max_input_tokens: int = 2048
    max_new_tokens: int = 384
    temperature: float = 0.0
    do_sample: bool = False
    seed: int = 42
    max_concurrent_inference: int = 2
    request_timeout_seconds: float = 30.0
    batch_max_items: int = 16
    batch_micro_batch_size: int = 4


class ApiSettings(BaseModel):
    service: ServiceConfig = Field(default_factory=ServiceConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    inference: InferenceConfig = Field(default_factory=InferenceConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "ApiSettings":
        if config_path is None:
            config_path = PROJECT_ROOT / "configs" / "api.yaml"

        data: Dict[str, Any] = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        # Environment variable overrides
        if "LOCALOPS_HOST" in os.environ:
            data.setdefault("service", {})["host"] = os.environ["LOCALOPS_HOST"]
        if "LOCALOPS_PORT" in os.environ:
            data.setdefault("service", {})["port"] = int(os.environ["LOCALOPS_PORT"])
        if "LOCALOPS_LOG_LEVEL" in os.environ:
            data.setdefault("service", {})["log_level"] = os.environ["LOCALOPS_LOG_LEVEL"]
        if "LOCALOPS_LOG_RAW_PAYLOADS" in os.environ:
            data.setdefault("service", {})["log_raw_payloads"] = (
                os.environ["LOCALOPS_LOG_RAW_PAYLOADS"].lower() in ("true", "1", "yes")
            )
        if "LOCALOPS_DEVICE" in os.environ:
            data.setdefault("model", {})["device"] = os.environ["LOCALOPS_DEVICE"]
        if "LOCALOPS_MAX_CONCURRENT" in os.environ:
            data.setdefault("inference", {})["max_concurrent_inference"] = int(
                os.environ["LOCALOPS_MAX_CONCURRENT"]
            )

        return cls(**data)


# Global settings singleton
settings = ApiSettings.load()
