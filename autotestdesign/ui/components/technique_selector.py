"""Reusable technique checkbox matrix for strategy configuration."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from autotestdesign.models.schemas import (
    Requirement,
    RiskAssessment,
    StrategyAssignment,
    TechniqueParameter,
)


def render_technique_matrix(
    requirements: list[Requirement],
    risks: list[RiskAssessment],
    assignments: list[StrategyAssignment],
    all_techniques: list[str] | None = None,
) -> list[StrategyAssignment]:
    """Render a requirement x technique checkbox matrix.

    Returns updated list of StrategyAssignment objects based on user edits.
    """
    if all_techniques is None:
        all_techniques = ["EP", "BVA", "DecisionTable", "StateTransition"]

    risk_map = {r.requirement_id: r for r in risks}
    assignment_map: dict[tuple[str, str], StrategyAssignment] = {}
    for a in assignments:
        assignment_map[(a.requirement_id, a.technique)] = a

    rows = []
    for req in requirements:
        risk = risk_map.get(req.id)
        priority = risk.priority.value if risk else "M"
        row: dict = {
            "Req ID": req.id,
            "Title": req.title or req.raw_text[:60],
            "Risk": priority,
        }
        for tech in all_techniques:
            key = (req.id, tech)
            existing = assignment_map.get(key)
            row[tech] = existing.enabled if existing else False
        rows.append(row)

    df = pd.DataFrame(rows)
    column_config: dict = {
        "Req ID": st.column_config.TextColumn("Req ID", width="small"),
        "Title": st.column_config.TextColumn("Title", width="medium"),
        "Risk": st.column_config.TextColumn("Risk", width="small"),
    }
    for tech in all_techniques:
        column_config[tech] = st.column_config.CheckboxColumn(tech, width="small")

    edited = st.data_editor(
        df,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        key="tech_matrix",
        num_rows="fixed",
    )

    new_assignments: list[StrategyAssignment] = []
    for _, row in edited.iterrows():
        req_id = str(row["Req ID"])
        for tech in all_techniques:
            key = (req_id, tech)
            existing = assignment_map.get(key)
            sa = StrategyAssignment(
                id=existing.id if existing else StrategyAssignment().id,
                requirement_id=req_id,
                technique=tech,
                enabled=bool(row.get(tech, False)),
                params=existing.params if existing else TechniqueParameter(),
            )
            new_assignments.append(sa)

    return new_assignments
