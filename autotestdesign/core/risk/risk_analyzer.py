"""FR 2.0 - Risk scoring and test priority."""

from __future__ import annotations

import json
import re

from autotestdesign.core.llm_client import chat_json, has_llm, load_prompt
from autotestdesign.models.schemas import Priority, Requirement, RiskAssessment

HIGH_KEYWORDS = re.compile(
    r"security|auth|login|password|encrypt|payment|privilege|lock|session|安全|登录|密码",
    re.I,
)
MED_KEYWORDS = re.compile(
    r"valid|invalid|format|range|boundary|error|验证|格式|边界",
    re.I,
)


def _rule_score(req: Requirement) -> tuple[int, Priority, str]:
    text = req.raw_text + " " + req.title
    score = 40
    reasons: list[str] = []
    if HIGH_KEYWORDS.search(text):
        score += 35
        reasons.append("Security/authentication related")
    if MED_KEYWORDS.search(text):
        score += 20
        reasons.append("Input validation / error handling")
    if req.structured.data_ranges:
        score += 10
        reasons.append("Defined data ranges increase failure impact")
    score = min(100, score)
    if score >= 80:
        return score, Priority.HIGH, "; ".join(reasons) or "High impact requirement"
    if score >= 50:
        return score, Priority.MEDIUM, "; ".join(reasons) or "Medium impact requirement"
    return score, Priority.LOW, "; ".join(reasons) or "Low impact requirement"


def assess_risks(requirements: list[Requirement]) -> list[RiskAssessment]:
    if not requirements:
        return []

    if has_llm():
        system = load_prompt("risk_assessment.md")
        payload = {
            "requirements": [
                {
                    "id": r.id,
                    "raw_text": r.raw_text,
                    "structured": r.structured.model_dump(),
                }
                for r in requirements
            ]
        }
        result = chat_json(system, json.dumps(payload, ensure_ascii=False))
        if result and "risks" in result:
            out: list[RiskAssessment] = []
            for item in result["risks"]:
                pr = item.get("priority", "M")
                try:
                    priority = Priority(pr)
                except ValueError:
                    priority = Priority.MEDIUM
                out.append(
                    RiskAssessment(
                        requirement_id=item.get("requirement_id", ""),
                        score=int(item.get("score", 50)),
                        priority=priority,
                        reason=item.get("reason", ""),
                    )
                )
            return out

    return [
        RiskAssessment(
            requirement_id=r.id,
            score=_rule_score(r)[0],
            priority=_rule_score(r)[1],
            reason=_rule_score(r)[2],
        )
        for r in requirements
    ]
