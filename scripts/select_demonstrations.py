"""
Utility script to deterministically select, freeze, and validate the 6 few-shot demonstrations for E3.
Demonstrations are drawn exclusively from train.jsonl.
Guarantees 100% zero-leakage against test.jsonl.
"""

import hashlib
import json
import os
from pathlib import Path


def select_and_freeze_demonstrations(
    train_path: str = "data/generated/train.jsonl",
    test_path: str = "data/generated/test.jsonl",
    output_manifest: str = "reports/evaluation/few_shot_manifest.json",
    output_config: str = "configs/evaluation/few_shot_demonstrations.json",
) -> dict:
    test_ids = set()
    test_tpls = set()
    with open(test_path, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            test_ids.add(r["incident_id"])
            test_tpls.add(r["metadata"]["template_id"])

    # Target diverse coverage across 6 incident types and 4 severities
    target_specs = [
        ("DATABASE", "P1_CRITICAL"),
        ("INFRASTRUCTURE", "P2_HIGH"),
        ("APPLICATION", "P3_MEDIUM"),
        ("SECURITY", "P1_CRITICAL"),
        ("NETWORK", "P4_LOW"),
        ("MESSAGING", "P2_HIGH"),
    ]

    selected = []
    found_types = set()

    with open(train_path, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            inc_type = r["target"]["incident_type"]
            sev = r["target"]["severity"]
            tpl = r["metadata"]["template_id"]

            # Leakage checks
            if r["incident_id"] in test_ids or tpl in test_tpls:
                continue

            for t_type, t_sev in target_specs:
                if inc_type == t_type and sev == t_sev and t_type not in found_types:
                    rec_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()
                    demo_entry = {
                        "incident_id": r["incident_id"],
                        "incident_type": inc_type,
                        "incident_family": r["metadata"]["incident_family"],
                        "severity": sev,
                        "technology": r["metadata"]["technology"],
                        "template_id": tpl,
                        "record_hash": rec_hash,
                        "raw_log": r["raw_log"],
                        "target": r["target"],
                    }
                    selected.append(demo_entry)
                    found_types.add(t_type)
                    break

            if len(selected) == 6:
                break

    if len(selected) != 6:
        raise RuntimeError(f"Expected 6 demonstrations, got {len(selected)}")

    # Verify zero leakage
    for demo in selected:
        assert demo["incident_id"] not in test_ids, f"Leakage: demo ID {demo['incident_id']} in test!"
        assert demo["template_id"] not in test_tpls, f"Leakage: template ID {demo['template_id']} in test!"

    manifest = {"demonstrations": selected}

    Path(output_manifest).parent.mkdir(parents=True, exist_ok=True)
    Path(output_config).parent.mkdir(parents=True, exist_ok=True)

    with open(output_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    with open(output_config, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Successfully froze {len(selected)} demonstrations to:")
    print(f" - {output_manifest}")
    print(f" - {output_config}")
    return manifest


if __name__ == "__main__":
    select_and_freeze_demonstrations()
