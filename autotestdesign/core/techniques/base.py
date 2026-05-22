"""Shared types and orchestration for black-box techniques."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
) -> TechniqueResult:
    from autotestdesign.core.techniques import (
        boundary_value,
        decision_table,
        equivalence_partitioning,
    )

    risk_map = {r.requirement_id: r for r in risks}
    merged = TechniqueResult()

    def run(fn):
        return fn(requirements, risk_map)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(
            pool.map(
                run,
                [
                    equivalence_partitioning.generate,
                    boundary_value.generate,
                    decision_table.generate,
                ],
            )
        )
    for res in results:
        merged.test_cases.extend(res.test_cases)
        merged.coverage_items.extend(res.coverage_items)
        merged.strategies.extend(res.strategies)
    return merged
