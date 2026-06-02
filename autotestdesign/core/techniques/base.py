"""Shared types and orchestration for black-box techniques."""

from __future__ import annotations

from dataclasses import dataclass, field

from autotestdesign.models.schemas import (
    CoverageItem,
    Requirement,
    RiskAssessment,
    TestCase,
    TestStrategy,
)


@dataclass
class TechniqueResult:
    test_cases: list[TestCase] = field(default_factory=list)
    coverage_items: list[CoverageItem] = field(default_factory=list)
    strategies: list[TestStrategy] = field(default_factory=list)


def generate_all_techniques(
    requirements: list[Requirement],
    risks: list[RiskAssessment],
    assignments: list | None = None,
    params: "TechniqueParameter | None" = None,
) -> TechniqueResult:
    from autotestdesign.core.techniques import (
        boundary_value,
        decision_table,
        equivalence_partitioning,
    )
    from autotestdesign.models.schemas import TechniqueParameter

    risk_map = {r.requirement_id: r for r in risks}
    merged = TechniqueResult()

    if params is None:
        params = TechniqueParameter()

    TECH_GENERATORS = {
        "EP": (
            equivalence_partitioning.generate,
            lambda: {
                "valid_partitions": params.ep_valid_partitions,
                "invalid_partitions": params.ep_invalid_partitions,
            },
        ),
        "BVA": (
            boundary_value.generate,
            lambda: {"offset": params.bva_offset},
        ),
        "DecisionTable": (
            decision_table.generate,
            lambda: {},
        ),
    }

    for tech, (generator, kwargs_fn) in TECH_GENERATORS.items():
        if assignments is not None:
            active_req_ids = {
                a.requirement_id for a in assignments
                if a.technique == tech and a.enabled
            }
            active_reqs = [r for r in requirements if r.id in active_req_ids]
        else:
            active_reqs = list(requirements)

        if not active_reqs:
            continue

        kwargs = kwargs_fn()
        res = generator(active_reqs, risk_map, **kwargs)
        merged.test_cases.extend(res.test_cases)
        merged.coverage_items.extend(res.coverage_items)
        merged.strategies.extend(res.strategies)

    return merged
