"""FR 3.0 - Decision Table testing."""

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
        technique="DecisionTable",
        rationale="Decision table for login condition combinations",
    )
    rules = [
        ("empty username", {"username": "", "password": "Pass1234"}, "username is required"),
        ("empty password", {"username": "user01", "password": ""}, "password is required"),
        ("invalid username format", {"username": "ab", "password": "Pass1234"}, "invalid username"),
        ("invalid password format", {"username": "user01", "password": "short"}, "invalid password"),
        ("valid credentials", {"username": "user01", "password": "Pass1234"}, "redirect to /success"),
        ("wrong password", {"username": "user01", "password": "Wrong999"}, "invalid credentials"),
    ]
    req = requirements[0] if requirements else None
    if not req:
        return result
    priority = risk_map.get(req.id, None)
    pr = priority.priority if priority else Priority.HIGH
    score = priority.score if priority else 75
    for title, data, expected in rules:
        cov = CoverageItem(
            requirement_id=req.id,
            item_type="decision_rule",
            description=f"Rule: {title}",
        )
        result.coverage_items.append(cov)
        strategy.coverage_ids.append(cov.id)
        result.test_cases.append(
            TestCase(
                requirement_id=req.id,
                title=f"DT-{title}",
                technique="DecisionTable",
                priority=pr,
                preconditions="On login page",
                steps=["Fill username and password", "Click Login"],
                test_data=data,
                expected=expected,
                risk_score=score,
                coverage_ids=[cov.id],
                strategy_id=strategy.id,
            )
        )
    strategy.requirement_ids = [req.id]
    result.strategies.append(strategy)
    return result


def generate(
    requirements: list[Requirement],
    risk_map: dict[str, RiskAssessment],
    feedback_cases: list[dict] | None = None,
) -> TechniqueResult:
    llm = try_llm("decision_table.md", "DecisionTable", requirements, risk_map, feedback_cases)
    return llm if llm else _fallback(requirements, risk_map)
