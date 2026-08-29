"""Pluggable storage layer for context items and sources."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import ContextItem, Source, SourceKind


class StorageBackend(Protocol):
    def save_source(self, source: Source) -> None: ...

    def get_source(self, source_id: str) -> Source | None: ...

    def save_item(self, item: ContextItem) -> None: ...

    def get_item(self, item_id: str) -> ContextItem | None: ...

    def items_by_key(self, key: str) -> list[ContextItem]: ...

    def all_items(self) -> list[ContextItem]: ...

    def all_active_items(self) -> list[ContextItem]: ...

    def all_sources(self) -> list[Source]: ...

    def close(self) -> None: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    metadata TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    version INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    provenance TEXT NOT NULL,
    confidence REAL NOT NULL,
    relationships TEXT NOT NULL,
    metadata TEXT NOT NULL,
    superseded_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_items_key ON items(key);
"""


class SQLiteStorage:
    """Default, local-first, zero-config storage backend."""

    def __init__(self, path: str | Path = "context_engine.db") -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save_source(self, source: Source) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO sources (id, kind, name, metadata) VALUES (?, ?, ?, ?)",
            (source.id, source.kind.value, source.name, json.dumps(source.metadata)),
        )
        self._conn.commit()

    def get_source(self, source_id: str) -> Source | None:
        row = self._conn.execute(
            "SELECT id, kind, name, metadata FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        if row is None:
            return None
        return Source(id=row[0], kind=SourceKind(row[1]), name=row[2], metadata=json.loads(row[3]))

    def save_item(self, item: ContextItem) -> None:
        data = item.model_dump(mode="json")
        self._conn.execute(
            "INSERT OR REPLACE INTO items "
            "(id, key, content, source_id, source_kind, version, timestamp, provenance, "
            "confidence, relationships, metadata, superseded_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                item.id,
                item.key,
                item.content,
                item.source_id,
                item.source_kind.value,
                item.version,
                data["timestamp"],
                item.provenance,
                item.confidence,
                json.dumps(item.relationships),
                json.dumps(item.metadata),
                item.superseded_by,
            ),
        )
        self._conn.commit()

    def get_item(self, item_id: str) -> ContextItem | None:
        row = self._conn.execute(self._select_sql() + " WHERE id = ?", (item_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def items_by_key(self, key: str) -> list[ContextItem]:
        rows = self._conn.execute(
            self._select_sql() + " WHERE key = ? ORDER BY version ASC", (key,)
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def all_items(self) -> list[ContextItem]:
        rows = self._conn.execute(self._select_sql() + " ORDER BY timestamp ASC").fetchall()
        return [self._row_to_item(r) for r in rows]

    def all_active_items(self) -> list[ContextItem]:
        rows = self._conn.execute(
            self._select_sql() + " WHERE superseded_by IS NULL ORDER BY timestamp ASC"
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def all_sources(self) -> list[Source]:
        rows = self._conn.execute("SELECT id, kind, name, metadata FROM sources").fetchall()
        return [Source(id=r[0], kind=SourceKind(r[1]), name=r[2], metadata=json.loads(r[3])) for r in rows]

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _select_sql() -> str:
        return (
            "SELECT id, key, content, source_id, source_kind, version, timestamp, provenance, "
            "confidence, relationships, metadata, superseded_by FROM items"
        )

    @staticmethod
    def _row_to_item(row: tuple) -> ContextItem:
        (iid, key, content, source_id, source_kind, version, ts, provenance,
         confidence, relationships, metadata, superseded_by) = row
        return ContextItem(
            id=iid,
            key=key,
            content=content,
            source_id=source_id,
            source_kind=SourceKind(source_kind),
            version=version,
            timestamp=datetime.fromisoformat(ts),
            provenance=provenance,
            confidence=confidence,
            relationships=json.loads(relationships),
            metadata=json.loads(metadata),
            superseded_by=superseded_by,
        )


class InMemoryStorage:
    """Simple in-memory backend, useful for tests and short-lived scripts."""

    def __init__(self) -> None:
        self._sources: dict[str, Source] = {}
        self._items: dict[str, ContextItem] = {}

    def save_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def get_source(self, source_id: str) -> Source | None:
        return self._sources.get(source_id)

    def save_item(self, item: ContextItem) -> None:
        self._items[item.id] = item

    def get_item(self, item_id: str) -> ContextItem | None:
        return self._items.get(item_id)

    def items_by_key(self, key: str) -> list[ContextItem]:
        return sorted((i for i in self._items.values() if i.key == key), key=lambda i: i.version)

    def all_items(self) -> list[ContextItem]:
        return sorted(self._items.values(), key=lambda i: i.timestamp)

    def all_active_items(self) -> list[ContextItem]:
        return [i for i in self.all_items() if i.is_active]

    def all_sources(self) -> list[Source]:
        return list(self._sources.values())

    def close(self) -> None:
        pass
