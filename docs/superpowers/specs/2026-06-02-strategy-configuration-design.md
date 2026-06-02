# Strategy Configuration — Design Spec

**Date:** 2026-06-02
**Scope:** Add user-controlled test strategy configuration before test case generation

## Overview

The current pipeline auto-generates test cases using all three black-box techniques (EP, BVA, DecisionTable) immediately after risk assessment. Users have no control over which techniques to apply, with what parameters, or how to organize the output.

This spec adds a **Strategy Configuration** step between Risk Assessment and Test Case Generation, giving users control over technique selection, parameter tuning, suite organization, and preview before generation.

## Priority Order

| Priority | Feature | Rationale |
|----------|---------|-----------|
| P1 | F2.2 Technique Mapping + Confirm Button | Core: without this there is no "strategy configuration" |
| P2 | F2.4 Strategy Preview + F2.1 Coverage Enhancements | Validates strategy before generation |
| P3 | F2.3 Test Suite Grouping + Tags | Organizes output, lower urgency |
| Deferred | Drag-drop, card view, undo/redo | UX polish, not blocking core flow |

## Data Model Changes (`models/schemas.py`)

### New Models

```python
class TechniqueParameter(BaseModel):
    bva_offset: int = Field(default=1, ge=1, le=5)
    ep_valid_partitions: int = Field(default=1, ge=1, le=5)
    ep_invalid_partitions: int = Field(default=2, ge=1, le=5)

class StrategyAssignment(BaseModel):
    id: str  # SA-xxxxxxxx
    requirement_id: str
    technique: str  # "EP" | "BVA" | "DecisionTable" | "StateTransition"
    enabled: bool = True
    params: TechniqueParameter = Field(default_factory=TechniqueParameter)

class TestSuite(BaseModel):
    id: str  # TS-xxxxxxxx
    name: str = ""
    description: str = ""
    requirement_ids: list[str] = Field(default_factory=list)
    priority: int = 0
```

### Modified Models

- `TestCase`: add `tags: list[str]`, `suite_id: str`
- `Project`: add `strategy_assignments: list[StrategyAssignment]`, `suites: list[TestSuite]`, `technique_params: TechniqueParameter`

## New Modules

### `core/strategy/recommender.py`
- Loads rules from `recommender_rules.json` (editable JSON config)
- `recommend_for_risk(priority: Priority) -> list[str]`
- `recommend_for_requirement(req, risk) -> list[str]`
- Rule format: `{"risk": "H", "techniques": ["DecisionTable", "BVA"], "reason": "..."}`

### `core/strategy/preview.py`
- `estimate_case_count(requirements, assignments, params) -> dict` — rule-based, no LLM
  - EP: `(valid_partitions + invalid_partitions)` per req
  - BVA: `(offset * 2 + 2)` per boundary field
  - DT: `2^n` (n=conditions, capped)
- `estimate_coverage(requirements, assignments) -> dict` — per-risk-level coverage %

### `core/strategy/suite_manager.py`
- `create_suite(project, name, description, req_ids) -> TestSuite`
- `update_suite(project, suite_id, **kwargs) -> TestSuite`
- `delete_suite(project, suite_id) -> None`
- `assign_to_suite(project, suite_id, req_ids) -> None`
- `reorder_suites(project, ordered_ids) -> None`

## Modified Modules

### `core/techniques/boundary_value.py`
- `generate()` accepts `offset: int = 1`
- offset=1: 6 cases per field; offset=2: 8 cases per field, etc.

### `core/techniques/equivalence_partitioning.py`
- `generate()` accepts `valid_partitions: int = 1`, `invalid_partitions: int = 2`

### `core/techniques/base.py`
- `generate_all_techniques()` accepts `assignments: list[StrategyAssignment]`, `params: TechniqueParameter`
- Only runs enabled techniques for requirements specified in assignments

### `core/pipeline.py`
- `run_techniques()` reads `project.strategy_assignments` and `project.technique_params`
- Backward compatible: if no assignments, auto-recommends and runs all three techniques
- Calls `_apply_suite_assignments()` to sync suite_id to test cases

### `core/review.py`
- Extend `log_review()` to record strategy assignment changes

## UI Changes (`ui/streamlit_app.py`)

### New Tabs

**Strategy tab** — Two-column layout:
- Left panel:
  - "Auto-Recommend" button (calls recommender engine)
  - Requirement-Technique checkbox matrix (rows=requirements, columns=techniques, color-coded by risk)
  - BVA offset slider (±1 to ±5)
  - EP valid/invalid partition sliders
  - Suite quick-assign section
  - "Apply Strategy & Generate Test Cases" confirm button
- Right panel (live preview):
  - Estimated total test case count (big number)
  - Breakdown by technique
  - Coverage estimation progress bars by risk level (H/M/L)

**Suites tab**:
- Create suite form (name, description)
- Suite card list with requirement counts, edit/delete buttons
- Quick-assign: multi-select requirements → target suite → assign

### Enhanced Tab

**Coverage tab** — Add dedicated add form above existing data editor:
- Type dropdown (functional/security/boundary/performance/usability)
- Requirement selector
- Description input
- "Add" button
- Tag management bar (predefined tags + free input)

## Implementation File List

### New files
| File | Purpose |
|------|---------|
| `core/strategy/__init__.py` | Strategy subpackage |
| `core/strategy/recommender.py` | Risk→technique recommendation |
| `core/strategy/preview.py` | Estimation engine |
| `core/strategy/suite_manager.py` | Suite CRUD |
| `core/strategy/recommender_rules.json` | Configurable rules |
| `ui/components/__init__.py` | UI components package |
| `ui/components/technique_selector.py` | Reusable technique checkbox matrix |

### Modified files
| File | Changes |
|------|---------|
| `models/schemas.py` | +3 models, modify TestCase + Project |
| `core/pipeline.py` | run_techniques accepts strategy config |
| `core/techniques/base.py` | Selective technique generation |
| `core/techniques/boundary_value.py` | Accept offset parameter |
| `core/techniques/equivalence_partitioning.py` | Accept partition parameters |
| `ui/streamlit_app.py` | New Strategy/Suites tabs, enhanced Coverage tab |
| `core/review.py` | Extended logging |

## Backward Compatibility

- If `project.strategy_assignments` is empty, the pipeline auto-recommends using the JSON rules and runs all recommended techniques — same behavior as today (all three techniques)
- If no `TechniqueParameter` is set, defaults apply (offset=1, valid_partitions=1, invalid_partitions=2) — same output as today
- Existing saved projects load and work without migration
