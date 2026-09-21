"""LocalOps AI - Phase 14 Severity Calibration Continuation QLoRA Fine-Tuning.

Continues fine-tuning from Phase 5 adapter (artifacts/phase_5/final_adapter/)
on the contrastive severity calibration dataset without modifying Phase 3/5/6
locked artifacts.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
import random
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import torch
from peft import PeftModel, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

from src.dashboard.energy_tracker import EnergyTracker
from src.training.dataset import LocalOpsChatDataset
from src.training.qlora import get_parameter_summary, get_quantization_config
from src.training.validator import GenerationValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("localops.train_phase14")


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def compute_file_sha256(file_path: str | Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 14 Severity Calibration Fine-Tuning")
    parser.add_argument("--smoke", action="store_true", help="Run rapid smoke test")
    parser.add_argument("--epochs", type=float, default=1.0, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=6e-5, help="Learning rate")
    parser.add_argument("--base-adapter", type=str, default="artifacts/phase_5/final_adapter", help="Source adapter")
    parser.add_argument("--output-dir", type=str, default="artifacts/phase_14", help="Output directory")
    args = parser.parse_args()

    set_seed(42)
    start_time_mono = datetime.datetime.now()
    start_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    train_file = PROJECT_ROOT / "data" / "severity_calibration" / "train.jsonl"
    val_file = PROJECT_ROOT / "data" / "severity_calibration" / "validation.jsonl"
    out_dir = PROJECT_ROOT / args.output_dir
    checkpoints_dir = out_dir / "checkpoints"
    final_adapter_dir = out_dir / "final_adapter"

    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    final_adapter_dir.mkdir(parents=True, exist_ok=True)

    max_train_samples = 32 if args.smoke else None
    max_val_samples = 16 if args.smoke else None

    logger.info("=" * 60)
    logger.info("PHASE 14 SEVERITY CALIBRATION CONTINUATION FINE-TUNING")
    logger.info(f"Mode: {'SMOKE TEST' if args.smoke else 'FULL CONTINUATION'}")
    logger.info(f"Base Adapter: {args.base_adapter}")
    logger.info("=" * 60)

    # 1. Load Datasets
    system_prompt = (
        "You are a production incident triage assistant.\n"
        "Return only valid JSON following the required schema."
    )
    logger.info(f"Loading training data from {train_file}...")
    train_dataset = LocalOpsChatDataset.create_hf_dataset(
        str(train_file), system_prompt=system_prompt, max_samples=max_train_samples
    )
    logger.info(f"Loading validation data from {val_file}...")
    val_dataset = LocalOpsChatDataset.create_hf_dataset(
        str(val_file), system_prompt=system_prompt, max_samples=max_val_samples
    )
    logger.info(f"Train records: {len(train_dataset)}, Validation records: {len(val_dataset)}")

    # 2. Load Base Model and Base Adapter
    base_model_id = "Qwen/Qwen2.5-1.5B-Instruct"
    bnb_config = get_quantization_config(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype="bfloat16",
    )

    tokenizer = AutoTokenizer.from_pretrained(
        base_model_id,
        trust_remote_code=True,
        local_files_only=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    logger.info(f"Loading base model {base_model_id} in 4-bit NF4...")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        quantization_config=bnb_config,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
        device_map="auto",
        trust_remote_code=True,
        local_files_only=True,
    )

    base_model = prepare_model_for_kbit_training(
        base_model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )

    base_adapter_path = str(PROJECT_ROOT / args.base_adapter)
    logger.info(f"Loading pre-trained adapter from {base_adapter_path} (is_trainable=True)...")
    model = PeftModel.from_pretrained(
        base_model,
        base_adapter_path,
        is_trainable=True,
    )

    summary = get_parameter_summary(model)
    logger.info(
        f"Adapter loaded. Trainable parameters: {summary['trainable_parameters']:,} / "
        f"{summary['total_parameters']:,} ({summary['trainable_percentage']:.3f}%)"
    )

    # 3. Setup SFT Trainer
    batch_size = 4
    grad_accum = 4  # Effective batch size = 16
    eval_steps = 5 if args.smoke else 15
    save_steps = 5 if args.smoke else 15
    logging_steps = 1 if args.smoke else 5
    epochs = 1.0 if args.smoke else args.epochs

    sft_config = SFTConfig(
        output_dir=str(checkpoints_dir),
        max_length=1024,
        assistant_only_loss=True,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_steps=3 if args.smoke else 5,
        lr_scheduler_type="cosine",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit",
        logging_steps=logging_steps,
        eval_strategy="steps",
        eval_steps=eval_steps,
        save_strategy="steps",
        save_steps=save_steps,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=True,
        fp16=False,
        seed=42,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        processing_class=tokenizer,
    )

    # 4. Train
    energy_tracker = EnergyTracker.get_instance()
    energy_tracker.start()

    logger.info("Starting Phase 14 continuation QLoRA training...")
    train_result = trainer.train()

    energy_stats = energy_tracker.stop()
    peak_vram_mb = torch.cuda.max_memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0

    # 5. Evaluate on Validation Set
    eval_metrics = trainer.evaluate()
    logger.info(f"Validation evaluation metrics: {eval_metrics}")

    # 6. Save Best Adapter
    logger.info(f"Saving best validation-selected adapter to {final_adapter_dir}...")
    trainer.save_model(str(final_adapter_dir))
    tokenizer.save_pretrained(str(final_adapter_dir))

    # 7. Write Manifest and Validation Metrics
    end_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    duration_str = str(datetime.datetime.now() - start_time_mono)

    training_manifest = {
        "phase": 14,
        "mode": "smoke" if args.smoke else "continuation_fine_tuning",
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "duration": duration_str,
        "base_model": base_model_id,
        "source_adapter": args.base_adapter,
        "target_adapter": str(final_adapter_dir.relative_to(PROJECT_ROOT)),
        "selection_rule": "Predeclared validation-only minimum eval_loss (metric_for_best_model: eval_loss).",
        "best_eval_loss": eval_metrics.get("eval_loss"),
        "dataset": {
            "train_file": str(train_file.relative_to(PROJECT_ROOT)),
            "train_sha256": compute_file_sha256(train_file),
            "train_record_count": len(train_dataset),
            "validation_file": str(val_file.relative_to(PROJECT_ROOT)),
            "validation_sha256": compute_file_sha256(val_file),
            "validation_record_count": len(val_dataset),
            "test_ood_isolated": True,
            "manual_12_logs_isolated": True,
        },
        "parameters": summary,
        "hyperparameters": {
            "learning_rate": args.lr,
            "epochs": epochs,
            "per_device_batch_size": batch_size,
            "gradient_accumulation_steps": grad_accum,
            "effective_batch_size": batch_size * grad_accum,
            "max_length": 1024,
            "optimizer": "paged_adamw_8bit",
            "scheduler": "cosine",
            "seed": 42,
            "assistant_only_loss": True,
        },
        "hardware": {
            "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
            "peak_vram_mb": round(peak_vram_mb, 2),
            "total_energy_wh": (energy_stats or {}).get("energy_wh", 0.0),
        },
    }

    manifest_path = out_dir / "training_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(training_manifest, f, indent=2)
    logger.info(f"Saved training manifest to {manifest_path}")

    val_metrics_out = {
        "eval_loss": eval_metrics.get("eval_loss"),
        "eval_runtime_seconds": eval_metrics.get("eval_runtime"),
        "eval_samples_per_second": eval_metrics.get("eval_samples_per_second"),
        "selection_metric": "eval_loss",
        "timestamp": end_timestamp,
    }
    val_metrics_path = out_dir / "validation_metrics.json"
    with open(val_metrics_path, "w", encoding="utf-8") as f:
        json.dump(val_metrics_out, f, indent=2)
    logger.info(f"Saved validation metrics to {val_metrics_path}")
    logger.info("Phase 14 QLoRA continuation training complete!")


if __name__ == "__main__":
    main()
