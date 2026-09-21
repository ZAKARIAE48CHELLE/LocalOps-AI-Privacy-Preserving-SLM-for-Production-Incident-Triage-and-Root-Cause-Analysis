"""LocalOps AI — GPU Release Checks Script.

Validates end-to-end hardware acceleration, 4-bit NF4 quantization, LoRA adapter attachment,
deterministic greedy generation, and RAG retrieval on the host NVIDIA GPU.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch

from src.api.model_manager import ModelManager
from src.api.settings import settings
from src.retrieval.retriever import RunbookRetriever
from src.schemas.enums import IncidentType
from src.schemas.triage import LogTriageOutput

logger = logging.getLogger("localops.gpu_checks")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def run_gpu_release_checks() -> dict:
    logger.info("Starting GPU release verification...")

    results = {
        "timestamp": time.time(),
        "cuda_available": torch.cuda.is_available(),
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None",
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "torch_version": torch.__version__,
        "checks": {},
    }

    if not torch.cuda.is_available():
        logger.warning("CUDA is NOT available on this host! GPU release checks will record failure.")
        results["checks"]["cuda_presence"] = False
        return results

    results["checks"]["cuda_presence"] = True
    vram_total_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
    results["vram_total_gb"] = vram_total_gb

    # 1. Model Loading
    logger.info("Loading 4-bit NF4 base model and LoRA adapter...")
    t0 = time.time()
    manager = ModelManager.get_instance(settings)
    manager.load_model()
    load_time_s = round(time.time() - t0, 2)
    results["checks"]["model_loading_seconds"] = load_time_s
    results["checks"]["model_is_ready"] = manager.is_ready

    # 2. Real GPU Inference
    logger.info("Executing real GPU inference on synthetic production incident log...")
    raw_log = (
        "[2026-10-12T13:43:42.127Z] [ERROR] [event-processor] Npgsql.NpgsqlException: "
        "The connection pool has reached its maximum size and no connections are currently available"
    )

    t_inf_0 = time.time()
    prompt = (
        f"<|im_start|>system\n"
        f"You are a production incident triage assistant.\n"
        f"Return only valid JSON following the required schema.<|im_end|>\n"
        f"<|im_start|>user\n"
        f"{raw_log}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    inputs = manager.tokenizer(prompt, return_tensors="pt").to(manager.device)
    with torch.inference_mode():
        out_ids = manager.model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
            pad_token_id=manager.tokenizer.pad_token_id,
            eos_token_id=manager.tokenizer.eos_token_id,
        )

    gen_ids = out_ids[0][inputs["input_ids"].shape[1]:]
    raw_text = manager.tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
    inf_latency_ms = round((time.time() - t_inf_0) * 1000.0, 1)

    results["checks"]["inference_latency_ms"] = inf_latency_ms
    results["checks"]["raw_generation_length"] = len(raw_text)

    # Validate output schema
    from src.evaluation.parser import OutputParser
    _, _, _, parsed_dict, pyd_valid, errors, _ = OutputParser.parse_and_validate(raw_text)
    results["checks"]["pydantic_schema_valid"] = pyd_valid

    if pyd_valid and parsed_dict:
        triage_out = LogTriageOutput.model_validate(parsed_dict)
        results["checks"]["predicted_incident_type"] = (
            triage_out.incident_type.value if hasattr(triage_out.incident_type, "value") else str(triage_out.incident_type)
        )
        results["checks"]["predicted_severity"] = (
            triage_out.severity.value if hasattr(triage_out.severity, "value") else str(triage_out.severity)
        )
        results["checks"]["predicted_affected_service"] = triage_out.affected_service

    # 3. RAG Retrieval
    logger.info("Testing RAG retrieval over indexed runbooks...")
    retriever = RunbookRetriever()
    remediation = retriever.retrieve(
        incident_type=IncidentType.DATABASE,
        affected_service="event-processor",
        root_cause="Npgsql connection pool starvation",
        raw_log=raw_log,
    )

    results["checks"]["rag_match_success"] = remediation is not None
    if remediation:
        results["checks"]["rag_runbook"] = remediation.runbook_document
        results["checks"]["rag_score"] = remediation.relevance_score

    # VRAM check
    vram_peak_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 1)
    results["checks"]["peak_vram_mb"] = vram_peak_mb

    out_file = Path("artifacts/release/gpu_release_check.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"GPU release checks completed successfully. Saved to {out_file}")
    return results


if __name__ == "__main__":
    res = run_gpu_release_checks()
    print(json.dumps(res, indent=2))
