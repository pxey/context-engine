"""Retrieval and ranking.

The default retriever is dependency-free keyword overlap scored together
with recency and confidence — good enough to be useful out of the box and
completely free of any LLM/embedding provider. Callers who want semantic
retrieval can inject their own ``Retriever`` (e.g. wrapping an embedding
model of their choice); the engine has no opinion on which one.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from .models import ContextItem

_WORD_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text)}


class Retriever(Protocol):
    def score(self, query: str, item: ContextItem) -> float: ...


class KeywordRetriever:
    """Default retriever: Jaccard-style keyword overlap, weighted by the
    item's own confidence and a mild recency boost. No embeddings, no
    external calls.
    """

    def __init__(self, recency_half_life_days: float = 30.0) -> None:
        self.recency_half_life_days = recency_half_life_days

    def score(self, query: str, item: ContextItem) -> float:
        query_tokens = _tokenize(query)
        item_tokens = _tokenize(item.content)
        if not query_tokens or not item_tokens:
            overlap = 0.0
        else:
            overlap = len(query_tokens & item_tokens) / len(query_tokens | item_tokens)

        age_days = max((datetime.now(UTC) - item.timestamp).total_seconds() / 86400.0, 0.0)
        recency = 0.5 ** (age_days / self.recency_half_life_days) if self.recency_half_life_days > 0 else 1.0

        return (0.7 * overlap + 0.3 * recency) * item.confidence


class EmbeddingRetriever:
    """Optional retriever for callers who want semantic search. Pass any
    ``embed(text) -> Sequence[float]`` function — the engine never imports
    a specific embedding provider, so you stay in full control of cost and
    vendor choice.
    """

    def __init__(self, embed: Callable[[str], list[float]]) -> None:
        self._embed = embed
        self._cache: dict[str, list[float]] = {}

    def _vector(self, text: str) -> list[float]:
        if text not in self._cache:
            self._cache[text] = self._embed(text)
        return self._cache[text]

    def score(self, query: str, item: ContextItem) -> float:
        q = self._vector(query)
        v = self._vector(item.content)
        if not q or not v or len(q) != len(v):
            return 0.0
        dot = sum(a * b for a, b in zip(q, v))
        norm_q = sum(a * a for a in q) ** 0.5
        norm_v = sum(b * b for b in v) ** 0.5
        if norm_q == 0 or norm_v == 0:
            return 0.0
        return (dot / (norm_q * norm_v)) * item.confidence


def rank(query: str, items: list[ContextItem], retriever: Retriever, top_k: int = 10) -> list[ContextItem]:
    scored = [(retriever.score(query, item), item) for item in items]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for score, item in scored[:top_k] if score > 0]
