"""ContextEngine: the primary developer-facing API.

    engine.add(...)
    engine.update(...)
    engine.snapshot(...)
    engine.retrieve(...)
    engine.explain(...)
    engine.validate(...)
"""

from __future__ import annotations

from typing import Any

from .conflict import detect_conflicts
from .models import (
    ConflictRecord,
    ContextItem,
    ContextPackage,
    Explanation,
    Source,
    SourceKind,
    ValidationResult,
)
from .ranking import KeywordRetriever, Retriever, rank
from .storage import SQLiteStorage, StorageBackend
from .validation import DEFAULT_VALIDATORS, Validator, validate_item


class ContextEngine:
    """Provider-agnostic context infrastructure: ingest, version, validate,
    retrieve, and explain context for AI applications and agents.
    """

    def __init__(
        self,
        storage: StorageBackend | None = None,
        retriever: Retriever | None = None,
        validators: list[Validator] | None = None,
    ) -> None:
        self.storage: StorageBackend = storage if storage is not None else SQLiteStorage()
        self.retriever: Retriever = retriever if retriever is not None else KeywordRetriever()
        self.validators: list[Validator] = validators if validators is not None else DEFAULT_VALIDATORS

    # -- sources ----------------------------------------------------------

    def register_source(self, name: str, kind: SourceKind | str, **metadata: Any) -> Source:
        if isinstance(kind, str):
            kind = SourceKind(kind)
        source = Source(kind=kind, name=name, metadata=metadata)
        self.storage.save_source(source)
        return source

    # -- ingestion ----------------------------------------------------------

    def add(
        self,
        key: str,
        content: str,
        source: Source,
        *,
        provenance: str = "",
        confidence: float = 1.0,
        relationships: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        validate: bool = True,
    ) -> ContextItem:
        """Ingest a new, independent context item under ``key``.

        Unlike :meth:`update`, this does not supersede any existing item —
        use it for the first observation of a key, or when multiple
        sources legitimately report the same key concurrently (conflict
        detection will surface disagreements).
        """
        existing = self.storage.items_by_key(key)
        version = max((i.version for i in existing), default=0) + 1
        item = ContextItem(
            key=key,
            content=content,
            source_id=source.id,
            source_kind=source.kind,
            version=version,
            provenance=provenance or f"added from source '{source.name}'",
            confidence=confidence,
            relationships=relationships or [],
            metadata=metadata or {},
        )
        if validate:
            result = validate_item(item, self.validators)
            if not result.valid:
                messages = "; ".join(i.message for i in result.issues if i.severity == "error")
                raise ValueError(f"context item failed validation: {messages}")
        self.storage.save_item(item)
        return item

    def update(
        self,
        key: str,
        content: str,
        source: Source,
        *,
        provenance: str = "",
        confidence: float = 1.0,
        relationships: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        validate: bool = True,
    ) -> ContextItem:
        """Supersede the current active item(s) for ``key`` with a new
        version, preserving history.
        """
        new_item = self.add(
            key,
            content,
            source,
            provenance=provenance or f"updated from source '{source.name}'",
            confidence=confidence,
            relationships=relationships,
            metadata=metadata,
            validate=validate,
        )
        for old in self.storage.items_by_key(key):
            if old.id == new_item.id or not old.is_active:
                continue
            superseded = old.model_copy(update={"superseded_by": new_item.id})
            self.storage.save_item(superseded)
        return new_item

    # -- retrieval ----------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 10, *, only_active: bool = True) -> ContextPackage:
        """Rank and package the context items most relevant to ``query``."""
        pool = self.storage.all_active_items() if only_active else self.storage.all_items()
        ranked = rank(query, pool, self.retriever, top_k=top_k)
        return ContextPackage(query=query, items=ranked)

    def snapshot(self, keys: list[str] | None = None) -> ContextPackage:
        """Package the current active items — deterministic and
        reproducible: the same underlying data always yields the same
        ``snapshot_hash``.
        """
        if keys is None:
            items = self.storage.all_active_items()
        else:
            items = []
            for key in keys:
                items.extend(i for i in self.storage.items_by_key(key) if i.is_active)
        items.sort(key=lambda i: i.key)
        return ContextPackage(items=items)

    # -- explainability ----------------------------------------------------------

    def explain(self, item_id: str) -> Explanation | None:
        item = self.storage.get_item(item_id)
        if item is None:
            return None
        source = self.storage.get_source(item.source_id)
        influenced_by = [rid for rid in item.relationships if self.storage.get_item(rid) is not None]
        reason_parts = [f"version {item.version} of key '{item.key}'"]
        if source is not None:
            reason_parts.append(f"from source '{source.name}' ({source.kind.value})")
        if influenced_by:
            reason_parts.append(f"influenced by {len(influenced_by)} related item(s)")
        return Explanation(
            item_id=item.id,
            source=source,
            version=item.version,
            provenance=item.provenance,
            confidence=item.confidence,
            influenced_by=influenced_by,
            reason="; ".join(reason_parts),
        )

    # -- validation & conflicts ----------------------------------------------------------

    def validate(self, item_id: str) -> ValidationResult | None:
        item = self.storage.get_item(item_id)
        if item is None:
            return None
        return validate_item(item, self.validators)

    def conflicts(self) -> list[ConflictRecord]:
        return detect_conflicts(self.storage)

    def close(self) -> None:
        self.storage.close()
