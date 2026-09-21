"""Phase 12 Verification Suite — Portfolio Polish, Release Integrity & Final Benchmark."""
import json
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.unit
def test_final_project_audit_exists():
    audit_file = PROJECT_ROOT / "documentation" / "FINAL_PROJECT_AUDIT.md"
    assert audit_file.exists(), "documentation/FINAL_PROJECT_AUDIT.md must exist."
    content = audit_file.read_text(encoding="utf-8")
    for phase_num in range(1, 12):
        assert f"Phase {phase_num}" in content, f"Audit must cover Phase {phase_num}."
    assert "LOCKED" in content, "Audit must certify locked status."


@pytest.mark.unit
def test_final_benchmark_integrity():
    bench_file = PROJECT_ROOT / "artifacts" / "release" / "final_benchmark.json"
    assert bench_file.exists(), "artifacts/release/final_benchmark.json must exist."
    with open(bench_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "canonical_comparison_table" in data or "model_benchmarks" in data
    assert "retrieval_augmented_generation" in data

    if "e4_canonical_summary" in data:
        e4 = data["e4_canonical_summary"]
        assert e4["pydantic_valid_rate"] == 0.991
        assert e4["incident_type_macro_f1"] == 0.9892
        assert e4["severity_macro_f1"] == 0.9955
        assert e4["affected_service_exact_match"] == 0.991
        assert e4["evidence_verbatim_rate"] == 0.9675
    else:
        e4 = data["model_benchmarks"]["fine_tuned_e4_qlora"]
        assert e4["incident_type_macro_f1"] > 0.95
        assert e4["severity_macro_f1"] > 0.95

    # Check canonical table deltas
    if "canonical_comparison_table" in data:
        table = data["canonical_comparison_table"]
        assert table["incident_type_macro_f1"]["delta_vs_best_baseline"] > 0.50
        assert table["severity_macro_f1"]["delta_vs_best_baseline"] > 0.70


@pytest.mark.unit
def test_serving_parity_status():
    parity_file = PROJECT_ROOT / "artifacts" / "release" / "serving_parity.json"
    assert parity_file.exists(), "artifacts/release/serving_parity.json must exist."
    with open(parity_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("status") == "PASSED", "Serving parity must be PASSED."
    assert data.get("exact_parity_rate") == 1.0, "Exact parity rate must be 100%."
    assert data.get("schema_validity_rate") == 1.0, "Schema validity must be 100%."
    assert len(data.get("records", [])) == 6, "Must test 6 stratified records."


@pytest.mark.unit
def test_model_and_dataset_cards_exist():
    model_card = PROJECT_ROOT / "MODEL_CARD.md"
    dataset_card = PROJECT_ROOT / "DATASET_CARD.md"
    assert model_card.exists(), "MODEL_CARD.md must exist."
    assert dataset_card.exists(), "DATASET_CARD.md must exist."

    mc_content = model_card.read_text(encoding="utf-8")
    assert "Qwen/Qwen2.5-1.5B-Instruct" in mc_content
    assert "checkpoint-100" in mc_content
    assert "Synthetic" in mc_content or "synthetic" in mc_content

    dc_content = dataset_card.read_text(encoding="utf-8")
    assert "36 Incident Families" in dc_content
    assert "7,200" in dc_content


@pytest.mark.unit
def test_documentation_completeness():
    required_docs = [
        "documentation/architecture.md",
        "documentation/api.md",
        "documentation/operations.md",
        "documentation/reproducibility.md",
        "README.md"
    ]
    for doc in required_docs:
        doc_path = PROJECT_ROOT / doc
        assert doc_path.exists(), f"Required documentation {doc} must exist."
        assert doc_path.stat().st_size > 500, f"{doc} must contain substantive content."


@pytest.mark.unit
def test_release_checksums_and_notes():
    checksums_file = PROJECT_ROOT / "artifacts" / "release" / "checksums.sha256"
    release_notes = PROJECT_ROOT / "artifacts" / "release" / "release_notes.md"
    assert checksums_file.exists(), "artifacts/release/checksums.sha256 must exist."
    assert release_notes.exists(), "artifacts/release/release_notes.md must exist."

    lines = [line.strip() for line in checksums_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 10, "Checksums file must record at least 10 critical artifacts."
    for line in lines:
        parts = line.split()
        assert len(parts) == 2, f"Invalid checksum line format: {line}"
        sha, rel_file = parts
        assert len(sha) == 64, f"Invalid SHA-256 hash length: {sha}"
        target_path = PROJECT_ROOT / rel_file
        assert target_path.exists(), f"File {rel_file} listed in checksums.sha256 must exist on disk."


@pytest.mark.unit
def test_demo_scenario_integrity():
    demo_file = PROJECT_ROOT / "scripts" / "demo_localops.py"
    assert demo_file.exists(), "scripts/demo_localops.py must exist."
    
    from scripts.demo_localops import DEMO_SCENARIOS
    assert len(DEMO_SCENARIOS) == 6, "Must define 6 curated demo scenarios."
    domains = {s["domain"] for s in DEMO_SCENARIOS}
    expected_domains = {"APPLICATION", "DATABASE", "INFRASTRUCTURE", "NETWORK", "SECURITY", "MESSAGING"}
    assert domains == expected_domains, "Demo must cover all 6 incident domains."
    
    severities = {s["expected_severity"] for s in DEMO_SCENARIOS}
    assert "P1_CRITICAL" in severities, "Demo must include P1_CRITICAL."
    assert "P4_LOW" in severities, "Demo must include P4_LOW."
