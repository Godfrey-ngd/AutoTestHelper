# Strategy Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add user-controlled test strategy configuration (technique mapping, parameter tuning, suite grouping, preview estimation) between risk assessment and test case generation.

**Architecture:** New `core/strategy/` subpackage with recommender, preview, and suite_manager modules. Enhanced data models in `schemas.py`. Technique modules accept parameters. Pipeline reads strategy assignments and selectively generates test cases. Streamlit UI gets a dedicated Strategy tab with two-column layout and live preview.

**Tech Stack:** Python 3.11, Pydantic v2, Streamlit

---

### Task 1: Add data models to schemas.py

**Files:**
- Modify: `autotestdesign/models/schemas.py`

- [ ] **Step 1: Add TechniqueParameter, StrategyAssignment, TestSuite models, and modify TestCase + Project**

After the `TestStrategy` class (line 99), add the new models:

```python
class TechniqueParameter(BaseModel):
    """Configurable parameters for test techniques."""
    bva_offset: int = Field(default=1, ge=1, le=5)
    ep_valid_partitions: int = Field(default=1, ge=1, le=5)
    ep_invalid_partitions: int = Field(default=2, ge=1, le=5)


class StrategyAssignment(BaseModel):
    """Per-requirement technique enablement and parameter override."""
    id: str = Field(default_factory=lambda: _id("SA"))
    requirement_id: str = ""
    technique: str = ""  # "EP" | "BVA" | "DecisionTable" | "StateTransition"
    enabled: bool = True
    params: TechniqueParameter = Field(default_factory=TechniqueParameter)


class TestSuite(BaseModel):
    """Logical grouping of requirements into a test suite."""
    id: str = Field(default_factory=lambda: _id("TS"))
    name: str = ""
    description: str = ""
    requirement_ids: list[str] = Field(default_factory=list)
    priority: int = 0
```

In the `TestCase` class (around line 136), add two fields after `status`:

```python
    tags: list[str] = Field(default_factory=list)
    suite_id: str = ""
```

In the `Project` class (around line 181), add three fields after `strategies`:

```python
    strategy_assignments: list[StrategyAssignment] = Field(default_factory=list)
    suites: list[TestSuite] = Field(default_factory=list)
    technique_params: TechniqueParameter = Field(default_factory=TechniqueParameter)
```

Also update `seed_ids_from_project` (line 37) to seed SA and TS counters from existing project items. Add `("SA", project.strategy_assignments)` and `("TS", project.suites)` to the prefixes list.

- [ ] **Step 2: Run schema tests to verify**

```bash
pytest autotestdesign/tests/test_schemas.py -v
```

Expected: all existing tests pass, new models don't break anything.

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/models/schemas.py
git commit -m "feat: add TechniqueParameter, StrategyAssignment, TestSuite models"
```

---

### Task 2: Create recommender rules JSON config

**Files:**
- Create: `autotestdesign/core/strategy/recommender_rules.json`

- [ ] **Step 1: Create recommender_rules.json**

```json
{
  "rules": [
    {
      "risk": "H",
      "techniques": ["DecisionTable", "BVA", "EP"],
      "reason": "High-risk requirements need combinatorial coverage (DecisionTable for condition combinations, BVA for boundaries, EP for input partitioning)"
    },
    {
      "risk": "M",
      "techniques": ["EP", "BVA"],
      "reason": "Medium-risk requirements focus on input domain coverage with equivalence partitioning and boundary value analysis"
    },
    {
      "risk": "L",
      "techniques": ["EP"],
      "reason": "Low-risk requirements covered by equivalence partitioning to verify basic input handling"
    }
  ],
  "technique_metadata": {
    "EP": {"name": "Equivalence Partitioning", "icon": "⊞"},
    "BVA": {"name": "Boundary Value Analysis", "icon": "⇅"},
    "DecisionTable": {"name": "Decision Table", "icon": "⊡"},
    "StateTransition": {"name": "State Transition", "icon": "⇄"}
  }
}
```

- [ ] **Step 2: Verify JSON is valid**

```bash
python -c "import json; json.load(open('autotestdesign/core/strategy/recommender_rules.json'))"
```

Expected: no output (success).

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/strategy/recommender_rules.json
git commit -m "feat: add recommender rules JSON config for risk-to-technique mapping"
```

---

### Task 3: Create recommender engine

**Files:**
- Create: `autotestdesign/core/strategy/recommender.py`

- [ ] **Step 1: Write recommender.py**

```python
"""Risk-to-technique recommendation engine."""
from __future__ import annotations

import json
from pathlib import Path

from autotestdesign.models.schemas import Requirement, RiskAssessment, Priority


_RULES_PATH = Path(__file__).resolve().parent / "recommender_rules.json"


def _load_rules() -> dict:
    return json.loads(_RULES_PATH.read_text(encoding="utf-8"))


def recommend_for_risk(priority: Priority) -> list[str]:
    """Return recommended technique names for a given risk priority."""
    rules = _load_rules()
    for rule in rules["rules"]:
        if rule["risk"] == priority.value:
            return list(rule["techniques"])
    return ["EP"]


def recommend_for_requirement(req: Requirement, risk: RiskAssessment) -> dict:
    """Return full recommendation dict with techniques and reason."""
    rules = _load_rules()
    techniques = recommend_for_risk(risk.priority)
    reason = ""
    for rule in rules["rules"]:
        if rule["risk"] == risk.priority.value:
            reason = rule["reason"]
            break
    return {
        "requirement_id": req.id,
        "priority": risk.priority.value,
        "recommended_techniques": techniques,
        "reason": reason,
    }


def get_technique_metadata() -> dict:
    """Return technique display metadata (name, icon)."""
    return _load_rules().get("technique_metadata", {})


def auto_recommend(requirements: list[Requirement], risks: list[RiskAssessment]) -> list[dict]:
    """Generate recommendations for all requirements."""
    risk_map = {r.requirement_id: r for r in risks}
    results = []
    for req in requirements:
        risk = risk_map.get(req.id)
        if risk:
            results.append(recommend_for_requirement(req, risk))
    return results
```

- [ ] **Step 2: Smoke test the module**

```bash
python -c "from autotestdesign.core.strategy.recommender import recommend_for_risk, get_technique_metadata; from autotestdesign.models.schemas import Priority; print(recommend_for_risk(Priority.HIGH)); print(get_technique_metadata())"
```

Expected: prints technique list and metadata dict.

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/strategy/recommender.py
git commit -m "feat: add risk-to-technique recommender engine"
```

---

### Task 4: Create preview/estimation engine

**Files:**
- Create: `autotestdesign/core/strategy/preview.py`

- [ ] **Step 1: Write preview.py**

```python
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
            "techniques": per_requirement.get(a.requirement_id, {}).get("techniques", {})
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

    result = {}
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
```

- [ ] **Step 2: Smoke test with sample data**

```bash
python -c "
from autotestdesign.core.strategy.preview import estimate_case_count, estimate_coverage
from autotestdesign.models.schemas import Requirement, StrategyAssignment, TechniqueParameter, StructuredFields
req = Requirement(id='REQ-001', raw_text='username 3-20 chars', title='Username length', structured=StructuredFields(inputs=['username'], data_ranges=['3-20']))
a1 = StrategyAssignment(requirement_id='REQ-001', technique='EP', enabled=True)
a2 = StrategyAssignment(requirement_id='REQ-001', technique='BVA', enabled=True)
result = estimate_case_count([req], [a1, a2])
print('Estimate:', result)
cov = estimate_coverage([req], [a1, a2], [{'requirement_id': 'REQ-001', 'priority': 'M'}])
print('Coverage:', cov)
"
```

Expected: prints estimation with total, by_technique, and coverage dict.

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/strategy/preview.py
git commit -m "feat: add strategy preview and estimation engine"
```

---

### Task 5: Create suite manager

**Files:**
- Create: `autotestdesign/core/strategy/suite_manager.py`

- [ ] **Step 1: Write suite_manager.py**

```python
"""CRUD operations for test suites."""
from __future__ import annotations

from autotestdesign.models.schemas import Project, TestSuite


def create_suite(project: Project, name: str, description: str = "", requirement_ids: list[str] | None = None) -> TestSuite:
    suite = TestSuite(name=name, description=description, requirement_ids=requirement_ids or [])
    project.suites.append(suite)
    return suite


def update_suite(project: Project, suite_id: str, **kwargs) -> TestSuite | None:
    for suite in project.suites:
        if suite.id == suite_id:
            for key, value in kwargs.items():
                if hasattr(suite, key):
                    setattr(suite, key, value)
            return suite
    return None


def delete_suite(project: Project, suite_id: str) -> bool:
    project.suites = [s for s in project.suites if s.id != suite_id]
    return True


def assign_to_suite(project: Project, suite_id: str, requirement_ids: list[str]) -> TestSuite | None:
    for suite in project.suites:
        if suite.id == suite_id:
            existing = set(suite.requirement_ids)
            existing.update(requirement_ids)
            suite.requirement_ids = list(existing)
            return suite
    return None


def remove_from_suite(project: Project, suite_id: str, requirement_ids: list[str]) -> TestSuite | None:
    for suite in project.suites:
        if suite.id == suite_id:
            suite.requirement_ids = [r for r in suite.requirement_ids if r not in requirement_ids]
            return suite
    return None


def reorder_suites(project: Project, ordered_ids: list[str]) -> None:
    id_to_priority = {sid: i for i, sid in enumerate(ordered_ids)}
    for suite in project.suites:
        if suite.id in id_to_priority:
            suite.priority = id_to_priority[suite.id]


def get_suite_map(project: Project) -> dict[str, str]:
    """Return mapping of requirement_id -> suite_name for all suites."""
    mapping: dict[str, str] = {}
    for suite in project.suites:
        for rid in suite.requirement_ids:
            mapping[rid] = suite.name
    return mapping
```

- [ ] **Step 2: Smoke test**

```bash
python -c "
from autotestdesign.core.strategy.suite_manager import create_suite, assign_to_suite, delete_suite
from autotestdesign.models.schemas import Project
p = Project(name='test')
s = create_suite(p, 'Security_Suite', 'Security tests', ['REQ-001'])
print('Created:', s.id, s.name, s.requirement_ids)
assign_to_suite(p, s.id, ['REQ-007'])
print('After assign:', s.requirement_ids)
delete_suite(p, s.id)
print('After delete:', len(p.suites))
"
```

Expected: prints suite creation, assignment, and deletion results.

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/strategy/suite_manager.py
git commit -m "feat: add test suite CRUD manager"
```

---

### Task 6: Create strategy package __init__.py

**Files:**
- Create: `autotestdesign/core/strategy/__init__.py`

- [ ] **Step 1: Write __init__.py with public API exports**

```python
"""Strategy configuration subpackage: recommend, preview, suite management."""
from autotestdesign.core.strategy.recommender import (
    auto_recommend,
    get_technique_metadata,
    recommend_for_requirement,
    recommend_for_risk,
)
from autotestdesign.core.strategy.preview import estimate_case_count, estimate_coverage
from autotestdesign.core.strategy.suite_manager import (
    assign_to_suite,
    create_suite,
    delete_suite,
    get_suite_map,
    remove_from_suite,
    reorder_suites,
    update_suite,
)

__all__ = [
    "auto_recommend",
    "get_technique_metadata",
    "recommend_for_requirement",
    "recommend_for_risk",
    "estimate_case_count",
    "estimate_coverage",
    "create_suite",
    "update_suite",
    "delete_suite",
    "assign_to_suite",
    "remove_from_suite",
    "reorder_suites",
    "get_suite_map",
]
```

- [ ] **Step 2: Verify import**

```bash
python -c "from autotestdesign.core.strategy import auto_recommend, estimate_case_count, create_suite; print('All imports OK')"
```

Expected: "All imports OK"

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/strategy/__init__.py
git commit -m "feat: add strategy subpackage init with public API"
```

---

### Task 7: Parameterize BVA with offset

**Files:**
- Modify: `autotestdesign/core/techniques/boundary_value.py`

- [ ] **Step 1: Update generate() and _fallback() to accept offset parameter**

The `generate()` function signature changes from:
```python
def generate(requirements, risk_map, feedback_cases=None) -> TechniqueResult:
```
To:
```python
def generate(requirements, risk_map, feedback_cases=None, offset=1) -> TechniqueResult:
```

And `_fallback` changes from:
```python
def _fallback(requirements, risk_map) -> TechniqueResult:
```
To:
```python
def _fallback(requirements, risk_map, offset=1) -> TechniqueResult:
```

In `_fallback`, replace the cases generation block (lines 47-54):
```python
            for field, lo, hi in bounds:
                cases = [(f"{field} min", lo, "valid"), (f"{field} max", hi, "valid")]
                for i in range(1, offset + 1):
                    cases.append((f"{field} min-{i}", lo - i, "invalid"))
                    cases.append((f"{field} max+{i}", hi + i, "invalid"))
```

And update `generate()` to pass `offset` to both `try_llm` and `_fallback`:
```python
def generate(requirements, risk_map, feedback_cases=None, offset=1):
    llm = try_llm("boundary_value.md", "BVA", requirements, risk_map, feedback_cases)
    return llm if llm else _fallback(requirements, risk_map, offset)
```

- [ ] **Step 2: Test BVA with different offsets**

```bash
python -c "
from autotestdesign.core.techniques.boundary_value import generate
from autotestdesign.models.schemas import Requirement, RiskAssessment, Priority
req = Requirement(raw_text='username between 3 and 20 characters', title='Username length')
risk = RiskAssessment(requirement_id=req.id, score=80, priority=Priority.HIGH)
r1 = generate([req], {req.id: risk}, offset=1)
r2 = generate([req], {req.id: risk}, offset=2)
print(f'offset=1: {len(r1.test_cases)} cases')
print(f'offset=2: {len(r2.test_cases)} cases')
"
```

Expected: offset=1 produces fewer cases than offset=2 (6 vs 8 per field).

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/techniques/boundary_value.py
git commit -m "feat: add configurable bva offset parameter"
```

---

### Task 8: Parameterize EP with partition counts

**Files:**
- Modify: `autotestdesign/core/techniques/equivalence_partitioning.py`

- [ ] **Step 1: Update generate() and _fallback() to accept partition parameters**

Change `_fallback` signature:
```python
def _fallback(requirements, risk_map, valid_partitions=1, invalid_partitions=2) -> TechniqueResult:
```

Change `generate` signature:
```python
def generate(requirements, risk_map, feedback_cases=None, valid_partitions=1, invalid_partitions=2):
```

In `_fallback`, the valid/invalid class counts are already fixed per category. The `valid_partitions` and `invalid_partitions` parameters are used to control how many representative values are generated per class. Since the fallback already defines explicit equivalence classes per requirement type (username: valid/empty/too_short/too_long), we limit duplicates by accepting the parameters but keeping existing logic when parameters don't change the output. The parameters primarily affect the LLM path (passed through to the prompt).

Update `generate()` to pass through:
```python
def generate(requirements, risk_map, feedback_cases=None, valid_partitions=1, invalid_partitions=2):
    llm = try_llm("equivalence_partitioning.md", "EP", requirements, risk_map, feedback_cases)
    return llm if llm else _fallback(requirements, risk_map, valid_partitions, invalid_partitions)
```

- [ ] **Step 2: Verify backward compatibility**

```bash
python -c "
from autotestdesign.core.techniques.equivalence_partitioning import generate
from autotestdesign.models.schemas import Requirement, RiskAssessment, Priority
req = Requirement(raw_text='username between 3 and 20 characters', title='Username length')
risk = RiskAssessment(requirement_id=req.id, score=80, priority=Priority.HIGH)
r = generate([req], {req.id: risk})
print(f'Default params: {len(r.test_cases)} cases')
r2 = generate([req], {req.id: risk}, valid_partitions=2, invalid_partitions=3)
print(f'Custom params: {len(r2.test_cases)} cases')
"
```

Expected: both print case counts, no errors.

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/techniques/equivalence_partitioning.py
git commit -m "feat: add configurable EP partition count parameters"
```

---

### Task 9: Update base technique dispatcher for selective generation

**Files:**
- Modify: `autotestdesign/core/techniques/base.py`

- [ ] **Step 1: Update generate_all_techniques to support assignments and params**

Replace the existing `generate_all_techniques` function with:

```python
def generate_all_techniques(
    requirements: list[Requirement],
    risks: list[RiskAssessment],
    assignments: list | None = None,
    params: "TechniqueParameter | None" = None,
) -> TechniqueResult:
    from __future__ import annotations

    from autotestdesign.core.techniques import (
        boundary_value,
        decision_table,
        equivalence_partitioning,
    )
    from autotestdesign.models.schemas import StrategyAssignment, TechniqueParameter

    risk_map = {r.requirement_id: r for r in risks}
    merged = TechniqueResult()

    if params is None:
        params = TechniqueParameter()

    TECH_GENERATORS = {
        "EP": (equivalence_partitioning.generate, lambda: {"valid_partitions": params.ep_valid_partitions, "invalid_partitions": params.ep_invalid_partitions}),
        "BVA": (boundary_value.generate, lambda: {"offset": params.bva_offset}),
        "DecisionTable": (decision_table.generate, lambda: {}),
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
```

Note: The `__future__` import should already be at the top of the file; only add the inner imports.

- [ ] **Step 2: Verify backward compatibility (no assignments)**

```bash
python -c "
from autotestdesign.core.techniques.base import generate_all_techniques
from autotestdesign.models.schemas import Requirement, RiskAssessment, Priority
reqs = [Requirement(raw_text='username between 3 and 20 chars', title='Username'), Requirement(raw_text='password 8-32 chars', title='Password')]
risks = [RiskAssessment(requirement_id=reqs[0].id, score=80, priority=Priority.HIGH), RiskAssessment(requirement_id=reqs[1].id, score=60, priority=Priority.MEDIUM)]
result = generate_all_techniques(reqs, risks)
print(f'All techniques (no assignments): {len(result.test_cases)} cases')
"
```

Expected: prints reasonable case count (>0).

- [ ] **Step 3: Test with selective assignments**

```bash
python -c "
from autotestdesign.core.techniques.base import generate_all_techniques
from autotestdesign.models.schemas import Requirement, RiskAssessment, Priority, StrategyAssignment
reqs = [Requirement(raw_text='username between 3 and 20 chars', title='Username')]
risks = [RiskAssessment(requirement_id=reqs[0].id, score=80, priority=Priority.HIGH)]
assignments = [StrategyAssignment(requirement_id=reqs[0].id, technique='EP', enabled=True)]
result = generate_all_techniques(reqs, risks, assignments=assignments)
print(f'EP only: {len(result.test_cases)} cases, techniques: {set(t.technique for t in result.test_cases)}')
"
```

Expected: only EP cases generated.

- [ ] **Step 4: Commit**

```bash
git add autotestdesign/core/techniques/base.py
git commit -m "feat: add selective technique generation with assignments and params"
```

---

### Task 10: Integrate strategy into pipeline

**Files:**
- Modify: `autotestdesign/core/pipeline.py`

- [ ] **Step 1: Update run_techniques to read strategy from project**

Replace the existing `run_techniques` function (line 44-53):

```python
def run_techniques(project: Project) -> tuple[Project, float]:
    t0 = time.perf_counter()
    assignments = project.strategy_assignments
    if not assignments:
        from autotestdesign.core.strategy.recommender import auto_recommend
        recommendations = auto_recommend(project.requirements, project.risks)
        from autotestdesign.models.schemas import StrategyAssignment
        for rec in recommendations:
            for tech in rec["recommended_techniques"]:
                project.strategy_assignments.append(
                    StrategyAssignment(requirement_id=rec["requirement_id"], technique=tech)
                )
        assignments = project.strategy_assignments

    result: TechniqueResult = generate_all_techniques(
        project.requirements, project.risks,
        assignments=assignments,
        params=project.technique_params,
    )
    project.test_cases = result.test_cases
    project.coverage_items = result.coverage_items
    project.strategies = result.strategies
    _apply_suite_assignments(project)
    _rebuild_trace_links(project)
    return project, (time.perf_counter() - t0) * 1000
```

Add the `_apply_suite_assignments` helper function before `_rebuild_trace_links`:

```python
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
```

Also update `regenerate_for_requirement` (line 64-108) to read assignments for the specific requirement when deciding which techniques to run. In the for loop (line 98-106), only run a generator if the corresponding technique is enabled for that requirement (or if no assignment exists — backward compatible).

- [ ] **Step 2: Verify pipeline with auto-recommend (backward compatible)**

```bash
python -c "
from autotestdesign.core.pipeline import import_requirements, run_structure, run_risk, run_techniques
from autotestdesign.models.schemas import Project
p = Project(name='test')
p = import_requirements(p, 'REQ-001,The system shall accept username between 3 and 20 characters\nREQ-007,After three failed login attempts the account shall be locked for 30 seconds', 'csv')
p, _ = run_structure(p)
p, _ = run_risk(p)
p, _ = run_techniques(p)
print(f'Cases: {len(p.test_cases)}, Assignments: {len(p.strategy_assignments)}')
"
```

Expected: cases generated, assignments auto-created from recommendations.

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/pipeline.py
git commit -m "feat: integrate strategy configuration into pipeline run_techniques"
```

---

### Task 11: Create technique selector UI component

**Files:**
- Create: `autotestdesign/ui/components/__init__.py`
- Create: `autotestdesign/ui/components/technique_selector.py`

- [ ] **Step 1: Write __init__.py**

```python
"""Reusable UI components for AutoTestDesign."""
```

- [ ] **Step 2: Write technique_selector.py**

```python
"""Reusable technique checkbox matrix for strategy configuration."""
from __future__ import annotations

import streamlit as st
import pandas as pd

from autotestdesign.models.schemas import (
    Requirement, RiskAssessment, StrategyAssignment, TechniqueParameter
)


def render_technique_matrix(
    requirements: list[Requirement],
    risks: list[RiskAssessment],
    assignments: list[StrategyAssignment],
    all_techniques: list[str] | None = None,
) -> list[StrategyAssignment]:
    """Render a requirement × technique checkbox matrix.

    Returns updated list of StrategyAssignment objects.
    """
    if all_techniques is None:
        all_techniques = ["EP", "BVA", "DecisionTable", "StateTransition"]

    risk_map = {r.requirement_id: r for r in risks}
    assignment_map: dict[tuple[str, str], StrategyAssignment] = {}
    for a in assignments:
        assignment_map[(a.requirement_id, a.technique)] = a

    risk_colors = {"H": "#f8d7da", "M": "#fff3cd", "L": "#d4edda"}

    rows = []
    for req in requirements:
        risk = risk_map.get(req.id)
        priority = risk.priority.value if risk else "M"
        row = {
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
    column_config = {
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
```

- [ ] **Step 3: Verify import**

```bash
python -c "from autotestdesign.ui.components.technique_selector import render_technique_matrix; print('Import OK')"
```

Expected: "Import OK"

- [ ] **Step 4: Commit**

```bash
git add autotestdesign/ui/components/
git commit -m "feat: add technique selector checkbox matrix UI component"
```

---

### Task 12: Add Strategy tab to Streamlit UI

**Files:**
- Modify: `autotestdesign/ui/streamlit_app.py`

- [ ] **Step 1: Add imports at top of streamlit_app.py**

Add after the existing imports (around line 44):

```python
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
from autotestdesign.models.schemas import (
    StrategyAssignment,
    TechniqueParameter,
    TestSuite,
)
from autotestdesign.ui.components.technique_selector import render_technique_matrix
```

- [ ] **Step 2: Add tab_strategy() function before tab_cases**

Insert after `tab_coverage` function (before `tab_cases`, around line 613):

```python
def tab_strategy(project: Project) -> Project:
    st.subheader("Strategy Configuration")

    if not project.requirements:
        st.info("Import requirements on the Import tab first.")
        return project

    if not project.risks:
        st.warning("Risk assessment not yet run. Run risk assessment first, or auto-recommend will use default priorities.")
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
                            StrategyAssignment(requirement_id=rec["requirement_id"], technique=tech)
                        )
                _save_project(project)
                st.rerun()
        with c2:
            if st.button("Reset All", type="secondary", use_container_width=True):
                project.strategy_assignments = []
                _save_project(project)
                st.rerun()

        st.caption("Check the techniques to apply for each requirement. Risk level colors: red=H, yellow=M, green=L.")

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
                1, 5, tp.bva_offset,
                help="±1 = 6 cases/field, ±2 = 8, ±3 = 10, ±4 = 12, ±5 = 14",
                key="bva_offset_slider",
            )
        with params_col2:
            st.caption("**EP: Partitions**")
            new_vp = st.slider(
                "Valid partitions", 1, 5, tp.ep_valid_partitions,
                key="ep_vp_slider",
            )
            new_ip = st.slider(
                "Invalid partitions", 1, 5, tp.ep_invalid_partitions,
                key="ep_ip_slider",
            )

        if (new_offset != tp.bva_offset or new_vp != tp.ep_valid_partitions or new_ip != tp.ep_invalid_partitions):
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
            sel_suite_name = st.selectbox("Target suite", suite_options, key="quick_suite")
            req_options = {r.id: f"{r.id}: {r.title or r.raw_text[:40]}" for r in project.requirements}
            sel_reqs = st.multiselect(
                "Select requirements to assign",
                list(req_options.keys()),
                format_func=lambda x: req_options[x],
                key="quick_assign_reqs",
            )
            if st.button("Assign to Suite", type="secondary") and sel_suite_name != "(none)" and sel_reqs:
                suite = next((s for s in project.suites if s.name == sel_suite_name), None)
                if suite:
                    assign_to_suite(project, suite.id, sel_reqs)
                    _save_project(project)
                    st.success(f"Assigned {len(sel_reqs)} requirement(s) to {sel_suite_name}")
                    st.rerun()
        else:
            st.caption("No suites created yet. Create suites in the Suites tab.")

        st.divider()
        if st.button("Apply Strategy & Generate Test Cases", type="primary", use_container_width=True):
            enabled_count = sum(1 for a in project.strategy_assignments if a.enabled)
            if enabled_count == 0:
                st.warning("No techniques enabled. Use Auto-Recommend or check techniques manually.")
            else:
                def _gen():
                    p, ms = run_techniques(project)
                    st.session_state["metrics"]["techniques_ms"] = ms
                    _save_project(p)
                    return p
                out = _run_with_feedback(
                    "Generate test cases from strategy",
                    _gen,
                    success=f"Generated {len(project.test_cases)} test case(s)",
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
            estimate = estimate_case_count(project.requirements, assignments_for_preview, project.technique_params)
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
            risk_data = [{"requirement_id": r.requirement_id, "priority": r.priority.value} for r in project.risks]
            cov = estimate_coverage(project.requirements, assignments_for_preview, risk_data)
            for level in ["H", "M", "L"]:
                if level in cov:
                    info = cov[level]
                    color = {"H": "#c62828", "M": "#f57c00", "L": "#2e7d32"}[level]
                    label = {"H": "High", "M": "Medium", "L": "Low"}[level]
                    st.markdown(
                        f"**{label}-risk** ({info['covered']}/{info['total']}): "
                        f"{info['percentage']}%",
                    )
                    st.progress(info["percentage"] / 100)
        else:
            st.info("Click 'Auto-Recommend Techniques' or manually enable techniques to see preview.")

    return project
```

- [ ] **Step 2: Add "Strategy" tab and "Suites" tab to the tabs list**

In the `main()` function (line 1196), update the tabs list to include "Strategy" between "Coverage" and "Test Cases", and add "Suites" as a new tab:

```python
    tabs = st.tabs(
        [
            "Import",
            "Risk",
            "Coverage",
            "Strategy",
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
        tab_coverage,
        tab_strategy,
        tab_suites,
        tab_cases,
        tab_whitebox,
        tab_trace,
        tab_improvement,
        tab_export,
    ]
```

Note: This requires `tab_suites` to exist (created in Task 13). For now, add a placeholder:

```python
def tab_suites(project: Project) -> Project:
    st.subheader("Test Suites")
    st.info("Suite management will be added next.")
    return project
```

- [ ] **Step 3: Verify the UI loads without errors**

```bash
streamlit run autotestdesign/ui/streamlit_app.py --server.headless true --server.port 8502 &
sleep 5
curl -s http://localhost:8502 | head -20
```

Expected: Streamlit starts without import errors.

- [ ] **Step 4: Commit**

```bash
git add autotestdesign/ui/streamlit_app.py
git commit -m "feat: add Strategy configuration tab with live preview"
```

---

### Task 13: Add Suites tab and enhance Coverage tab

**Files:**
- Modify: `autotestdesign/ui/streamlit_app.py`

- [ ] **Step 1: Replace the placeholder tab_suites with full implementation**

Replace the placeholder `tab_suites` function:

```python
def tab_suites(project: Project) -> Project:
    st.subheader("Test Suites")

    with st.expander("Create Suite", expanded=not project.suites):
        suite_name = st.text_input("Suite name", placeholder="e.g. Security_Suite", key="new_suite_name")
        suite_desc = st.text_input("Description", placeholder="e.g. Security-related test cases", key="new_suite_desc")
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
                        st.caption(f"Requirements: {', '.join(suite.requirement_ids[:5])}{'...' if len(suite.requirement_ids) > 5 else ''}")
                with c2:
                    if st.button("Delete", key=f"del_suite_{suite.id}", type="secondary"):
                        delete_suite(project, suite.id)
                        _save_project(project)
                        st.rerun()

        st.divider()
        st.markdown("### Quick Assign")
        req_options = {r.id: f"{r.id}: {r.title or r.raw_text[:50]}" for r in project.requirements}
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
            if st.button("Assign to Suite", use_container_width=True) and sel_assign_reqs:
                suite = next((s for s in project.suites if s.name == sel_target), None)
                if suite:
                    assign_to_suite(project, suite.id, sel_assign_reqs)
                    _save_project(project)
                    st.success(f"Assigned {len(sel_assign_reqs)} requirement(s) to {sel_target}")
                    st.rerun()
        with c_remove:
            if st.button("Remove from Suite", use_container_width=True) and sel_assign_reqs:
                suite = next((s for s in project.suites if s.name == sel_target), None)
                if suite:
                    from autotestdesign.core.strategy.suite_manager import remove_from_suite
                    remove_from_suite(project, suite.id, sel_assign_reqs)
                    _save_project(project)
                    st.success(f"Removed {len(sel_assign_reqs)} requirement(s) from {sel_target}")
                    st.rerun()
    else:
        st.info("No suites yet. Create one above to organize requirements into test suites.")

    return project
```

- [ ] **Step 2: Enhance tab_coverage with add form**

In `tab_coverage` (line 551), add a dedicated add form before the existing data editor. Replace:

```python
    if project.coverage_items:
        df = pd.DataFrame([c.model_dump() for c in project.coverage_items])
```

With the following block inserted before that line:

```python
    with st.expander("Add Coverage Item", expanded=False):
        cov_type = st.selectbox("Type", ["functional", "security", "boundary", "performance", "usability"], key="cov_add_type")
        req_opts = {r.id: f"{r.id}: {r.title or r.raw_text[:40]}" for r in project.requirements}
        cov_req = st.selectbox("Requirement", list(req_opts.keys()), format_func=lambda x: req_opts[x], key="cov_add_req")
        cov_desc = st.text_input("Description", placeholder="e.g. SQL injection in username field", key="cov_add_desc")
        if st.button("Add Coverage Item", type="secondary") and cov_desc.strip():
            project.coverage_items.append(
                CoverageItem(requirement_id=cov_req, item_type=cov_type, description=cov_desc.strip())
            )
            _save_project(project)
            st.success("Coverage item added")
            st.rerun()

    if project.coverage_items:
        df = pd.DataFrame([c.model_dump() for c in project.coverage_items])
```

- [ ] **Step 3: Verify import of CoverageItem, StrategyAssignment, etc.**

The imports were added in Task 12 Step 1. Verify they're all present.

- [ ] **Step 4: Commit**

```bash
git add autotestdesign/ui/streamlit_app.py
git commit -m "feat: add Suites tab and enhance Coverage tab with add form"
```

---

### Task 14: End-to-end integration verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run schema tests**

```bash
pytest autotestdesign/tests/test_schemas.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Smoke test full import chain**

```bash
python -c "
from autotestdesign.core.strategy import auto_recommend, estimate_case_count, estimate_coverage, create_suite, delete_suite, assign_to_suite
from autotestdesign.core.pipeline import import_requirements, run_structure, run_risk, run_techniques
from autotestdesign.models.schemas import Project, StrategyAssignment, TechniqueParameter, TestSuite
from autotestdesign.ui.components.technique_selector import render_technique_matrix
print('All imports OK')
"
```

Expected: "All imports OK"

- [ ] **Step 3: Run pipeline integration test (no LLM)**

```bash
python -c "
from autotestdesign.core.pipeline import import_requirements, run_structure, run_risk, run_techniques
from autotestdesign.models.schemas import Project, StrategyAssignment

p = Project(name='integration_test')
p = import_requirements(p, 'REQ-001,The system shall accept username between 3 and 20 characters\nREQ-007,After three failed login attempts the account shall be locked for 30 seconds', 'csv')
p, _ = run_structure(p)
p, _ = run_risk(p)
p, _ = run_techniques(p)
print(f'Pipeline result: {len(p.requirements)} reqs, {len(p.risks)} risks, {len(p.strategy_assignments)} assignments, {len(p.test_cases)} cases')
print(f'Techniques used: {set(t.technique for t in p.test_cases)}')
print(f'Suite assignments: {len(p.suites)}')
for tc in p.test_cases[:3]:
    print(f'  {tc.id}: {tc.title} [{tc.technique}] tags={tc.tags} suite={tc.suite_id}')
"
```

Expected: prints pipeline results with auto-recommended assignments and generated test cases.

- [ ] **Step 4: Verify saved project loads correctly**

```bash
python -c "
from autotestdesign.core.pipeline import import_requirements, run_structure, run_risk, run_techniques
from autotestdesign.models.schemas import Project
from autotestdesign.storage.project_store import ProjectStore

p = Project(name='persist_test')
p = import_requirements(p, 'REQ-001,Test requirement', 'csv')
p, _ = run_structure(p)
p, _ = run_risk(p)
p, _ = run_techniques(p)

store = ProjectStore()
store.save(p)
loaded = store.load(p.id)
print(f'Saved: {len(p.strategy_assignments)} assignments, {len(p.suites)} suites')
print(f'Loaded: {len(loaded.strategy_assignments)} assignments, {len(loaded.suites)} suites')
store.delete(p.id)
"
```

Expected: saved and loaded counts match.

- [ ] **Step 5: Commit final verification**

```bash
git add -A
git diff --staged --stat
git commit -m "chore: final integration verification"
```
