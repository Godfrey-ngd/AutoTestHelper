"""FR 3.0 - Equivalence Partitioning."""

from __future__ import annotations

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


def _fallback(
    requirements: list[Requirement],
    risk_map: dict[str, RiskAssessment],
) -> TechniqueResult:
    result = TechniqueResult()
    strategy = TestStrategy(
        technique="EP",
        rationale="Equivalence class partitioning for valid/invalid inputs",
    )
    for req in requirements:
        text = req.raw_text.lower()
        priority = risk_map[req.id].priority if req.id in risk_map else Priority.MEDIUM
        score = risk_map[req.id].score if req.id in risk_map else 50
        classes: list[tuple[str, dict[str, str], str]] = []
        if "username" in text or "用户" in req.raw_text:
            classes = [
                ("valid", {"username": "user01", "password": "Pass1234"}, "redirect to /success"),
                ("empty", {"username": "", "password": "Pass1234"}, "username is required"),
                ("too_short", {"username": "ab", "password": "Pass1234"}, "invalid username"),
                ("too_long", {"username": "a" * 21, "password": "Pass1234"}, "invalid username"),
            ]
        elif "password" in text or "密码" in req.raw_text:
            classes = [
                ("valid", {"username": "user01", "password": "Pass1234"}, "redirect to /success"),
                ("no_digit", {"username": "user01", "password": "Password"}, "invalid password"),
                ("empty", {"username": "user01", "password": ""}, "password is required"),
                ("too_short", {"username": "user01", "password": "short"}, "invalid password"),
            ]
        else:
            classes = [
                ("valid", {"username": "valid_input", "password": "valid_input"}, "success"),
                ("invalid", {"username": "", "password": ""}, "error"),
            ]
        for cls_name, test_data, expected in classes:
            cov = CoverageItem(
                requirement_id=req.id,
                item_type="equivalence_class",
                description=f"{cls_name} class for {req.title[:40]}",
            )
            result.coverage_items.append(cov)
            strategy.coverage_ids.append(cov.id)
            strategy.requirement_ids.append(req.id)
            result.test_cases.append(
                TestCase(
                    requirement_id=req.id,
                    title=f"EP-{cls_name}: {req.title[:30]}",
                    technique="EP",
                    priority=priority,
                    preconditions="User on login page",
                    steps=["Enter test data", "Submit login form"],
                    test_data=test_data,
                    expected=expected,
                    risk_score=score,
                    coverage_ids=[cov.id],
                    strategy_id=strategy.id,
                )
            )
    result.strategies.append(strategy)
    return result


def generate(
    requirements: list[Requirement],
    risk_map: dict[str, RiskAssessment],
    feedback_cases: list[dict] | None = None,
) -> TechniqueResult:
    llm = try_llm("equivalence_partitioning.md", "EP", requirements, risk_map, feedback_cases)
    return llm if llm else _fallback(requirements, risk_map)
