"""FR 2.0 - Risk scoring and test priority."""

from __future__ import annotations

import json
import re

from autotestdesign.core.llm_client import chat_json, has_llm, load_prompt
from autotestdesign.models.schemas import Priority, Requirement, RiskAssessment, RiskWeights

HIGH_KEYWORDS = re.compile(
    r"security|auth|login|password|encrypt|payment|privilege|lock|session|安全|登录|密码",
    re.I,
)
MED_KEYWORDS = re.compile(
    r"valid|invalid|format|range|boundary|error|验证|格式|边界",
    re.I,
)


def _rule_score(req: Requirement, weights: RiskWeights) -> tuple[int, Priority, str]:
    text = req.raw_text + " " + req.title
    # Compute per-dimension sub-scores (0-100)
    impact = 40
    failure = 20
    detectability = 30
    reasons: list[str] = []
    if HIGH_KEYWORDS.search(text):
        impact += 40
        failure += 30
        reasons.append("Security/authentication related")
    if MED_KEYWORDS.search(text):
        failure += 30
        detectability += 20
        reasons.append("Input validation / error handling")
    if req.structured.data_ranges:
        failure += 20
        reasons.append("Defined data ranges increase failure probability")
    if req.structured.conditions:
        failure += 15
    # Apply configurable weights
    score = int(
        min(100, impact) * weights.business_impact
        + min(100, failure) * weights.failure_probability
        + min(100, detectability) * weights.detectability
    )
    score = min(100, score)
    if score >= 80:
        return score, Priority.HIGH, "; ".join(reasons) or "High impact requirement"
    if score >= 50:
        return score, Priority.MEDIUM, "; ".join(reasons) or "Medium impact requirement"
    return score, Priority.LOW, "; ".join(reasons) or "Low impact requirement"


def assess_risks(
    requirements: list[Requirement], weights: RiskWeights | None = None
) -> list[RiskAssessment]:
    if weights is None:
        weights = RiskWeights()
    if not requirements:
        return []

    if has_llm():
        system = _build_llm_prompt(weights)
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
            score=_rule_score(r, weights)[0],
            priority=_rule_score(r, weights)[1],
            reason=_rule_score(r, weights)[2],
        )
        for r in requirements
    ]


def _build_llm_prompt(weights: RiskWeights) -> str:
    """Load the risk assessment prompt and inject the configured weights."""
    template = load_prompt("risk_assessment.md")
    bi = int(weights.business_impact * 100)
    fp = int(weights.failure_probability * 100)
    de = int(weights.detectability * 100)
    # Replace the weight table
    new_table = (
        f"| **Business Impact** | {bi}% | What is the consequence of failure? Does it affect security, data integrity, revenue, user trust, or legal compliance? |\n"
        f"| **Failure Probability** | {fp}% | How likely is this requirement to fail? Consider complexity (many conditions, complex ranges), dependency on external systems, historical defect patterns. |\n"
        f"| **Detectability** | {de}% | If this requirement fails, how hard is it to detect? Is the failure obvious to users, or could it silently corrupt data? |"
    )
    template = re.sub(
        r"\| \*\*Business Impact\*\* \| \d+% \|.*\n\| \*\*Failure Probability\*\* \| \d+% \|.*\n\| \*\*Detectability\*\* \| \d+% \|.*",
        new_table,
        template,
    )
    # Replace the scoring formula
    template = re.sub(
        r"score = \(impact × 0\.\d+\) \+ \(probability × 0\.\d+\) \+ \(detectability × 0\.\d+\)",
        f"score = (impact x {weights.business_impact:.2f}) + (probability x {weights.failure_probability:.2f}) + (detectability x {weights.detectability:.2f})",
        template,
    )
    return template
