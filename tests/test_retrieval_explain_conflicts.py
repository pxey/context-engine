from context_engine import ContextEngine, SourceKind
from context_engine.storage import InMemoryStorage


def _engine() -> ContextEngine:
    return ContextEngine(storage=InMemoryStorage())


def test_retrieve_ranks_by_keyword_overlap_and_confidence():
    engine = _engine()
    src = engine.register_source("docs", SourceKind.DOCUMENT)
    engine.add("doc.a", "the billing cycle resets every month", src, confidence=1.0)
    engine.add("doc.b", "cats are wonderful pets", src, confidence=1.0)

    package = engine.retrieve("when does the billing cycle reset", top_k=5)
    assert package.items
    assert package.items[0].key == "doc.a"


def test_snapshot_is_deterministic():
    engine = _engine()
    src = engine.register_source("docs", SourceKind.DOCUMENT)
    engine.add("doc.a", "hello", src)
    engine.add("doc.b", "world", src)

    snap1 = engine.snapshot()
    snap2 = engine.snapshot()
    assert snap1.snapshot_hash == snap2.snapshot_hash


def test_explain_reports_source_and_version():
    engine = _engine()
    src = engine.register_source("crm", SourceKind.DATABASE_RECORD)
    item = engine.add("user.plan", "enterprise", src, provenance="synced from CRM nightly job")

    explanation = engine.explain(item.id)
    assert explanation is not None
    assert explanation.source is not None
    assert explanation.source.name == "crm"
    assert explanation.version == 1
    assert "synced from CRM" in explanation.provenance


def test_conflicts_detected_between_disagreeing_active_items():
    engine = _engine()
    src_a = engine.register_source("crm", SourceKind.DATABASE_RECORD)
    src_b = engine.register_source("support-ticket", SourceKind.USER_PROVIDED)

    engine.add("user.plan", "starter", src_a)
    engine.add("user.plan", "enterprise", src_b)

    conflicts = engine.conflicts()
    assert len(conflicts) == 1
    assert conflicts[0].key == "user.plan"


def test_update_resolves_conflict_for_future_snapshots():
    engine = _engine()
    src_a = engine.register_source("crm", SourceKind.DATABASE_RECORD)
    src_b = engine.register_source("support-ticket", SourceKind.USER_PROVIDED)

    engine.add("user.plan", "starter", src_a)
    engine.add("user.plan", "enterprise", src_b)
    assert len(engine.conflicts()) == 1

    engine.update("user.plan", "enterprise", src_b, provenance="confirmed by CRM sync")
    assert engine.conflicts() == []
