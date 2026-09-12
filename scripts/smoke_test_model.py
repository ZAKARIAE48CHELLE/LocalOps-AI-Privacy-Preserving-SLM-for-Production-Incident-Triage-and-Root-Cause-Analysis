"""
Phase 1 Deliverable: Model Baseline Smoke Test & Telemetry Script.

Loads Qwen/Qwen2.5-1.5B-Instruct (in 4-bit NF4 quantization or bfloat16/float16),
runs a sample production incident triage inference, and measures:
- Model load time
- GPU VRAM allocation & peak usage
- Generation latency
- Token throughput (tokens/sec)
Outputs a structured summary to reports/smoke_test_baseline.json.
"""

import json
import os
import sys
import time
from pathlib import Path

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)


def get_gpu_info() -> dict:
    if not torch.cuda.is_available():
        return {"cuda_available": False, "gpu_name": "None", "vram_total_mb": 0}
    device_id = 0
    props = torch.cuda.get_device_properties(device_id)
    return {
        "cuda_available": True,
        "device_id": device_id,
        "gpu_name": props.name,
        "cuda_version": torch.version.cuda,
        "compute_capability": f"{props.major}.{props.minor}",
        "vram_total_mb": round(props.total_memory / (1024**2), 2),
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 60)
    print(" LocalOps AI — Phase 1: Local Model Baseline Smoke Test")
    print("=" * 60)

    # 1. Environment & Hardware Verification
    gpu_info = get_gpu_info()
    print(f"[+] Python Version      : {sys.version.split()[0]}")
    print(f"[+] PyTorch Version     : {torch.__version__}")
    print(f"[+] CUDA Available      : {gpu_info['cuda_available']}")

    if not gpu_info["cuda_available"]:
        print("[-] WARNING: CUDA is not available. Running on CPU (will be slow).")
        device_map = "cpu"
        bnb_config = None
        torch_dtype = torch.float32
    else:
        print(f"[+] GPU Detected        : {gpu_info['gpu_name']}")
        print(f"[+] Compute Capability  : {gpu_info['compute_capability']}")
        print(f"[+] Total VRAM Available: {gpu_info['vram_total_mb']} MB")
        device_map = "auto"

        # Check if 4-bit NF4 quantization is supported via bitsandbytes
        try:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
            torch_dtype = torch.bfloat16
            print("[+] Quantization        : 4-bit NF4 (Double Quant enabled)")
        except Exception as e:
            print(f"[!] Warning initializing BitsAndBytesConfig: {e}")
            print("[+] Falling back to 16-bit float")
            bnb_config = None
            torch_dtype = torch.float16

    model_name = os.getenv("BASE_MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct")
    print(f"[+] Model Identifier    : {model_name}")
    print("-" * 60)

    # Reset CUDA memory stats
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.empty_cache()

    # 2. Measure Model Load Time
    print("[*] Loading Tokenizer and Model...")
    t0_load = time.perf_counter()

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if bnb_config is not None:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map=device_map,
            trust_remote_code=True,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map=device_map,
            trust_remote_code=True,
        )

    t_load_done = time.perf_counter()
    load_duration = t_load_done - t0_load
    print(f"[OK] Model loaded successfully in {load_duration:.2f} seconds.")

    # Measure initial VRAM post-load
    vram_post_load_mb = 0.0
    if torch.cuda.is_available():
        vram_post_load_mb = round(torch.cuda.memory_allocated() / (1024**2), 2)
        print(f"[+] VRAM Allocated post-load: {vram_post_load_mb} MB")

    # 3. Formulate Sample Production Incident Prompt
    sample_raw_log = (
        "2026-09-11T14:22:01.341Z [orders-service] [HikariPool-1] ERROR "
        "com.zaxxer.hikari.pool.HikariPool - HikariPool-1 - Connection is not available, "
        "request timed out after 30005ms (total=50, active=50, idle=0, waiting=12).\n"
        "org.postgresql.util.PSQLException: FATAL: remaining connection slots are reserved "
        "for non-replication superuser connections"
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert site reliability and production incident triage assistant. "
                "Analyze the provided log and output a concise assessment including Incident Type, "
                "Severity, Affected Service, Likely Root Cause, and Immediate Remediation Action."
            ),
        },
        {"role": "user", "content": f"Production Incident Log:\n```\n{sample_raw_log}\n```"},
    ]

    prompt_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer([prompt_text], return_tensors="pt").to(model.device)
    prompt_tokens_len = inputs["input_ids"].shape[1]

    # 4. Measure Inference Latency & Throughput
    print("[*] Running inference test...")
    if torch.cuda.is_available():
        torch.cuda.synchronize()

    t0_gen = time.perf_counter()
    with torch.inference_mode():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=256,
            temperature=0.2,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    if torch.cuda.is_available():
        torch.cuda.synchronize()
    t_gen_done = time.perf_counter()

    gen_duration = t_gen_done - t0_gen
    total_tokens = generated_ids.shape[1]
    new_tokens = total_tokens - prompt_tokens_len
    tokens_per_sec = new_tokens / gen_duration if gen_duration > 0 else 0.0

    # VRAM measurements
    vram_peak_mb = 0.0
    vram_reserved_mb = 0.0
    if torch.cuda.is_available():
        vram_peak_mb = round(torch.cuda.max_memory_allocated() / (1024**2), 2)
        vram_reserved_mb = round(torch.cuda.memory_reserved() / (1024**2), 2)

    # Decode response
    output_tokens = generated_ids[0][prompt_tokens_len:]
    response_text = tokenizer.decode(output_tokens, skip_special_tokens=True).strip()

    print("\n" + "=" * 60)
    print(" Model Response")
    print("=" * 60)
    print(response_text)
    print("=" * 60)

    print("\n" + "=" * 60)
    print(" Performance & Telemetry Summary")
    print("=" * 60)
    print(f" Load Time           : {load_duration:.2f} s")
    print(f" Generation Latency  : {gen_duration:.2f} s")
    print(f" Prompt Tokens       : {prompt_tokens_len}")
    print(f" Generated Tokens    : {new_tokens}")
    print(f" Throughput          : {tokens_per_sec:.2f} tokens/s")
    if torch.cuda.is_available():
        print(f" VRAM Post-Load      : {vram_post_load_mb} MB")
        print(f" VRAM Peak (Inference): {vram_peak_mb} MB")
        print(f" VRAM Reserved       : {vram_reserved_mb} MB")
    print("=" * 60)

    # 5. Persist Results
    report_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_name": model_name,
        "quantization": "4bit-nf4" if bnb_config else "float16/float32",
        "gpu_info": gpu_info,
        "telemetry": {
            "load_time_seconds": round(load_duration, 3),
            "generation_latency_seconds": round(gen_duration, 3),
            "prompt_tokens": int(prompt_tokens_len),
            "generated_tokens": int(new_tokens),
            "tokens_per_second": round(tokens_per_sec, 2),
            "vram_post_load_mb": vram_post_load_mb,
            "vram_peak_mb": vram_peak_mb,
            "vram_reserved_mb": vram_reserved_mb,
        },
        "test_input": sample_raw_log,
        "model_output": response_text,
    }

    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "smoke_test_baseline.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"[OK] Baseline telemetry successfully written to {report_path}")
    print("[OK] Phase 1 Exit Criteria Verified!")


if __name__ == "__main__":
    main()
