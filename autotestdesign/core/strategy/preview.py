"""Strategy preview: estimate test case count and coverage before generation."""
from __future__ import annotations

from autotestdesign.models.schemas import Requirement, StrategyAssignment, TechniqueParameter


def _count_conditions(req: Requirement) -> int:
    """Heuristic: count structured conditions for DecisionTable estimation."""
    return max(1, len(req.structured.conditions) + 1)


def estimate_case_count(
    requirements: list[Requirement],
    assignments: list[StrategyAssignment],
    params: TechniqueParameter | None = None,
) -> dict:
    """Estimate how many test cases will be generated from current strategy.

    Returns dict with: total, by_technique, per_requirement
    """
    if params is None:
        params = TechniqueParameter()

    req_map = {r.id: r for r in requirements}
    by_technique: dict[str, int] = {}
    per_requirement: dict[str, dict] = {}

    for a in assignments:
        if not a.enabled:
            continue
        req = req_map.get(a.requirement_id)
        if req is None:
            continue
        count = 0
        tech = a.technique
        if tech == "EP":
            count = params.ep_valid_partitions + params.ep_invalid_partitions
        elif tech == "BVA":
            num_fields = max(1, len(req.structured.data_ranges) + len(req.structured.inputs))
            count = (params.bva_offset * 2 + 2) * num_fields
        elif tech == "DecisionTable":
            n = _count_conditions(req)
            count = min(2 ** n, 8)
        elif tech == "StateTransition":
            count = 3
        by_technique[tech] = by_technique.get(tech, 0) + count
        per_requirement[a.requirement_id] = {
            "title": req.title or req.raw_text[:60],
            "techniques": per_requirement.get(a.requirement_id, {}).get("techniques", {}),
        }
        per_requirement[a.requirement_id]["techniques"][tech] = count

    total = sum(by_technique.values())
    return {
        "total": total,
        "by_technique": by_technique,
        "per_requirement": per_requirement,
    }


def estimate_coverage(
    requirements: list[Requirement],
    assignments: list[StrategyAssignment],
    risks: list[dict],
) -> dict:
    """Estimate coverage percentage by risk level.

    risks: list of dicts with 'requirement_id' and 'priority' keys
    """
    req_map = {r.id: r for r in requirements}
    risk_map = {r["requirement_id"]: r["priority"] for r in risks}

    by_risk: dict[str, dict[str, int]] = {}
    for req in requirements:
        level = risk_map.get(req.id, "M")
        by_risk.setdefault(level, {"total": 0, "covered": 0})
        by_risk[level]["total"] += 1

    covered_ids: set[str] = set()
    for a in assignments:
        if a.enabled and a.requirement_id in req_map:
            covered_ids.add(a.requirement_id)

    for req_id in covered_ids:
        level = risk_map.get(req_id, "M")
        if level in by_risk:
            by_risk[level]["covered"] += 1

    result: dict = {}
    for level in ["H", "M", "L"]:
        if level in by_risk:
            t = by_risk[level]["total"]
            c = by_risk[level]["covered"]
            result[level] = {
                "total": t,
                "covered": min(c, t),
                "percentage": round(c / t * 100) if t > 0 else 0,
            }
    return result
