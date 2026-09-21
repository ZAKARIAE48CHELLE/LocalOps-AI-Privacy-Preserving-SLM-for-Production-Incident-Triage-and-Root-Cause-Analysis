"""
FastAPI Server for Phase 4 Baseline Evaluation Real-Time Monitor.
Provides live telemetry, experiment progress, ETA calculation, GPU stats,
and real-time prediction feeds.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.dashboard.energy_tracker import EnergyTracker

app = FastAPI(title="LocalOps AI Evaluation Mission Control")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
EVAL_DIR = PROJECT_ROOT / "reports" / "evaluation"


def get_gpu_stats() -> Dict[str, Any]:
    """Reads real-time GPU statistics via nvidia-smi."""
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) >= 6:
                return {
                    "name": parts[0],
                    "gpu_util_pct": float(parts[1]),
                    "memory_used_mb": float(parts[2]),
                    "memory_total_mb": float(parts[3]),
                    "temp_c": float(parts[4]),
                    "power_w": float(parts[5]),
                }
    except Exception:
        pass
    return {
        "name": "NVIDIA RTX 3070",
        "gpu_util_pct": 0.0,
        "memory_used_mb": 0.0,
        "memory_total_mb": 8192.0,
        "temp_c": 0.0,
        "power_w": 0.0,
    }


def read_last_lines(file_path: Path, max_lines: int = 10) -> List[Dict[str, Any]]:
    """Reads the last N lines of a JSONL file without loading the whole file into memory."""
    if not file_path.exists():
        return []

    lines = []
    try:
        with open(file_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            buffer = bytearray()
            pointer = f.tell()
            while pointer > 0 and len(lines) < max_lines:
                read_size = min(4096, pointer)
                pointer -= read_size
                f.seek(pointer)
                chunk = f.read(read_size)
                buffer = chunk + buffer
                split_lines = buffer.split(b"\n")
                # Keep remaining partial line in buffer
                buffer = split_lines[0]
                for line in reversed(split_lines[1:]):
                    if line.strip():
                        try:
                            lines.append(json.loads(line.decode("utf-8")))
                        except Exception:
                            continue
                        if len(lines) >= max_lines:
                            break
            if buffer.strip() and len(lines) < max_lines:
                try:
                    lines.append(json.loads(buffer.decode("utf-8")))
                except Exception:
                    pass
    except Exception:
        pass
    return lines


def count_lines(file_path: Path) -> int:
    """Fast line count for JSONL."""
    if not file_path.exists():
        return 0
    count = 0
    try:
        with open(file_path, "rb") as f:
            for line in f:
                if line.strip():
                    count += 1
    except Exception:
        pass
    return count


@app.get("/api/status")
def get_evaluation_status():
    e1_path = EVAL_DIR / "e1_zero_shot" / "predictions.jsonl"
    e2_path = EVAL_DIR / "e2_structured" / "predictions.jsonl"
    e3_path = EVAL_DIR / "e3_few_shot" / "predictions.jsonl"

    c1 = count_lines(e1_path)
    c2 = count_lines(e2_path)
    c3 = count_lines(e3_path)

    total_target = 1440 * 3
    total_completed = c1 + c2 + c3

    # Determine current active experiment
    if c1 < 1440:
        active_exp = "E1"
        active_name = "E1 — Zero-Shot"
        active_count = c1
        recent_records = read_last_lines(e1_path, max_lines=8)
    elif c2 < 1440:
        active_exp = "E2"
        active_name = "E2 — Strong Structured Prompt"
        active_count = c2
        recent_records = read_last_lines(e2_path, max_lines=8)
    elif c3 < 1440:
        active_exp = "E3"
        active_name = "E3 — Few-Shot Prompting"
        active_count = c3
        recent_records = read_last_lines(e3_path, max_lines=8)
    else:
        active_exp = "COMPLETED"
        active_name = "Benchmark Complete"
        active_count = 1440
        recent_records = read_last_lines(e3_path, max_lines=8)

    # Calculate pace & ETA from recent records
    recent_latencies = [
        r.get("latency_seconds", 0.0)
        for r in recent_records
        if r.get("latency_seconds", 0.0) > 0
    ]
    avg_latency = (
        sum(recent_latencies) / len(recent_latencies) if recent_latencies else 20.0
    )

    remaining_in_active = max(0, 1440 - active_count)
    eta_active_sec = remaining_in_active * avg_latency

    remaining_total = max(0, total_target - total_completed)
    # E3 is ~11s, E2 is ~18s, E1 is ~20s
    eta_total_sec = (
        (max(0, 1440 - c1) * 20.0)
        + (max(0, 1440 - c2) * 18.0)
        + (max(0, 1440 - c3) * 11.0)
    )

    # Format ETAs
    def fmt_eta(seconds: float) -> str:
        if seconds <= 0:
            return "Complete"
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}h {m}m"
        return f"{m}m {s}s"

    # Latest record preview
    latest_record = recent_records[0] if recent_records else None

    # Sanitize recent records for frontend
    clean_recent = []
    for r in recent_records:
        gt = r.get("ground_truth") or {}
        meta = r.get("metadata") or {}
        parsed = r.get("parsed_output") or {}
        clean_recent.append(
            {
                "incident_id": r.get("incident_id"),
                "experiment_id": r.get("experiment_id"),
                "strict_json_valid": r.get("strict_json_valid", False),
                "json_extraction_success": r.get("json_extraction_success", False),
                "pydantic_valid": r.get("pydantic_valid", False),
                "latency_seconds": round(r.get("latency_seconds", 0.0), 2),
                "prompt_tokens": r.get("prompt_tokens", 0),
                "generated_tokens": r.get("generated_tokens", 0),
                "tokens_per_second": round(r.get("tokens_per_second", 0.0), 1),
                "incident_type_gt": gt.get("incident_type"),
                "incident_type_pred": parsed.get("incident_type"),
                "severity_gt": gt.get("severity"),
                "severity_pred": parsed.get("severity"),
                "affected_service_gt": gt.get("affected_service"),
                "affected_service_pred": parsed.get("affected_service"),
                "incident_family": meta.get("incident_family"),
                "technology": meta.get("technology"),
                "raw_output_preview": (r.get("raw_model_output") or "")[:280] + "...",
            }
        )

    # Check for completed metrics files
    metrics_status = {
        "E1": (EVAL_DIR / "e1_zero_shot" / "metrics.json").exists(),
        "E2": (EVAL_DIR / "e2_structured" / "metrics.json").exists(),
        "E3": (EVAL_DIR / "e3_few_shot" / "metrics.json").exists(),
        "final_comparison": (EVAL_DIR / "baseline_comparison.json").exists(),
    }

    gpu_info = get_gpu_stats()
    energy_info = EnergyTracker.get_instance().get_telemetry(
        completed_records=total_completed, total_records=total_target
    )

    return {
        "timestamp": time.time(),
        "overall": {
            "completed": total_completed,
            "total": total_target,
            "progress_pct": round((total_completed / total_target) * 100, 2),
            "eta_formatted": fmt_eta(eta_total_sec),
            "eta_seconds": round(eta_total_sec, 0),
        },
        "active_experiment": {
            "id": active_exp,
            "name": active_name,
            "completed": active_count,
            "total": 1440,
            "progress_pct": round((active_count / 1440) * 100, 2),
            "avg_latency_sec": round(avg_latency, 2),
            "eta_formatted": fmt_eta(eta_active_sec),
        },
        "experiments": {
            "E1": {
                "name": "Zero-Shot",
                "completed": c1,
                "total": 1440,
                "progress_pct": round((c1 / 1440) * 100, 2),
                "status": "COMPLETED" if c1 >= 1440 else ("RUNNING" if active_exp == "E1" else "PENDING"),
            },
            "E2": {
                "name": "Strong Structured Prompt",
                "completed": c2,
                "total": 1440,
                "progress_pct": round((c2 / 1440) * 100, 2),
                "status": "COMPLETED" if c2 >= 1440 else ("RUNNING" if active_exp == "E2" else "PENDING"),
            },
            "E3": {
                "name": "Few-Shot (6 Demos)",
                "completed": c3,
                "total": 1440,
                "progress_pct": round((c3 / 1440) * 100, 2),
                "status": "COMPLETED" if c3 >= 1440 else ("RUNNING" if active_exp == "E3" else "PENDING"),
            },
        },
        "gpu": gpu_info,
        "energy": energy_info,
        "metrics_ready": metrics_status,
        "recent_predictions": clean_recent,
        "configuration": {
            "model_id": "Qwen/Qwen2.5-1.5B-Instruct",
            "quantization": "4-bit NF4",
            "compute_dtype": "bfloat16",
            "batch_size": 8,
            "temperature": 0.0,
            "max_new_tokens": 384,
            "device": "NVIDIA GeForce RTX 3070 Laptop GPU (85W)",
        },
    }


PHASE5_DIR = PROJECT_ROOT / "artifacts" / "phase_5"


@app.get("/api/training_status")
def get_training_status():
    live_file = PHASE5_DIR / "live_training_state.json"
    metrics_file = PHASE5_DIR / "training_metrics.json"

    gpu_info = get_gpu_stats()
    energy_info = EnergyTracker.get_instance().get_telemetry()

    state = {
        "status": "ready",
        "global_step": 0,
        "max_steps": 810,
        "epoch": 0.0,
        "progress_pct": 0.0,
        "train_loss": None,
        "eval_loss": None,
        "learning_rate": 1.5e-4,
        "eta_seconds": 0,
        "eta_formatted": "Ready to Train",
        "elapsed_seconds": 0,
        "latest_generation_metrics": None,
        "recent_history": [],
        "generation_history": [],
        "best_checkpoint": None,
        "best_eval_loss": None,
    }

    if metrics_file.exists():
        try:
            with open(metrics_file, "r", encoding="utf-8") as f:
                metrics = json.load(f)
                state.update({
                    "status": "completed",
                    "global_step": metrics.get("total_steps", 810),
                    "max_steps": metrics.get("total_steps", 810),
                    "epoch": 3.0,
                    "progress_pct": 100.0,
                    "train_loss": metrics.get("final_train_loss"),
                    "eval_loss": metrics.get("best_eval_loss"),
                    "eta_formatted": "Completed",
                    "elapsed_seconds": metrics.get("train_runtime_seconds", 0.0),
                    "latest_generation_metrics": metrics.get("final_generation_metrics"),
                    "recent_history": (metrics.get("training_history") or [])[-60:],
                    "generation_history": metrics.get("generation_eval_history") or [],
                    "best_checkpoint": metrics.get("best_checkpoint"),
                    "best_eval_loss": metrics.get("best_eval_loss"),
                })
        except Exception:
            pass

    if live_file.exists():
        try:
            with open(live_file, "r", encoding="utf-8") as f:
                live_data = json.load(f)
                if live_data.get("status") in ["running", "evaluating"]:
                    state.update(live_data)
                elif state["status"] != "completed":
                    state.update(live_data)
        except Exception:
            pass

    # Load agent activity if present
    activity_file = PHASE5_DIR / "agent_activity.json"
    activity_info = {}
    if activity_file.exists():
        try:
            with open(activity_file, "r", encoding="utf-8") as f:
                activity_info = json.load(f)
        except Exception:
            pass

    return {
        "timestamp": time.time(),
        "training": state,
        "gpu": gpu_info,
        "energy": energy_info,
        "activity": activity_info,
        "model_spec": {
            "model_id": "Qwen/Qwen2.5-1.5B-Instruct",
            "method": "4-bit QLoRA (NF4)",
            "lora_rank": 16,
            "lora_alpha": 32,
            "trainable_params": 18464768,
            "trainable_pct": 1.182,
            "effective_batch_size": 16,
            "max_length": 1024,
            "device": "NVIDIA GeForce RTX 3070 Laptop GPU (8GB)",
        },
    }


@app.get("/api/checkpoints_comparison")
def get_checkpoints_comparison():
    comp_file = PHASE5_DIR / "checkpoint_validation_comparison.json"
    if comp_file.exists():
        try:
            with open(comp_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}
    return []


@app.get("/api/agent_activity")
def get_agent_activity():
    activity_file = PHASE5_DIR / "agent_activity.json"
    if activity_file.exists():
        try:
            with open(activity_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}
    return {"current_status": "IDLE", "timeline": []}


@app.get("/api/action_prompt")
def get_action_prompt():
    prompt_file = PHASE5_DIR / "user_action_prompt.json"
    response_file = PHASE5_DIR / "user_action_response.json"

    if not prompt_file.exists():
        return {"active": False}

    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt_data = json.load(f)

        if response_file.exists():
            with open(response_file, "r", encoding="utf-8") as rf:
                resp = json.load(rf)
            return {
                **prompt_data,
                "active": False,
                "answered": True,
                "response": resp,
            }

        return {
            **prompt_data,
            "active": True,
        }
    except Exception as e:
        return {"active": False, "error": str(e)}


@app.post("/api/action_response")
async def post_action_response(request: Request):
    response_file = PHASE5_DIR / "user_action_response.json"
    try:
        data = await request.json()
        data["received_at"] = time.time()
        data["received_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        PHASE5_DIR.mkdir(parents=True, exist_ok=True)
        with open(response_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return {"status": "ok", "saved": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/phase6_status")
def get_phase6_status():
    e4_dir = PROJECT_ROOT / "reports" / "evaluation" / "e4_qlora"
    preds_file = e4_dir / "predictions.jsonl"
    metrics_file = e4_dir / "metrics.json"
    live_status_file = PROJECT_ROOT / "artifacts" / "phase_6" / "live_evaluation_status.json"

    completed = count_lines(preds_file)
    total = 1440
    progress_pct = round((completed / total) * 100.0, 1)

    live_data = {}
    if live_status_file.exists():
        try:
            with open(live_status_file, "r", encoding="utf-8") as f:
                live_data = json.load(f)
        except Exception:
            pass

    metrics_data = None
    if metrics_file.exists():
        try:
            with open(metrics_file, "r", encoding="utf-8") as f:
                metrics_data = json.load(f)
        except Exception:
            pass

    recent_predictions = read_last_lines(preds_file, max_lines=6)

    return {
        "timestamp": time.time(),
        "status": "completed" if completed >= total else "evaluating" if completed > 0 else "ready",
        "completed": completed,
        "total": total,
        "progress_pct": min(100.0, progress_pct),
        "recent_predictions": recent_predictions,
        "metrics": metrics_data,
        "live_telemetry": live_data,
    }


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "LocalOps AI Dashboard Static assets initializing..."}
