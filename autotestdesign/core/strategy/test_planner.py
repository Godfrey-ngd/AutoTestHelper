"""Risk-driven test planning: effort allocation, test depth, priority, phases."""
from __future__ import annotations

import json
from pathlib import Path

from autotestdesign.models.schemas import (
    Priority,
    Requirement,
    RiskAssessment,
    TestLevel,
    TestPlanItem,
)

_RULES_PATH = Path(__file__).resolve().parent / "recommender_rules.json"


def _load_rules() -> dict:
    return json.loads(_RULES_PATH.read_text(encoding="utf-8"))


def auto_generate_plan(
    requirements: list[Requirement],
    risks: list[RiskAssessment],
) -> list[TestPlanItem]:
    """Generate a test plan from risk data using configurable defaults."""
    rules = _load_rules()
    defaults = rules.get("test_plan_defaults", {})
    phases = rules.get("test_phases", ["Phase 1: Smoke", "Phase 2: Functional", "Phase 3: Regression"])

    risk_map = {r.requirement_id: r for r in risks}
    items: list[TestPlanItem] = []

    for req in requirements:
        risk = risk_map.get(req.id)
        priority = risk.priority.value if risk else "M"
        risk_defaults = defaults.get(priority, defaults.get("M", {}))

        level_str = risk_defaults.get("test_level", "standard")
        try:
            test_level = TestLevel(level_str)
        except ValueError:
            test_level = TestLevel.STANDARD

        phase = phases[2] if test_level == TestLevel.COMPREHENSIVE else (
            phases[1] if test_level == TestLevel.STANDARD else phases[0]
        )

        items.append(TestPlanItem(
            requirement_id=req.id,
            risk_level=priority,
            test_level=test_level,
            effort_pct=risk_defaults.get("effort_pct", 0),
            priority_order=0,
            phase=phase,
            skip=False,
        ))

    # Assign priority order: H first, then M, then L
    _assign_priority_order(items)

    # Normalize effort percentages
    items = recalculate_effort(items)

    return items


def recalculate_effort(items: list[TestPlanItem]) -> list[TestPlanItem]:
    """Normalize effort percentages to sum to 100 for all non-skipped items."""
    active = [it for it in items if not it.skip]
    total = sum(it.effort_pct for it in active)
    if total > 0:
        for it in active:
            it.effort_pct = round(it.effort_pct / total * 100, 1)
    return items


def _assign_priority_order(items: list[TestPlanItem]) -> None:
    """Assign execution order: H first, then M, then L."""
    risk_order = {"H": 0, "M": 1, "L": 2}
    sorted_items = sorted(items, key=lambda it: (
        risk_order.get(it.risk_level, 1),
        it.requirement_id,
    ))
    for i, item in enumerate(sorted_items, 1):
        item.priority_order = i


def get_phases() -> list[str]:
    return _load_rules().get("test_phases", [])


def get_plan_summary(items: list[TestPlanItem]) -> dict:
    """Return summary stats for the plan."""
    total = len(items)
    skipped = sum(1 for it in items if it.skip)
    active = total - skipped

    by_level: dict[str, int] = {}
    by_phase: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    for it in items:
        if it.skip:
            continue
        by_level[it.test_level.value] = by_level.get(it.test_level.value, 0) + 1
        by_phase[it.phase] = by_phase.get(it.phase, 0) + 1
        by_risk[it.risk_level] = by_risk.get(it.risk_level, 0) + 1

    return {
        "total": total,
        "active": active,
        "skipped": skipped,
        "by_level": by_level,
        "by_phase": by_phase,
        "by_risk": by_risk,
    }
