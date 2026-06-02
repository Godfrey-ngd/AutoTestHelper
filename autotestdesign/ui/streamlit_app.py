"""AutoTestDesign Streamlit UI - interactive test design review."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd
import streamlit as st

T = TypeVar("T")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autotestdesign.core.exporters.export import export_csv, export_json_bytes
from autotestdesign.core.llm_client import has_llm
from autotestdesign.core.optimizer.suite_optimizer import optimize_suite
from autotestdesign.core.oracle.oracle_generator import generate_oracle
from autotestdesign.core.pipeline import (
    import_requirements,
    regenerate_for_requirement,
    run_full_pipeline,
    run_risk,
    run_structure,
    run_techniques,
    add_whitebox,
)
from autotestdesign.core.review import log_review
from autotestdesign.models.schemas import (
    CoverageItem,
    Priority,
    Project,
    Requirement,
    RiskWeights,
    StrategyAssignment,
    StructuredFields,
    TechniqueParameter,
    TestCase,
    TestLevel,
    TestPlanItem,
    TestStrategy,
    TestSuite,
    seed_ids_from_project,
)
from autotestdesign.core.strategy import (
    auto_recommend,
    estimate_case_count,
    estimate_coverage,
    get_technique_metadata,
)
from autotestdesign.core.strategy.suite_manager import (
    assign_to_suite,
    create_suite,
    delete_suite,
)
from autotestdesign.core.strategy.test_planner import auto_generate_plan, get_plan_summary
from autotestdesign.ui.components.technique_selector import render_technique_matrix
from autotestdesign.storage.project_store import ProjectStore

SAMPLE_REQ = """REQ-001,The system shall accept username between 3 and 20 characters
REQ-002,The system shall accept password between 8 and 32 characters with at least one digit
REQ-003,Empty username shall show error message username is required
REQ-004,Empty password shall show error message password is required
REQ-005,Valid credentials user01 and Pass1234 shall redirect to success page
REQ-006,Invalid credentials shall show error invalid credentials
REQ-007,After three failed login attempts the account shall be locked for 30 seconds
"""


def _get_store() -> ProjectStore:
    return ProjectStore(ROOT / "data" / "projects")


def _load_project() -> Project | None:
    pid = st.session_state.get("project_id")
    if not pid:
        return None
    project = _get_store().load(pid)
    if project is not None:
        seed_ids_from_project(project)
    return project


def _save_project(project: Project) -> None:
    _get_store().save(project)
    st.session_state["project_id"] = project.id


def _init_state() -> None:
    if "project_id" not in st.session_state:
        st.session_state["project_id"] = None
    if "metrics" not in st.session_state:
        st.session_state["metrics"] = {}
    if "last_job_message" not in st.session_state:
        st.session_state["last_job_message"] = None


def _wait_hint() -> str:
    if has_llm():
        return "Calling LLM API — this may take 10–60 seconds. Please wait…"
    return "Using rule engine — usually completes within a few seconds…"


def _run_with_feedback(
    title: str,
    fn: Callable[[], T] | None = None,
    *,
    success: str | None = None,
    steps: list[tuple[str, Callable[[], Any]]] | None = None,
) -> Any:
    """Run a long job with st.status progress and toast on completion."""
    if not fn and not steps:
        return None
    with st.status(title, expanded=True) as status:
        st.caption(_wait_hint())
        progress = st.progress(0, text="Starting…")
        t0 = time.perf_counter()
        try:
            result: Any = None
            if steps:
                total = len(steps)
                for i, (label, step_fn) in enumerate(steps, start=1):
                    st.write(f"**{i}/{total}** {label}")
                    progress.progress((i - 1) / total, text=label)
                    result = step_fn()
                progress.progress(1.0, text="Done" if not fn else "Finalizing…")
            if fn:
                if not steps:
                    progress.progress(0.15, text="Processing…")
                result = fn()
            elapsed = (time.perf_counter() - t0) * 1000
            progress.progress(1.0, text="Complete")
            msg = success or f"{title} complete ({elapsed:.0f} ms)"
            status.update(label=msg, state="complete")
            st.session_state["last_job_message"] = msg
            st.toast(msg, icon="✅")
            return result
        except Exception as exc:
            status.update(label=f"{title} failed", state="error")
            st.error(str(exc))
            st.exception(exc)
            return None


def _show_last_job_banner() -> None:
    msg = st.session_state.get("last_job_message")
    if msg:
        st.success(f"Last operation: {msg}")


def _require_content(content: str) -> bool:
    if content and content.strip():
        return True
    st.warning("Paste requirements in the text box, or select **Sample login requirements**.")
    return False


def page_sidebar() -> None:
    st.sidebar.title("AutoTestDesign")
    st.sidebar.caption("AI-driven test design (ISTQB / ISO 29119-4)")
    if has_llm():
        st.sidebar.success("LLM enabled")
    else:
        st.sidebar.warning("Rule-based fallback (set OPENAI_API_KEY)")

    store = _get_store()
    ids = store.list_ids()
    if ids:
        sel = st.sidebar.selectbox("Open project", ids, key="open_proj")
        if st.sidebar.button("Load project"):
            st.session_state["project_id"] = sel
            st.rerun()

    with st.sidebar.expander("New project"):
        name = st.text_input("Project name", "Login Module Test")
        desc = st.text_area("Target app", "Web login module (username/password)")
        if st.button("Create project"):
            p = Project(name=name, target_app_description=desc)
            store.save(p)
            st.session_state["project_id"] = p.id
            st.rerun()


def tab_import(project: Project) -> Project:
    st.subheader("1. Import & Parse (FR 1.0 / 1.1)")
    source = st.radio(
        "Source",
        ["Paste", "Structured Form", "Sample login requirements"],
        horizontal=True,
    )

    if source == "Sample login requirements":
        content = SAMPLE_REQ
        st.code(content)
        fmt = st.selectbox("Format hint", ["auto", "csv", "text"])
        st.caption(_wait_hint())
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Import only", type="secondary", key="import_only_sample"):
                if not _require_content(content):
                    return project
                def _do():
                    p = import_requirements(project, content, fmt)
                    _save_project(p)
                    return p
                out = _run_with_feedback("Import requirements", _do)
                if out is not None:
                    project = out
                    st.success(f"Imported {len(project.requirements)} requirement(s)")
        with c2:
            if st.button("Import + Structure", type="secondary", key="import_struct_sample"):
                if not _require_content(content):
                    return project
                def _do():
                    p = import_requirements(project, content, fmt)
                    p, ms = run_structure(p)
                    st.session_state["metrics"]["structure_ms"] = ms
                    _save_project(p)
                    return p, ms
                out = _run_with_feedback(
                    "Import and structure",
                    lambda: _do()[0],
                    success="Structuring complete",
                    steps=[("Parse requirement text", lambda: None)],
                )
                if out is not None:
                    project = out
                    ms = st.session_state["metrics"].get("structure_ms", 0)
                    st.success(f"Structuring complete ({ms:.0f} ms)")
        with c3:
            if st.button("Run full pipeline", type="primary", key="full_pipeline_sample"):
                if not _require_content(content):
                    return project
                project = _run_full_pipeline_content(project, content, fmt)
    elif source == "Paste":
        content = st.text_area("Requirements (CSV id,text or one per line)", height=200)
        fmt = st.selectbox("Format hint", ["auto", "csv", "text"])
        st.caption(_wait_hint())
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Import only", type="secondary", key="import_only_paste"):
                if not _require_content(content):
                    return project
                def _do():
                    p = import_requirements(project, content, fmt)
                    _save_project(p)
                    return p
                out = _run_with_feedback("Import requirements", _do)
                if out is not None:
                    project = out
                    st.success(f"Imported {len(project.requirements)} requirement(s)")
        with c2:
            if st.button("Import + Structure", type="secondary", key="import_struct_paste"):
                if not _require_content(content):
                    return project
                def _do():
                    p = import_requirements(project, content, fmt)
                    p, ms = run_structure(p)
                    st.session_state["metrics"]["structure_ms"] = ms
                    _save_project(p)
                    return p, ms
                out = _run_with_feedback(
                    "Import and structure",
                    lambda: _do()[0],
                    success="Structuring complete",
                    steps=[("Parse requirement text", lambda: None)],
                )
                if out is not None:
                    project = out
                    ms = st.session_state["metrics"].get("structure_ms", 0)
                    st.success(f"Structuring complete ({ms:.0f} ms)")
        with c3:
            if st.button("Run full pipeline", type="primary", key="full_pipeline_paste"):
                if not _require_content(content):
                    return project
                project = _run_full_pipeline_content(project, content, fmt)
    elif source == "Structured Form":
        project = _tab_import_form(project)

    if project.requirements:
        rows = [
            {
                "id": r.id,
                "title": r.title,
                "inputs": ", ".join(r.structured.inputs),
                "ranges": ", ".join(r.structured.data_ranges),
                "conditions": ", ".join(r.structured.conditions[:2]),
            }
            for r in project.requirements
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    return project


def _run_full_pipeline_content(project: Project, content: str, fmt: str) -> Project:
    """Extracted helper: run full pipeline on text content."""
    holder: dict[str, Any] = {"project": project}

    def _step_import() -> None:
        holder["project"] = import_requirements(holder["project"], content, fmt)

    def _step_structure() -> None:
        p, ms = run_structure(holder["project"])
        holder["project"] = p
        st.session_state["metrics"]["structure_ms"] = ms

    def _step_risk() -> None:
        p, ms = run_risk(holder["project"])
        holder["project"] = p
        st.session_state["metrics"]["risk_ms"] = ms

    def _step_techniques() -> None:
        p, ms = run_techniques(holder["project"])
        holder["project"] = p
        st.session_state["metrics"]["techniques_ms"] = ms

    def _finalize() -> Project:
        _save_project(holder["project"])
        return holder["project"]

    if "structure_ms" not in st.session_state.get("metrics", {}):
        st.session_state["metrics"] = {}

    out = _run_with_feedback(
        "Run full pipeline",
        _finalize,
        steps=[
            ("FR 1.0 Import requirements", _step_import),
            ("FR 1.1 Structure", _step_structure),
            ("FR 2.0 Risk assessment", _step_risk),
            ("FR 3.0 Black-box cases (EP / BVA / Decision Table)", _step_techniques),
        ],
    )
    if out is not None:
        m = st.session_state.get("metrics", {})
        st.success(
            f"Pipeline complete: {len(out.requirements)} requirement(s), "
            f"{len(out.test_cases)} test case(s) "
            f"(structure {m.get('structure_ms', 0):.0f} ms / "
            f"risk {m.get('risk_ms', 0):.0f} ms / "
            f"cases {m.get('techniques_ms', 0):.0f} ms)"
        )
        return out
    return project


def _tab_import_form(project: Project) -> Project:
    """Structured form input for individual requirements (FR 1.0)."""
    st.caption("Fill in the fields for each requirement and add it to the list.")

    # Init session state for form-built requirements
    form_key = f"form_reqs_{project.id}"
    if form_key not in st.session_state:
        st.session_state[form_key] = []

    # -- Single requirement form --
    with st.form("req_form"):
        col_left, col_right = st.columns([1, 2])
        with col_left:
            req_id = st.text_input("Requirement ID", placeholder="Auto-generated if blank")
            req_title = st.text_input("Title", placeholder="Brief title")
        with col_right:
            req_text = st.text_area(
                "Raw requirement text *",
                placeholder="e.g.: After three failed login attempts the account shall be locked for 30 seconds",
            )

        st.markdown("**Structured fields** (optional — skip to auto-parse from text)")
        sc1, sc2 = st.columns(2)
        with sc1:
            inputs_raw = st.text_input(
                "Input fields",
                placeholder="username, password (comma-separated)",
            )
            conditions_raw = st.text_input(
                "Pre-conditions",
                placeholder="counter >= 3 (comma-separated)",
            )
        with sc2:
            ranges_raw = st.text_input(
                "Data ranges",
                placeholder="username: 3-20 chars, password: 8-32 chars",
            )
            expected_raw = st.text_input(
                "Expected actions",
                placeholder="account locked for 30s (comma-separated)",
            )

        submitted = st.form_submit_button("Add requirement", type="primary")

    if submitted:
        if not req_text.strip():
            st.error("Raw requirement text is required.")
        else:
            rid = req_id.strip() if req_id.strip() else Requirement().id
            structured = StructuredFields(
                inputs=[s.strip() for s in inputs_raw.split(",") if s.strip()],
                data_ranges=[s.strip() for s in ranges_raw.split(",") if s.strip()],
                conditions=[s.strip() for s in conditions_raw.split(",") if s.strip()],
                expected_actions=[s.strip() for s in expected_raw.split(",") if s.strip()],
            )
            new_req = Requirement(
                id=rid,
                title=req_title.strip() or req_text.strip()[:80],
                raw_text=req_text.strip(),
                structured=structured,
            )
            # Avoid duplicate IDs
            existing_ids = {r.id for r in st.session_state[form_key]}
            if new_req.id in existing_ids:
                new_req.id = Requirement().id
            st.session_state[form_key].append(new_req)
            st.rerun()

    # -- List of added requirements --
    pending = st.session_state[form_key]
    if pending:
        st.markdown(f"**{len(pending)} requirement(s) in buffer**")
        pending_df = pd.DataFrame(
            [
                {
                    "id": r.id,
                    "title": r.title,
                    "text": r.raw_text[:100],
                    "inputs": ", ".join(r.structured.inputs),
                    "ranges": ", ".join(r.structured.data_ranges),
                    "conditions": ", ".join(r.structured.conditions),
                    "expected": ", ".join(r.structured.expected_actions),
                }
                for r in pending
            ]
        )
        st.dataframe(pending_df, use_container_width=True)

        # Clear / Delete
        c_del, c_clear = st.columns(2)
        with c_del:
            del_id = st.selectbox("Remove requirement by ID", [r.id for r in pending], key="del_select")
            if st.button("Remove selected"):
                st.session_state[form_key] = [r for r in pending if r.id != del_id]
                st.rerun()
        with c_clear:
            if st.button("Clear all"):
                st.session_state[form_key] = []
                st.rerun()

        # -- Import into project --
        st.divider()
        imp_col1, imp_col2 = st.columns(2)
        with imp_col1:
            if st.button("Import into project", type="primary"):
                def _do():
                    project.requirements.extend(st.session_state[form_key])
                    st.session_state[form_key] = []
                    _save_project(project)
                    return project
                out = _run_with_feedback("Import requirements", _do)
                if out is not None:
                    project = out
                    st.success(f"Imported {len(project.requirements)} requirement(s)")
                    st.rerun()
        with imp_col2:
            if st.button("Import + Structure", type="secondary"):
                def _do():
                    project.requirements.extend(st.session_state[form_key])
                    st.session_state[form_key] = []
                    p, ms = run_structure(project)
                    st.session_state["metrics"]["structure_ms"] = ms
                    _save_project(p)
                    return p
                out = _run_with_feedback("Import and structure", _do)
                if out is not None:
                    project = out
                    ms = st.session_state["metrics"].get("structure_ms", 0)
                    st.success(f"Structured {len(project.requirements)} requirement(s) ({ms:.0f} ms)")
                    st.rerun()
    else:
        st.info("No requirements added yet. Use the form above to add requirements one by one.")

    return project


def tab_risk(project: Project) -> Project:
    st.subheader("2. Risk & Priority (FR 2.0)")

    # Weight configuration
    with st.expander("Risk weight configuration", expanded=True):
        st.caption("Adjust the weight of each dimension used in risk scoring.")
        col1, col2, col3 = st.columns(3)
        new_bi = col1.slider(
            "Business Impact",
            0, 100,
            int(project.risk_weights.business_impact * 100),
            step=5,
            format="%d%%",
            help="Consequence of failure: security, data integrity, revenue, user trust.",
        )
        new_fp = col2.slider(
            "Failure Probability",
            0, 100,
            int(project.risk_weights.failure_probability * 100),
            step=5,
            format="%d%%",
            help="Likelihood of failure: complexity, dependencies, historical defects.",
        )
        new_de = col3.slider(
            "Detectability",
            0, 100,
            int(project.risk_weights.detectability * 100),
            step=5,
            format="%d%%",
            help="Ease of detection: obvious to users, or silent data corruption.",
        )
        total = new_bi + new_fp + new_de
        if total != 100:
            st.warning(f"Weights sum to {total}%, not 100%. Scores will be scaled proportionally.")
        weights_changed = (
            new_bi != int(project.risk_weights.business_impact * 100)
            or new_fp != int(project.risk_weights.failure_probability * 100)
            or new_de != int(project.risk_weights.detectability * 100)
        )

    if not project.requirements:
        st.info("Import requirements on the Import tab first.")
        return project

    assess_label = "Re-assess with new weights" if weights_changed and project.risks else "Assess risks"
    if st.button(assess_label, type="primary"):
        def _do():
            # Normalize weights to sum to 1.0
            s = new_bi + new_fp + new_de
            project.risk_weights = RiskWeights(
                business_impact=new_bi / s if s else 0.4,
                failure_probability=new_fp / s if s else 0.35,
                detectability=new_de / s if s else 0.25,
            )
            p, ms = run_risk(project)
            st.session_state["metrics"]["risk_ms"] = ms
            _save_project(p)
            return p

        out = _run_with_feedback("Risk assessment", _do, success="Risk analysis complete")
        if out is not None:
            project = out

    if project.risks:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "requirement_id": r.requirement_id,
                        "score": r.score,
                        "priority": r.priority.value,
                        "reason": r.reason,
                    }
                    for r in project.risks
                ]
            ),
            use_container_width=True,
        )
    return project


def tab_coverage(project: Project) -> Project:
    st.subheader("3. Coverage Items (Interactive)")
    if not project.requirements:
        st.info("Import requirements on the Import tab first.")
    elif st.button("Generate test cases (FR 3.0)", type="primary"):
        holder = {"p": project}

        def _risk_if_needed() -> None:
            if not holder["p"].risks:
                holder["p"], _ = run_risk(holder["p"])

        def _gen_cases() -> None:
            holder["p"], ms = run_techniques(holder["p"])
            st.session_state["metrics"]["techniques_ms"] = ms

        def _save() -> Project:
            _save_project(holder["p"])
            return holder["p"]

        out = _run_with_feedback(
            "Generate test cases",
            _save,
            steps=[
                ("Risk analysis (if not done yet)", _risk_if_needed),
                ("EP / BVA / Decision Table", _gen_cases),
            ],
        )
        if out is not None:
            project = out
            ms = st.session_state["metrics"].get("techniques_ms", 0)
            st.success(f"Generated {len(project.test_cases)} test case(s) ({ms:.0f} ms)")

    with st.expander("Add Coverage Item", expanded=False):
        cov_type = st.selectbox(
            "Type",
            ["functional", "security", "boundary", "performance", "usability"],
            key="cov_add_type",
        )
        req_opts = {
            r.id: f"{r.id}: {r.title or r.raw_text[:40]}"
            for r in project.requirements
        }
        cov_req = st.selectbox(
            "Requirement",
            list(req_opts.keys()),
            format_func=lambda x: req_opts[x],
            key="cov_add_req",
        )
        cov_desc = st.text_input(
            "Description",
            placeholder="e.g. SQL injection in username field",
            key="cov_add_desc",
        )
        if st.button("Add Coverage Item", type="secondary") and cov_desc.strip():
            project.coverage_items.append(
                CoverageItem(
                    requirement_id=cov_req,
                    item_type=cov_type,
                    description=cov_desc.strip(),
                )
            )
            _save_project(project)
            st.success("Coverage item added")
            st.rerun()

    if project.coverage_items:
        df = pd.DataFrame([c.model_dump() for c in project.coverage_items])
        edited = st.data_editor(df, num_rows="dynamic", key="cov_editor")
        if st.button("Save coverage edits", type="secondary"):
            with st.spinner("Saving coverage items…"):
                old = {c.id: c for c in project.coverage_items}
                new_items = []
                for _, row in edited.iterrows():
                    cid = str(row.get("id", ""))
                    item = CoverageItem(
                        id=cid or CoverageItem().id,
                        requirement_id=str(row.get("requirement_id", "")),
                        item_type=str(row.get("item_type", "")),
                        description=str(row.get("description", "")),
                    )
                    if cid in old and old[cid].description != item.description:
                        log_review(
                            project,
                            "CoverageItem",
                            cid,
                            "description",
                            old[cid].description,
                            item.description,
                        )
                    new_items.append(item)
                project.coverage_items = new_items
                _save_project(project)
            st.toast("Coverage items saved", icon="✅")
            st.success("Coverage items saved")
    return project


def tab_planning(project: Project) -> Project:
    st.subheader("Test Planning")

    if not project.requirements:
        st.info("Import requirements on the Import tab first.")
        return project

    if not project.risks:
        st.warning("Run risk assessment first to generate a test plan.")
        return project

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("### Test Plan")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Auto-Generate Plan", type="primary", use_container_width=True):
                project.test_plan_items = auto_generate_plan(
                    project.requirements, project.risks
                )
                _save_project(project)
                st.rerun()
        with c2:
            if st.button("Clear Plan", type="secondary", use_container_width=True):
                project.test_plan_items = []
                _save_project(project)
                st.rerun()

        if project.test_plan_items:
            import pandas as pd
            phases = sorted(set(it.phase for it in project.test_plan_items))
            rows = []
            for it in sorted(project.test_plan_items, key=lambda x: x.priority_order):
                rows.append({
                    "Priority": it.priority_order,
                    "Req ID": it.requirement_id,
                    "Risk": it.risk_level,
                    "Test Level": it.test_level.value,
                    "Effort %": it.effort_pct,
                    "Phase": it.phase,
                    "Skip": it.skip,
                    "Notes": it.notes,
                })
            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df,
                column_config={
                    "Priority": st.column_config.NumberColumn("Priority", width="small"),
                    "Req ID": st.column_config.TextColumn("Req ID", width="small"),
                    "Risk": st.column_config.TextColumn("Risk", width="small"),
                    "Test Level": st.column_config.SelectboxColumn(
                        "Test Level",
                        options=["comprehensive", "standard", "smoke"],
                        width="medium",
                    ),
                    "Effort %": st.column_config.NumberColumn("Effort %", width="small", format="%.1f"),
                    "Phase": st.column_config.SelectboxColumn(
                        "Phase",
                        options=phases if phases else ["Phase 1: Smoke", "Phase 2: Functional", "Phase 3: Regression"],
                        width="medium",
                    ),
                    "Skip": st.column_config.CheckboxColumn("Skip", width="small"),
                    "Notes": st.column_config.TextColumn("Notes", width="medium"),
                },
                hide_index=True,
                use_container_width=True,
                key="plan_editor",
                num_rows="fixed",
            )

            if st.button("Save Plan", type="secondary"):
                new_items = []
                for _, row in edited.iterrows():
                    level_str = str(row.get("Test Level", "standard"))
                    try:
                        level = TestLevel(level_str)
                    except ValueError:
                        level = TestLevel.STANDARD
                    new_items.append(TestPlanItem(
                        requirement_id=str(row.get("Req ID", "")),
                        risk_level=str(row.get("Risk", "M")),
                        test_level=level,
                        effort_pct=float(row.get("Effort %", 0)),
                        priority_order=int(row.get("Priority", 0)),
                        phase=str(row.get("Phase", "")),
                        skip=bool(row.get("Skip", False)),
                        notes=str(row.get("Notes", "")),
                    ))
                project.test_plan_items = new_items
                _save_project(project)
                st.success("Plan saved")
                st.rerun()
        else:
            st.info("Click 'Auto-Generate Plan' to create a risk-driven test plan.")

    with col_right:
        st.markdown("### Plan Summary")
        if project.test_plan_items:
            summary = get_plan_summary(project.test_plan_items)
            st.metric("Total Requirements", summary["total"])
            c_a, c_s = st.columns(2)
            with c_a:
                st.metric("Active", summary["active"])
            with c_s:
                st.metric("Skipped", summary["skipped"])

            st.markdown("**By Test Level**")
            for level, count in summary.get("by_level", {}).items():
                st.text(f"{level}: {count}")

            st.markdown("**By Phase**")
            for phase, count in summary.get("by_phase", {}).items():
                st.text(f"{phase}: {count}")

            st.markdown("**Effort Distribution**")
            for it in sorted(project.test_plan_items, key=lambda x: x.priority_order):
                if it.skip:
                    continue
                st.text(f"{it.requirement_id} [{it.risk_level}]: {it.effort_pct}%")
        else:
            st.info("Generate a plan to see summary.")

    return project


def tab_strategy(project: Project) -> Project:
    st.subheader("Strategy Configuration")

    if not project.requirements:
        st.info("Import requirements on the Import tab first.")
        return project

    if not project.risks:
        st.warning("Risk assessment not yet run. Run it first or auto-recommend will use defaults.")
        if st.button("Run Risk Assessment Now", type="secondary"):
            def _do_risk():
                p, ms = run_risk(project)
                st.session_state["metrics"]["risk_ms"] = ms
                _save_project(p)
                return p

            out = _run_with_feedback("Risk assessment", _do_risk)
            if out is not None:
                project = out
                st.rerun()

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("### Technique Mapping")
        all_techniques = ["EP", "BVA", "DecisionTable", "StateTransition"]

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Auto-Recommend Techniques", type="primary", use_container_width=True):
                recommendations = auto_recommend(project.requirements, project.risks)
                project.strategy_assignments = []
                for rec in recommendations:
                    for tech in rec["recommended_techniques"]:
                        project.strategy_assignments.append(
                            StrategyAssignment(
                                requirement_id=rec["requirement_id"], technique=tech
                            )
                        )
                _save_project(project)
                st.rerun()
        with c2:
            if st.button("Reset All", type="secondary", use_container_width=True):
                project.strategy_assignments = []
                _save_project(project)
                st.rerun()

        st.caption(
            "Check the techniques to apply for each requirement. "
            "Risk: H=High (red), M=Medium (yellow), L=Low (green)."
        )

        assignments = render_technique_matrix(
            project.requirements,
            project.risks,
            project.strategy_assignments,
            all_techniques,
        )
        if assignments != project.strategy_assignments:
            project.strategy_assignments = assignments
            _save_project(project)

        st.divider()
        st.markdown("### Technique Parameters")
        tp = project.technique_params

        params_col1, params_col2 = st.columns(2)
        with params_col1:
            st.caption("**BVA: Boundary Offset**")
            new_offset = st.slider(
                "Offset",
                1,
                5,
                tp.bva_offset,
                help="+/-1 = 4 cases/field, +/-2 = 6, +/-3 = 8, +/-4 = 10, +/-5 = 12",
                key="bva_offset_slider",
            )
        with params_col2:
            st.caption("**EP: Partitions**")
            new_vp = st.slider(
                "Valid partitions", 1, 5, tp.ep_valid_partitions, key="ep_vp_slider"
            )
            new_ip = st.slider(
                "Invalid partitions",
                1,
                5,
                tp.ep_invalid_partitions,
                key="ep_ip_slider",
            )

        if (
            new_offset != tp.bva_offset
            or new_vp != tp.ep_valid_partitions
            or new_ip != tp.ep_invalid_partitions
        ):
            project.technique_params = TechniqueParameter(
                bva_offset=new_offset,
                ep_valid_partitions=new_vp,
                ep_invalid_partitions=new_ip,
            )
            _save_project(project)

        st.divider()
        st.markdown("### Suite Quick-Assign")
        if project.suites:
            suite_names = [s.name for s in project.suites]
            suite_options = ["(none)"] + suite_names
            sel_suite_name = st.selectbox(
                "Target suite", suite_options, key="quick_suite"
            )
            req_options = {
                r.id: f"{r.id}: {r.title or r.raw_text[:40]}"
                for r in project.requirements
            }
            sel_reqs = st.multiselect(
                "Select requirements to assign",
                list(req_options.keys()),
                format_func=lambda x: req_options[x],
                key="quick_assign_reqs",
            )
            if (
                st.button("Assign to Suite", type="secondary")
                and sel_suite_name != "(none)"
                and sel_reqs
            ):
                suite = next(
                    (s for s in project.suites if s.name == sel_suite_name), None
                )
                if suite:
                    assign_to_suite(project, suite.id, sel_reqs)
                    _save_project(project)
                    st.success(
                        f"Assigned {len(sel_reqs)} requirement(s) to {sel_suite_name}"
                    )
                    st.rerun()
        else:
            st.caption("No suites created yet. Create suites in the Suites tab.")

        st.divider()
        if st.button(
            "Apply Strategy & Generate Test Cases",
            type="primary",
            use_container_width=True,
        ):
            enabled_count = sum(
                1 for a in project.strategy_assignments if a.enabled
            )
            if enabled_count == 0:
                st.warning(
                    "No techniques enabled. Use Auto-Recommend or check techniques manually."
                )
            else:

                def _gen():
                    p, ms = run_techniques(project)
                    st.session_state["metrics"]["techniques_ms"] = ms
                    _save_project(p)
                    return p

                out = _run_with_feedback(
                    "Generate test cases from strategy",
                    _gen,
                    success=f"Generated test cases complete",
                )
                if out is not None:
                    project = out
                    st.success(
                        f"Generated {len(project.test_cases)} test case(s) "
                        f"({st.session_state['metrics'].get('techniques_ms', 0):.0f} ms)"
                    )

    with col_right:
        st.markdown("### Live Preview")
        assignments_for_preview = project.strategy_assignments

        if assignments_for_preview:
            estimate = estimate_case_count(
                project.requirements,
                assignments_for_preview,
                project.technique_params,
            )
            st.markdown(
                f"<div style='background:#f0f7ff;border-radius:8px;padding:16px;text-align:center'>"
                f"<p style='margin:0;font-size:14px;color:#666'>Estimated Test Cases</p>"
                f"<p style='margin:0;font-size:48px;font-weight:bold;color:#1976d2'>{estimate['total']}</p>"
                f"<p style='margin:0;font-size:12px;color:#666'>from {len(project.requirements)} requirement(s)</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.markdown("**Breakdown by Technique**")
            breakdown = estimate.get("by_technique", {})
            for tech, count in sorted(breakdown.items()):
                metadata = get_technique_metadata().get(tech, {})
                icon = metadata.get("icon", "")
                name = metadata.get("name", tech)
                st.text(f"{icon} {name}: {count}")

            st.markdown("**Coverage Estimation**")
            risk_data = [
                {
                    "requirement_id": r.requirement_id,
                    "priority": r.priority.value,
                }
                for r in project.risks
            ]
            cov = estimate_coverage(
                project.requirements, assignments_for_preview, risk_data
            )
            for level in ["H", "M", "L"]:
                if level in cov:
                    info = cov[level]
                    label = {"H": "High", "M": "Medium", "L": "Low"}[level]
                    st.markdown(
                        f"**{label}-risk** ({info['covered']}/{info['total']}): "
                        f"{info['percentage']}%"
                    )
                    st.progress(info["percentage"] / 100)
        else:
            st.info(
                "Click 'Auto-Recommend Techniques' or manually enable techniques to see preview."
            )

    return project


def tab_suites(project: Project) -> Project:
    st.subheader("Test Suites")

    with st.expander("Create Suite", expanded=not project.suites):
        suite_name = st.text_input(
            "Suite name",
            placeholder="e.g. Security_Suite",
            key="new_suite_name",
        )
        suite_desc = st.text_input(
            "Description",
            placeholder="e.g. Security-related test cases",
            key="new_suite_desc",
        )
        if st.button("Create Suite", type="primary") and suite_name.strip():
            create_suite(project, suite_name.strip(), suite_desc.strip())
            _save_project(project)
            st.success(f"Created suite: {suite_name}")
            st.rerun()

    if project.suites:
        for suite in sorted(project.suites, key=lambda s: s.priority):
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{suite.name}**")
                    st.caption(suite.description or "No description")
                    st.caption(f"{len(suite.requirement_ids)} requirement(s)")
                    if suite.requirement_ids:
                        st.caption(
                            f"Requirements: {', '.join(suite.requirement_ids[:5])}"
                            f"{'...' if len(suite.requirement_ids) > 5 else ''}"
                        )
                with c2:
                    if st.button(
                        "Delete", key=f"del_suite_{suite.id}", type="secondary"
                    ):
                        delete_suite(project, suite.id)
                        _save_project(project)
                        st.rerun()

        st.divider()
        st.markdown("### Quick Assign")
        req_options = {
            r.id: f"{r.id}: {r.title or r.raw_text[:50]}"
            for r in project.requirements
        }
        sel_assign_reqs = st.multiselect(
            "Requirements",
            list(req_options.keys()),
            format_func=lambda x: req_options[x],
            key="suite_assign_reqs",
        )
        sel_target = st.selectbox(
            "Target suite",
            [s.name for s in project.suites],
            key="suite_assign_target",
        )
        c_assign, c_remove = st.columns(2)
        with c_assign:
            if (
                st.button("Assign to Suite", use_container_width=True)
                and sel_assign_reqs
            ):
                suite = next(
                    (s for s in project.suites if s.name == sel_target), None
                )
                if suite:
                    assign_to_suite(project, suite.id, sel_assign_reqs)
                    _save_project(project)
                    st.success(
                        f"Assigned {len(sel_assign_reqs)} requirement(s) to {sel_target}"
                    )
                    st.rerun()
        with c_remove:
            if (
                st.button("Remove from Suite", use_container_width=True)
                and sel_assign_reqs
            ):
                suite = next(
                    (s for s in project.suites if s.name == sel_target), None
                )
                if suite:
                    from autotestdesign.core.strategy.suite_manager import (
                        remove_from_suite,
                    )

                    remove_from_suite(project, suite.id, sel_assign_reqs)
                    _save_project(project)
                    st.success(
                        f"Removed {len(sel_assign_reqs)} requirement(s) from {sel_target}"
                    )
                    st.rerun()
    else:
        st.info(
            "No suites yet. Create one above to organize requirements into test suites."
        )

    return project


def tab_cases(project: Project) -> Project:
    st.subheader("Test Cases (Interactive)")
    req_ids = [r.id for r in project.requirements]
    sel_req = st.selectbox("Regenerate for requirement", req_ids or ["—"])
    if st.button("Regenerate cases for selected requirement", type="primary") and req_ids:
        def _do():
            p = regenerate_for_requirement(project, sel_req)
            _save_project(p)
            return p

        out = _run_with_feedback(
            f"Regenerate cases ({sel_req})",
            _do,
            success=f"{sel_req} test cases updated",
        )
        if out is not None:
            project = out
            n = len([t for t in project.test_cases if t.requirement_id == sel_req])
            st.success(f"Regenerated cases for {sel_req} ({n} case(s) for this requirement)")

    if project.test_cases:
        rows = []
        for tc in project.test_cases:
            rows.append(
                {
                    "id": tc.id,
                    "requirement_id": tc.requirement_id,
                    "title": tc.title,
                    "technique": tc.technique,
                    "priority": tc.priority.value,
                    "status": tc.status,
                    "steps": " | ".join(tc.steps),
                    "test_data": str(tc.test_data),
                    "expected": tc.expected,
                }
            )
        edited = st.data_editor(
            pd.DataFrame(rows), num_rows="dynamic", use_container_width=True, key="tc_editor"
        )
        if st.button("Save test case edits", type="secondary"):
            with st.spinner("Saving test cases…"):
                new_cases = []
                old = {t.id: t for t in project.test_cases}
                for _, row in edited.iterrows():
                    tid = str(row.get("id", ""))
                    pr = Priority(str(row.get("priority", "M")))
                    new_status = str(row.get("status", "active"))
                    tc = TestCase(
                        id=tid or TestCase().id,
                        requirement_id=str(row.get("requirement_id", "")),
                        title=str(row.get("title", "")),
                        technique=str(row.get("technique", "")),
                        priority=pr,
                        steps=str(row.get("steps", "")).split(" | "),
                        test_data=old[tid].test_data if tid in old else {},
                        expected=str(row.get("expected", "")),
                        status=new_status,
                    )
                    if tid in old:
                        if old[tid].expected != tc.expected:
                            log_review(
                                project, "TestCase", tid, "expected",
                                old[tid].expected, tc.expected,
                            )
                        if old[tid].status != tc.status:
                            log_review(
                                project, "TestCase", tid, "status",
                                old[tid].status, tc.status,
                                note="Marked as invalid" if tc.status == "invalid" else "Restored to active",
                            )
                    new_cases.append(tc)
                project.test_cases = new_cases
                _save_project(project)
            st.toast("Test cases saved", icon="✅")

    with st.expander("FR 5.0 Test Oracle"):
        if project.requirements:
            r0 = project.requirements[0]
            td = st.text_input("username", "user01")
            pd_in = st.text_input("password", "Pass1234")
            if st.button("Generate expected result"):
                with st.spinner("Generating expected result…"):
                    exp = generate_oracle(r0, {"username": td, "password": pd_in})
                st.info(exp)
    return project


def tab_trace(project: Project) -> None:
    st.subheader("6. Traceability Matrix")
    if not project.requirements:
        st.info("Import requirements first")
        return

    # — Summary matrix —
    matrix = []
    for r in project.requirements:
        covs = [c for c in project.coverage_items if c.requirement_id == r.id]
        cases = [t for t in project.test_cases if t.requirement_id == r.id]
        matrix.append(
            {
                "requirement": r.id,
                "title": r.title or r.raw_text[:60],
                "coverage_count": len(covs),
                "case_count": len(cases),
                "techniques": ", ".join(sorted({t.technique for t in cases})),
            }
        )
    st.dataframe(pd.DataFrame(matrix), use_container_width=True)

    if not project.coverage_items and not project.test_cases:
        st.caption("Run the pipeline to generate coverage items and test cases first.")
        return

    # — Drill-down: requirement → coverage items → test cases —
    st.divider()
    st.markdown("### Drill-down: Requirement → Coverage → Test Cases")
    req_ids = [r.id for r in project.requirements]
    selected_req = st.selectbox("Select requirement", req_ids, key="trace_drill_req")
    if selected_req:
        req = next((r for r in project.requirements if r.id == selected_req), None)
        if req:
            st.markdown(f"**{req.id}**: {req.title or req.raw_text[:80]}")

        # Coverage items for this requirement
        req_covs = [c for c in project.coverage_items if c.requirement_id == selected_req]
        if req_covs:
            st.caption(f"Coverage items ({len(req_covs)})")
            cov_data = [
                {"id": c.id, "type": c.item_type, "description": c.description}
                for c in req_covs
            ]
            st.dataframe(pd.DataFrame(cov_data), use_container_width=True, hide_index=True)
        else:
            st.caption("No coverage items for this requirement.")

        # Test cases for this requirement
        req_cases = [t for t in project.test_cases if t.requirement_id == selected_req]
        if req_cases:
            st.caption(f"Test cases ({len(req_cases)})")
            case_data = [
                {
                    "id": tc.id,
                    "title": tc.title,
                    "technique": tc.technique,
                    "priority": tc.priority.value,
                    "status": tc.status,
                }
                for tc in req_cases
            ]
            st.dataframe(pd.DataFrame(case_data), use_container_width=True, hide_index=True)
        else:
            st.caption("No test cases for this requirement.")

    # — Reverse trace: test case → requirement —
    if project.test_cases:
        st.divider()
        st.markdown("### Reverse trace: Test Case → Requirement")
        tc_ids = sorted(tc.id for tc in project.test_cases)
        selected_tc = st.selectbox("Select test case", tc_ids, key="trace_rev_tc")
        if selected_tc:
            tc = next((t for t in project.test_cases if t.id == selected_tc), None)
            if tc:
                linked_req = next(
                    (r for r in project.requirements if r.id == tc.requirement_id), None
                )
                req_label = (
                    f"{linked_req.id}: {linked_req.title}"
                    if linked_req
                    else tc.requirement_id or "(none)"
                )
                st.markdown(
                    f"**{tc.id}** ({tc.technique}, {tc.priority.value}) → **{req_label}**"
                )
                st.caption(f"Steps: {' | '.join(tc.steps)}")
                st.caption(f"Expected: {tc.expected}")

    if project.trace_links:
        st.caption(f"{len(project.trace_links)} total trace links")


def tab_improve(project: Project) -> Project:
    st.subheader("7. Evidence-based Improvement")

    # — Invalid cases summary —
    invalid_cases = [tc for tc in project.test_cases if tc.status == "invalid"]
    if invalid_cases:
        st.markdown(f"### {len(invalid_cases)} Invalid Test Case(s)")
        inv_data = [
            {
                "id": tc.id,
                "requirement_id": tc.requirement_id,
                "title": tc.title,
                "technique": tc.technique,
                "expected": tc.expected,
            }
            for tc in invalid_cases
        ]
        st.dataframe(pd.DataFrame(inv_data), use_container_width=True, hide_index=True)

        # Regenerate with feedback from invalid cases
        st.markdown("#### Regenerate with feedback")
        st.caption(
            "Invalid cases for the selected requirement will be injected as "
            "negative examples into the LLM prompt to improve output."
        )
        inv_req_ids = sorted({tc.requirement_id for tc in invalid_cases})
        sel_fb_req = st.selectbox(
            "Requirement to regenerate", inv_req_ids, key="fb_req_select"
        )
        if st.button("Regenerate with feedback", type="primary"):
            def _do():
                p = regenerate_for_requirement(project, sel_fb_req, feedback_cases=invalid_cases)
                _save_project(p)
                return p

            out = _run_with_feedback(
                f"Regenerate with feedback ({sel_fb_req})",
                _do,
                success="Regenerated using evidence from invalid cases",
            )
            if out is not None:
                project = out
                new_cases = [t for t in project.test_cases if t.requirement_id == sel_fb_req]
                st.success(
                    f"Regenerated {len(new_cases)} case(s) for {sel_fb_req} "
                    f"using {len(invalid_cases)} invalid case(s) as feedback"
                )
    else:
        st.info(
            "No invalid cases yet. Mark cases as invalid in the "
            "Test Cases tab by changing their status to 'invalid'."
        )

    # — Manual improvement —
    st.divider()
    st.markdown("### Manual improvement")
    if st.button("Add improvement test case (manual)"):
        req_id = project.requirements[0].id if project.requirements else ""
        tc = TestCase(
            requirement_id=req_id,
            title="IMPROVED: Session timeout after login",
            technique="EP",
            priority=Priority.HIGH,
            steps=["Login successfully", "Idle 30 minutes", "Perform action"],
            expected="Redirect to login with session expired message",
        )
        log_review(
            project,
            "TestCase",
            tc.id,
            "created",
            "",
            tc.title,
            note="Evidence-based improvement",
        )
        project.test_cases.append(tc)
        _save_project(project)
        st.success("Added improvement case")
        st.rerun()

    # — Review log —
    st.divider()
    st.markdown("### Review audit log")
    if project.review_events:
        st.dataframe(
            pd.DataFrame([e.model_dump() for e in project.review_events]),
            use_container_width=True,
        )
    else:
        st.info("Edit coverage or test cases to record review events")
    return project


def tab_whitebox(project: Project) -> Project:
    st.subheader("White-Box Testing (FR 4.0)")

    from autotestdesign.core.whitebox import (
        CRITERIA_MAP,
        detect_and_parse,
        derive_control_flow_graph,
        derive_state_machine,
        optimize_result,
        run_coverage,
    )
    from autotestdesign.core.whitebox.models import ControlFlowGraph, StateMachine

    col_left, col_right = st.columns([2, 3])

    with col_left:
        st.markdown("### Model Definition")
        model_type = st.radio(
            "Model type",
            ["State Machine", "Control Flow Graph"],
            key="wb_model_type",
            horizontal=True,
        )
        input_mode = st.radio(
            "Input mode",
            ["Manual (Mermaid/JSON)", "LLM Derive from Requirements"],
            key="wb_input_mode",
            horizontal=True,
        )

        model_text = ""
        model: StateMachine | ControlFlowGraph | None = None

        if input_mode.startswith("Manual"):
            model_text = st.text_area(
                "Paste Mermaid or JSON model definition",
                height=250,
                key="wb_model_text",
                placeholder="stateDiagram-v2\n    [*] --> Idle\n    Idle --> Active: start\n    Active --> [*]: stop",
            )
            if model_text.strip():
                model = detect_and_parse(model_text.strip())
                if model:
                    st.success(
                        f"Parsed: {type(model).__name__} — "
                        f"{len(model.states if isinstance(model, StateMachine) else model.nodes)} nodes, "
                        f"{len(model.transitions if isinstance(model, StateMachine) else model.edges)} edges"
                    )
                else:
                    st.error("Could not parse model. Check syntax.")
        else:
            if st.button("Derive from Requirements", key="wb_derive_btn"):
                if not project.requirements:
                    st.warning("No requirements found. Import requirements first.")
                else:
                    with st.spinner("LLM is deriving model from requirements..."):
                        if model_type == "State Machine":
                            model = derive_state_machine(project.requirements)
                        else:
                            model = derive_control_flow_graph(project.requirements)
                    if model:
                        st.success(
                            f"Derived {type(model).__name__} with "
                            f"{len(model.states if isinstance(model, StateMachine) else model.nodes)} nodes"
                        )
                        st.session_state["wb_derived_model"] = model
                        st.json(model.model_dump())
                    else:
                        st.error("LLM derivation failed. Check API key or try manual input.")

            if "wb_derived_model" in st.session_state:
                model = st.session_state["wb_derived_model"]

        st.markdown("### Coverage Criteria")
        is_sm = model_type == "State Machine"
        sm_criteria = ["state", "transition"]
        cfg_criteria = ["statement", "branch", "path", "condition", "mcdc"]
        available = sm_criteria if is_sm else cfg_criteria

        selected_criteria = st.multiselect(
            "Select coverage criteria",
            available,
            default=available[:3],
            key="wb_criteria",
        )

        optimize = st.checkbox("Apply optimization (greedy + postman)", value=True, key="wb_optimize")

        if st.button("Generate Coverage Sequences", key="wb_generate_btn", type="primary"):
            if model is None:
                st.error("No model defined. Provide a model first.")
            elif not selected_criteria:
                st.error("Select at least one coverage criterion.")
            else:
                with st.spinner("Generating coverage sequences..."):
                    results = run_coverage(model, selected_criteria)
                    sm_for_opt = model if isinstance(model, StateMachine) else None
                    if optimize:
                        results = [optimize_result(r, sm_for_opt) for r in results]
                    st.session_state["wb_results"] = results
                    st.session_state["wb_model"] = model

    with col_right:
        st.markdown("### Results")
        results = st.session_state.get("wb_results")
        model_stored = st.session_state.get("wb_model")

        if results:
            for i, result in enumerate(results):
                with st.expander(
                    f"{result.model_type} — {result.coverage_pct:.0f}% coverage "
                    f"({sum(1 for t in result.coverage_targets if t.covered)}/"
                    f"{len(result.coverage_targets)} targets)",
                    expanded=i == 0,
                ):
                    st.markdown("**Coverage Targets:**")
                    for t in result.coverage_targets:
                        st.text(f"{'[OK]' if t.covered else '[  ]'} {t.target_type}: {t.description}")

                    st.markdown("**Test Sequences:**")
                    for j, seq in enumerate(result.test_sequences):
                        path_str = " -> ".join(seq)
                        st.text(f"Seq {j + 1}: {path_str}")

            if st.button("Add to Test Suite", key="wb_add_to_suite"):
                _add_whitebox_results(project, results, model_stored)
                _save_project(project)
                st.success(
                    f"Added {sum(len(r.test_sequences) for r in results)} "
                    "white-box test cases to the suite"
                )
                st.rerun()

        # Render diagram if available
        if model_stored:
            if isinstance(model_stored, StateMachine):
                mermaid_lines = ["stateDiagram-v2"]
                for t in model_stored.transitions:
                    mermaid_lines.append(f"    {t.source} --> {t.target}: {t.trigger}")
                st.markdown("### Model Diagram")
                st.code("\n".join(mermaid_lines), language="mermaid")
        elif project.state_diagram:
            st.markdown("### Model Diagram")
            st.code(project.state_diagram, language="mermaid")

    return project


def _add_whitebox_results(project: Project, results: list, model) -> None:
    """Add whitebox coverage results as TestCases to the project."""
    from autotestdesign.core.whitebox.models import WhiteboxResult
    from autotestdesign.core.pipeline import _rebuild_trace_links

    first_req = project.requirements[0].id if project.requirements else ""
    for result in results:
        for i, seq in enumerate(result.test_sequences):
            path_desc = " -> ".join(seq)
            technique = (
                "StateTransition"
                if result.model_type == "state_machine"
                else "ControlFlowPath"
            )
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

    if results:
        combined = WhiteboxResult()
        combined.model_type = results[0].model_type
        for r in results:
            combined.coverage_targets.extend(r.coverage_targets)
            combined.test_sequences.extend(r.test_sequences)
        total = len(combined.coverage_targets)
        covered = sum(1 for t in combined.coverage_targets if t.covered)
        combined.coverage_pct = (covered / total * 100) if total else 100
        project.whitebox_result = combined.model_dump()

    _rebuild_trace_links(project)


def tab_export(project: Project) -> None:
    st.subheader("8. Export (FR 6.0)")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Download JSON",
            export_json_bytes(project),
            file_name=f"{project.name.replace(' ', '_')}.json",
            mime="application/json",
        )
    with c2:
        st.download_button(
            "Download CSV",
            export_csv(project),
            file_name=f"{project.name.replace(' ', '_')}_cases.csv",
            mime="text/csv",
        )

    st.subheader("Optional: FR 4.0 / FR 7.0")
    if st.button("Add white-box state model (FR 4.0)"):
        out = _run_with_feedback(
            "Add white-box state model",
            lambda: add_whitebox(project),
            success="State model added",
        )
        if out is not None:
            project = out
            _save_project(project)
            st.success("State model added")
    if project.state_diagram:
        st.markdown(project.state_diagram)

    if st.button("Optimize suite by risk (FR 7.0)"):
        with st.spinner("Optimizing test suite…"):
            project.optimized_case_ids = optimize_suite(project)
            _save_project(project)
        st.toast("Suite optimization complete", icon="✅")
        st.write(f"Optimized order: {len(project.optimized_case_ids)} unique cases")

    m = st.session_state.get("metrics", {})
    if m:
        st.metric("Structure ms", f"{m.get('structure_ms', 0):.0f}")
        st.metric("Risk ms", f"{m.get('risk_ms', 0):.0f}")
        st.metric("Techniques ms", f"{m.get('techniques_ms', 0):.0f}")


def main() -> None:
    st.set_page_config(page_title="AutoTestDesign", layout="wide")
    _init_state()
    page_sidebar()
    project = _load_project()
    if not project:
        st.title("AutoTestDesign")
        st.info("Create or load a project from the sidebar.")
        st.markdown(
            """
**Workflow:** Import → Structure → Risk → Generate cases → Review → Export

Target application for this assignment: **Login Web Module** (`target-app/`)
            """
        )
        return

    st.title(project.name)
    st.caption(project.target_app_description)
    _show_last_job_banner()

    tabs = st.tabs(
        [
            "Import",
            "Risk",
            "Planning",
            "Strategy",
            "Coverage",
            "Suites",
            "Test Cases",
            "White-Box",
            "Traceability",
            "Improvement",
            "Export",
        ]
    )
    handlers = [
        tab_import,
        tab_risk,
        tab_planning,
        tab_strategy,
        tab_coverage,
        tab_suites,
        tab_cases,
        tab_whitebox,
        tab_trace,
        tab_improve,
        tab_export,
    ]
    for tab, fn in zip(tabs, handlers):
        with tab:
            if fn is tab_trace:
                fn(project)
            else:
                project = fn(project)


if __name__ == "__main__":
    main()
