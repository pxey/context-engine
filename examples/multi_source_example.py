"""Example: pulling context about a user from two disagreeing sources,
detecting the conflict, resolving it, then retrieving and explaining.

Run:
    python examples/multi_source_example.py
"""

from __future__ import annotations

from context_engine import ContextEngine, SourceKind
from context_engine.storage import InMemoryStorage


def main() -> None:
    engine = ContextEngine(storage=InMemoryStorage())

    crm = engine.register_source("crm", SourceKind.DATABASE_RECORD)
    support = engine.register_source("support-ticket-482", SourceKind.USER_PROVIDED)
    docs = engine.register_source("onboarding-doc", SourceKind.DOCUMENT)

    engine.add("user.plan", "starter", crm, confidence=0.8, provenance="CRM nightly sync")
    engine.add("user.plan", "enterprise", support, confidence=0.6, provenance="customer said so in ticket #482")
    engine.add(
        "onboarding.billing_note",
        "Enterprise customers are billed annually in advance.",
        docs,
        confidence=1.0,
        provenance="onboarding handbook, section 4",
    )

    print("== Conflicts ==")
    for conflict in engine.conflicts():
        print(f"[{conflict.kind.value}] {conflict.description}")

    print("\n== Resolving via CRM as source of truth ==")
    resolved = engine.update("user.plan", "enterprise", crm, provenance="confirmed with customer, CRM updated")
    print(f"Conflicts after resolution: {engine.conflicts()}")

    print("\n== Retrieve: 'how is billing handled?' ==")
    package = engine.retrieve("how is billing handled for the user's plan?", top_k=3)
    for item in package.items:
        print(f"- [{item.key}] {item.content}")
    print(f"snapshot_hash={package.snapshot_hash}")

    print("\n== Explain the resolved plan item ==")
    explanation = engine.explain(resolved.id)
    print(explanation.reason if explanation else "not found")


if __name__ == "__main__":
    main()
