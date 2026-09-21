"""LocalOps AI — Runbook Indexer.

Parses markdown runbooks into structured searchable chunks and persists them
to artifacts/phase_8/runbooks_index.json.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List

from src.retrieval.schemas import RunbookChunk
from src.schemas.enums import IncidentType

logger = logging.getLogger("localops.retrieval.indexer")


def parse_runbook_markdown(file_path: Path) -> List[RunbookChunk]:
    """Parses a markdown runbook into structured chunks per section."""
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Extract title
    title = file_path.stem.replace("_", " ").title()
    for line in lines:
        if line.startswith("# Runbook:"):
            title = line.replace("# Runbook:", "").strip()
            break
        elif line.startswith("# "):
            title = line.replace("# ", "").strip()
            break

    # Extract metadata block
    incident_type_str = ""
    affected_services: List[str] = []
    keywords: List[str] = []

    for line in lines:
        if "- **Incident Type**:" in line:
            incident_type_str = line.split("- **Incident Type**:")[1].strip()
        elif "- **Affected Services**:" in line:
            raw_srv = line.split("- **Affected Services**:")[1].strip()
            affected_services = [s.strip() for s in raw_srv.split(",") if s.strip()]
        elif "- **Keywords**:" in line:
            raw_kw = line.split("- **Keywords**:")[1].strip()
            keywords = [k.strip() for k in raw_kw.split(",") if k.strip()]

    # Map incident type
    incident_type_map = {
        "DATABASE": IncidentType.DATABASE,
        "INFRASTRUCTURE": IncidentType.INFRASTRUCTURE,
        "APPLICATION": IncidentType.APPLICATION,
        "SECURITY": IncidentType.SECURITY,
        "NETWORK": IncidentType.NETWORK,
        "MESSAGING": IncidentType.MESSAGING,
    }

    incident_type = incident_type_map.get(incident_type_str.upper())
    if not incident_type:
        # Infer from filename or default to APPLICATION
        stem_upper = file_path.stem.upper()
        for k, v in incident_type_map.items():
            if k in stem_upper:
                incident_type = v
                break
        if not incident_type:
            incident_type = IncidentType.APPLICATION

    # Split by H2 sections (## Section Name)
    section_pattern = re.compile(r"^##\s+(.+)$")
    chunks: List[RunbookChunk] = []

    current_section = "Overview"
    current_content_lines: List[str] = []

    for line in lines:
        match = section_pattern.match(line)
        if match:
            # Commit previous section if non-empty
            if current_content_lines:
                sec_text = "\n".join(current_content_lines).strip()
                if sec_text:
                    chunk_id = f"{file_path.stem}_{current_section.lower().replace(' ', '_')}"
                    chunks.append(
                        RunbookChunk(
                            chunk_id=chunk_id,
                            document=file_path.name,
                            title=title,
                            section=current_section,
                            incident_type=incident_type,
                            affected_services=affected_services,
                            keywords=keywords,
                            content=sec_text,
                        )
                    )
            current_section = match.group(1).strip()
            current_content_lines = []
        else:
            if not line.startswith("# ") and not line.startswith("- **"):
                current_content_lines.append(line)

    # Commit final section
    if current_content_lines:
        sec_text = "\n".join(current_content_lines).strip()
        if sec_text:
            chunk_id = f"{file_path.stem}_{current_section.lower().replace(' ', '_')}"
            chunks.append(
                RunbookChunk(
                    chunk_id=chunk_id,
                    document=file_path.name,
                    title=title,
                    section=current_section,
                    incident_type=incident_type,
                    affected_services=affected_services,
                    keywords=keywords,
                    content=sec_text,
                )
            )

    return chunks


def build_runbook_index(
    runbooks_dir: Path = Path("runbooks"),
    output_path: Path = Path("artifacts/phase_8/runbooks_index.json"),
) -> List[RunbookChunk]:
    """Indexes all runbooks in directory and writes to output_path."""
    if not runbooks_dir.exists():
        raise FileNotFoundError(f"Runbooks directory not found: {runbooks_dir}")

    all_chunks: List[RunbookChunk] = []
    md_files = list(runbooks_dir.glob("*.md"))
    if not md_files:
        raise ValueError(f"No markdown runbooks found in {runbooks_dir}")

    for md_file in sorted(md_files):
        chunks = parse_runbook_markdown(md_file)
        all_chunks.extend(chunks)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [chunk.model_dump() for chunk in all_chunks]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2)

    logger.info(f"Indexed {len(all_chunks)} chunks from {len(md_files)} runbooks into {output_path}")
    return all_chunks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    chunks = build_runbook_index()
    print(f"Successfully indexed {len(chunks)} runbook sections.")
