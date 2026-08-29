import pytest

from context_engine import ContextEngine, SourceKind
from context_engine.storage import InMemoryStorage


def _engine() -> ContextEngine:
    return ContextEngine(storage=InMemoryStorage())


def test_add_creates_first_version():
    engine = _engine()
    src = engine.register_source("crm", SourceKind.DATABASE_RECORD)
    item = engine.add("user.plan", "starter", src)
    assert item.version == 1
    assert item.is_active


def test_update_supersedes_previous_version():
    engine = _engine()
    src = engine.register_source("crm", SourceKind.DATABASE_RECORD)
    v1 = engine.add("user.plan", "starter", src)
    v2 = engine.update("user.plan", "enterprise", src)

    stored_v1 = engine.storage.get_item(v1.id)
    assert stored_v1 is not None
    assert stored_v1.superseded_by == v2.id
    assert not stored_v1.is_active

    active = [i for i in engine.storage.items_by_key("user.plan") if i.is_active]
    assert len(active) == 1
    assert active[0].content == "enterprise"


def test_add_rejects_empty_content_by_default():
    engine = _engine()
    src = engine.register_source("crm", SourceKind.DATABASE_RECORD)
    with pytest.raises(ValueError):
        engine.add("user.plan", "   ", src)


def test_add_allows_skipping_validation():
    engine = _engine()
    src = engine.register_source("crm", SourceKind.DATABASE_RECORD)
    item = engine.add("user.plan", "   ", src, validate=False)
    assert item.content.strip() == ""
