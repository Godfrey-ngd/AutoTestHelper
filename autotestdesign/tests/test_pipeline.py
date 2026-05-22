"""Unit tests for AutoTestDesign pipeline."""

from __future__ import annotations

from autotestdesign.core.exporters.export import export_csv
from autotestdesign.core.pipeline import import_requirements, run_full_pipeline
from autotestdesign.core.optimizer.suite_optimizer import optimize_suite
from autotestdesign.models.schemas import Project

SAMPLE = """REQ-001,Username 3-20 characters
REQ-002,Password 8-32 with one digit
REQ-003,Empty username shows username is required
"""


def test_full_pipeline_produces_cases():
    p = Project(name="test")
    p = import_requirements(p, SAMPLE, "csv")
    p, metrics = run_full_pipeline(p)
    assert len(p.requirements) >= 3
    assert len(p.risks) >= 3
    assert len(p.test_cases) > 0
    techniques = {tc.technique for tc in p.test_cases}
    assert "EP" in techniques
    assert "BVA" in techniques
    assert "DecisionTable" in techniques
    assert metrics.techniques_ms >= 0


def test_export_csv():
    p = Project(name="test")
    p = import_requirements(p, SAMPLE, "csv")
    p, _ = run_full_pipeline(p)
    csv_out = export_csv(p)
    assert "test_case_id" in csv_out
    assert "technique" in csv_out


def test_optimize_suite():
    p = Project(name="test")
    p = import_requirements(p, SAMPLE, "csv")
    p, _ = run_full_pipeline(p)
    ids = optimize_suite(p)
    assert len(ids) > 0
    assert len(ids) <= len(p.test_cases)
