"""FR 6.0 - Export test artifacts."""

from __future__ import annotations

import csv
import io
import json

from autotestdesign.models.schemas import Project


def export_json_bytes(project: Project) -> bytes:
    return json.dumps(
        project.model_dump(mode="json"),
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")


def export_csv(project: Project) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "test_case_id",
            "requirement_id",
            "title",
            "technique",
            "priority",
            "risk_score",
            "preconditions",
            "steps",
            "test_data",
            "expected",
            "coverage_ids",
        ]
    )
    risk_map = {r.requirement_id: r for r in project.risks}
    for tc in project.test_cases:
        risk = risk_map.get(tc.requirement_id)
        writer.writerow(
            [
                tc.id,
                tc.requirement_id,
                tc.title,
                tc.technique,
                tc.priority.value,
                tc.risk_score,
                tc.preconditions,
                " | ".join(tc.steps),
                json.dumps(tc.test_data, ensure_ascii=False),
                tc.expected,
                ";".join(tc.coverage_ids),
            ]
        )
    return buf.getvalue()
