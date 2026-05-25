# White-Box Testing (FR 4.0) — Design Spec

**Date:** 2026-05-25
**Status:** Approved
**Scope:** Complete white-box testing module for AutoTestDesign

## 1. Goal

Replace the hardcoded login state machine in `core/whitebox/state_model.py` with a general-purpose white-box testing module that supports:
- User-defined state machines and control flow graphs (Mermaid, JSON, or manual form input)
- LLM auto-derivation of models from structured requirements
- Seven coverage criteria with test sequence generation
- Graph-based + greedy optimization for minimal test suites
- Independent UI tab for interactive modeling

## 2. Architecture

```
autotestdesign/core/whitebox/
├── __init__.py          # Public API re-exports
├── models.py            # StateMachine, ControlFlowGraph, CoverageTarget, WhiteboxResult
├── model_parser.py      # Parse Mermaid stateDiagram / flowchart / JSON → internal models
├── llm_derive.py        # LLM prompt + parse → derive models from requirements
├── coverage.py          # Coverage criteria: state, transition, statement, branch, path, condition, MC/DC
├── optimizer.py         # Sequence optimization: Chinese postman, greedy set cover
└── state_model.py       # Kept as built-in example (existing hardcoded login model)

autotestdesign/prompts/
└── whitebox_model.md    # LLM prompt for model derivation

Modified files:
├── models/schemas.py    # New Pydantic models + Project fields
├── core/pipeline.py     # Generalized add_whitebox()
└── ui/streamlit_app.py  # New "White-Box (FR 4.0)" tab
```

## 3. Data Models

### StateMachine
- `name: str`
- `states: list[StateNode]` — `id`, `label`, `is_initial`, `is_final`
- `transitions: list[Transition]` — `id`, `source`, `target`, `trigger`, `guard`, `effect`

### ControlFlowGraph
- `name: str`
- `nodes: list[CFGNode]` — `id`, `label`, `node_type` (entry/statement/decision/merge/exit)
- `edges: list[CFGEdge]` — `id`, `source`, `target`, `condition` (true/false/guard)

### CoverageTarget
- `id`, `target_type`, `description`, `covered: bool`

### WhiteboxResult
- `model_type: str` — "state_machine" | "control_flow_graph"
- `coverage_targets: list[CoverageTarget]`
- `test_sequences: list[list[str]]` — ordered node/state ID sequences
- `test_cases: list[TestCase]` — existing TestCase format, technique = "StateTransition" or "ControlFlowPath"

### Project additions
- `state_machine: Optional[StateMachine] = None`
- `control_flow_graph: Optional[ControlFlowGraph] = None`
- `whitebox_result: Optional[WhiteboxResult] = None`

## 4. Coverage Criteria

| Criterion | Algorithm | Input Model |
|-----------|-----------|-------------|
| State coverage | BFS shortest paths to visit every state | StateMachine |
| Transition coverage | Chinese postman tour (balance odd-degree nodes, find Eulerian circuit) | StateMachine |
| Statement coverage | DFS all CFGNode (non-merge) | ControlFlowGraph |
| Branch coverage | Enumerate all CFGEdge per decision node (true + false) | ControlFlowGraph |
| Path coverage | McCabe basis path: cyclomatic complexity = E-N+2, pick independent paths | ControlFlowGraph |
| Condition coverage | For each decision node's condition, derive T/F inputs | ControlFlowGraph |
| MC/DC | Pairwise independence: for each condition, find a pair where flipping it flips the decision | ControlFlowGraph |

## 5. Optimization

1. **Chinese postman** — For transition coverage on state machine. If the graph is not Eulerian, add duplicate edges to balance odd-degree nodes, then find Eulerian circuit.
2. **Path merging** — For CFG path coverage, merge paths sharing common prefixes/suffixes into a single walk.
3. **Greedy set cover** — Select sequences covering the most uncovered targets first, repeat until all targets covered.
4. **Risk-weighted sort** — Order final test cases by risk score (high priority first).

## 6. Module Input / Output

### Input paths
- **Manual Mermaid**: User pastes `stateDiagram-v2` or `flowchart` / `graph` in the UI text area
- **Manual JSON**: User provides structured JSON conforming to StateMachine or ControlFlowGraph schema
- **LLM derive**: User clicks "Derive from requirements" — LLM receives structured requirements + whitebox_model.md prompt, returns JSON model

### Output
- `WhiteboxResult` containing coverage targets and test sequences
- Test sequences converted to `TestCase` objects with `technique="StateTransition"` or `technique="ControlFlowPath"`, appended to `project.test_cases`
- Coverage statistics (e.g., "8/8 states covered, 12/12 transitions covered, 95% path coverage")
- Mermaid diagram rendered inline for visual inspection

## 7. UI Layout (New Tab: "White-Box (FR 4.0)")

Three-column layout:

**Left — Model Input**
- Radio: State Machine / Control Flow Graph
- Radio: Manual Input / LLM Derive
- Conditional: Mermaid editor (textarea) or "Derive from Requirements" button
- Preview: rendered Mermaid diagram
- "Confirm Model" button → parses and stores model

**Center — Coverage & Generation**
- Multi-select: coverage criteria (State/Transition/Branch/Path/Condition/MC/DC)
- Checkbox: apply greedy optimization
- "Generate Coverage Sequences" button
- Progress spinner during generation

**Right — Results**
- Coverage summary metrics
- Table: test sequences (Sequence #, Path, Coverage achieved, Priority)
- Mermaid rendering of covered paths if applicable
- "Add to Test Suite" button → appends TestCases to project

## 8. Prompt Design (`whitebox_model.md`)

Follows existing prompt pattern (Role → Methodology → Few-shot → Schema → Rules → Self-check):
- **Role**: Senior ISTQB white-box test designer
- **Input**: Structured requirements (inputs, data_ranges, conditions, expected_actions)
- **Output**: JSON with either StateMachine or ControlFlowGraph
- **Few-shot examples**: Login state machine (existing), Calculator CFG (addition flow with conditionals), Todo list CFG (CRUD with branches)
- **Self-verification**: states are reachable, transitions have triggers, CFG has single entry/exit, all decision nodes have both branches

## 9. Backward Compatibility

- Keep `state_model.py` and `build_login_state_model()` as a built-in example
- `add_whitebox()` gains optional parameters: `state_machine`, `cfg`, `criteria`, `optimize`
- No breaking changes to existing API

## 10. Testing Strategy

- Unit tests for each coverage algorithm (in-memory, no LLM)
- Unit tests for model_parser (Mermaid → StateMachine, Mermaid → CFG, JSON → models)
- Unit tests for optimizer (known graphs with known optimal solutions)
- Smoke test for llm_derive (only when LLM is available)
- No pipeline test changes needed (white-box is not in run_full_pipeline)

## 11. Performance

- All graph algorithms operate on small graphs (states < 50, nodes < 100), so polynomial and even exponential algorithms (like path enumeration for MC/DC) are fine
- LLM derivation is a single API call per model type, comparable to existing technique prompts
- No real-time constraints beyond existing <2s target for non-LLM paths
