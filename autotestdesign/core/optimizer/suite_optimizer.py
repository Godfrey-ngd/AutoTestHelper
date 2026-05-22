"""FR 7.0 - Prioritize and minimize test suite by risk."""

from __future__ import annotations

import json

from autotestdesign.models.schemas import Priority, Project, TestCase


def _case_key(tc: TestCase) -> str:
    return f"{tc.requirement_id}|{tc.technique}|{tc.title}|{json.dumps(tc.test_data, sort_keys=True)}"


def optimize_suite(project: Project) -> list[str]:
    """Return ordered test case IDs: unique cases sorted by risk (H first)."""
    priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    seen: set[str] = set()
    unique: list[TestCase] = []
    for tc in sorted(
        project.test_cases,
        key=lambda c: (priority_order.get(c.priority, 9), -c.risk_score),
    ):
        key = _case_key(tc)
        if key in seen:
            continue
        seen.add(key)
        unique.append(tc)
    return [tc.id for tc in unique]
