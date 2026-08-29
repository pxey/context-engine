"""Conflict detection: find active items that share a key but disagree."""

from __future__ import annotations

from itertools import combinations

from .models import ConflictKind, ConflictRecord, ContextItem
from .storage import StorageBackend


def detect_conflicts(storage: StorageBackend) -> list[ConflictRecord]:
    """Scan all active items and flag keys where two or more active items
    have different content — i.e. the engine currently has no single
    answer for "what is the value of this key?".
    """
    active = storage.all_active_items()
    by_key: dict[str, list[ContextItem]] = {}
    for item in active:
        by_key.setdefault(item.key, []).append(item)

    conflicts: list[ConflictRecord] = []
    for key, items in by_key.items():
        if len(items) < 2:
            continue
        for a, b in combinations(items, 2):
            if a.content_hash != b.content_hash:
                conflicts.append(
                    ConflictRecord(
                        key=key,
                        kind=ConflictKind.VALUE_MISMATCH,
                        item_ids=[a.id, b.id],
                        description=(
                            f"Key '{key}' has disagreeing active values from "
                            f"sources {a.source_id} and {b.source_id}."
                        ),
                    )
                )
    return conflicts
