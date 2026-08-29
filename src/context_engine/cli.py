"""Command-line interface for inspecting an AI Context Engine database.

    ctxeng show --db context_engine.db
    ctxeng retrieve "some query" --db context_engine.db
    ctxeng explain <item_id> --db context_engine.db
    ctxeng conflicts --db context_engine.db
"""

from __future__ import annotations

import argparse
import sys

from .conflict import detect_conflicts
from .engine import ContextEngine
from .storage import SQLiteStorage


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ctxeng", description="Inspect an AI Context Engine database.")
    parser.add_argument("--db", default="context_engine.db")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show", help="List all active context items.")

    p_retrieve = sub.add_parser("retrieve", help="Retrieve and rank items for a query.")
    p_retrieve.add_argument("query")
    p_retrieve.add_argument("--top-k", type=int, default=5)

    p_explain = sub.add_parser("explain", help="Explain a context item.")
    p_explain.add_argument("item_id")

    sub.add_parser("conflicts", help="List detected conflicts across active items.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    storage = SQLiteStorage(args.db)
    engine = ContextEngine(storage=storage)

    try:
        if args.command == "show":
            for item in storage.all_active_items():
                print(f"[{item.key}] v{item.version} ({item.confidence:.2f}) {item.id}: {item.content[:80]}")

        elif args.command == "retrieve":
            package = engine.retrieve(args.query, top_k=args.top_k)
            for item in package.items:
                print(f"[{item.key}] {item.id}: {item.content[:100]}")
            print(f"\nsnapshot_hash={package.snapshot_hash}")

        elif args.command == "explain":
            explanation = engine.explain(args.item_id)
            if explanation is None:
                print(f"Item not found: {args.item_id}", file=sys.stderr)
                return 1
            print(explanation.reason)
            print(f"provenance: {explanation.provenance}")
            print(f"confidence: {explanation.confidence}")

        elif args.command == "conflicts":
            conflicts = detect_conflicts(storage)
            if not conflicts:
                print("No conflicts detected.")
            for c in conflicts:
                print(f"[{c.kind.value}] {c.description}")

        return 0
    finally:
        storage.close()


if __name__ == "__main__":
    raise SystemExit(main())
