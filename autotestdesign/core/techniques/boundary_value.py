"""FR 3.0 - Boundary Value Analysis."""

from __future__ import annotations

import re

from autotestdesign.core.techniques._helpers import try_llm
from autotestdesign.core.techniques.base import TechniqueResult
from autotestdesign.models.schemas import (
    CoverageItem,
    Priority,
    Requirement,
    RiskAssessment,
    TestCase,
    TestStrategy,
)


def _extract_bounds(text: str) -> list[tuple[str, int, int]]:
    bounds = []
    for m in re.finditer(r"(\w+).*?(\d+)\s*[-–to]\s*(\d+)", text, re.I):
        bounds.append((m.group(1), int(m.group(2)), int(m.group(3))))
    if "username" in text.lower() and not any(b[0] == "username" for b in bounds):
        bounds.append(("username", 3, 20))
    if "password" in text.lower() and not any(b[0] == "password" for b in bounds):
        bounds.append(("password", 8, 32))
    return bounds


def _fallback(
    requirements: list[Requirement],
    risk_map: dict[str, RiskAssessment],
) -> TechniqueResult:
    result = TechniqueResult()
    strategy = TestStrategy(
        technique="BVA",
        rationale="Boundary value analysis on numeric length constraints",
    )
    for req in requirements:
        text = req.raw_text
        priority = risk_map[req.id].priority if req.id in risk_map else Priority.MEDIUM
        score = risk_map[req.id].score if req.id in risk_map else 50
        bounds = _extract_bounds(text)
        if not bounds:
            bounds = [("field", 1, 10)]
        for field, lo, hi in bounds:
            cases = [
                (f"{field} min-1", lo - 1, "invalid"),
                (f"{field} min", lo, "valid"),
                (f"{field} min+1", lo + 1, "valid"),
                (f"{field} max-1", hi - 1, "valid"),
                (f"{field} max", hi, "valid"),
                (f"{field} max+1", hi + 1, "invalid"),
            ]
            for title, length, validity in cases:
                val = "x" * max(0, length) if length > 0 else ""
                if field == "username":
                    test_data = {"username": val or "", "password": "Pass1234"}
                    if validity == "valid":
                        expected = "redirect to /success" if val else "username is required"
                    elif val == "":
                        expected = "username is required"
                    else:
                        expected = "invalid username"
                elif field == "password":
                    test_data = {"username": "user01", "password": val or ""}
                    if val == "":
                        expected = "password is required"
                    else:
                        expected = "invalid password"
                else:
                    test_data = {field: val or ""}
                    expected = f"{validity} {field}"
                cov = CoverageItem(
                    requirement_id=req.id,
                    item_type="boundary",
                    description=f"BVA {title} (len={length})",
                )
                result.coverage_items.append(cov)
                strategy.coverage_ids.append(cov.id)
                result.test_cases.append(
                    TestCase(
                        requirement_id=req.id,
                        title=f"BVA-{title}",
                        technique="BVA",
                        priority=priority,
                        preconditions="User on login page",
                        steps=[f"Enter {field} with length {length}", "Submit"],
                        test_data=test_data,
                        expected=expected,
                        risk_score=score,
                        coverage_ids=[cov.id],
                        strategy_id=strategy.id,
                    )
                )
        strategy.requirement_ids.append(req.id)
    result.strategies.append(strategy)
    return result


def generate(
    requirements: list[Requirement],
    risk_map: dict[str, RiskAssessment],
    feedback_cases: list[dict] | None = None,
) -> TechniqueResult:
    llm = try_llm("boundary_value.md", "BVA", requirements, risk_map, feedback_cases)
    return llm if llm else _fallback(requirements, risk_map)
