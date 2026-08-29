"""Core domain model for the AI Context Engine.

    Source -> Context Item -> Identity -> Version -> Relationship
           -> Validation -> Retrieval -> Context Package

Every :class:`ContextItem` carries a stable id, a logical ``key`` (its
"identity" — the entity it is a version of, e.g. ``"user.email"`` or
``"doc:readme#section-2"``), a source, a version number, provenance, a
confidence score, and relationships to other items. Items are immutable
once created; "updating" a key creates a new version and supersedes the
old one, so the full history is always reconstructable.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceKind(str, Enum):
    DOCUMENT = "document"
    MESSAGE = "message"
    DATABASE_RECORD = "database_record"
    API_RESPONSE = "api_response"
    TOOL_OUTPUT = "tool_output"
    AGENT_OBSERVATION = "agent_observation"
    USER_PROVIDED = "user_provided"


class Source(BaseModel):
    """Where a piece of context came from."""

    id: str = Field(default_factory=lambda: _new_id("src"))
    kind: SourceKind
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class ContextItem(BaseModel):
    """A single, immutable, versioned unit of context."""

    id: str = Field(default_factory=lambda: _new_id("ctx"))
    key: str
    """Logical identity this item is a version of. Two items with the same
    key are different versions/observations of the same fact."""

    content: str
    source_id: str
    source_kind: SourceKind
    version: int = 1
    timestamp: datetime = Field(default_factory=_utcnow)
    provenance: str = ""
    """Human-readable explanation of how this item was produced."""
    confidence: float = 1.0
    relationships: list[str] = Field(default_factory=list)
    """IDs of other ContextItems this one relates to / depends on."""
    metadata: dict[str, Any] = Field(default_factory=dict)
    superseded_by: str | None = None

    model_config = {"frozen": True}

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()[:16]

    @property
    def is_active(self) -> bool:
        return self.superseded_by is None


class ConflictKind(str, Enum):
    VALUE_MISMATCH = "value_mismatch"
    STALE_SOURCE = "stale_source"


class ConflictRecord(BaseModel):
    """Two or more active items share a key but disagree on content."""

    key: str
    kind: ConflictKind
    item_ids: list[str]
    description: str
    detected_at: datetime = Field(default_factory=_utcnow)


class ValidationIssue(BaseModel):
    field: str
    message: str
    severity: str = "error"  # "error" | "warning"


class ValidationResult(BaseModel):
    item_id: str
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class ContextPackage(BaseModel):
    """A reproducible, explainable bundle of context items produced by a
    single retrieve()/snapshot() call.
    """

    id: str = Field(default_factory=lambda: _new_id("pkg"))
    query: str | None = None
    items: list[ContextItem]
    created_at: datetime = Field(default_factory=_utcnow)

    @property
    def snapshot_hash(self) -> str:
        """Deterministic hash of the package contents — reproducing the
        same items yields the same hash, useful for caching/auditing."""
        joined = "|".join(sorted(f"{i.id}:{i.content_hash}" for i in self.items))
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]

    def as_text(self, separator: str = "\n\n") -> str:
        return separator.join(item.content for item in self.items)


class Explanation(BaseModel):
    """Answers: why was this item included, from which source/version,
    and what other context influenced its selection?
    """

    item_id: str
    source: Source | None
    version: int
    provenance: str
    confidence: float
    influenced_by: list[str]
    """IDs of items in `relationships` that influenced this one."""
    reason: str
