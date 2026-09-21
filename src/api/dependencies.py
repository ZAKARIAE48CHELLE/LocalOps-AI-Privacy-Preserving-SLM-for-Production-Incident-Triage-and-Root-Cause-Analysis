"""LocalOps AI — API Dependencies & Injections."""

from __future__ import annotations

import asyncio
from typing import Optional
from src.api.inference_service import InferenceService
from src.api.model_manager import ModelManager
from src.api.settings import settings

_concurrency_semaphore: Optional[asyncio.Semaphore] = None


def get_model_manager() -> ModelManager:
    return ModelManager.get_instance(settings)


def get_inference_service() -> InferenceService:
    return InferenceService(model_manager=get_model_manager(), cfg=settings)


def get_concurrency_limiter() -> asyncio.Semaphore:
    global _concurrency_semaphore
    if _concurrency_semaphore is None:
        _concurrency_semaphore = asyncio.Semaphore(settings.inference.max_concurrent_inference)
    return _concurrency_semaphore


_retriever_instance: Optional[RunbookRetriever] = None


def get_runbook_retriever() -> RunbookRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        from src.retrieval.retriever import RunbookRetriever
        _retriever_instance = RunbookRetriever()
    return _retriever_instance

