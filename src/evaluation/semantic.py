"""
Local semantic similarity module for Phase 4: Baseline Evaluation.
Computes cosine similarity between predicted and target text using local sentence embeddings
via sentence-transformers/all-MiniLM-L6-v2.
Runs 100% locally with zero external API calls.
"""

from typing import Any, List, Optional, Tuple
import torch


class LocalSemanticEvaluator:
    """
    Computes semantic similarity locally using sentence-transformers/all-MiniLM-L6-v2.
    Ensures attention-mask-aware mean pooling, L2 normalization, and cosine similarity.
    Supports offline fallback if the model is unavailable.
    """

    def __init__(
        self,
        model_name_or_path: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu",
    ):
        self.model_name = model_name_or_path
        self.device = device if torch.cuda.is_available() and device == "cuda" else "cpu"
        self._tokenizer = None
        self._model = None
        self._loaded = False
        self._init_error: Optional[str] = None

    def _ensure_loaded(self) -> bool:
        """Lazily loads the embedding model from cache or Hugging Face repository."""
        if self._loaded:
            return True
        if self._init_error:
            return False

        try:
            from transformers import AutoModel, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(self.model_name).to(self.device)
            self._model.eval()
            self._loaded = True
            return True
        except Exception as e:
            self._init_error = str(e)
            return False

    @staticmethod
    def _mean_pooling(model_output: Any, attention_mask: torch.Tensor) -> torch.Tensor:
        """
        Attention-mask-aware mean pooling to extract sentence embedding from token embeddings.
        Tokens that are masked (padding) are explicitly excluded from the average.
        """
        token_embeddings = model_output[0]  # First element contains hidden states [batch_size, seq_len, hidden_dim]
        input_mask_expanded = (
            attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        )
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, dim=1)
        sum_mask = torch.clamp(input_mask_expanded.sum(dim=1), min=1e-9)
        return sum_embeddings / sum_mask

    @staticmethod
    def _token_overlap_fallback(text_a: str, text_b: str) -> float:
        """Deterministic lexical fallback when embedding model is not available."""
        tokens_a = set(text_a.lower().split())
        tokens_b = set(text_b.lower().split())
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a.intersection(tokens_b)
        union = tokens_a.union(tokens_b)
        return len(intersection) / len(union)

    def _encode_texts(self, texts: List[str], batch_size: int = 64) -> torch.Tensor:
        """
        Encodes a list of texts into L2-normalized sentence embeddings using mean pooling.
        """
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            ).to(self.device)
            output = self._model(**encoded)
            embs = self._mean_pooling(output, encoded["attention_mask"])
            norm_embs = torch.nn.functional.normalize(embs, p=2, dim=1)
            all_embeddings.append(norm_embs)
        return torch.cat(all_embeddings, dim=0)

    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Computes cosine similarity between two sentences using L2-normalized embeddings."""
        if not text_a or not text_b:
            return 0.0
        if text_a.strip() == text_b.strip():
            return 1.0

        if not self._ensure_loaded():
            return round(self._token_overlap_fallback(text_a, text_b), 4)

        try:
            with torch.no_grad():
                embs = self._encode_texts([text_a, text_b], batch_size=2)
                sim = torch.dot(embs[0], embs[1]).item()
                return round(max(0.0, min(1.0, float(sim))), 4)
        except Exception:
            return round(self._token_overlap_fallback(text_a, text_b), 4)

    def compute_batch_similarities(
        self, pairs: List[Tuple[str, str]], batch_size: int = 64
    ) -> List[float]:
        """
        Vectorized computation of pairwise cosine similarities for a list of (text_a, text_b) pairs.
        Uses attention-mask-aware mean pooling and L2 normalization.
        """
        if not pairs:
            return []

        if not self._ensure_loaded():
            return [self.compute_similarity(a, b) for a, b in pairs]

        try:
            with torch.no_grad():
                results = [0.0] * len(pairs)
                compute_indices = []
                comp_a = []
                comp_b = []

                for idx, (a, b) in enumerate(pairs):
                    if not a or not b:
                        results[idx] = 0.0
                    elif a.strip() == b.strip():
                        results[idx] = 1.0
                    else:
                        compute_indices.append(idx)
                        comp_a.append(a)
                        comp_b.append(b)

                if compute_indices:
                    embs_a = self._encode_texts(comp_a, batch_size=batch_size)
                    embs_b = self._encode_texts(comp_b, batch_size=batch_size)
                    sims = (embs_a * embs_b).sum(dim=-1).clamp(0.0, 1.0).tolist()
                    for idx, s in zip(compute_indices, sims):
                        results[idx] = round(float(s), 4)

                return results
        except Exception:
            return [self.compute_similarity(a, b) for a, b in pairs]

