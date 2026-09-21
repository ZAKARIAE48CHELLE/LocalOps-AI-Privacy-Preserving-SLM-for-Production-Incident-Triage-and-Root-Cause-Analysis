"""Unit and integration tests for Phase 5 QLoRA fine-tuning pipeline."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch
import yaml
from datasets import Dataset
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

from src.schemas import IncidentType, LogTriageOutput, Severity
from src.training.dataset import (
    LocalOpsChatDataset,
    format_training_messages,
    serialize_target_to_canonical_json,
)
from src.training.qlora import (
    get_lora_config,
    get_parameter_summary,
    get_quantization_config,
    load_qlora_model_and_tokenizer,
)


class TestDatasetFormattingAndIsolation:
    """Tests for dataset conversion, canonical serialization, and test split isolation."""

    def test_canonical_json_serialization(self):
        target = {
            "incident_type": "DATABASE",
            "severity": "P1_CRITICAL",
            "affected_service": "auth-db",
            "root_cause": "Deadlock encountered on user session table.",
            "suggested_action": "Kill blocked backend transaction and inspect lock wait timeout.",
            "confidence": 0.95,
            "evidence": ["Deadlock found when trying to get lock", "transaction rollback"],
        }
        serialized = serialize_target_to_canonical_json(target)
        parsed = json.loads(serialized)

        # Assert all 7 schema fields present
        assert parsed["incident_type"] == "DATABASE"
        assert parsed["severity"] == "P1_CRITICAL"
        assert parsed["affected_service"] == "auth-db"
        assert parsed["root_cause"] == "Deadlock encountered on user session table."
        assert parsed["confidence"] == 0.95
        assert len(parsed["evidence"]) == 2

        # Assert no metadata fields leaked
        assert "incident_family" not in parsed
        assert "template_id" not in parsed
        assert "diagnostic_clarity" not in parsed
        assert "noise_profile" not in parsed

    def test_format_training_messages_chatml(self):
        raw_log = "[ERROR] Connection pool starvation on 10.0.0.1:5432"
        target = {
            "incident_type": "DATABASE",
            "severity": "P2_HIGH",
            "affected_service": "pool-svc",
            "root_cause": "Connection pool capacity exceeded.",
            "suggested_action": "Increase pool limit.",
            "confidence": 0.88,
            "evidence": ["Connection pool starvation"],
        }
        messages = format_training_messages(raw_log, target)

        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert "incident triage assistant" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == raw_log
        assert messages[2]["role"] == "assistant"
        # Validate that assistant response parses into LogTriageOutput
        parsed = LogTriageOutput(**json.loads(messages[2]["content"]))
        assert parsed.incident_type == "DATABASE"

    def test_test_split_isolation_guard(self):
        """Verify that any attempt to load test.jsonl in Phase 5 is rejected."""
        with pytest.raises(ValueError, match="Dataset isolation boundary violation"):
            LocalOpsChatDataset.assert_not_test_split("data/generated/test.jsonl")

        with pytest.raises(ValueError, match="Dataset isolation boundary violation"):
            LocalOpsChatDataset.assert_not_test_split("path/to/test.jsonl")

        with pytest.raises(ValueError, match="Dataset isolation boundary violation"):
            LocalOpsChatDataset.load_records("data/generated/test.jsonl")

        with pytest.raises(ValueError, match="Dataset isolation boundary violation"):
            LocalOpsChatDataset.create_hf_dataset("data/generated/test.jsonl")


class TestAssistantLossMasking:
    """Tests that user/system prompt tokens are strictly masked from the loss."""

    def test_assistant_only_loss_masking_mechanism(self):
        tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
        system_text = "You are a production incident triage assistant."
        user_text = "CRITICAL: memory leak on auth-gateway."
        assistant_json = '{"incident_type":"APPLICATION","severity":"P1_CRITICAL"}'

        sample_data = [{
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": assistant_json},
            ]
        }]
        ds = Dataset.from_list(sample_data)

        cfg = SFTConfig(
            output_dir="artifacts/phase_5/test_loss_masking",
            max_length=512,
            assistant_only_loss=True,
            per_device_train_batch_size=1,
            report_to="none",
        )

        trainer = SFTTrainer(
            model="Qwen/Qwen2.5-1.5B-Instruct",
            args=cfg,
            train_dataset=ds,
            processing_class=tokenizer,
        )
        batch = next(iter(trainer.get_train_dataloader()))
        labels = batch["labels"][0]

        # Decode the unmasked tokens (where label != -100)
        unmasked_tokens = labels[labels != -100]
        decoded_unmasked = tokenizer.decode(unmasked_tokens, skip_special_tokens=False)

        # Assert that the system prompt and user query are NOT in the unmasked labels
        assert system_text not in decoded_unmasked
        assert user_text not in decoded_unmasked

        # Assert that the assistant JSON tokens ARE present in the unmasked labels
        assert "APPLICATION" in decoded_unmasked
        assert "P1_CRITICAL" in decoded_unmasked


class TestQLoRAArchitectureAndConfig:
    """Tests for 4-bit NF4 configuration, PEFT target modules, and parameter efficiency."""

    def test_quantization_config(self):
        bnb_cfg = get_quantization_config(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype="bfloat16",
        )
        assert bnb_cfg.load_in_4bit is True
        assert bnb_cfg.bnb_4bit_quant_type == "nf4"
        assert bnb_cfg.bnb_4bit_use_double_quant is True
        assert bnb_cfg.bnb_4bit_compute_dtype == torch.bfloat16

    def test_lora_config_targets_all_linear(self):
        lora_cfg = get_lora_config(r=16, lora_alpha=32, lora_dropout=0.05)
        expected_targets = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
        assert set(lora_cfg.target_modules) == expected_targets
        assert lora_cfg.r == 16
        assert lora_cfg.lora_alpha == 32
        assert lora_cfg.lora_dropout == 0.05

    def test_parameter_summary_calculation(self):
        class DummyModule(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.frozen = torch.nn.Linear(10, 10, bias=False)
                self.frozen.weight.requires_grad = False
                self.trainable = torch.nn.Linear(10, 2, bias=False)
                self.trainable.weight.requires_grad = True

        dummy = DummyModule()
        summary = get_parameter_summary(dummy)
        assert summary["trainable_parameters"] == 20
        assert summary["total_parameters"] == 120
        assert summary["trainable_percentage"] > 0.0

    def test_config_file_loading_and_validation(self):
        config_path = Path("configs/training.yaml")
        assert config_path.exists()
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        assert cfg["model"]["base_model_id"] == "Qwen/Qwen2.5-1.5B-Instruct"
        assert cfg["quantization"]["load_in_4bit"] is True
        assert cfg["lora"]["r"] == 16
        assert cfg["lora"]["lora_alpha"] == 32
        eff_batch = cfg["training"]["per_device_train_batch_size"] * cfg["training"]["gradient_accumulation_steps"]
        assert eff_batch == 16
        assert cfg["training"]["assistant_only_loss"] is True
        assert cfg["data"]["max_length"] == 1024
