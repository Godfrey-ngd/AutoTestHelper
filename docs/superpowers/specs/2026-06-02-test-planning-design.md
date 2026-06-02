# Test Planning — Design Spec

**Date:** 2026-06-02
**Scope:** Add a Test Planning layer between Risk Assessment and Strategy Configuration

## Overview

Risk Assessment tells you "how risky is each requirement" (H/M/L). But there's no explicit planning step that answers: how much testing effort to allocate, what depth/level of testing per requirement, what execution order, and which phase each belongs to.

Test Planning fills this gap. It runs parallel to Strategy Configuration — Planning answers "how much / what order", Strategy answers "what techniques / what parameters".

## Data Model (`models/schemas.py`)

### New Enum

```python
class TestLevel(str, Enum):
    COMPREHENSIVE = "comprehensive"
    STANDARD = "standard"
    SMOKE = "smoke"
```

### New Model

```python
class TestPlanItem(BaseModel):
    requirement_id: str = ""
    risk_level: str = ""              # H / M / L
    test_level: TestLevel = TestLevel.STANDARD
    effort_pct: float = 0.0           # % of total test effort
    estimated_cases: int = 0
    priority_order: int = 0           # 1 = first to execute
    phase: str = "Phase 2: Functional"
    skip: bool = False
    notes: str = ""
```

### Project Modification

Add to `Project`:
```python
test_plan_items: list[TestPlanItem] = Field(default_factory=list)
```

## Risk → TestLevel Mapping (`recommender_rules.json` extension)

Add to existing JSON:
```json
"test_plan_defaults": {
  "H": {"test_level": "comprehensive", "effort_pct": 50},
  "M": {"test_level": "standard", "effort_pct": 35},
  "L": {"test_level": "smoke", "effort_pct": 15}
},
"test_phases": [
  "Phase 1: Smoke",
  "Phase 2: Functional",
  "Phase 3: Regression"
]
```

## New Module: `core/strategy/test_planner.py`

- `auto_generate_plan(requirements, risks) -> list[TestPlanItem]` — generates a complete plan based on risk data
- `recalculate_effort(items) -> list[TestPlanItem]` — normalizes effort percentages to sum to 100%
- Uses `recommender_rules.json` for default mappings

## UI: `tab_planning` in `streamlit_app.py`

**Position:** Risk → Planning → Strategy

**Left panel:**
- "Auto-Generate Plan" button
- Editable plan matrix (data_editor): Req ID | Risk | Test Level | Effort% | Est.Cases | Priority | Phase | Skip | Notes
- Recalculate button

**Right panel:**
- Summary cards: total reqs, covered vs skipped
- Effort distribution bar chart
- Phase breakdown: cases per phase

## Integration

- Planning and Strategy are parallel/independent
- Both feed into test case generation (pipeline reads both)
- Strategy's auto-recommend can optionally check Planning decisions
- No hard coupling between the two

## Files

| File | Change |
|------|--------|
| `models/schemas.py` | +TestLevel enum, +TestPlanItem model, Project +field |
| `models/__init__.py` | Export TestLevel, TestPlanItem |
| `core/strategy/recommender_rules.json` | +test_plan_defaults, +test_phases |
| `core/strategy/test_planner.py` | New: auto plan generation |
| `core/strategy/__init__.py` | Export test_planner functions |
| `ui/streamlit_app.py` | +tab_planning, adjust tabs order |
