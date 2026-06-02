"""Risk-to-technique recommendation engine."""
from __future__ import annotations

import json
from pathlib import Path

from autotestdesign.models.schemas import Priority, Requirement, RiskAssessment

_RULES_PATH = Path(__file__).resolve().parent / "recommender_rules.json"


def _load_rules() -> dict:
    return json.loads(_RULES_PATH.read_text(encoding="utf-8"))


def recommend_for_risk(priority: Priority) -> list[str]:
    """Return recommended technique names for a given risk priority."""
    rules = _load_rules()
    for rule in rules["rules"]:
        if rule["risk"] == priority.value:
            return list(rule["techniques"])
    return ["EP"]


def recommend_for_requirement(req: Requirement, risk: RiskAssessment) -> dict:
    """Return full recommendation dict with techniques and reason."""
    rules = _load_rules()
    techniques = recommend_for_risk(risk.priority)
    reason = ""
    for rule in rules["rules"]:
        if rule["risk"] == risk.priority.value:
            reason = rule["reason"]
            break
    return {
        "requirement_id": req.id,
        "priority": risk.priority.value,
        "recommended_techniques": techniques,
        "reason": reason,
    }


def get_technique_metadata() -> dict:
    """Return technique display metadata (name, icon)."""
    return _load_rules().get("technique_metadata", {})


def auto_recommend(
    requirements: list[Requirement],
    risks: list[RiskAssessment],
) -> list[dict]:
    """Generate recommendations for all requirements."""
    risk_map = {r.requirement_id: r for r in risks}
    results: list[dict] = []
    for req in requirements:
        risk = risk_map.get(req.id)
        if risk:
            results.append(recommend_for_requirement(req, risk))
    return results
