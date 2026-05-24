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
    StructuredFields,
    TestCase,
    TestStrategy,
)
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
    return _get_store().load(pid)


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


def tab_strategy(project: Project) -> Project:
    st.subheader("4. Test Strategy")
    if not project.strategies and st.button("Create default strategies"):
        project.strategies = [
            TestStrategy(
                technique="EP",
                rationale="Equivalence partitioning for input classes",
                requirement_ids=[r.id for r in project.requirements],
            ),
            TestStrategy(
                technique="BVA",
                rationale="Boundary values on length constraints",
                requirement_ids=[r.id for r in project.requirements],
            ),
            TestStrategy(
                technique="DecisionTable",
                rationale="Condition combinations for login",
                requirement_ids=[r.id for r in project.requirements],
            ),
        ]
        _save_project(project)
    if project.strategies:
        df = pd.DataFrame(
            [
                {
                    "id": s.id,
                    "technique": s.technique,
                    "rationale": s.rationale,
                    "requirements": ",".join(s.requirement_ids),
                }
                for s in project.strategies
            ]
        )
        edited = st.data_editor(df, num_rows="dynamic", key="str_editor")
        if st.button("Save strategy edits", type="secondary"):
            with st.spinner("Saving strategies…"):
                new_s = []
                for _, row in edited.iterrows():
                    new_s.append(
                        TestStrategy(
                            id=str(row.get("id", TestStrategy().id)),
                            technique=str(row.get("technique", "")),
                            rationale=str(row.get("rationale", "")),
                            requirement_ids=str(row.get("requirements", "")).split(",")
                            if row.get("requirements")
                            else [],
                        )
                    )
                project.strategies = new_s
                _save_project(project)
            st.toast("Strategies saved", icon="✅")
    return project


def tab_cases(project: Project) -> Project:
    st.subheader("5. Test Cases (Interactive)")
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
                    tc = TestCase(
                        id=tid or TestCase().id,
                        requirement_id=str(row.get("requirement_id", "")),
                        title=str(row.get("title", "")),
                        technique=str(row.get("technique", "")),
                        priority=pr,
                        steps=str(row.get("steps", "")).split(" | "),
                        test_data=old[tid].test_data if tid in old else {},
                        expected=str(row.get("expected", "")),
                    )
                    if tid in old and old[tid].expected != tc.expected:
                        log_review(
                            project, "TestCase", tid, "expected", old[tid].expected, tc.expected
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
    matrix = []
    for r in project.requirements:
        covs = [c for c in project.coverage_items if c.requirement_id == r.id]
        cases = [t for t in project.test_cases if t.requirement_id == r.id]
        matrix.append(
            {
                "requirement": r.id,
                "coverage_count": len(covs),
                "case_count": len(cases),
                "techniques": ", ".join(sorted({t.technique for t in cases})),
            }
        )
    st.dataframe(pd.DataFrame(matrix), use_container_width=True)
    if project.trace_links:
        st.caption(f"{len(project.trace_links)} trace links")


def tab_improve(project: Project) -> Project:
    st.subheader("7. Evidence-based Improvement")
    st.caption("Review log captures designer changes for audit trail")
    if project.review_events:
        st.dataframe(
            pd.DataFrame([e.model_dump() for e in project.review_events]),
            use_container_width=True,
        )
    else:
        st.info("Edit coverage or test cases to record review events")

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
    return project


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
            "Coverage",
            "Strategy",
            "Test Cases",
            "Traceability",
            "Improvement",
            "Export",
        ]
    )
    handlers = [
        tab_import,
        tab_risk,
        tab_coverage,
        tab_strategy,
        tab_cases,
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
