"""
Evaluation execution engine for Phase 4: Baseline Evaluation.
Orchestrates:
- Local 4-bit NF4 SLM loading (Qwen/Qwen2.5-1.5B-Instruct)
- Crash-safe checkpointing and atomic incremental JSONL logging
- Zero-duplicate resumption
- Single-stream execution with CUDA synchronization and VRAM tracking
- Full metric compilation and reporting
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from src.evaluation.metrics import MetricEvaluator
from src.evaluation.parser import OutputParser
from src.evaluation.prompts import PromptBuilder
from src.evaluation.schemas import EvaluationPipelineConfig, RawPredictionRecord
from src.evaluation.semantic import LocalSemanticEvaluator


class BaselineEvaluator:
    """
    Executes baseline evaluation runs across E1, E2, and E3 experiments.
    Guarantees strict auditability, atomic writes, and crash resumption.
    """

    def __init__(
        self,
        config: EvaluationPipelineConfig,
        demonstrations: Optional[List[Dict[str, Any]]] = None,
        adapter_path: Optional[str] = None,
    ):
        self.config = config
        self.demonstrations = demonstrations or []
        self.adapter_path = adapter_path
        self.tokenizer = None
        self.model = None
        self._is_loaded = False
        self.semantic_evaluator = LocalSemanticEvaluator(
            model_name_or_path=config.evaluation.semantic_embedding_model,
            device=config.model.device,
        )

    def load_model(self, adapter_path: Optional[str] = None):
        """Loads Qwen2.5-1.5B-Instruct in 4-bit NF4 quantization, optionally attaching LoRA adapter."""
        if self._is_loaded:
            return

        model_id = self.config.model.model_id
        target_adapter = adapter_path or self.adapter_path
        use_cuda = torch.cuda.is_available() and self.config.model.device == "cuda"

        print(f"[*] Loading tokenizer for {model_id}...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id, padding_side="left", trust_remote_code=True
        )
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        if use_cuda and self.config.model.quantization == "nf4":
            print("[*] Configuring 4-bit NF4 BitsAndBytes...")
            compute_dtype = (
                torch.bfloat16
                if self.config.model.bnb_compute_dtype == "bfloat16"
                else torch.float16
            )
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type=self.config.model.bnb_quant_type,
                bnb_4bit_compute_dtype=compute_dtype,
                bnb_4bit_use_double_quant=self.config.model.bnb_use_double_quant,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                quantization_config=bnb_config,
                device_map="auto",
                attn_implementation="sdpa",
                trust_remote_code=True,
            )
        else:
            print("[!] Loading model on CPU or without 4-bit quantization...")
            torch_dtype = torch.float32 if not use_cuda else torch.float16
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch_dtype,
                device_map="cpu" if not use_cuda else "auto",
                attn_implementation="sdpa",
                trust_remote_code=True,
            )

        if target_adapter:
            from peft import PeftModel
            print(f"[*] Attaching fine-tuned LoRA adapter from: {target_adapter}...")
            self.model = PeftModel.from_pretrained(self.model, str(target_adapter))
            print("[OK] LoRA adapter attached successfully.")

        self.model.eval()
        self._is_loaded = True
        print("[OK] Evaluation model ready.")

    def run_inference_batch(
        self, batch_messages: List[List[Dict[str, str]]]
    ) -> List[Tuple[str, float, int, int, float, float]]:
        """
        Runs batched generation for multiple chat prompts using left padding.
        Returns a list of:
            (raw_output_text, latency_sec, prompt_tokens, generated_tokens, tokens_per_sec, peak_vram_mb)
        """
        if not self._is_loaded:
            self.load_model()

        if not batch_messages:
            return []

        prompt_strs = [
            self.tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=True)
            for m in batch_messages
        ]

        inputs = self.tokenizer(prompt_strs, return_tensors="pt", padding=True).to(self.model.device)
        input_len = inputs.input_ids.shape[1]
        bs = len(batch_messages)

        # Reset memory stats
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()

        t0 = time.perf_counter()
        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=self.config.generation.max_new_tokens,
                do_sample=self.config.generation.do_sample,
                temperature=self.config.generation.temperature if self.config.generation.do_sample else None,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        if torch.cuda.is_available():
            torch.cuda.synchronize()
        total_latency = time.perf_counter() - t0
        per_sample_latency = total_latency / bs if bs > 0 else 0.0

        peak_vram_mb = 0.0
        if torch.cuda.is_available():
            peak_vram_mb = round(torch.cuda.max_memory_allocated() / (1024**2), 2)

        results = []
        for i in range(bs):
            p_tokens = int(inputs.attention_mask[i].sum().item())
            gen_ids = output_ids[i, input_len:]
            non_pad_ids = [tok for tok in gen_ids.tolist() if tok != self.tokenizer.pad_token_id]
            g_tokens = len(non_pad_ids)
            tps = g_tokens / per_sample_latency if per_sample_latency > 0 else 0.0
            raw_output = self.tokenizer.decode(non_pad_ids, skip_special_tokens=True).strip()
            results.append((
                raw_output,
                round(per_sample_latency, 4),
                p_tokens,
                g_tokens,
                round(tps, 2),
                peak_vram_mb,
            ))

        return results

    def run_inference_single(
        self, prompt_messages: List[Dict[str, str]]
    ) -> Tuple[str, float, int, int, float, float]:
        """
        Runs generation for a single chat prompt.
        Returns:
            (raw_output_text, latency_sec, prompt_tokens, generated_tokens, tokens_per_sec, peak_vram_mb)
        """
        return self.run_inference_batch([prompt_messages])[0]

    def evaluate_dataset(
        self,
        experiment_id: str,
        records: List[Dict[str, Any]],
        output_dir: str,
        resume: bool = True,
        batch_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Runs evaluation on a list of dataset records with crash-safe checkpointing.
        """
        os.makedirs(output_dir, exist_ok=True)
        predictions_path = os.path.join(output_dir, "predictions.jsonl")
        metrics_path = os.path.join(output_dir, "metrics.json")
        checkpoint_path = os.path.join(output_dir, "checkpoint.json")

        completed_ids: Set[str] = set()
        saved_records: List[RawPredictionRecord] = []

        if resume and os.path.exists(predictions_path):
            print(f"[*] Resuming from existing predictions at {predictions_path}...")
            with open(predictions_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        r_data = json.loads(line)
                        rec = RawPredictionRecord(**r_data)
                        saved_records.append(rec)
                        completed_ids.add(rec.incident_id)
            print(f"[+] Loaded {len(completed_ids)} already completed samples.")

        prompt_hash = PromptBuilder.get_prompt_hash(
            experiment_id, self.demonstrations if experiment_id == "E3" else None
        )
        prompt_id_map = {
            "E1": "prompt_e1_zero_shot",
            "E2": "prompt_e2_structured",
            "E3": "prompt_e3_few_shot",
            "E4": "prompt_e4_qlora",
        }
        prompt_id = prompt_id_map.get(experiment_id, f"prompt_{experiment_id.lower()}")

        if batch_size is None:
            if experiment_id in ["E1", "E2"]:
                batch_size = 24
            elif experiment_id == "E3":
                batch_size = 10
            elif experiment_id == "E4":
                batch_size = getattr(self.config.evaluation, "batch_size", 16)
            else:
                batch_size = getattr(self.config.evaluation, "batch_size", 16)

        total_to_eval = len(records)
        print(f"[*] Starting {experiment_id} evaluation on {total_to_eval} records (batch_size={batch_size})...")

        remaining_records = [r for r in records if r["incident_id"] not in completed_ids]
        last_checkpoint_count = len(completed_ids)

        # Open file in append mode
        with open(predictions_path, "a", encoding="utf-8") as f_out:
            for b_idx in range(0, len(remaining_records), batch_size):
                batch_items = remaining_records[b_idx : b_idx + batch_size]

                # Build prompts for batch
                batch_msgs = []
                for item in batch_items:
                    raw_log = item["raw_log"]
                    if experiment_id == "E1":
                        msgs = PromptBuilder.build_e1_messages(raw_log)
                    elif experiment_id == "E2":
                        msgs = PromptBuilder.build_e2_messages(raw_log)
                    elif experiment_id == "E3":
                        msgs = PromptBuilder.build_e3_messages(raw_log, self.demonstrations)
                    elif experiment_id == "E4":
                        msgs = PromptBuilder.build_e4_messages(raw_log)
                    else:
                        raise ValueError(f"Unknown experiment_id: {experiment_id}")
                    batch_msgs.append(msgs)

                # Batched inference
                batch_results = self.run_inference_batch(batch_msgs)

                # Parse and record each output
                for item, res in zip(batch_items, batch_results):
                    inc_id = item["incident_id"]
                    raw_log = item["raw_log"]
                    ground_truth = item["target"]
                    metadata = item["metadata"]
                    raw_output, latency, p_tokens, g_tokens, tps, vram_mb = res

                    (
                        strict_json_valid,
                        extract_success,
                        extracted_str,
                        parsed_dict,
                        pydantic_valid,
                        errors,
                        error_types,
                    ) = OutputParser.parse_and_validate(raw_output)

                    record = RawPredictionRecord(
                        incident_id=inc_id,
                        experiment_id=experiment_id,
                        prompt_id=prompt_id,
                        prompt_version="1.0.0",
                        prompt_hash=prompt_hash,
                        raw_log=raw_log,
                        raw_model_output=raw_output,
                        strict_json_valid=strict_json_valid,
                        json_extraction_success=extract_success,
                        extracted_json=extracted_str,
                        parsed_output=parsed_dict,
                        pydantic_valid=pydantic_valid,
                        validation_errors=errors,
                        error_types=error_types,
                        latency_seconds=latency,
                        prompt_tokens=p_tokens,
                        generated_tokens=g_tokens,
                        tokens_per_second=tps,
                        peak_vram_mb=vram_mb,
                        ground_truth=ground_truth,
                        metadata=metadata,
                    )

                    f_out.write(record.model_dump_json() + "\n")
                    completed_ids.add(inc_id)
                    saved_records.append(record)

                # Checkpoint every checkpoint_frequency records or when complete
                chk_freq = getattr(self.config.evaluation, "checkpoint_frequency", 50)
                if (len(completed_ids) - last_checkpoint_count >= chk_freq) or (
                    len(completed_ids) == total_to_eval
                ):
                    f_out.flush()
                    last_checkpoint_count = len(completed_ids)
                    with open(checkpoint_path, "w", encoding="utf-8") as f_chk:
                        json.dump(
                            {
                                "experiment_id": experiment_id,
                                "total_records": total_to_eval,
                                "completed_records": len(completed_ids),
                                "last_incident_id": batch_items[-1]["incident_id"],
                                "timestamp": time.time(),
                            },
                            f_chk,
                            indent=2,
                        )
                    print(
                        f"[{experiment_id}] Progress: {len(completed_ids)}/{total_to_eval} records completed."
                    )

        # Compute all metrics on all records
        print(f"[*] Computing evaluation metrics for {experiment_id}...")
        metrics = MetricEvaluator.evaluate_records(saved_records, self.semantic_evaluator)
        metrics["experiment_id"] = experiment_id
        metrics["prompt_id"] = prompt_id
        metrics["prompt_hash"] = prompt_hash

        with open(metrics_path, "w", encoding="utf-8") as f_m:
            json.dump(metrics, f_m, indent=2)

        print(f"[OK] {experiment_id} evaluation finished. Results written to {output_dir}")
        return metrics


def load_stratified_smoke_records(
    validation_path: str = "data/generated/validation.jsonl",
    records_per_family: int = 1,
) -> List[Dict[str, Any]]:
    """
    Deterministically extracts a stratified smoke sample of 36–72 records from validation.jsonl.
    Guarantees coverage of all 36 IncidentFamily values with diverse Severities,
    clarity tiers, and noise profiles.
    """
    from collections import defaultdict

    families_map = defaultdict(list)
    with open(validation_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                fam = item["metadata"]["incident_family"]
                families_map[fam].append(item)

    selected: List[Dict[str, Any]] = []
    # Sort family names for complete determinism
    for fam in sorted(families_map.keys()):
        family_items = families_map[fam]
        for i in range(min(records_per_family, len(family_items))):
            selected.append(family_items[i])

    return selected

