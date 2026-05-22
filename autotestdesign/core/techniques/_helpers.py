"""Helpers for technique modules."""

from __future__ import annotations

import json
from typing import Any

from autotestdesign.core.llm_client import chat_json, has_llm, load_prompt
from autotestdesign.core.techniques.base import TechniqueResult
from autotestdesign.models.schemas import (
    CoverageItem,
    Priority,
    Requirement,
    RiskAssessment,
    TestCase,
    TestStrategy,
)


def _priority(risk_map: dict[str, RiskAssessment], req_id: str) -> Priority:
    r = risk_map.get(req_id)
    return r.priority if r else Priority.MEDIUM


def _risk_score(risk_map: dict[str, RiskAssessment], req_id: str) -> int:
    r = risk_map.get(req_id)
    return r.score if r else 50


def merge_llm_result(
    data: dict[str, Any],
    technique: str,
    risk_map: dict[str, RiskAssessment],
) -> TechniqueResult:
    result = TechniqueResult()
    strategy = TestStrategy(
        technique=technique,
        rationale=f"ISO 29119-4 {technique} applied to requirements",
        requirement_ids=[],
    )
    cov_by_desc: dict[str, CoverageItem] = {}
    for item in data.get("coverage_items", []):
        cov = CoverageItem(
            requirement_id=item.get("requirement_id", ""),
            item_type=item.get("item_type", technique),
            description=item.get("description", ""),
        )
        cov_by_desc[cov.description] = cov
        result.coverage_items.append(cov)
        strategy.coverage_ids.append(cov.id)
        if cov.requirement_id and cov.requirement_id not in strategy.requirement_ids:
            strategy.requirement_ids.append(cov.requirement_id)

    for tc in data.get("test_cases", []):
        rid = tc.get("requirement_id", "")
        cov_ids = []
        desc = tc.get("coverage_description", "")
        if desc in cov_by_desc:
            cov_ids.append(cov_by_desc[desc].id)
        elif result.coverage_items:
            cov_ids.append(result.coverage_items[-1].id)
        case = TestCase(
            requirement_id=rid,
            title=tc.get("title", ""),
            technique=tc.get("technique", technique),
            priority=_priority(risk_map, rid),
            preconditions=tc.get("preconditions", ""),
            steps=tc.get("steps", []),
            test_data=tc.get("test_data", {}),
            expected=tc.get("expected", ""),
            risk_score=_risk_score(risk_map, rid),
            coverage_ids=cov_ids,
            strategy_id=strategy.id,
        )
        result.test_cases.append(case)
    result.strategies.append(strategy)
    return result


def try_llm(
    prompt_file: str,
    technique: str,
    requirements: list[Requirement],
    risk_map: dict[str, RiskAssessment],
) -> TechniqueResult | None:
    if not has_llm():
        return None
    system = load_prompt(prompt_file)
    payload = {
        "requirements": [r.model_dump() for r in requirements],
        "risks": [risk_map[r.id].model_dump() for r in requirements if r.id in risk_map],
    }
    data = chat_json(system, json.dumps(payload, ensure_ascii=False))
    if data:
        return merge_llm_result(data, technique, risk_map)
    return None
