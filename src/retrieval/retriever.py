"""LocalOps AI — Runbook Retriever.

Implements hybrid keyword, incident-type, and semantic retrieval over
indexed operational runbooks.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.retrieval.index_runbooks import build_runbook_index
from src.retrieval.schemas import RemediationRecommendation, RunbookChunk
from src.schemas.enums import IncidentType

logger = logging.getLogger("localops.retrieval.retriever")


class RunbookRetriever:
    """Retrieves the most relevant operational runbook section for a given incident."""

    def __init__(
        self,
        index_path: Path = Path("artifacts/phase_8/runbooks_index.json"),
        runbooks_dir: Path = Path("runbooks"),
    ):
        self.index_path = index_path
        self.runbooks_dir = runbooks_dir
        self.chunks: List[RunbookChunk] = []
        self._load_or_build_index()

    def _load_or_build_index(self):
        """Loads chunks from persistent index, or builds if absent."""
        if not self.index_path.exists():
            logger.info(f"Index not found at {self.index_path}. Building from {self.runbooks_dir}...")
            self.chunks = build_runbook_index(self.runbooks_dir, self.index_path)
        else:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.chunks = [RunbookChunk.model_validate(item) for item in data]
            logger.info(f"Loaded {len(self.chunks)} runbook chunks from {self.index_path}")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple deterministic tokenizer splitting on non-alphanumeric characters."""
        return re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text.lower())

    def retrieve(
        self,
        incident_type: IncidentType,
        affected_service: Optional[str] = None,
        root_cause: Optional[str] = None,
        raw_log: Optional[str] = None,
        preferred_section: str = "Immediate Mitigation",
    ) -> Optional[RemediationRecommendation]:
        """
        Retrieves the top-ranked remediation recommendation for the given incident.
        Uses hybrid scoring: incident type affinity, keyword overlap, service matching,
        and BM25-style term frequency.
        """
        if not self.chunks:
            return None

        query_text = f"{root_cause or ''} {raw_log or ''}".strip().lower()
        query_tokens = set(self._tokenize(query_text))

        best_chunk: Optional[RunbookChunk] = None
        best_score = -1.0
        best_matched_keywords: List[str] = []

        for chunk in self.chunks:
            score = 0.0
            matched_kws = []

            # 1. IncidentType Match (Strong categorical baseline: 0.35)
            if chunk.incident_type == incident_type:
                score += 0.35

            # 2. Section Relevance (Prioritize actionable operational mitigation: 0.15)
            if chunk.section.lower() == preferred_section.lower():
                score += 0.15
            elif "mitigation" in chunk.section.lower():
                score += 0.10
            elif "diagnosis" in chunk.section.lower():
                score += 0.05

            # 3. Affected Service Match (0.15)
            if affected_service and chunk.affected_services:
                clean_service = affected_service.lower().strip()
                if any(clean_service in s.lower() or s.lower() in clean_service for s in chunk.affected_services):
                    score += 0.15

            # 4. Keyword & Signature Matches (up to 0.25)
            if chunk.keywords:
                for kw in chunk.keywords:
                    kw_clean = kw.lower().strip()
                    if kw_clean in query_text:
                        matched_kws.append(kw)
                if matched_kws:
                    kw_ratio = min(len(matched_kws) / max(len(chunk.keywords), 1), 1.0)
                    score += 0.25 * kw_ratio

            # 5. Token Overlap / BM25 Jaccard (up to 0.10)
            chunk_tokens = set(self._tokenize(f"{chunk.title} {chunk.content}"))
            if query_tokens and chunk_tokens:
                intersection = query_tokens.intersection(chunk_tokens)
                overlap_ratio = len(intersection) / len(query_tokens)
                score += min(overlap_ratio * 0.10, 0.10)

            # Cap score between 0.0 and 1.0
            final_score = round(min(max(score, 0.0), 1.0), 3)

            if final_score > best_score:
                best_score = final_score
                best_chunk = chunk
                best_matched_keywords = matched_kws

        if not best_chunk or best_score < 0.20:
            return None

        return RemediationRecommendation(
            runbook_document=best_chunk.document,
            runbook_title=best_chunk.title,
            section=best_chunk.section,
            content=best_chunk.content,
            relevance_score=best_score,
            matched_keywords=best_matched_keywords,
        )
