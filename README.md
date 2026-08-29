# AI Context Engine

A provider-agnostic Python infrastructure library for collecting,
normalizing, versioning, validating, retrieving, and packaging context for
AI applications and agents.

This is **not** another vector database or a simple memory library. It's
the layer underneath one: it answers *where a piece of context came from*,
*which version was used*, *why it was selected*, and *whether it conflicts
with something else you know*.

```
Source -> Context Item -> Identity -> Version -> Relationship
       -> Validation -> Retrieval -> Context Package
```

## Why

Agents pull context from many sources in many formats. Once that context
is mixed into a prompt, you typically can't answer:

- Why was this particular piece of information included?
- Which source produced it, and which version?
- Does it conflict with something else the system knows?
- Can I reproduce the exact context that was used for a past decision?

AI Context Engine keeps every context item as a small, immutable, versioned
record with provenance and confidence, so these questions always have an
answer.

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.12+. The only hard runtime dependency is `pydantic`.
**No OpenAI/Anthropic/Google SDK is required** — retrieval defaults to a
dependency-free keyword ranker; plug in your own embedding function only
if and when you want semantic search.

## Quick start

```python
from context_engine import ContextEngine, SourceKind

engine = ContextEngine()  # defaults to a local SQLite file

crm = engine.register_source("crm", SourceKind.DATABASE_RECORD)
engine.add("user.plan", "enterprise", crm, confidence=0.95, provenance="CRM nightly sync")

package = engine.retrieve("what plan is the user on?")
print(package.as_text())
```

### Versioning

```python
engine.update("user.plan", "starter", crm, provenance="customer downgraded")
# the old value is superseded, not deleted — full history stays queryable
```

### Conflict detection

```python
support = engine.register_source("support-ticket", SourceKind.USER_PROVIDED)
engine.add("user.plan", "enterprise", support)  # disagrees with CRM's "starter"

for conflict in engine.conflicts():
    print(conflict.description)
```

### Explainability

```python
item = engine.add("user.region", "eu-west", crm, provenance="CRM field `region`")
explanation = engine.explain(item.id)
print(explanation.reason)       # why this item, which source, which version
print(explanation.provenance)
```

### Reproducible snapshots

```python
snapshot = engine.snapshot(keys=["user.plan", "user.region"])
print(snapshot.snapshot_hash)   # identical inputs -> identical hash
```

### CLI

```bash
ctxeng show --db context_engine.db
ctxeng retrieve "what plan is the user on" --db context_engine.db
ctxeng explain <item_id> --db context_engine.db
ctxeng conflicts --db context_engine.db
```

## Design principles

- **Library first, not SaaS.** No server, no hosted product, no telemetry.
- **Provider-agnostic.** Works with zero LLM/embedding dependency. If you
  want semantic retrieval, inject an `EmbeddingRetriever(embed=your_fn)` —
  the engine never imports a specific vendor SDK.
- **Immutable, versioned items.** Nothing is overwritten; `update()`
  supersedes, it never deletes, so history and audit trails are free.
- **Provenance is a first-class field**, not an afterthought bolted onto
  metadata.
- **Pluggable everything.** `StorageBackend`, `Retriever`, and `Validator`
  are all protocols — swap in Postgres, embeddings, or custom validation
  rules without touching the core.

## Project layout

```
src/context_engine/
  models.py     Source, ContextItem, ContextPackage, Explanation, ConflictRecord
  engine.py     ContextEngine — add/update/retrieve/snapshot/explain/validate
  storage.py    StorageBackend protocol + SQLiteStorage + InMemoryStorage
  ranking.py    KeywordRetriever (default) + EmbeddingRetriever (optional)
  conflict.py   detect_conflicts() — disagreeing active items per key
  validation.py pluggable Validator protocol + default validators
  cli.py        `ctxeng` command-line tool
tests/          pytest suite
examples/       runnable example scripts
```

## Status

Alpha / MVP. Core model, versioning, conflict detection, keyword retrieval,
explainability, and SQLite storage are implemented and tested. Not yet
implemented: built-in embedding providers (by design — bring your own),
distributed storage backends, and streaming ingestion.

## License

MIT
