"""AI Context Engine.

A provider-agnostic infrastructure layer for collecting, normalizing,
versioning, validating, retrieving, and packaging context for AI
applications and agents — usable without any specific LLM provider.

Quick start::

    from context_engine import ContextEngine, SourceKind

    engine = ContextEngine()
    src = engine.register_source("crm", SourceKind.DATABASE_RECORD)

    engine.add("user.plan", "enterprise", src, confidence=0.95)
    package = engine.retrieve("what plan is the user on?")
    print(package.as_text())
"""

from .conflict import detect_conflicts
from .engine import ContextEngine
from .models import (
    ConflictKind,
    ConflictRecord,
    ContextItem,
    ContextPackage,
    Explanation,
    Source,
    SourceKind,
    ValidationIssue,
    ValidationResult,
)
from .ranking import EmbeddingRetriever, KeywordRetriever, Retriever
from .storage import InMemoryStorage, SQLiteStorage, StorageBackend
from .validation import DEFAULT_VALIDATORS, Validator, validate_item

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_VALIDATORS",
    "ConflictKind",
    "ConflictRecord",
    "ContextEngine",
    "ContextItem",
    "ContextPackage",
    "EmbeddingRetriever",
    "Explanation",
    "InMemoryStorage",
    "KeywordRetriever",
    "Retriever",
    "SQLiteStorage",
    "Source",
    "SourceKind",
    "StorageBackend",
    "ValidationIssue",
    "ValidationResult",
    "Validator",
    "__version__",
    "detect_conflicts",
    "validate_item",
]
