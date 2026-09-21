"""LocalOps AI - Phase 5 Training Engine & Telemetry Pipeline.

Wraps TRL SFTTrainer with assistant-only response loss masking, NVML hardware
telemetry (power, energy, VRAM), generation validation callbacks, and
structured artifact generation.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from peft import PeftModel
from transformers import (
    PreTrainedTokenizerBase,
    TrainerCallback,
    TrainerControl,
    TrainerState,
    TrainingArguments,
)
from trl import SFTConfig, SFTTrainer

from src.dashboard.energy_tracker import EnergyTracker
from src.training.qlora import get_parameter_summary
from src.training.validator import GenerationValidator

logger = logging.getLogger("localops.training.trainer")


class LocalOpsTrainingCallback(TrainerCallback):
    """Callback for tracking training dynamics, telemetry, and periodic generation checks."""

    def __init__(
        self,
        validator: Optional[GenerationValidator] = None,
        generation_eval_steps: int = 200,
        output_dir: str = "artifacts/phase_5",
    ) -> None:
        self.validator = validator
        self.generation_eval_steps = generation_eval_steps
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict[str, Any]] = []
        self.generation_eval_history: List[Dict[str, Any]] = []
        self.start_time: float = time.time()

    def _write_live_state(self, state: TrainerState, status: str = "running") -> None:
        """Writes real-time training telemetry for mobile and desktop mission control."""
        try:
            live_file = self.output_dir / "live_training_state.json"
            latest_train_loss = None
            latest_eval_loss = None
            latest_lr = None

            for entry in reversed(self.history):
                if "loss" in entry and latest_train_loss is None:
                    latest_train_loss = entry["loss"]
                if "eval_loss" in entry and latest_eval_loss is None:
                    latest_eval_loss = entry["eval_loss"]
                if "learning_rate" in entry and latest_lr is None:
                    latest_lr = entry["learning_rate"]
                if latest_train_loss is not None and latest_eval_loss is not None and latest_lr is not None:
                    break

            latest_gen = self.generation_eval_history[-1] if self.generation_eval_history else None

            max_steps = max(1, state.max_steps) if state.max_steps > 0 else 810
            progress_pct = round((state.global_step / max_steps) * 100, 2)

            elapsed = time.time() - self.start_time
            steps_completed = max(1, state.global_step)
            steps_remaining = max(0, max_steps - state.global_step)
            sec_per_step = elapsed / steps_completed if steps_completed > 0 else 0
            eta_sec = steps_remaining * sec_per_step

            if status == "completed":
                eta_fmt = "Completed"
            elif eta_sec > 0:
                h = int(eta_sec // 3600)
                m = int((eta_sec % 3600) // 60)
                s = int(eta_sec % 60)
                eta_fmt = f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"
            else:
                eta_fmt = "Calculating..."

            live_data = {
                "status": status,
                "global_step": state.global_step,
                "max_steps": max_steps,
                "epoch": round(state.epoch or 0.0, 2),
                "progress_pct": progress_pct,
                "train_loss": round(latest_train_loss, 4) if latest_train_loss is not None else None,
                "eval_loss": round(latest_eval_loss, 4) if latest_eval_loss is not None else None,
                "learning_rate": latest_lr,
                "eta_seconds": round(eta_sec, 1),
                "eta_formatted": eta_fmt,
                "elapsed_seconds": round(elapsed, 1),
                "latest_generation_metrics": latest_gen,
                "recent_history": self.history[-60:],
                "generation_history": self.generation_eval_history,
                "last_updated": time.time(),
            }
            with open(live_file, "w", encoding="utf-8") as f:
                json.dump(live_data, f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to write live training state: {e}")

    def on_train_begin(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        **kwargs: Any,
    ) -> None:
        self.start_time = time.time()
        self._write_live_state(state, status="running")

    def on_log(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        logs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        if logs:
            entry = {
                "step": state.global_step,
                "epoch": state.epoch,
                **logs,
            }
            self.history.append(entry)
            self._write_live_state(state, status="running")

    def on_step_end(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        model: Optional[PeftModel] = None,
        **kwargs: Any,
    ) -> None:
        if (
            self.validator is not None
            and state.global_step > 0
            and state.global_step % self.generation_eval_steps == 0
            and model is not None
        ):
            logger.info(f"Running periodic generation validation check at step {state.global_step}...")
            try:
                gen_metrics = self.validator.evaluate(model)
                gen_metrics["step"] = state.global_step
                gen_metrics["epoch"] = state.epoch
                self.generation_eval_history.append(gen_metrics)
                logger.info(
                    f"Step {state.global_step} Gen Eval: Valid={gen_metrics['schema_valid_rate']:.1%}, "
                    f"Sev F1={gen_metrics['severity_macro_f1']:.4f}, Type F1={gen_metrics['incident_type_macro_f1']:.4f}, "
                    f"P4 Recall={gen_metrics['p4_low_recall']:.4f}, Messaging Recall={gen_metrics['messaging_recall']:.4f}"
                )
            except Exception as e:
                logger.warning(f"Generation validation check failed at step {state.global_step}: {e}")

        if state.global_step % 10 == 0:
            self._write_live_state(state, status="running")

    def on_train_end(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        **kwargs: Any,
    ) -> None:
        self._write_live_state(state, status="completed")


class LocalOpsTrainer:
    """Orchestrates QLoRA fine-tuning for LocalOps AI."""

    def __init__(
        self,
        model: PeftModel,
        tokenizer: PreTrainedTokenizerBase,
        train_dataset: Any,
        eval_dataset: Any,
        config: Dict[str, Any],
        validator: Optional[GenerationValidator] = None,
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.train_dataset = train_dataset
        self.eval_dataset = eval_dataset
        self.config = config
        self.validator = validator

        training_cfg = config.get("training", {})
        data_cfg = config.get("data", {})
        val_cfg = config.get("validation", {})

        self.output_dir = Path(training_cfg.get("output_dir", "artifacts/phase_5"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        warmup_steps = training_cfg.get("warmup_steps")
        if warmup_steps is None:
            warmup_steps = 40

        self.sft_config = SFTConfig(
            output_dir=str(self.output_dir / "checkpoints"),
            max_length=data_cfg.get("max_length", 1024),
            assistant_only_loss=training_cfg.get("assistant_only_loss", True),
            num_train_epochs=training_cfg.get("num_train_epochs", 3.0),
            per_device_train_batch_size=training_cfg.get("per_device_train_batch_size", 2),
            per_device_eval_batch_size=training_cfg.get("per_device_eval_batch_size", 2),
            gradient_accumulation_steps=training_cfg.get("gradient_accumulation_steps", 8),
            learning_rate=training_cfg.get("learning_rate", 1.5e-4),
            weight_decay=training_cfg.get("weight_decay", 0.01),
            warmup_steps=warmup_steps,
            lr_scheduler_type=training_cfg.get("lr_scheduler_type", "cosine"),
            gradient_checkpointing=training_cfg.get("gradient_checkpointing", True),
            gradient_checkpointing_kwargs={"use_reentrant": False},
            optim=training_cfg.get("optim", "paged_adamw_8bit"),
            logging_steps=training_cfg.get("logging_steps", 10),
            eval_strategy=training_cfg.get("eval_strategy", "steps"),
            eval_steps=training_cfg.get("eval_steps", 100),
            save_strategy=training_cfg.get("save_strategy", "steps"),
            save_steps=training_cfg.get("save_steps", 100),
            save_total_limit=training_cfg.get("save_total_limit", 3),
            load_best_model_at_end=training_cfg.get("load_best_model_at_end", True),
            metric_for_best_model=training_cfg.get("metric_for_best_model", "eval_loss"),
            greater_is_better=training_cfg.get("greater_is_better", False),
            bf16=training_cfg.get("bf16", True),
            fp16=training_cfg.get("fp16", False),
            seed=training_cfg.get("seed", 42),
            report_to="none",
        )

        gen_eval_steps = val_cfg.get("generation_eval_steps", 200)
        self.callback = LocalOpsTrainingCallback(
            validator=self.validator,
            generation_eval_steps=gen_eval_steps,
            output_dir=str(self.output_dir),
        )

        self.trainer = SFTTrainer(
            model=self.model,
            args=self.sft_config,
            train_dataset=self.train_dataset,
            eval_dataset=self.eval_dataset,
            processing_class=self.tokenizer,
            callbacks=[self.callback],
        )

    def train(self, resume_from_checkpoint: Optional[str | bool] = None) -> Dict[str, Any]:
        """Executes training with hardware telemetry recording."""
        energy_tracker = EnergyTracker.get_instance()
        energy_tracker.start()

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()

        start_time = time.time()
        logger.info(f"Starting QLoRA training on device {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}...")

        train_result = self.trainer.train(resume_from_checkpoint=resume_from_checkpoint)
        duration_seconds = time.time() - start_time

        energy_tracker.stop()
        energy_summary = energy_tracker.get_telemetry()
        peak_vram_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2) if torch.cuda.is_available() else 0.0
        telemetry_summary = {
            **energy_summary,
            "peak_vram_mb": peak_vram_mb,
        }

        # Save final adapter and tokenizer
        final_adapter_dir = self.output_dir / "final_adapter"
        final_adapter_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving fine-tuned adapter to {final_adapter_dir}...")
        self.trainer.save_model(str(final_adapter_dir))
        self.tokenizer.save_pretrained(str(self.output_dir / "tokenizer"))

        # Run post-training generation validation on best model
        final_gen_metrics = {}
        if self.validator is not None:
            logger.info("Running final generation validation on selected checkpoint...")
            try:
                final_gen_metrics = self.validator.evaluate(self.model)
                logger.info(f"Final Best Checkpoint Validation Metrics: {final_gen_metrics}")
            except Exception as e:
                logger.warning(f"Final generation validation check failed: {e}")

        # Parameter summary
        param_summary = get_parameter_summary(self.model)
        state_steps = self.trainer.state.global_step

        training_metrics = {
            "train_runtime_seconds": round(duration_seconds, 2),
            "train_samples_per_second": round(train_result.metrics.get("train_samples_per_second", 0.0), 2),
            "train_steps_per_second": round(train_result.metrics.get("train_steps_per_second", 0.0), 2),
            "total_steps": state_steps,
            "final_train_loss": round(train_result.metrics.get("train_loss", 0.0), 4),
            "best_checkpoint": self.trainer.state.best_model_checkpoint,
            "best_eval_loss": round(self.trainer.state.best_metric, 4) if self.trainer.state.best_metric is not None else None,
            "parameters": param_summary,
            "telemetry": telemetry_summary,
            "final_generation_metrics": final_gen_metrics,
            "training_history": self.callback.history,
            "generation_eval_history": self.callback.generation_eval_history,
        }

        metrics_file = self.output_dir / "training_metrics.json"
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(training_metrics, f, indent=2)
        logger.info(f"Training metrics saved to {metrics_file}")

        return training_metrics
