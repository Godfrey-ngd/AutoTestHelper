"""Pipeline orchestration for AutoTestDesign."""

from __future__ import annotations

import time
from dataclasses import dataclass

from autotestdesign.core.importers.requirement_importer import parse_paste
from autotestdesign.core.parser.requirement_parser import structure_requirements
from autotestdesign.core.risk.risk_analyzer import assess_risks
from autotestdesign.core.techniques.base import TechniqueResult, generate_all_techniques
from autotestdesign.core.whitebox.state_model import build_login_state_model
from autotestdesign.models.schemas import Project, TraceLink


@dataclass
class PipelineMetrics:
    structure_ms: float = 0
    risk_ms: float = 0
    techniques_ms: float = 0


def import_requirements(project: Project, content: str, source: str = "auto") -> Project:
    project.requirements = parse_paste(content, source)
    return project


def run_structure(project: Project) -> tuple[Project, float]:
    t0 = time.perf_counter()
    project.requirements = structure_requirements(project.requirements)
    return project, (time.perf_counter() - t0) * 1000


def run_risk(project: Project) -> tuple[Project, float]:
    t0 = time.perf_counter()
    project.risks = assess_risks(project.requirements, project.risk_weights)
    for tc in project.test_cases:
        for r in project.risks:
            if tc.requirement_id == r.requirement_id:
                tc.risk_score = r.score
                tc.priority = r.priority
    return project, (time.perf_counter() - t0) * 1000


def run_techniques(project: Project) -> tuple[Project, float]:
    t0 = time.perf_counter()
    result: TechniqueResult = generate_all_techniques(
        project.requirements, project.risks
    )
    project.test_cases = result.test_cases
    project.coverage_items = result.coverage_items
    project.strategies = result.strategies
    _rebuild_trace_links(project)
    return project, (time.perf_counter() - t0) * 1000


def run_full_pipeline(project: Project) -> tuple[Project, PipelineMetrics]:
    metrics = PipelineMetrics()
    project, metrics.structure_ms = run_structure(project)
    project, metrics.risk_ms = run_risk(project)
    project, metrics.techniques_ms = run_techniques(project)
    return project, metrics


def regenerate_for_requirement(
    project: Project, requirement_id: str, feedback_cases: list | None = None
) -> Project:
    from autotestdesign.core.techniques import (
        boundary_value,
        decision_table,
        equivalence_partitioning,
    )

    reqs = [r for r in project.requirements if r.id == requirement_id]
    if not reqs:
        return project
    risk_map = {r.requirement_id: r for r in project.risks}

    # Build feedback payload from invalid cases
    fb_payload: list[dict] | None = None
    if feedback_cases:
        fb_payload = [
            {
                "title": tc.title,
                "technique": tc.technique,
                "requirement_id": tc.requirement_id,
                "expected": tc.expected,
                "steps": tc.steps,
            }
            for tc in feedback_cases
        ]

    project.test_cases = [
        tc for tc in project.test_cases if tc.requirement_id != requirement_id
    ]
    project.coverage_items = [
        c for c in project.coverage_items if c.requirement_id != requirement_id
    ]
    for gen in (
        equivalence_partitioning.generate,
        boundary_value.generate,
        decision_table.generate,
    ):
        res = gen(reqs, risk_map, fb_payload)
        project.test_cases.extend(res.test_cases)
        project.coverage_items.extend(res.coverage_items)
        project.strategies.extend(res.strategies)
    _rebuild_trace_links(project)
    return project


def add_whitebox(project: Project) -> Project:
    diagram, cases = build_login_state_model(project)
    project.state_diagram = diagram
    project.test_cases.extend(cases)
    _rebuild_trace_links(project)
    return project


def _rebuild_trace_links(project: Project) -> None:
    links: list[TraceLink] = []
    for tc in project.test_cases:
        for cov_id in tc.coverage_ids:
            links.append(
                TraceLink(
                    requirement_id=tc.requirement_id,
                    coverage_id=cov_id,
                    strategy_id=tc.strategy_id,
                    test_case_id=tc.id,
                )
            )
        if not tc.coverage_ids:
            links.append(
                TraceLink(
                    requirement_id=tc.requirement_id,
                    test_case_id=tc.id,
                    strategy_id=tc.strategy_id,
                )
            )
    project.trace_links = links
