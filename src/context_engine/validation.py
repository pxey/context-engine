"""Validation: pluggable checks run against a ContextItem before/after
ingestion. The engine ships with a small set of sane defaults; callers can
add their own by implementing the ``Validator`` protocol.
"""

from __future__ import annotations

from typing import Protocol

from .models import ContextItem, ValidationIssue, ValidationResult


class Validator(Protocol):
    def check(self, item: ContextItem) -> list[ValidationIssue]: ...


class NonEmptyContentValidator:
    def check(self, item: ContextItem) -> list[ValidationIssue]:
        if not item.content or not item.content.strip():
            return [ValidationIssue(field="content", message="content is empty", severity="error")]
        return []


class ConfidenceRangeValidator:
    def check(self, item: ContextItem) -> list[ValidationIssue]:
        if not (0.0 <= item.confidence <= 1.0):
            return [
                ValidationIssue(
                    field="confidence",
                    message=f"confidence {item.confidence} is outside [0, 1]",
                    severity="error",
                )
            ]
        return []


class ProvenanceRequiredValidator:
    def check(self, item: ContextItem) -> list[ValidationIssue]:
        if not item.provenance:
            return [
                ValidationIssue(
                    field="provenance",
                    message="provenance is missing — item cannot be explained",
                    severity="warning",
                )
            ]
        return []


DEFAULT_VALIDATORS: list[Validator] = [
    NonEmptyContentValidator(),
    ConfidenceRangeValidator(),
    ProvenanceRequiredValidator(),
]


def validate_item(item: ContextItem, validators: list[Validator] | None = None) -> ValidationResult:
    validators = validators if validators is not None else DEFAULT_VALIDATORS
    issues: list[ValidationIssue] = []
    for validator in validators:
        issues.extend(validator.check(item))
    valid = not any(issue.severity == "error" for issue in issues)
    return ValidationResult(item_id=item.id, valid=valid, issues=issues)
