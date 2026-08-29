from context_engine.models import ContextItem, Source, SourceKind
from context_engine.storage import InMemoryStorage, SQLiteStorage


def test_context_item_content_hash_stable():
    a = ContextItem(key="k", content="hello", source_id="s1", source_kind=SourceKind.USER_PROVIDED)
    b = ContextItem(key="k", content="hello", source_id="s2", source_kind=SourceKind.USER_PROVIDED)
    assert a.content_hash == b.content_hash


def test_context_item_is_active_by_default():
    item = ContextItem(key="k", content="v", source_id="s1", source_kind=SourceKind.USER_PROVIDED)
    assert item.is_active


def test_inmemory_storage_roundtrip():
    storage = InMemoryStorage()
    src = Source(kind=SourceKind.DOCUMENT, name="readme")
    storage.save_source(src)
    item = ContextItem(key="doc.title", content="Hello World", source_id=src.id, source_kind=src.kind)
    storage.save_item(item)

    assert storage.get_item(item.id) == item
    assert storage.get_source(src.id) == src
    assert len(storage.items_by_key("doc.title")) == 1


def test_sqlite_storage_roundtrip(tmp_path):
    db_path = tmp_path / "ctx.db"
    storage = SQLiteStorage(db_path)
    src = Source(kind=SourceKind.API_RESPONSE, name="billing-api")
    storage.save_source(src)
    item = ContextItem(
        key="user.plan", content="enterprise", source_id=src.id, source_kind=src.kind, confidence=0.9
    )
    storage.save_item(item)
    storage.close()

    reopened = SQLiteStorage(db_path)
    fetched = reopened.get_item(item.id)
    assert fetched is not None
    assert fetched.content == "enterprise"
    assert fetched.confidence == 0.9
    reopened.close()
