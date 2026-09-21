"""LocalOps AI — Inference Service."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import torch

from src.api.exceptions import (
    GpuResourceExhaustedError,
    InputTooLargeError,
    InvalidRequestError,
    ModelNotReadyError,
    ModelOutputInvalidError,
)
from src.api.model_manager import ModelManager
from src.api.schemas import InferenceTelemetry
from src.api.settings import ApiSettings, settings
from src.evaluation.parser import OutputParser
from src.schemas.triage import LogTriageOutput
from src.severity.extractor import ImpactExtractor
from src.severity.policy import SeverityPolicyEngine

logger = logging.getLogger("localops.inference_service")

SYSTEM_PROMPT = (
    "You are a production incident triage assistant.\n"
    "Return only valid JSON following the required schema."
)


class InferenceService:
    """Handles prompt construction, batched generation, parsing, and strict validation."""

    def __init__(
        self,
        model_manager: Optional[ModelManager] = None,
        cfg: Optional[ApiSettings] = None,
    ):
        self.cfg = cfg or settings
        self.model_manager = model_manager or ModelManager.get_instance(self.cfg)
        self.impact_extractor = ImpactExtractor()
        self.policy_engine = SeverityPolicyEngine()

    def _format_prompt(self, raw_log: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_log},
        ]
        tokenizer = self.model_manager.tokenizer
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    def triage_single(
        self,
        raw_log: str,
        request_id: str,
    ) -> Tuple[LogTriageOutput, InferenceTelemetry]:
        """Performs single incident log triage."""
        if not self.model_manager.is_ready:
            raise ModelNotReadyError("Model is not loaded or ready for inference.", request_id=request_id)

        if len(raw_log) > self.cfg.inference.max_input_characters:
            raise InputTooLargeError(
                f"raw_log length ({len(raw_log)}) exceeds maximum allowed {self.cfg.inference.max_input_characters} characters.",
                request_id=request_id,
            )

        tokenizer = self.model_manager.tokenizer
        model = self.model_manager.model
        device = next(model.parameters()).device

        prompt = self._format_prompt(raw_log)

        start_time = time.time()
        try:
            inputs = tokenizer(
                [prompt],
                return_tensors="pt",
                truncation=True,
                max_length=self.cfg.inference.max_input_tokens,
            )
            prompt_tokens = inputs["input_ids"].shape[1]
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.inference_mode():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=self.cfg.inference.max_new_tokens,
                    do_sample=self.cfg.inference.do_sample,
                    temperature=self.cfg.inference.temperature,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )

            gen_tokens = outputs[:, prompt_tokens:]
            generated_token_count = gen_tokens.shape[1]
            raw_output = tokenizer.decode(gen_tokens[0], skip_special_tokens=True).strip()

            latency_ms = (time.time() - start_time) * 1000.0

        except torch.cuda.OutOfMemoryError as oom:
            logger.error(f"CUDA OOM in triage_single (req_id={request_id}): {oom}")
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            raise GpuResourceExhaustedError("GPU memory exhausted during inference.", request_id=request_id)
        except Exception as e:
            logger.error(f"Inference execution error (req_id={request_id}): {e}")
            raise e

        # Privacy-safe logging
        if self.cfg.service.log_raw_payloads:
            logger.debug(f"Req {request_id} raw generation: {raw_output}")

        # Parse and strictly validate
        _, _, _, parsed_dict, pydantic_valid, errors, _ = OutputParser.parse_and_validate(raw_output)
        if not pydantic_valid or parsed_dict is None:
            err_msg = (
                f"Model generated invalid structured output: "
                f"{'; '.join(errors) if errors else 'unparseable JSON'}"
            )
            from src.observability.metrics import MetricsRegistry
            MetricsRegistry.get_instance().inc_schema_invalid()
            MetricsRegistry.get_instance().inc_model_output_invalid()
            raise ModelOutputInvalidError(err_msg, request_id=request_id)

        parsed_output = LogTriageOutput.model_validate(parsed_dict)

        # Phase 14 Two-Stage Severity Calibration (Layer A + B + C)
        impact = self.impact_extractor.extract(
            raw_log,
            parsed_output.root_cause,
            parsed_output.suggested_action,
        )
        decision = self.policy_engine.evaluate(impact)
        severity_source = "POLICY_ENGINE"
        if not decision.is_insufficient_evidence:
            parsed_output = parsed_output.model_copy(update={"severity": decision.severity})
        else:
            severity_source = "MODEL"

        telemetry = InferenceTelemetry(
            latency_ms=round(latency_ms, 2),
            prompt_tokens=prompt_tokens,
            generated_tokens=generated_token_count,
            severity_source=severity_source,
            severity_reason_code=decision.reason_code,
        )

        return parsed_output, telemetry

    def triage_batch(
        self,
        logs: List[str],
        request_ids: List[str],
    ) -> List[Tuple[Optional[LogTriageOutput], Optional[InferenceTelemetry], Optional[str]]]:
        """
        Performs batched incident triage using micro-batches to prevent VRAM spikes.
        Returns list of (LogTriageOutput | None, InferenceTelemetry | None, error_message | None).
        """
        if not self.model_manager.is_ready:
            raise ModelNotReadyError("Model is not loaded or ready for inference.")

        total = len(logs)
        results: List[Tuple[Optional[LogTriageOutput], Optional[InferenceTelemetry], Optional[str]]] = [
            (None, None, None) for _ in range(total)
        ]

        # Filter out locally invalid requests first
        valid_indices = []
        for i, (log_text, req_id) in enumerate(zip(logs, request_ids)):
            if not log_text or not log_text.strip():
                results[i] = (None, None, "Empty or whitespace-only log")
            elif len(log_text) > self.cfg.inference.max_input_characters:
                results[i] = (None, None, f"Input exceeds maximum allowed {self.cfg.inference.max_input_characters} characters")
            else:
                valid_indices.append(i)

        if not valid_indices:
            return results

        tokenizer = self.model_manager.tokenizer
        model = self.model_manager.model
        device = next(model.parameters()).device
        micro_size = self.cfg.inference.batch_micro_batch_size

        for b_start in range(0, len(valid_indices), micro_size):
            batch_slice = valid_indices[b_start : b_start + micro_size]
            batch_logs = [logs[idx] for idx in batch_slice]
            batch_req_ids = [request_ids[idx] for idx in batch_slice]

            prompts = [self._format_prompt(l) for l in batch_logs]
            b_start_time = time.time()

            try:
                inputs = tokenizer(
                    prompts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=self.cfg.inference.max_input_tokens,
                )
                prompt_lens = [int((row != tokenizer.pad_token_id).sum()) for row in inputs["input_ids"]]
                inputs = {k: v.to(device) for k, v in inputs.items()}

                with torch.inference_mode():
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=self.cfg.inference.max_new_tokens,
                        do_sample=self.cfg.inference.do_sample,
                        temperature=self.cfg.inference.temperature,
                        pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=tokenizer.eos_token_id,
                    )

                b_latency_ms = (time.time() - b_start_time) * 1000.0
                per_item_latency = round(b_latency_ms / len(batch_slice), 2)

                prefix_len = inputs["input_ids"].shape[1]
                gen_tokens_batch = outputs[:, prefix_len:]

                for j, global_idx in enumerate(batch_slice):
                    gen_toks = gen_tokens_batch[j]
                    gen_count = int((gen_toks != tokenizer.pad_token_id).sum())
                    raw_text = tokenizer.decode(gen_toks, skip_special_tokens=True).strip()

                    _, _, _, parsed_dict, pyd_valid, errors, _ = OutputParser.parse_and_validate(raw_text)
                    if pyd_valid and parsed_dict:
                        validated_out = LogTriageOutput.model_validate(parsed_dict)
                        # Phase 14 Two-Stage Severity Calibration
                        impact = self.impact_extractor.extract(
                            logs[global_idx],
                            validated_out.root_cause,
                            validated_out.suggested_action,
                        )
                        decision = self.policy_engine.evaluate(impact)
                        severity_source = "POLICY_ENGINE"
                        if not decision.is_insufficient_evidence:
                            validated_out = validated_out.model_copy(update={"severity": decision.severity})
                        else:
                            severity_source = "MODEL"

                        telem = InferenceTelemetry(
                            latency_ms=per_item_latency,
                            prompt_tokens=prompt_lens[j],
                            generated_tokens=gen_count,
                            severity_source=severity_source,
                            severity_reason_code=decision.reason_code,
                        )
                        results[global_idx] = (validated_out, telem, None)
                    else:
                        err_detail = "; ".join(errors) if errors else "Invalid JSON"
                        results[global_idx] = (None, None, f"MODEL_OUTPUT_INVALID: {err_detail}")

            except torch.cuda.OutOfMemoryError:
                logger.error(f"CUDA OOM on micro-batch slice {batch_slice}. Falling back to sequential execution.")
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                # Process sequentially on OOM
                for global_idx in batch_slice:
                    try:
                        out, telem = self.triage_single(logs[global_idx], request_ids[global_idx])
                        results[global_idx] = (out, telem, None)
                    except Exception as ex:
                        results[global_idx] = (None, None, str(ex))
            except Exception as ex:
                logger.error(f"Error processing micro-batch slice: {ex}")
                for global_idx in batch_slice:
                    results[global_idx] = (None, None, str(ex))

        return results
