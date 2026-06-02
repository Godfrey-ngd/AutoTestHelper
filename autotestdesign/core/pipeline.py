"""Pipeline orchestration for AutoTestDesign."""

from __future__ import annotations

import time
from dataclasses import dataclass

from autotestdesign.core.importers.requirement_importer import parse_paste
from autotestdesign.core.parser.requirement_parser import structure_requirements
from autotestdesign.core.risk.risk_analyzer import assess_risks
from autotestdesign.core.techniques.base import TechniqueResult, generate_all_techniques
from autotestdesign.models.schemas import Project, TestCase, TraceLink


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
    assignments = project.strategy_assignments
    if not assignments:
        from autotestdesign.core.strategy.recommender import auto_recommend
        from autotestdesign.models.schemas import StrategyAssignment

        recommendations = auto_recommend(project.requirements, project.risks)
        for rec in recommendations:
            for tech in rec["recommended_techniques"]:
                project.strategy_assignments.append(
                    StrategyAssignment(
                        requirement_id=rec["requirement_id"], technique=tech
                    )
                )
        assignments = project.strategy_assignments

    result: TechniqueResult = generate_all_techniques(
        project.requirements,
        project.risks,
        assignments=assignments,
        params=project.technique_params,
    )
    project.test_cases = result.test_cases
    project.coverage_items = result.coverage_items
    project.strategies = result.strategies
    _apply_suite_assignments(project)
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
    tech_map = {
        "EP": equivalence_partitioning.generate,
        "BVA": boundary_value.generate,
        "DecisionTable": decision_table.generate,
    }
    for tech, gen in tech_map.items():
        # Check if this technique is enabled for the requirement
        assignment = next(
            (a for a in project.strategy_assignments if a.requirement_id == requirement_id and a.technique == tech),
            None,
        )
        if assignment is not None and not assignment.enabled:
            continue
        kwargs = {}
        if tech == "BVA":
            kwargs["offset"] = project.technique_params.bva_offset
        elif tech == "EP":
            kwargs["valid_partitions"] = project.technique_params.ep_valid_partitions
            kwargs["invalid_partitions"] = project.technique_params.ep_invalid_partitions
        res = gen(reqs, risk_map, fb_payload, **kwargs)
        project.test_cases.extend(res.test_cases)
        project.coverage_items.extend(res.coverage_items)
        project.strategies.extend(res.strategies)
    _rebuild_trace_links(project)
    return project


def add_whitebox(
    project: Project,
    model_text: str | None = None,
    criteria: list[str] | None = None,
    optimize: bool = True,
) -> Project:
    """Add white-box test cases from a state machine or control flow graph.

    Args:
        project: Current project
        model_text: Mermaid or JSON model definition. If None, uses built-in login model.
        criteria: Coverage criteria names. Default depends on model type.
        optimize: Whether to apply greedy / Chinese postman optimization.
    """
    from autotestdesign.core.whitebox.models import StateMachine, ControlFlowGraph, WhiteboxResult
    from autotestdesign.core.whitebox.model_parser import detect_and_parse
    from autotestdesign.core.whitebox.coverage import run_coverage
    from autotestdesign.core.whitebox.optimizer import optimize_result
    from autotestdesign.core.whitebox.state_model import LOGIN_STATE_DIAGRAM

    model = None
    if model_text and model_text.strip():
        model = detect_and_parse(model_text.strip())

    if model is None:
        model = detect_and_parse(LOGIN_STATE_DIAGRAM)
        if model is None:
            return project

    project.state_diagram = model_text if model_text else LOGIN_STATE_DIAGRAM

    if criteria is None:
        if isinstance(model, StateMachine):
            criteria = ["state", "transition"]
        else:
            criteria = ["statement", "branch", "path"]

    results = run_coverage(model, criteria)

    sm_for_opt = model if isinstance(model, StateMachine) else None
    if optimize:
        results = [optimize_result(r, sm_for_opt) for r in results]

    first_req = project.requirements[0].id if project.requirements else ""
    for result in results:
        for i, seq in enumerate(result.test_sequences):
            path_desc = " -> ".join(seq)
            technique = "StateTransition" if result.model_type == "state_machine" else "ControlFlowPath"
            project.test_cases.append(
                TestCase(
                    title=f"WB-{technique}-{i + 1}: {path_desc[:60]}",
                    requirement_id=first_req,
                    technique=technique,
                    preconditions=seq[0] if seq else "",
                    steps=[f"Follow path: {path_desc}"],
                    expected=f"Reach: {seq[-1]}" if seq else "",
                )
            )

    combined = WhiteboxResult()
    if results:
        combined.model_type = results[0].model_type
        combined.coverage_targets = []
        combined.test_sequences = []
        for r in results:
            combined.coverage_targets.extend(r.coverage_targets)
            combined.test_sequences.extend(r.test_sequences)
        total = len(combined.coverage_targets)
        covered = sum(1 for t in combined.coverage_targets if t.covered)
        combined.coverage_pct = (covered / total * 100) if total else 100
    project.whitebox_result = combined.model_dump()

    _rebuild_trace_links(project)
    return project


def _apply_suite_assignments(project: Project) -> None:
    """Sync suite_id and tags to test cases based on suite assignments."""
    suite_map: dict[str, str] = {}  # requirement_id -> suite_name
    suite_ids: dict[str, str] = {}  # requirement_id -> suite_id
    for suite in project.suites:
        for rid in suite.requirement_ids:
            suite_map[rid] = suite.name
            suite_ids[rid] = suite.id
    for tc in project.test_cases:
        if tc.requirement_id in suite_ids:
            tc.suite_id = suite_ids[tc.requirement_id]
            tag = f"#{suite_map[tc.requirement_id].lower().replace(' ', '_')}"
            if tag not in tc.tags:
                tc.tags.append(tag)


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
