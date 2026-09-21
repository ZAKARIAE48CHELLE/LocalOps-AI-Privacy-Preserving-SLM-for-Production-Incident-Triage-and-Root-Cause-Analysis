import json
import logging
import sys
from pathlib import Path
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evaluate_checkpoints")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.validator import GenerationValidator

def main():
    val_file = PROJECT_ROOT / "data" / "generated" / "validation.jsonl"
    checkpoints_dir = PROJECT_ROOT / "artifacts" / "phase_5" / "checkpoints"
    final_adapter_dir = PROJECT_ROOT / "artifacts" / "phase_5" / "final_adapter"
    metrics_file = PROJECT_ROOT / "artifacts" / "phase_5" / "training_metrics.json"

    with open(metrics_file, "r", encoding="utf-8") as f:
        training_metrics = json.load(f)

    # Extract recorded eval_loss for steps
    eval_losses = {}
    for entry in training_metrics.get("training_history", []):
        if "eval_loss" in entry and "step" in entry:
            eval_losses[entry["step"]] = entry["eval_loss"]

    logger.info(f"Recorded eval losses: {eval_losses}")

    # Targets to evaluate
    eval_targets = [
        ("checkpoint-100", checkpoints_dir / "checkpoint-100", 100),
        ("checkpoint-800", checkpoints_dir / "checkpoint-800", 800),
        ("checkpoint-810", checkpoints_dir / "checkpoint-810", 810),
        ("final_adapter_step810", final_adapter_dir, 810),
    ]

    base_model_id = "Qwen/Qwen2.5-1.5B-Instruct"
    logger.info(f"Loading base model {base_model_id} in 4-bit NF4...")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        base_model_id,
        trust_remote_code=True,
        padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        quantization_config=bnb_config,
        device_map={"": 0},
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
    )

    validator = GenerationValidator(
        validation_file=val_file,
        tokenizer=tokenizer,
        sample_size=48,
    )

    results = []

    for name, adapter_path, step in eval_targets:
        if not adapter_path.exists():
            logger.warning(f"Target path {adapter_path} does not exist, skipping.")
            continue

        logger.info("=" * 60)
        logger.info(f"Evaluating: {name} from {adapter_path} (step {step})")
        logger.info("=" * 60)

        # Load adapter
        peft_model = PeftModel.from_pretrained(base_model, str(adapter_path))
        peft_model.eval()

        gen_metrics = validator.evaluate(peft_model, device="cuda", max_new_tokens=384)
        del peft_model
        torch.cuda.empty_cache()

        rec_eval_loss = eval_losses.get(step, None)

        record = {
            "name": name,
            "path": str(adapter_path),
            "step": step,
            "eval_loss": rec_eval_loss,
            **gen_metrics,
        }
        results.append(record)
        logger.info(f"Result for {name}: {record}")

    # Save to JSON
    output_path = PROJECT_ROOT / "artifacts" / "phase_5" / "checkpoint_validation_comparison.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Saved comparison to {output_path}")

if __name__ == "__main__":
    main()
