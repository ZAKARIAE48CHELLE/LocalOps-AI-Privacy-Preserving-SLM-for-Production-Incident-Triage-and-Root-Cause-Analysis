"""LocalOps AI - Phase 5 QLoRA Fine-Tuning CLI Script.

Orchestrates Phase 5 fine-tuning, supporting smoke tests, full 3-epoch
training, checkpoint resumption, manifest generation, and loss curve plotting.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import torch
import yaml

from src.training.dataset import LocalOpsChatDataset
from src.training.qlora import get_parameter_summary, load_qlora_model_and_tokenizer
from src.training.trainer import LocalOpsTrainer
from src.training.validator import GenerationValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("localops.train_qlora")


def set_seed(seed: int = 42) -> None:
    """Sets deterministic random seeds across Python, NumPy, PyTorch, and CUDA."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def compute_file_sha256(file_path: str | Path) -> str:
    """Computes SHA-256 checksum for dataset integrity verification."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def plot_training_curves(history: list[dict], output_dir: Path) -> None:
    """Generates training and validation loss curve plots."""
    try:
        import matplotlib.pyplot as plt

        train_steps = []
        train_losses = []
        eval_steps = []
        eval_losses = []
        lr_steps = []
        lrs = []

        for entry in history:
            step = entry.get("step")
            if "loss" in entry and step is not None:
                train_steps.append(step)
                train_losses.append(entry["loss"])
            if "eval_loss" in entry and step is not None:
                eval_steps.append(step)
                eval_losses.append(entry["eval_loss"])
            if "learning_rate" in entry and step is not None:
                lr_steps.append(step)
                lrs.append(entry["learning_rate"])

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        if train_losses:
            ax1.plot(train_steps, train_losses, label="Training Loss", color="#2563eb", alpha=0.8)
        if eval_losses:
            ax1.plot(eval_steps, eval_losses, label="Validation Loss", color="#dc2626", marker="o", markersize=4)
        ax1.set_title("Cross-Entropy Loss vs. Step (Response Tokens Only)")
        ax1.set_xlabel("Optimization Step")
        ax1.set_ylabel("Loss")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        if lrs:
            ax2.plot(lr_steps, lrs, label="Learning Rate", color="#16a34a")
            ax2.set_title("Learning Rate Schedule (Cosine)")
            ax2.set_xlabel("Optimization Step")
            ax2.set_ylabel("Learning Rate")
            ax2.legend()
            ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plot_path = output_dir / "training_curves.png"
        plt.savefig(plot_path, dpi=150)
        plt.close()
        logger.info(f"Training curves saved to {plot_path}")
    except Exception as e:
        logger.warning(f"Failed to generate training curves plot: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LocalOps AI - Phase 5 QLoRA Fine-Tuning")
    parser.add_argument("--config", type=str, default="configs/training.yaml", help="Path to training config YAML")
    parser.add_argument("--smoke", action="store_true", help="Run a fast 5-step smoke test with small subset")
    parser.add_argument("--resume_from_checkpoint", type=str, default=None, help="Path to checkpoint or 'latest'")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config: Dict[str, Any] = yaml.safe_load(f)

    # Enforce dataset isolation before touching any files
    train_file = config["data"]["train_file"]
    val_file = config["data"]["validation_file"]
    LocalOpsChatDataset.assert_not_test_split(train_file)
    LocalOpsChatDataset.assert_not_test_split(val_file)

    seed = config["training"].get("seed", 42)
    set_seed(seed)

    start_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    start_time_mono = datetime.datetime.now()

    if args.smoke:
        logger.info("=" * 60)
        logger.info("PHASE 5 SMOKE TEST INITIALIZED (Fast Verification Mode)")
        logger.info("=" * 60)
        smoke_cfg = config.get("smoke", {})
        config["training"]["output_dir"] = smoke_cfg.get("output_dir", "artifacts/phase_5/smoke")
        config["training"]["max_steps"] = smoke_cfg.get("max_steps", 5)
        config["training"]["num_train_epochs"] = 1.0
        config["training"]["save_steps"] = 5
        config["training"]["eval_steps"] = 5
        config["training"]["logging_steps"] = 1
        config["validation"]["generation_eval_steps"] = 5
        train_samples = smoke_cfg.get("num_train_samples", 32)
        val_samples = smoke_cfg.get("num_val_samples", 8)
    else:
        logger.info("=" * 60)
        logger.info("PHASE 5 FULL QLORA TRAINING INITIALIZED")
        logger.info("=" * 60)
        train_samples = None
        val_samples = None

    output_dir = Path(config["training"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Datasets
    system_prompt = config["data"].get("system_prompt")
    logger.info(f"Loading training dataset from {train_file} (max_samples={train_samples})...")
    train_dataset = LocalOpsChatDataset.create_hf_dataset(
        train_file,
        system_prompt=system_prompt,
        max_samples=train_samples,
    )
    logger.info(f"Loading validation dataset from {val_file} (max_samples={val_samples})...")
    val_dataset = LocalOpsChatDataset.create_hf_dataset(
        val_file,
        system_prompt=system_prompt,
        max_samples=val_samples,
    )
    logger.info(f"Loaded {len(train_dataset)} training records, {len(val_dataset)} validation records.")

    # 2. Load Model & Tokenizer
    model, tokenizer = load_qlora_model_and_tokenizer(
        model_cfg=config["model"],
        quant_cfg=config["quantization"],
        lora_cfg=config["lora"],
        gradient_checkpointing=config["training"].get("gradient_checkpointing", True),
    )

    # 3. Setup Validator
    val_sample_size = config["validation"].get("generation_sample_size", 48) if not args.smoke else 8
    validator = GenerationValidator(
        validation_file=val_file,
        tokenizer=tokenizer,
        sample_size=val_sample_size,
        system_prompt=system_prompt,
    )

    # 4. Initialize Trainer
    trainer = LocalOpsTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        config=config,
        validator=validator,
    )

    # 5. Execute Training
    training_metrics = trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)

    end_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    duration_str = str(datetime.datetime.now() - start_time_mono)

    # 6. Generate Curves
    plot_training_curves(training_metrics["training_history"], output_dir)

    # 7. Generate Training Manifest
    train_checksum = compute_file_sha256(train_file)
    val_checksum = compute_file_sha256(val_file)

    manifest = {
        "phase": 5,
        "mode": "smoke" if args.smoke else "full_training",
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "duration": duration_str,
        "base_model": config["model"]["base_model_id"],
        "dataset": {
            "train_file": train_file,
            "train_sha256": train_checksum,
            "train_record_count": len(train_dataset),
            "validation_file": val_file,
            "validation_sha256": val_checksum,
            "validation_record_count": len(val_dataset),
            "test_split_isolated": True,
        },
        "qlora_config": {
            "rank": config["lora"]["r"],
            "alpha": config["lora"]["lora_alpha"],
            "dropout": config["lora"]["lora_dropout"],
            "target_modules": config["lora"]["target_modules"],
            "quantization": config["quantization"]["bnb_4bit_quant_type"],
            "double_quant": config["quantization"]["bnb_4bit_use_double_quant"],
        },
        "parameters": training_metrics["parameters"],
        "hyperparameters": {
            "learning_rate": config["training"]["learning_rate"],
            "epochs": config["training"]["num_train_epochs"],
            "per_device_batch_size": config["training"]["per_device_train_batch_size"],
            "gradient_accumulation_steps": config["training"]["gradient_accumulation_steps"],
            "effective_batch_size": config["training"]["per_device_train_batch_size"] * config["training"]["gradient_accumulation_steps"],
            "max_length": config["data"]["max_length"],
            "optimizer": config["training"]["optim"],
            "scheduler": config["training"]["lr_scheduler_type"],
            "seed": seed,
            "assistant_only_loss": config["training"]["assistant_only_loss"],
        },
        "hardware": {
            "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
            "cuda_available": torch.cuda.is_available(),
            "peak_vram_mb": training_metrics["telemetry"].get("peak_vram_mb"),
            "total_energy_wh": training_metrics["telemetry"].get("total_energy_wh"),
        },
        "best_checkpoint": training_metrics.get("best_checkpoint"),
        "best_eval_loss": training_metrics.get("best_eval_loss"),
        "final_generation_metrics": training_metrics.get("final_generation_metrics"),
    }

    manifest_path = output_dir / "training_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Training manifest saved to {manifest_path}")
    logger.info("Phase 5 run complete.")


if __name__ == "__main__":
    main()
