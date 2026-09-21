"""LocalOps AI - Validation Generation & Diagnostic Triage Evaluator.

Performs periodic generation-based evaluation on a stratified validation slice
from validation.jsonl (never test.jsonl) to track schema validity, Severity F1
(specifically P4_LOW recall), and IncidentType F1 (specifically MESSAGING).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import torch
from peft import PeftModel
from transformers import PreTrainedTokenizerBase

from src.evaluation.metrics import compute_f1_multiclass
from src.schemas import IncidentType, LogTriageOutput, Severity
from src.training.dataset import LocalOpsChatDataset

logger = logging.getLogger("localops.training.validator")


class GenerationValidator:
    """Evaluates fine-tuned checkpoints via greedy autoregressive generation."""

    def __init__(
        self,
        validation_file: str | Path,
        tokenizer: PreTrainedTokenizerBase,
        sample_size: int = 48,
        system_prompt: str = "You are a production incident triage assistant.\nReturn only valid JSON following the required schema.",
    ) -> None:
        LocalOpsChatDataset.assert_not_test_split(validation_file)
        self.tokenizer = tokenizer
        self.system_prompt = system_prompt
        self.sample_size = sample_size
        self.samples = self._load_stratified_validation_samples(validation_file, sample_size)

    def _load_stratified_validation_samples(
        self,
        validation_file: str | Path,
        sample_size: int,
    ) -> List[Dict[str, Any]]:
        """Selects a balanced stratified sample across all 6 IncidentTypes."""
        records = LocalOpsChatDataset.load_records(validation_file)

        by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for rec in records:
            inc_type = rec["target"]["incident_type"]
            by_type[inc_type].append(rec)

        target_per_type = max(1, sample_size // len(by_type))
        stratified = []
        for inc_type, type_records in by_type.items():
            stratified.extend(type_records[:target_per_type])

        logger.info(f"Loaded {len(stratified)} stratified validation samples for generation checks.")
        return stratified

    @torch.inference_mode()
    def evaluate(
        self,
        model: PeftModel,
        device: torch.device | str = "cuda",
        max_new_tokens: int = 384,
    ) -> Dict[str, Any]:
        """Runs greedy decoding and computes structured diagnostic metrics."""
        was_training = model.training
        model.eval()

        valid_count = 0
        y_true_type = []
        y_pred_type = []
        y_true_sev = []
        y_pred_sev = []

        messaging_total = 0
        messaging_correct = 0
        p4_total = 0
        p4_correct = 0

        for sample in self.samples:
            raw_log = sample["raw_log"]
            ground_truth = sample["target"]
            gt_type = ground_truth["incident_type"]
            gt_sev = ground_truth["severity"]

            if gt_type == IncidentType.MESSAGING.value:
                messaging_total += 1
            if gt_sev == Severity.P4_LOW.value:
                p4_total += 1

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": raw_log},
            ]
            prompt_text = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = self.tokenizer(
                prompt_text,
                return_tensors="pt",
                truncation=True,
                max_length=1024,
            ).to(device)

            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
            generated_tokens = output_ids[0, inputs["input_ids"].shape[1]:]
            generated_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

            y_true_type.append(gt_type)
            y_true_sev.append(gt_sev)

            # Validate against strict Pydantic model
            try:
                # Handle possible markdown fences if emitted
                clean_json = generated_text
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:]
                if clean_json.endswith("```"):
                    clean_json = clean_json[:-3]
                parsed_dict = json.loads(clean_json.strip())
                validated = LogTriageOutput(**parsed_dict)
                valid_count += 1

                pred_type = validated.incident_type.value if hasattr(validated.incident_type, "value") else str(validated.incident_type)
                pred_sev = validated.severity.value if hasattr(validated.severity, "value") else str(validated.severity)

                y_pred_type.append(pred_type)
                y_pred_sev.append(pred_sev)

                if gt_type == IncidentType.MESSAGING.value and pred_type == IncidentType.MESSAGING.value:
                    messaging_correct += 1
                if gt_sev == Severity.P4_LOW.value and pred_sev == Severity.P4_LOW.value:
                    p4_correct += 1

            except Exception:
                y_pred_type.append("INVALID")
                y_pred_sev.append("INVALID")

        if was_training:
            model.train()

        total = len(self.samples)
        schema_valid_rate = valid_count / total if total > 0 else 0.0

        all_incident_types = [t.value for t in IncidentType]
        all_severities = [s.value for s in Severity]

        type_macro_f1, _, _ = compute_f1_multiclass(y_true_type, y_pred_type, labels=all_incident_types)
        sev_macro_f1, _, _ = compute_f1_multiclass(y_true_sev, y_pred_sev, labels=all_severities)

        messaging_recall = messaging_correct / messaging_total if messaging_total > 0 else 0.0
        p4_recall = p4_correct / p4_total if p4_total > 0 else 0.0

        return {
            "validation_sample_count": total,
            "schema_valid_count": valid_count,
            "schema_valid_rate": round(schema_valid_rate, 4),
            "incident_type_macro_f1": round(float(type_macro_f1), 4),
            "severity_macro_f1": round(float(sev_macro_f1), 4),
            "messaging_recall": round(messaging_recall, 4),
            "p4_low_recall": round(p4_recall, 4),
        }
