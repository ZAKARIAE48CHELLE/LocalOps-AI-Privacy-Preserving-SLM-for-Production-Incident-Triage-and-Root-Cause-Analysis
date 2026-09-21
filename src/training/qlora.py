"""LocalOps AI - QLoRA Model & Adapter Configuration Module.

Loads Qwen2.5-1.5B-Instruct in 4-bit NF4 with double quantization,
configures PEFT low-rank adapters over all 7 linear projections,
and reports parameter efficiency statistics.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import torch
from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    PreTrainedModel,
    PreTrainedTokenizerBase,
)

logger = logging.getLogger("localops.training.qlora")


def get_quantization_config(
    load_in_4bit: bool = True,
    bnb_4bit_quant_type: str = "nf4",
    bnb_4bit_use_double_quant: bool = True,
    bnb_4bit_compute_dtype: str = "bfloat16",
) -> BitsAndBytesConfig:
    """Creates a BitsAndBytesConfig for 4-bit NF4 double quantization."""
    compute_dtype = getattr(torch, bnb_4bit_compute_dtype, torch.bfloat16)

    return BitsAndBytesConfig(
        load_in_4bit=load_in_4bit,
        bnb_4bit_quant_type=bnb_4bit_quant_type,
        bnb_4bit_use_double_quant=bnb_4bit_use_double_quant,
        bnb_4bit_compute_dtype=compute_dtype,
    )


def get_lora_config(
    r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    bias: str = "none",
    task_type: str = "CAUSAL_LM",
    target_modules: List[str] | None = None,
) -> LoraConfig:
    """Creates a PEFT LoraConfig targeting specified linear modules."""
    if target_modules is None:
        target_modules = [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]

    return LoraConfig(
        r=r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias=bias,
        task_type=task_type,
        target_modules=target_modules,
    )


def get_parameter_summary(model: PreTrainedModel | PeftModel) -> Dict[str, Any]:
    """Inspects and returns trainable vs frozen parameter counts."""
    trainable_params = 0
    all_param = 0
    for _, param in model.named_parameters():
        all_param += param.numel()
        if param.requires_grad:
            trainable_params += param.numel()

    trainable_pct = 100 * trainable_params / all_param if all_param > 0 else 0.0

    return {
        "trainable_parameters": trainable_params,
        "total_parameters": all_param,
        "trainable_percentage": round(trainable_pct, 4),
        "frozen_parameters": all_param - trainable_params,
    }


def load_qlora_model_and_tokenizer(
    model_cfg: Dict[str, Any],
    quant_cfg: Dict[str, Any],
    lora_cfg: Dict[str, Any],
    gradient_checkpointing: bool = True,
    device_map: str = "auto",
) -> Tuple[PeftModel, PreTrainedTokenizerBase]:
    """Loads base model in 4-bit, configures PEFT LoRA adapter, and returns model and tokenizer."""
    base_model_id = model_cfg.get("base_model_id", "Qwen/Qwen2.5-1.5B-Instruct")
    torch_dtype_str = model_cfg.get("torch_dtype", "bfloat16")
    compute_dtype = getattr(torch, torch_dtype_str, torch.bfloat16)
    attn_impl = model_cfg.get("attn_implementation", "sdpa")

    logger.info(f"Loading base model {base_model_id} with 4-bit quantization ({quant_cfg.get('bnb_4bit_quant_type')})...")

    bnb_config = get_quantization_config(
        load_in_4bit=quant_cfg.get("load_in_4bit", True),
        bnb_4bit_quant_type=quant_cfg.get("bnb_4bit_quant_type", "nf4"),
        bnb_4bit_use_double_quant=quant_cfg.get("bnb_4bit_use_double_quant", True),
        bnb_4bit_compute_dtype=quant_cfg.get("bnb_4bit_compute_dtype", "bfloat16"),
    )

    tokenizer = AutoTokenizer.from_pretrained(
        base_model_id,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"  # Standard for training

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        quantization_config=bnb_config,
        torch_dtype=compute_dtype,
        attn_implementation=attn_impl,
        device_map=device_map,
        trust_remote_code=True,
    )

    if gradient_checkpointing:
        base_model = prepare_model_for_kbit_training(
            base_model,
            use_gradient_checkpointing=True,
            gradient_checkpointing_kwargs={"use_reentrant": False},
        )

    peft_lora_config = get_lora_config(
        r=lora_cfg.get("r", 16),
        lora_alpha=lora_cfg.get("lora_alpha", 32),
        lora_dropout=lora_cfg.get("lora_dropout", 0.05),
        bias=lora_cfg.get("bias", "none"),
        task_type=lora_cfg.get("task_type", "CAUSAL_LM"),
        target_modules=lora_cfg.get("target_modules", None),
    )

    model = get_peft_model(base_model, peft_lora_config)

    summary = get_parameter_summary(model)
    logger.info(
        f"LoRA attached. Trainable: {summary['trainable_parameters']:,} / "
        f"{summary['total_parameters']:,} ({summary['trainable_percentage']:.3f}%)"
    )

    return model, tokenizer
