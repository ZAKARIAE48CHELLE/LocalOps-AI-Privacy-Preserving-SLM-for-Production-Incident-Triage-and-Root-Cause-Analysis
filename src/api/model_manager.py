"""LocalOps AI — Model Manager (Singleton Lifecycle)."""

from __future__ import annotations

import gc
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from src.api.settings import ApiSettings, settings

logger = logging.getLogger("localops.model_manager")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class ModelManager:
    """Manages the lifecycle, loading, readiness, and warmup of the fine-tuned model."""

    _instance: Optional["ModelManager"] = None
    _lock = threading.Lock()

    def __init__(self, cfg: Optional[ApiSettings] = None):
        self.cfg = cfg or settings
        self.tokenizer: Optional[Any] = None
        self.model: Optional[Any] = None
        self.device: str = self.cfg.model.device
        self.is_loaded: bool = False
        self.warmup_completed: bool = False
        self.warmup_latency_ms: float = 0.0
        self.init_error: Optional[str] = None
        self._load_lock = threading.Lock()

    @classmethod
    def get_instance(cls, cfg: Optional[ApiSettings] = None) -> "ModelManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(cfg)
            return cls._instance

    @property
    def is_ready(self) -> bool:
        return self.is_loaded and (self.warmup_completed or not self.cfg.model.warmup_enabled)

    def load_model(self, force_reload: bool = False):
        """Loads tokenizer, 4-bit base model, and QLoRA adapter into resident memory."""
        with self._load_lock:
            if self.is_loaded and not force_reload:
                return

            try:
                start_time = time.time()
                adapter_path = PROJECT_ROOT / self.cfg.model.adapter_path
                base_model_id = self.cfg.model.base_model_id

                logger.info(f"Loading tokenizer from: {adapter_path if adapter_path.exists() else base_model_id}")
                if adapter_path.exists() and (adapter_path / "tokenizer_config.json").exists():
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        str(adapter_path),
                        trust_remote_code=True,
                        fix_markdown=False,
                    )
                else:
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        base_model_id,
                        trust_remote_code=True,
                        fix_markdown=False,
                    )

                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                self.tokenizer.padding_side = "left"

                # Check CUDA availability
                cuda_available = torch.cuda.is_available() and self.device == "cuda"
                actual_device = "cuda" if cuda_available else "cpu"

                if cuda_available and self.cfg.model.load_in_4bit:
                    compute_dtype = (
                        torch.bfloat16
                        if self.cfg.model.bnb_4bit_compute_dtype == "bfloat16"
                        else torch.float16
                    )
                    bnb_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type=self.cfg.model.bnb_4bit_quant_type,
                        bnb_4bit_compute_dtype=compute_dtype,
                        bnb_4bit_use_double_quant=self.cfg.model.bnb_4bit_use_double_quant,
                    )
                    logger.info(f"Loading 4-bit base model {base_model_id} on CUDA...")
                    base_model = AutoModelForCausalLM.from_pretrained(
                        base_model_id,
                        quantization_config=bnb_config,
                        device_map="auto",
                        torch_dtype=compute_dtype,
                        trust_remote_code=True,
                    )
                else:
                    logger.info(f"Loading base model {base_model_id} on {actual_device} (fp32/fp16 fallback)...")
                    base_model = AutoModelForCausalLM.from_pretrained(
                        base_model_id,
                        torch_dtype=torch.float32,
                        trust_remote_code=True,
                    )
                    base_model.to(actual_device)

                # Attach PEFT adapter
                if adapter_path.exists():
                    logger.info(f"Attaching LoRA adapter from: {adapter_path}")
                    self.model = PeftModel.from_pretrained(base_model, str(adapter_path))
                else:
                    logger.warning(f"Adapter path {adapter_path} not found. Running base model only.")
                    self.model = base_model

                self.model.eval()
                self.is_loaded = True
                load_duration = time.time() - start_time
                logger.info(f"Model successfully loaded and resident in {load_duration:.2f}s.")

                # Warmup inference
                if self.cfg.model.warmup_enabled:
                    self._run_warmup()

            except Exception as e:
                self.init_error = str(e)
                self.is_loaded = False
                logger.error(f"Failed to load model: {e}", exc_info=True)
                raise e

    def _run_warmup(self):
        """Executes a single synthetic warmup inference to compile CUDA graphs and kernels."""
        if not self.is_loaded or self.model is None or self.tokenizer is None:
            return

        try:
            w_start = time.time()
            logger.info("Executing startup warmup inference...")
            warmup_log = self.cfg.model.warmup_sample_log

            messages = [
                {"role": "system", "content": "You are a production incident triage assistant. Return only valid JSON following the required schema."},
                {"role": "user", "content": warmup_log},
            ]
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = self.tokenizer([prompt], return_tensors="pt")
            device = next(self.model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.inference_mode():
                _ = self.model.generate(
                    **inputs,
                    max_new_tokens=64,
                    do_sample=False,
                    temperature=0.0,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )

            self.warmup_latency_ms = (time.time() - w_start) * 1000.0
            self.warmup_completed = True
            logger.info(f"Warmup completed in {self.warmup_latency_ms:.2f}ms.")
        except Exception as e:
            logger.warning(f"Warmup inference encountered non-fatal error: {e}")
            self.warmup_completed = True  # Non-blocking for CPU/mock environments

    def unload_model(self):
        """Releases model weights and frees CUDA memory on shutdown."""
        with self._load_lock:
            logger.info("Unloading model and cleaning up GPU memory...")
            self.model = None
            self.tokenizer = None
            self.is_loaded = False
            self.warmup_completed = False

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Model unloaded successfully.")
