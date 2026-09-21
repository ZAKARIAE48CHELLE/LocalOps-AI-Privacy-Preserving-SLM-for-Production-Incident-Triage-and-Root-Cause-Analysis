"""LocalOps AI — Phase 9 Docker & Packaging Test Suite."""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parent.parent


class TestDockerPackaging:

    def test_dockerfile_exists_and_syntax(self, repo_root):
        """Verify Dockerfile exists and enforces multi-stage non-root GPU setup."""
        df_path = repo_root / "Dockerfile"
        assert df_path.exists(), "Dockerfile must exist at repository root"

        content = df_path.read_text(encoding="utf-8")
        assert "FROM nvidia/cuda:12.4" in content
        assert "AS builder" in content
        assert "AS runner" in content
        assert "useradd" in content and "localops" in content
        assert "USER localops" in content
        assert "HEALTHCHECK" in content
        assert "/health" in content
        assert "ENTRYPOINT" in content

    def test_dockerignore_excludes_critical_paths(self, repo_root):
        """Verify .dockerignore excludes datasets, checkpoints, and environment artifacts."""
        di_path = repo_root / ".dockerignore"
        assert di_path.exists(), ".dockerignore must exist at repository root"

        content = di_path.read_text(encoding="utf-8")
        assert ".git" in content
        assert ".venv" in content
        assert "data/generated/" in content
        assert "__pycache__/" in content
        assert "checkpoint-*" in content

    def test_docker_compose_valid_yaml_and_structure(self, repo_root):
        """Verify docker-compose.yml parses and configures GPU device reservation & mounts."""
        dc_path = repo_root / "docker-compose.yml"
        assert dc_path.exists(), "docker-compose.yml must exist at repository root"

        with open(dc_path, "r", encoding="utf-8") as f:
            compose_cfg = yaml.safe_load(f)

        assert "services" in compose_cfg
        assert "localops-api" in compose_cfg["services"]

        service = compose_cfg["services"]["localops-api"]
        assert "ports" in service
        assert "environment" in service
        assert "volumes" in service
        assert "healthcheck" in service

        # Verify GPU device reservation
        deploy_res = service.get("deploy", {}).get("resources", {}).get("reservations", {})
        devices = deploy_res.get("devices", [])
        assert len(devices) > 0
        assert devices[0].get("driver") == "nvidia"
        assert "gpu" in devices[0].get("capabilities", [])

        # Verify model cache and adapter mounts
        vol_str = " ".join(service["volumes"])
        assert "final_adapter" in vol_str
        assert "huggingface" in vol_str

    def test_docker_env_example_contains_all_overrides(self, repo_root):
        """Verify docker.env.example specifies all required service switches."""
        env_path = repo_root / "configs" / "docker.env.example"
        assert env_path.exists()

        content = env_path.read_text(encoding="utf-8")
        assert "LOCALOPS_PORT" in content
        assert "LOCALOPS_LOG_RAW_PAYLOADS" in content
        assert "LOCALOPS_RAG_ENABLED" in content
        assert "HF_CACHE_DIR" in content
        assert "HF_HUB_OFFLINE" in content

    def test_smoke_test_script_exists_and_functional(self, repo_root):
        """Verify scripts/docker_smoke_test.py exists and defines run_smoke_test."""
        smoke_path = repo_root / "scripts" / "docker_smoke_test.py"
        assert smoke_path.exists()
        content = smoke_path.read_text(encoding="utf-8")
        assert "run_smoke_test" in content
        assert "/health" in content
        assert "/ready" in content
        assert "/api/v1/triage" in content
        assert "/api/v1/triage/enriched" in content
