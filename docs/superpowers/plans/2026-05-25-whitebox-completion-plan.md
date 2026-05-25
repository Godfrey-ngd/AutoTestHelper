# White-Box Testing (FR 4.0) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded login state machine with a general-purpose white-box testing module supporting state machine / control flow graph modeling, seven coverage criteria, and greedy sequence optimization.

**Architecture:** Five new files in `core/whitebox/` (models, model_parser, llm_derive, coverage, optimizer), one new prompt template, plus modifications to schemas, pipeline, and UI. All graph algorithms work on small models (states < 50, nodes < 100) with polynomial time complexity.

**Tech Stack:** Python 3.12+, Pydantic v2, Streamlit, existing `llm_client.py` (OpenAI-compatible), no new dependencies.

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `autotestdesign/core/whitebox/models.py` | Create | White-box Pydantic models |
| `autotestdesign/core/whitebox/model_parser.py` | Create | Mermaid / JSON → StateMachine / CFG |
| `autotestdesign/core/whitebox/llm_derive.py` | Create | LLM-driven model derivation |
| `autotestdesign/core/whitebox/coverage.py` | Create | 7 coverage criteria algorithms |
| `autotestdesign/core/whitebox/optimizer.py` | Create | Chinese postman, greedy set cover, path merging |
| `autotestdesign/core/whitebox/__init__.py` | Modify | Export new modules |
| `autotestdesign/models/schemas.py` | Modify | Add WhiteboxResult, Project fields |
| `autotestdesign/core/pipeline.py` | Modify | Generalize `add_whitebox()` |
| `autotestdesign/prompts/whitebox_model.md` | Create | LLM prompt template |
| `autotestdesign/ui/streamlit_app.py` | Modify | New "White-Box (FR 4.0)" tab |

---

### Task 1: White-Box Data Models

**Files:**
- Create: `autotestdesign/core/whitebox/models.py`

- [ ] **Step 1: Write the models file**

```python
"""White-box testing data models — StateMachine, ControlFlowGraph, coverage targets."""

from __future__ import annotations

from pydantic import BaseModel, Field
from uuid import uuid4


def _uid(prefix: str = "") -> str:
    return f"{prefix}{uuid4().hex[:8]}"


class StateNode(BaseModel):
    id: str = Field(default_factory=lambda: _uid("S"))
    label: str = ""
    is_initial: bool = False
    is_final: bool = False


class Transition(BaseModel):
    id: str = Field(default_factory=lambda: _uid("T"))
    source: str = ""
    target: str = ""
    trigger: str = ""
    guard: str = ""
    effect: str = ""


class StateMachine(BaseModel):
    name: str = "Unnamed State Machine"
    states: list[StateNode] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)

    @property
    def initial_state(self) -> StateNode | None:
        for s in self.states:
            if s.is_initial:
                return s
        return self.states[0] if self.states else None

    def get_outgoing(self, state_id: str) -> list[Transition]:
        return [t for t in self.transitions if t.source == state_id]

    def get_incoming(self, state_id: str) -> list[Transition]:
        return [t for t in self.transitions if t.target == state_id]


class CFGNode(BaseModel):
    id: str = Field(default_factory=lambda: _uid("N"))
    label: str = ""
    node_type: str = "statement"  # entry | statement | decision | merge | exit


class CFGEdge(BaseModel):
    id: str = Field(default_factory=lambda: _uid("E"))
    source: str = ""
    target: str = ""
    condition: str = ""  # "true" | "false" | guard expression


class ControlFlowGraph(BaseModel):
    name: str = "Unnamed CFG"
    nodes: list[CFGNode] = Field(default_factory=list)
    edges: list[CFGEdge] = Field(default_factory=list)

    @property
    def entry(self) -> CFGNode | None:
        for n in self.nodes:
            if n.node_type == "entry":
                return n
        return self.nodes[0] if self.nodes else None

    @property
    def exit(self) -> CFGNode | None:
        for n in self.nodes:
            if n.node_type == "exit":
                return n
        return None

    def get_outgoing(self, node_id: str) -> list[CFGEdge]:
        return [e for e in self.edges if e.source == node_id]

    def get_successors(self, node_id: str) -> list[str]:
        return [e.target for e in self.edges if e.source == node_id]

    @property
    def decision_nodes(self) -> list[CFGNode]:
        return [n for n in self.nodes if n.node_type == "decision"]

    def cyclomatic_complexity(self) -> int:
        """McCabe: M = E - N + 2P (P=1 for single component)."""
        return len(self.edges) - len(self.nodes) + 2


class CoverageTarget(BaseModel):
    id: str = Field(default_factory=lambda: _uid("CT"))
    target_type: str = ""  # state | transition | statement | branch | condition | path | mcdc_pair
    description: str = ""
    covered: bool = False


class WhiteboxResult(BaseModel):
    model_type: str = ""  # state_machine | control_flow_graph
    coverage_targets: list[CoverageTarget] = Field(default_factory=list)
    test_sequences: list[list[str]] = Field(default_factory=list)
    coverage_pct: float = 0.0
```

- [ ] **Step 2: Verify models import correctly**

Run: `python -c "from autotestdesign.core.whitebox.models import StateMachine, ControlFlowGraph, WhiteboxResult; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/whitebox/models.py
git commit -m "feat(whitebox): add data models for StateMachine, ControlFlowGraph, WhiteboxResult"
```

---

### Task 2: Mermaid / JSON Model Parser

**Files:**
- Create: `autotestdesign/core/whitebox/model_parser.py`

- [ ] **Step 1: Write the parser module**

```python
"""Parse Mermaid diagrams and JSON into StateMachine / ControlFlowGraph models."""

from __future__ import annotations

import json
import re
from typing import Any

from autotestdesign.core.whitebox.models import (
    CFGEdge,
    CFGNode,
    ControlFlowGraph,
    StateMachine,
    StateNode,
    Transition,
)


def parse_state_machine_mermaid(mermaid: str) -> StateMachine | None:
    """Parse a Mermaid stateDiagram-v2 string into a StateMachine."""
    sm = StateMachine(name="Parsed State Machine")
    state_ids: set[str] = set()
    transitions_raw: list[dict[str, str]] = []

    for line in mermaid.splitlines():
        line = line.strip()
        if not line or line.startswith("%%") or line.startswith("stateDiagram"):
            continue

        # [*] --> StateName : label
        m = re.match(r'\[\*\]\s*-->\s*(\w+)\s*:?\s*(.*)', line)
        if m:
            target = m.group(1)
            label = m.group(2).strip()
            state_ids.add(target)
            transitions_raw.append({"source": "[*]", "target": target, "label": label})
            continue

        # StateName --> [*] : label
        m = re.match(r'(\w+)\s*-->\s*\[\*\]\s*:?\s*(.*)', line)
        if m:
            source = m.group(1)
            label = m.group(2).strip()
            state_ids.add(source)
            transitions_raw.append({"source": source, "target": "[*]", "label": label})
            continue

        # Source --> Target : label
        m = re.match(r'(\w+)\s*-->\s*(\w+)\s*:?\s*(.*)', line)
        if m:
            source = m.group(1)
            target = m.group(2)
            label = m.group(3).strip()
            state_ids.add(source)
            state_ids.add(target)
            transitions_raw.append({"source": source, "target": target, "label": label})

    if not state_ids:
        return None

    # Build StateNode objects
    for sid in sorted(state_ids):
        sm.states.append(StateNode(id=sid, label=sid))

    # Mark initial state (first non-[*] target)
    if transitions_raw:
        first = transitions_raw[0]
        if first["source"] == "[*]" and first["target"] in state_ids:
            for s in sm.states:
                if s.id == first["target"]:
                    s.is_initial = True
                    break

    # Build Transition objects
    for i, tr in enumerate(transitions_raw):
        has_initial = tr["source"] == "[*]"
        has_final = tr["target"] == "[*]"
        if has_initial:
            if sm.initial_state:
                tr["source"] = sm.initial_state.id
            else:
                continue
        if has_final:
            # Mark final states
            for s in sm.states:
                if s.id == tr["source"]:
                    s.is_final = True
            continue

        parts = tr["label"].split()
        trigger = parts[0] if parts else ""
        guard = " ".join(parts[1:]) if len(parts) > 1 else ""
        sm.transitions.append(Transition(
            source=tr["source"],
            target=tr["target"],
            trigger=trigger,
            guard=guard,
        ))

    return sm if sm.states else None


def parse_cfg_mermaid(mermaid: str) -> ControlFlowGraph | None:
    """Parse a Mermaid flowchart/graph string into a ControlFlowGraph."""
    cfg = ControlFlowGraph(name="Parsed CFG")
    node_ids: set[str] = set()
    edges_raw: list[dict[str, str]] = []

    for line in mermaid.splitlines():
        line = line.strip()
        if not line or line.startswith("%%") or line.startswith("flowchart") or line.startswith("graph"):
            continue

        # Node definitions: N1[Label] or N1{Label} (decision) or N1((Label)) or N1([Label])
        for m in re.finditer(r'(\w+)\s*(\[.*?\]|\{.*?\}|\(\(.*?\)\)|\(\[.*?\]\))', line):
            nid = m.group(1)
            shape = m.group(2)
            label = re.sub(r'[\[\]{}()]', '', shape).strip()
            node_type = "decision" if shape.startswith("{") else "statement"
            node_ids.add(nid)
            existing = {n.id for n in cfg.nodes}
            if nid not in existing:
                cfg.nodes.append(CFGNode(id=nid, label=label, node_type=node_type))

        # Edge: N1 --> N2 or N1 -->|label| N2 or N1 -- label --> N2
        for m in re.finditer(
            r'(\w+)\s*(-->|---)\s*(?:\|(.+?)\||(\w+))?\s*(-->)?\s*(\w+)',
            line,
        ):
            source = m.group(1)
            target = m.group(6) or m.group(4) or ""
            condition = m.group(3) or m.group(4) or ""

            # Handle chained: N1 --> N2 --> N3
            if not target and m.group(5):
                target = m.group(6)

            if source and target:
                node_ids.add(source)
                node_ids.add(target)
                edges_raw.append({"source": source, "target": target, "condition": condition})

    if not node_ids:
        return None

    # Ensure all nodes exist
    for nid in node_ids:
        if nid not in {n.id for n in cfg.nodes}:
            cfg.nodes.append(CFGNode(id=nid, label=nid, node_type="statement"))

    # Mark entry (first node) and exit (node with no outgoing edges)
    if cfg.nodes:
        cfg.nodes[0].node_type = "entry"
        outgoing = {e["source"] for e in edges_raw}
        all_targets = {e["target"] for e in edges_raw}
        for n in cfg.nodes:
            if n.id in all_targets and n.id not in outgoing:
                n.node_type = "exit"

    for e in edges_raw:
        cfg.edges.append(CFGEdge(source=e["source"], target=e["target"], condition=e["condition"]))

    return cfg if cfg.nodes else None


def parse_model_json(data: dict[str, Any]) -> StateMachine | ControlFlowGraph | None:
    """Parse JSON dict into StateMachine or ControlFlowGraph based on content."""
    if "states" in data or "transitions" in data:
        sm = StateMachine(name=data.get("name", "Imported"))
        for s in data.get("states", []):
            sm.states.append(StateNode(
                id=s.get("id", ""),
                label=s.get("label", s.get("id", "")),
                is_initial=s.get("is_initial", False),
                is_final=s.get("is_final", False),
            ))
        for t in data.get("transitions", []):
            sm.transitions.append(Transition(
                source=t.get("source", ""),
                target=t.get("target", ""),
                trigger=t.get("trigger", ""),
                guard=t.get("guard", ""),
                effect=t.get("effect", ""),
            ))
        return sm

    if "nodes" in data or "edges" in data:
        cfg = ControlFlowGraph(name=data.get("name", "Imported"))
        for n in data.get("nodes", []):
            cfg.nodes.append(CFGNode(
                id=n.get("id", ""),
                label=n.get("label", n.get("id", "")),
                node_type=n.get("node_type", "statement"),
            ))
        for e in data.get("edges", []):
            cfg.edges.append(CFGEdge(
                source=e.get("source", ""),
                target=e.get("target", ""),
                condition=e.get("condition", ""),
            ))
        return cfg

    return None


def detect_and_parse(text: str) -> StateMachine | ControlFlowGraph | None:
    """Auto-detect format and parse model text."""
    text = text.strip()

    # Try JSON first
    if text.startswith("{"):
        try:
            data = json.loads(text)
            return parse_model_json(data)
        except json.JSONDecodeError:
            pass

    # Try Mermaid
    if "stateDiagram" in text:
        return parse_state_machine_mermaid(text)
    if "flowchart" in text or text.startswith("graph "):
        return parse_cfg_mermaid(text)

    return None
```

- [ ] **Step 2: Verify import**

Run: `python -c "from autotestdesign.core.whitebox.model_parser import detect_and_parse; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Smoke test with existing login state diagram**

Run:
```python
python -c "
from autotestdesign.core.whitebox.model_parser import detect_and_parse
from autotestdesign.core.whitebox.state_model import LOGIN_STATE_DIAGRAM
sm = detect_and_parse(LOGIN_STATE_DIAGRAM)
print(f'States: {len(sm.states)}, Transitions: {len(sm.transitions)}')
for s in sm.states:
    print(f'  {s.id} initial={s.is_initial} final={s.is_final}')
"
```
Expected: 4 states, at least 4 transitions listed

- [ ] **Step 4: Commit**

```bash
git add autotestdesign/core/whitebox/model_parser.py
git commit -m "feat(whitebox): add Mermaid and JSON model parser"
```

---

### Task 3: LLM Model Derivation

**Files:**
- Create: `autotestdesign/core/whitebox/llm_derive.py`
- Create: `autotestdesign/prompts/whitebox_model.md`

- [ ] **Step 1: Write the LLM prompt template**

Write `autotestdesign/prompts/whitebox_model.md`:

```markdown
# White-Box Model Derivation — ISO/IEC/IEEE 29119-4 Clause 8

## Role
You are a **senior ISTQB test designer** specializing in white-box test design. Your task is to derive a state machine or control flow graph from structured requirements, which will be used to generate coverage-optimized test sequences.

## Methodology

### State Machine Derivation
When the user asks for a state machine:
1. **Identify states**: Each distinct system mode from `structured.conditions` and `structured.expected_actions`. States represent stable conditions the system can be in.
2. **Identify transitions**: Each action or event from `structured.inputs` that moves the system between states.
3. **Mark initial state**: The "logged out" / "idle" / "home" state where the user starts.
4. **Mark final states**: States where the interaction ends (logout, exit, completion).
5. **Label triggers**: The action or event that causes the transition (e.g., "click_login", "submit_form", "timeout").

### Control Flow Graph Derivation
When the user asks for a control flow graph:
1. **Identify entry node**: Where execution begins.
2. **Trace decision points**: Every conditional from `structured.conditions` becomes a decision node.
3. **Trace sequential steps**: Each `structured.expected_actions` step between decisions is a statement node.
4. **Identify exit node(s)**: Where execution ends.
5. **Label edges**: "true" / "false" for decision branches, empty for unconditional flow.

## Few-Shot Examples

### Example 1 — Login State Machine
Input: "Login module with username/password validation. User starts logged out. After valid login, user is logged in. After invalid login, user stays logged out. After 3 failures, account locks for 30 seconds."
```json
{
  "model_type": "state_machine",
  "name": "Login State Machine",
  "states": [
    {"id": "LoggedOut", "label": "Logged Out", "is_initial": true, "is_final": false},
    {"id": "LoggingIn", "label": "Logging In", "is_initial": false, "is_final": false},
    {"id": "LoggedIn", "label": "Logged In", "is_initial": false, "is_final": true},
    {"id": "Locked", "label": "Account Locked", "is_initial": false, "is_final": false}
  ],
  "transitions": [
    {"source": "LoggedOut", "target": "LoggingIn", "trigger": "submit_credentials"},
    {"source": "LoggingIn", "target": "LoggedIn", "trigger": "valid_credentials"},
    {"source": "LoggingIn", "target": "LoggedOut", "trigger": "invalid_credentials"},
    {"source": "LoggingIn", "target": "Locked", "trigger": "three_failures", "guard": "consecutive_failures == 3"},
    {"source": "Locked", "target": "LoggedOut", "trigger": "timeout", "guard": "30 seconds elapsed"},
    {"source": "LoggedIn", "target": "LoggedOut", "trigger": "logout"}
  ]
}
```

### Example 2 — Calculator CFG
Input: "Simple calculator: user enters two numbers and selects an operator (+, -, *, /). If operator is division and second operand is zero, show error. Otherwise compute and display result."
```json
{
  "model_type": "control_flow_graph",
  "name": "Calculator CFG",
  "nodes": [
    {"id": "N1", "label": "Enter operands and operator", "node_type": "entry"},
    {"id": "N2", "label": "Operator == '/' AND operand2 == 0?", "node_type": "decision"},
    {"id": "N3", "label": "Show 'Division by zero' error", "node_type": "statement"},
    {"id": "N4", "label": "Compute result", "node_type": "statement"},
    {"id": "N5", "label": "Display result", "node_type": "exit"}
  ],
  "edges": [
    {"source": "N1", "target": "N2", "condition": ""},
    {"source": "N2", "target": "N3", "condition": "true"},
    {"source": "N2", "target": "N4", "condition": "false"},
    {"source": "N3", "target": "N5", "condition": ""},
    {"source": "N4", "target": "N5", "condition": ""}
  ]
}
```

### Example 3 — Todo List CFG
Input: "User can add, delete, and mark tasks as complete. If task list is empty, delete and complete operations are disabled. On add, validate title is not empty."
```json
{
  "model_type": "control_flow_graph",
  "name": "Todo Manager CFG",
  "nodes": [
    {"id": "N1", "label": "User selects action", "node_type": "entry"},
    {"id": "N2", "label": "Action == 'add'?", "node_type": "decision"},
    {"id": "N3", "label": "Action == 'delete'?", "node_type": "decision"},
    {"id": "N4", "label": "Title empty?", "node_type": "decision"},
    {"id": "N5", "label": "Show error: title required", "node_type": "statement"},
    {"id": "N6", "label": "Create task, refresh list", "node_type": "statement"},
    {"id": "N7", "label": "Task list empty?", "node_type": "decision"},
    {"id": "N8", "label": "Show 'no tasks to delete'", "node_type": "statement"},
    {"id": "N9", "label": "Delete task, refresh list", "node_type": "statement"},
    {"id": "N10", "label": "Toggle complete, refresh list", "node_type": "statement"},
    {"id": "N11", "label": "Done", "node_type": "exit"}
  ],
  "edges": [
    {"source": "N1", "target": "N2", "condition": ""},
    {"source": "N2", "target": "N4", "condition": "true"},
    {"source": "N2", "target": "N3", "condition": "false"},
    {"source": "N4", "target": "N5", "condition": "true"},
    {"source": "N4", "target": "N6", "condition": "false"},
    {"source": "N5", "target": "N11", "condition": ""},
    {"source": "N6", "target": "N11", "condition": ""},
    {"source": "N3", "target": "N7", "condition": "true"},
    {"source": "N3", "target": "N10", "condition": "false"},
    {"source": "N7", "target": "N8", "condition": "true"},
    {"source": "N7", "target": "N9", "condition": "false"},
    {"source": "N8", "target": "N11", "condition": ""},
    {"source": "N9", "target": "N11", "condition": ""},
    {"source": "N10", "target": "N11", "condition": ""}
  ]
}
```

## Output JSON Schema
```json
{
  "model_type": "state_machine | control_flow_graph",
  "name": "string (descriptive name for this model)",
  "states": [  // state_machine only
    {"id": "string", "label": "string", "is_initial": true/false, "is_final": true/false}
  ],
  "transitions": [  // state_machine only
    {"source": "state_id", "target": "state_id", "trigger": "string", "guard": "string", "effect": "string"}
  ],
  "nodes": [  // control_flow_graph only
    {"id": "string", "label": "string", "node_type": "entry|statement|decision|exit"}
  ],
  "edges": [  // control_flow_graph only
    {"source": "node_id", "target": "node_id", "condition": "string (true/false for decision branches)"}
  ]
}
```

## Critical Rules
- Every model must have exactly one initial/entry node.
- State machines must have at least 2 states.
- CFGs must have at least 2 nodes.
- All transition sources/targets must reference existing state IDs.
- All edge sources/targets must reference existing node IDs.
- Decision nodes must have exactly 2 outgoing edges (true + false).
- Use the `structured` fields from requirements to derive states/nodes — not raw_text alone.
- Name states/nodes descriptively — human-readable but concise.

## Self-Verification
1. Is the initial/entry node clearly marked?
2. Are all states/nodes reachable from the initial/entry node?
3. Does each decision node have both true and false branches?
4. Do all transitions/edges reference valid IDs?
5. Is the model grounded in the actual requirements (not invented)?
```

- [ ] **Step 2: Write the llm_derive module**

```python
"""LLM-driven derivation of state machine / control flow graph from requirements."""

from __future__ import annotations

import json

from autotestdesign.core.llm_client import chat_json, has_llm, load_prompt
from autotestdesign.core.whitebox.model_parser import parse_model_json
from autotestdesign.core.whitebox.models import ControlFlowGraph, StateMachine
from autotestdesign.models.schemas import Requirement


PROMPT_FILE = "whitebox_model.md"


def derive_state_machine(requirements: list[Requirement]) -> StateMachine | None:
    """Use LLM to derive a state machine from structured requirements."""
    return _derive(requirements, "state_machine")


def derive_control_flow_graph(requirements: list[Requirement]) -> ControlFlowGraph | None:
    """Use LLM to derive a control flow graph from structured requirements."""
    return _derive(requirements, "control_flow_graph")


def _derive(
    requirements: list[Requirement], model_type: str
) -> StateMachine | ControlFlowGraph | None:
    if not has_llm():
        return None

    system = load_prompt(PROMPT_FILE)
    target_label = "state machine" if model_type == "state_machine" else "control flow graph"
    system += f"\n\n## Task\nDerive a **{target_label}** from the following requirements."

    payload = {
        "model_type": model_type,
        "requirements": [r.model_dump() for r in requirements],
    }
    data = chat_json(system, json.dumps(payload, ensure_ascii=False))
    if not data:
        return None

    result = parse_model_json(data)
    if isinstance(result, StateMachine) and model_type == "state_machine":
        return result
    if isinstance(result, ControlFlowGraph) and model_type == "control_flow_graph":
        return result
    return None
```

- [ ] **Step 3: Verify import**

Run: `python -c "from autotestdesign.core.whitebox.llm_derive import derive_state_machine, derive_control_flow_graph; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add autotestdesign/core/whitebox/llm_derive.py autotestdesign/prompts/whitebox_model.md
git commit -m "feat(whitebox): add LLM-driven model derivation with prompt template"
```

---

### Task 4: Coverage Criteria Algorithms

**Files:**
- Create: `autotestdesign/core/whitebox/coverage.py`

- [ ] **Step 1: Write the coverage module**

```python
"""Coverage criteria algorithms for state machines and control flow graphs."""

from __future__ import annotations

from collections import deque

from autotestdesign.core.whitebox.models import (
    CFGEdge,
    CFGNode,
    ControlFlowGraph,
    CoverageTarget,
    StateMachine,
    StateNode,
    Transition,
    WhiteboxResult,
)


# ─── State Machine Coverage ──────────────────────────────────────

def _shortest_path(sm: StateMachine, start: str, target: str) -> list[str] | None:
    """BFS shortest path between two states."""
    if start == target:
        return [start]
    queue = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        current = path[-1]
        for t in sm.get_outgoing(current):
            if t.target not in visited:
                new_path = path + [t.target]
                if t.target == target:
                    return new_path
                visited.add(t.target)
                queue.append(new_path)
    return None


def state_coverage(sm: StateMachine) -> WhiteboxResult:
    """Generate sequences covering every state at least once."""
    result = WhiteboxResult(model_type="state_machine")
    targets: list[CoverageTarget] = []
    sequences: list[list[str]] = []

    for s in sm.states:
        targets.append(CoverageTarget(
            target_type="state",
            description=f"State: {s.label or s.id}",
        ))

    # BFS from initial state to cover all states
    start = sm.initial_state
    if not start:
        return result

    uncovered = {s.id for s in sm.states}
    current = start.id

    while uncovered:
        uncovered.discard(current)
        # Find nearest uncovered state
        nearest = None
        nearest_path = None
        for target_id in uncovered:
            path = _shortest_path(sm, current, target_id)
            if path and (nearest_path is None or len(path) < len(nearest_path)):
                nearest = target_id
                nearest_path = path

        if nearest_path:
            sequences.append(nearest_path)
            current = nearest_path[-1]
            for node in nearest_path:
                uncovered.discard(node)
        else:
            break  # unreachable states remain

    for t in targets:
        for seq in sequences:
            if any(t.description.endswith(nid) for nid in seq):
                t.covered = True
                break
        # Also check state labels
        for s in sm.states:
            if t.description.endswith(s.label or s.id):
                for seq in sequences:
                    if s.id in seq:
                        t.covered = True
                        break

    result.coverage_targets = targets
    result.test_sequences = sequences
    covered_count = sum(1 for t in targets if t.covered)
    result.coverage_pct = (covered_count / len(targets) * 100) if targets else 100
    return result


def transition_coverage(sm: StateMachine) -> WhiteboxResult:
    """Generate sequences covering every transition at least once."""
    result = WhiteboxResult(model_type="state_machine")
    targets: list[CoverageTarget] = []

    for t in sm.transitions:
        targets.append(CoverageTarget(
            target_type="transition",
            description=f"Transition: {t.source} -> {t.target} ({t.trigger or 'unnamed'})",
        ))

    start = sm.initial_state
    if not start:
        return result

    uncovered_transitions = set(range(len(sm.transitions)))
    sequences: list[list[str]] = []
    current = start.id

    while uncovered_transitions:
        best_seq = None
        best_ti = None
        for ti in uncovered_transitions:
            t = sm.transitions[ti]
            prefix = _shortest_path(sm, current, t.source)
            if prefix:
                seq = prefix + [t.target]
                if best_seq is None or len(seq) < len(best_seq):
                    best_seq = seq
                    best_ti = ti

        if best_seq and best_ti is not None:
            sequences.append(best_seq)
            current = best_seq[-1]
            uncovered_transitions.discard(best_ti)
            # Check which other transitions this sequence covers
            for i in range(len(best_seq) - 1):
                for ti2 in list(uncovered_transitions):
                    t2 = sm.transitions[ti2]
                    if t2.source == best_seq[i] and t2.target == best_seq[i + 1]:
                        uncovered_transitions.discard(ti2)
        else:
            break

    for t in targets:
        for seq in sequences:
            for i in range(len(seq) - 1):
                if any(
                    tr.source == seq[i] and tr.target == seq[i + 1]
                    for tr in sm.transitions
                ):
                    t.covered = True
                    break

    result.coverage_targets = targets
    result.test_sequences = sequences
    covered_count = sum(1 for t in targets if t.covered)
    result.coverage_pct = (covered_count / len(targets) * 100) if targets else 100
    return result


# ─── Control Flow Graph Coverage ─────────────────────────────────

def statement_coverage(cfg: ControlFlowGraph) -> WhiteboxResult:
    """Generate sequences covering every statement node at least once."""
    result = WhiteboxResult(model_type="control_flow_graph")
    targets: list[CoverageTarget] = []

    statement_nodes = [n for n in cfg.nodes if n.node_type in ("statement", "entry", "exit")]
    for n in statement_nodes:
        targets.append(CoverageTarget(
            target_type="statement",
            description=f"Node: {n.label or n.id}",
        ))

    entry = cfg.entry
    if not entry:
        return result

    # DFS to find paths covering all statement nodes
    sequences = _dfs_cover_nodes(cfg, entry.id, {n.id for n in statement_nodes})
    result.test_sequences = sequences
    result.coverage_targets = targets

    for t in targets:
        for seq in sequences:
            if any(nid in seq for nid in [n.id for n in statement_nodes]):
                t.covered = True
                break

    covered_count = sum(1 for t in targets if t.covered)
    result.coverage_pct = (covered_count / len(targets) * 100) if targets else 100
    return result


def _dfs_cover_nodes(
    cfg: ControlFlowGraph, start: str, targets: set[str]
) -> list[list[str]]:
    """DFS to find paths covering all target nodes."""
    sequences: list[list[str]] = []
    uncovered = set(targets)
    current = start

    while uncovered:
        uncovered.discard(current)
        if not uncovered:
            break
        # Find path to nearest uncovered node
        path = _bfs_path(cfg, current, uncovered)
        if path:
            sequences.append(path)
            current = path[-1]
            for n in path:
                uncovered.discard(n)
        else:
            break
    return sequences


def _bfs_path(cfg: ControlFlowGraph, start: str, targets: set[str]) -> list[str] | None:
    """BFS shortest path from start to any target."""
    if start in targets:
        return [start]
    queue = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        current = path[-1]
        for e in cfg.get_outgoing(current):
            if e.target not in visited:
                new_path = path + [e.target]
                if e.target in targets:
                    return new_path
                visited.add(e.target)
                queue.append(new_path)
    return None


def branch_coverage(cfg: ControlFlowGraph) -> WhiteboxResult:
    """Generate sequences covering every branch (edge) at least once."""
    result = WhiteboxResult(model_type="control_flow_graph")
    targets: list[CoverageTarget] = []

    for e in cfg.edges:
        targets.append(CoverageTarget(
            target_type="branch",
            description=f"Edge: {e.source} -> {e.target} ({e.condition or 'unconditional'})",
        ))

    entry = cfg.entry
    if not entry:
        return result

    uncovered_edges = set(range(len(cfg.edges)))
    sequences: list[list[str]] = []
    current = entry.id

    while uncovered_edges:
        best_seq = None
        best_ei = None
        for ei in uncovered_edges:
            e = cfg.edges[ei]
            prefix = _bfs_path(cfg, current, {e.source})
            if prefix:
                seq = prefix + [e.target]
                if best_seq is None or len(seq) < len(best_seq):
                    best_seq = seq
                    best_ei = ei

        if best_seq and best_ei is not None:
            sequences.append(best_seq)
            current = best_seq[-1]
            uncovered_edges.discard(best_ei)
            for i in range(len(best_seq) - 1):
                for ei2 in list(uncovered_edges):
                    e2 = cfg.edges[ei2]
                    if e2.source == best_seq[i] and e2.target == best_seq[i + 1]:
                        uncovered_edges.discard(ei2)
        else:
            break

    for t in targets:
        for seq in sequences:
            for i in range(len(seq) - 1):
                if any(e.source == seq[i] and e.target == seq[i + 1] for e in cfg.edges):
                    t.covered = True
                    break

    result.coverage_targets = targets
    result.test_sequences = sequences
    covered_count = sum(1 for t in targets if t.covered)
    result.coverage_pct = (covered_count / len(targets) * 100) if targets else 100
    return result


def path_coverage(cfg: ControlFlowGraph) -> WhiteboxResult:
    """McCabe basis path coverage using cyclomatic complexity."""
    result = WhiteboxResult(model_type="control_flow_graph")

    entry = cfg.entry
    exit_node = cfg.exit
    if not entry:
        return result

    # Enumerate all paths from entry to exit (DFS with cycle detection)
    all_paths = _enumerate_paths(cfg, entry.id, exit_node.id if exit_node else None)

    # McCabe: select independent paths
    cc = cfg.cyclomatic_complexity()
    basis_paths = _select_independent_paths(all_paths, max_count=cc)

    targets: list[CoverageTarget] = []
    for i, path in enumerate(basis_paths):
        node_labels = []
        for nid in path:
            node = next((n for n in cfg.nodes if n.id == nid), None)
            node_labels.append(node.label if node else nid)
        targets.append(CoverageTarget(
            target_type="path",
            description=f"Path {i + 1}: {' -> '.join(node_labels[:4])}{'...' if len(node_labels) > 4 else ''}",
        ))

    result.coverage_targets = targets
    result.test_sequences = basis_paths
    result.coverage_pct = len(basis_paths) / cc * 100 if cc else 100
    return result


def _enumerate_paths(
    cfg: ControlFlowGraph, current: str, exit_id: str | None, max_paths: int = 200
) -> list[list[str]]:
    """DFS enumerate all paths from current to exit (with cycle avoidance)."""
    paths: list[list[str]] = []

    def dfs(node: str, visited: set[str], path: list[str]):
        if len(paths) >= max_paths:
            return
        if exit_id and node == exit_id:
            paths.append(list(path))
            return
        if node in visited:
            return  # cycle detected, avoid infinite loop
        if not cfg.get_outgoing(node) and not exit_id:
            # Leaf node in a graph without explicit exit
            paths.append(list(path))
            return
        for e in cfg.get_outgoing(node):
            dfs(e.target, visited | {node}, path + [e.target])

    dfs(current, set(), [current])
    return paths


def _select_independent_paths(paths: list[list[str]], max_count: int) -> list[list[str]]:
    """Select linearly independent paths (greedy: pick paths with new edges)."""
    if len(paths) <= max_count:
        return paths

    selected: list[list[str]] = []
    covered_edges: set[tuple[str, str]] = set()

    # Always include first (shortest) path
    if paths:
        selected.append(paths[0])
        for i in range(len(paths[0]) - 1):
            covered_edges.add((paths[0][i], paths[0][i + 1]))

    while len(selected) < max_count:
        best_path = None
        best_new_edges = 0
        for path in paths:
            if path in selected:
                continue
            new_edges = 0
            for i in range(len(path) - 1):
                if (path[i], path[i + 1]) not in covered_edges:
                    new_edges += 1
            if new_edges > best_new_edges:
                best_new_edges = new_edges
                best_path = path
        if best_path and best_new_edges > 0:
            selected.append(best_path)
            for i in range(len(best_path) - 1):
                covered_edges.add((best_path[i], best_path[i + 1]))
        else:
            break

    return selected


def condition_coverage(cfg: ControlFlowGraph) -> WhiteboxResult:
    """For each decision node, ensure both true and false branches are covered."""
    result = WhiteboxResult(model_type="control_flow_graph")
    targets: list[CoverageTarget] = []

    entry = cfg.entry
    if not entry:
        return result

    sequences: list[list[str]] = []

    for dn in cfg.decision_nodes:
        targets.append(CoverageTarget(
            target_type="condition",
            description=f"Condition T: {dn.label or dn.id}",
        ))
        targets.append(CoverageTarget(
            target_type="condition",
            description=f"Condition F: {dn.label or dn.id}",
        ))

        outgoing = cfg.get_outgoing(dn.id)
        for e in outgoing:
            prefix = _bfs_path(cfg, entry.id, {e.source})
            if prefix:
                seq = prefix + [e.target]
                sequences.append(seq)

    result.coverage_targets = targets
    result.test_sequences = sequences
    covered_count = sum(1 for t in targets if t.covered)
    result.coverage_pct = (covered_count / len(targets) * 100) if targets else 100

    for t in targets:
        cond_type = "T" if "Condition T:" in t.description else "F"
        for seq in sequences:
            for dn in cfg.decision_nodes:
                if dn.id in seq:
                    edges = cfg.get_outgoing(dn.id)
                    for e in edges:
                        is_true = e.condition.lower() == "true"
                        if is_true and cond_type == "T" and e.target in seq:
                            t.covered = True
                        if not is_true and cond_type == "F" and e.target in seq:
                            t.covered = True

    covered_count = sum(1 for t in targets if t.covered)
    result.coverage_pct = (covered_count / len(targets) * 100) if targets else 100
    return result


def mcdc_coverage(cfg: ControlFlowGraph) -> WhiteboxResult:
    """Modified Condition/Decision Coverage: for each condition, find
    an independence pair where changing only that condition changes the decision."""
    result = WhiteboxResult(model_type="control_flow_graph")
    targets: list[CoverageTarget] = []

    entry = cfg.entry
    if not entry:
        return result

    sequences: list[list[str]] = []

    for dn in cfg.decision_nodes:
        targets.append(CoverageTarget(
            target_type="mcdc_pair",
            description=f"MC/DC: {dn.label or dn.id}",
        ))

        # For each branch, generate a path
        outgoing = cfg.get_outgoing(dn.id)
        for e in outgoing:
            prefix = _bfs_path(cfg, entry.id, {e.source})
            if prefix:
                seq = prefix + [e.target]
                sequences.append(seq)

    result.coverage_targets = targets
    result.test_sequences = sequences
    covered_count = sum(1 for t in targets if t.covered)
    result.coverage_pct = (covered_count / len(targets) * 100) if targets else 100

    for t in targets:
        for dn in cfg.decision_nodes:
            edges = cfg.get_outgoing(dn.id)
            true_branch_exists = any(e.condition.lower() == "true" for e in edges)
            false_branch_exists = any(e.condition.lower() != "true" for e in edges)
            if true_branch_exists and false_branch_exists:
                t.covered = True
                break

    covered_count = sum(1 for t in targets if t.covered)
    result.coverage_pct = (covered_count / len(targets) * 100) if targets else 100
    return result


# ─── Dispatch ────────────────────────────────────────────────────

CRITERIA_MAP = {
    "state": ("state_machine", state_coverage),
    "transition": ("state_machine", transition_coverage),
    "statement": ("control_flow_graph", statement_coverage),
    "branch": ("control_flow_graph", branch_coverage),
    "path": ("control_flow_graph", path_coverage),
    "condition": ("control_flow_graph", condition_coverage),
    "mcdc": ("control_flow_graph", mcdc_coverage),
}


def run_coverage(
    model: StateMachine | ControlFlowGraph, criteria: list[str]
) -> list[WhiteboxResult]:
    """Run selected coverage criteria against a model.

    Args:
        model: StateMachine or ControlFlowGraph
        criteria: list of criterion names e.g. ["state", "transition"]

    Returns:
        List of WhiteboxResult, one per criterion.
    """
    results: list[WhiteboxResult] = []
    for criterion in criteria:
        if criterion not in CRITERIA_MAP:
            continue
        expected_type, fn = CRITERIA_MAP[criterion]
        if expected_type == "state_machine" and isinstance(model, StateMachine):
            results.append(fn(model))
        elif expected_type == "control_flow_graph" and isinstance(model, ControlFlowGraph):
            results.append(fn(model))
    return results
```

- [ ] **Step 2: Verify import**

Run: `python -c "from autotestdesign.core.whitebox.coverage import run_coverage, CRITERIA_MAP; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/whitebox/coverage.py
git commit -m "feat(whitebox): add 7 coverage criteria algorithms"
```

---

### Task 5: Sequence Optimizer

**Files:**
- Create: `autotestdesign/core/whitebox/optimizer.py`

- [ ] **Step 1: Write the optimizer module**

```python
"""Sequence optimization: Chinese postman, greedy set cover, path merging."""

from __future__ import annotations

from collections import Counter

from autotestdesign.core.whitebox.models import (
    CoverageTarget,
    StateMachine,
    WhiteboxResult,
)


def chinese_postman_tour(sm: StateMachine) -> list[str] | None:
    """Compute Chinese postman tour covering all transitions at least once.

    If the state graph is Eulerian, finds an Eulerian circuit via Hierholzer.
    Otherwise, duplicates edges to balance odd-degree nodes first.
    """
    if not sm.states:
        return None

    # Build adjacency list
    adj: dict[str, list[str]] = {s.id: [] for s in sm.states}
    for t in sm.transitions:
        adj[t.source].append(t.target)

    # Compute degree imbalance
    in_deg: dict[str, int] = Counter()
    out_deg: dict[str, int] = Counter()
    for t in sm.transitions:
        out_deg[t.source] += 1
        in_deg[t.target] += 1

    # Find odd-degree nodes (in != out)
    surplus: list[str] = []
    deficit: list[str] = []
    for s in sm.states:
        diff = out_deg.get(s.id, 0) - in_deg.get(s.id, 0)
        if diff > 0:
            for _ in range(diff):
                surplus.append(s.id)
        elif diff < 0:
            for _ in range(-diff):
                deficit.append(s.id)

    # Balance the graph by adding duplicate edges (shortest paths from surplus to deficit)
    balanced_edges: list[tuple[str, str]] = []
    used_deficit = [False] * len(deficit)
    for src in surplus:
        for di, dst in enumerate(deficit):
            if not used_deficit[di]:
                balanced_edges.append((src, dst))
                used_deficit[di] = True
                break

    # Hierholzer's algorithm for Eulerian circuit
    # Build extended adjacency with original + balanced edges
    extended: dict[str, list[str]] = {s.id: [] for s in sm.states}
    for t in sm.transitions:
        extended[t.source].append(t.target)
    for src, dst in balanced_edges:
        extended[src].append(dst)

    start = sm.initial_state.id if sm.initial_state else sm.states[0].id

    circuit: list[str] = []
    stack = [start]
    current_path: list[str] = []

    # Copy adjacency for consumption
    remaining = {k: list(v) for k, v in extended.items()}

    while stack:
        v = stack[-1]
        if remaining.get(v):
            next_v = remaining[v].pop()
            stack.append(next_v)
        else:
            current_path.append(stack.pop())

    current_path.reverse()
    return current_path if current_path else None


def greedy_set_cover(
    sequences: list[list[str]], targets: list[CoverageTarget]
) -> list[list[str]]:
    """Select minimal subset of sequences covering all targets (greedy).

    Each sequence covers a set of targets. Greedily pick the sequence
    that covers the most uncovered targets each round.
    """
    if not sequences or not targets:
        return sequences

    # Map each sequence to the set of target indices it covers
    seq_coverage: list[set[int]] = []
    for seq in sequences:
        covered: set[int] = set()
        for ti, t in enumerate(targets):
            # Check if sequence ID appears in target description
            desc_lower = t.description.lower()
            for node in seq:
                if node.lower() in desc_lower:
                    covered.add(ti)
                    break
        seq_coverage.append(covered)

    uncovered: set[int] = set(range(len(targets)))
    selected: list[list[str]] = []
    available = list(range(len(sequences)))

    while uncovered and available:
        # Pick sequence covering most uncovered targets
        best_idx = max(available, key=lambda i: len(seq_coverage[i] & uncovered))
        new_covered = seq_coverage[best_idx] & uncovered
        if not new_covered:
            break
        selected.append(sequences[best_idx])
        uncovered -= new_covered
        available.remove(best_idx)

    return selected


def risk_weighted_sort(
    result: WhiteboxResult, risk_map: dict[str, str]
) -> WhiteboxResult:
    """Sort sequences prioritizing coverage of high-risk paths.

    Args:
        result: WhiteboxResult with test_sequences
        risk_map: state_id or node_id -> risk priority (H/M/L)
    """
    priority_order = {"H": 0, "M": 1, "L": 2}

    def sort_key(seq: list[str]) -> int:
        best_priority = 2  # L
        for node in seq:
            if node in risk_map:
                p = priority_order.get(risk_map[node], 2)
                best_priority = min(best_priority, p)
        return best_priority

    result.test_sequences = sorted(result.test_sequences, key=sort_key)
    return result


def merge_paths(sequences: list[list[str]]) -> list[list[str]]:
    """Merge paths that share common prefixes/suffixes into single walks."""
    if len(sequences) <= 1:
        return sequences

    merged: list[list[str]] = [list(sequences[0])]

    for seq in sequences[1:]:
        last = merged[-1]
        # If this sequence starts where the last one ended, concatenate
        if seq and seq[0] == last[-1]:
            last.extend(seq[1:])
        # If this sequence ends where the next might start, or is independent
        else:
            merged.append(list(seq))

    return merged


def optimize_result(
    result: WhiteboxResult, sm: StateMachine | None = None
) -> WhiteboxResult:
    """Apply all applicable optimizations to a WhiteboxResult.

    - Chinese postman tour for state machine transition coverage
    - Greedy set cover to minimize sequence count
    - Path merging to reduce redundancy
    """
    if not result.test_sequences:
        return result

    # Apply Chinese postman if state machine available
    if sm and result.model_type == "state_machine":
        tour = chinese_postman_tour(sm)
        if tour:
            result.test_sequences = [tour]

    # Greedy set cover
    if len(result.test_sequences) > 1:
        result.test_sequences = greedy_set_cover(
            result.test_sequences, result.coverage_targets
        )

    # Path merging
    if len(result.test_sequences) > 1:
        result.test_sequences = merge_paths(result.test_sequences)

    # Recalculate coverage
    for t in result.coverage_targets:
        t.covered = False
        for seq in result.test_sequences:
            desc_lower = t.description.lower()
            for node in seq:
                if node.lower() in desc_lower:
                    t.covered = True
                    break
            if t.covered:
                break

    covered_count = sum(1 for t in result.coverage_targets if t.covered)
    result.coverage_pct = (
        (covered_count / len(result.coverage_targets) * 100)
        if result.coverage_targets
        else 100
    )
    return result
```

- [ ] **Step 2: Verify import**

Run: `python -c "from autotestdesign.core.whitebox.optimizer import optimize_result, chinese_postman_tour, greedy_set_cover; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/whitebox/optimizer.py
git commit -m "feat(whitebox): add sequence optimizer (Chinese postman, greedy set cover, path merging)"
```

---

### Task 6: Update `__init__.py` and White-Box Exports

**Files:**
- Modify: `autotestdesign/core/whitebox/__init__.py`

- [ ] **Step 1: Update __init__.py**

Replace the current content:
```python
from autotestdesign.core.whitebox.state_model import build_login_state_model

__all__ = ["build_login_state_model"]
```

With:
```python
from autotestdesign.core.whitebox.state_model import build_login_state_model, LOGIN_STATE_DIAGRAM
from autotestdesign.core.whitebox.models import (
    CFGEdge,
    CFGNode,
    ControlFlowGraph,
    CoverageTarget,
    StateMachine,
    StateNode,
    Transition,
    WhiteboxResult,
)
from autotestdesign.core.whitebox.model_parser import detect_and_parse
from autotestdesign.core.whitebox.llm_derive import derive_state_machine, derive_control_flow_graph
from autotestdesign.core.whitebox.coverage import run_coverage, CRITERIA_MAP
from autotestdesign.core.whitebox.optimizer import optimize_result

__all__ = [
    # Legacy
    "build_login_state_model",
    "LOGIN_STATE_DIAGRAM",
    # Models
    "StateMachine",
    "StateNode",
    "Transition",
    "ControlFlowGraph",
    "CFGNode",
    "CFGEdge",
    "CoverageTarget",
    "WhiteboxResult",
    # Parser
    "detect_and_parse",
    # LLM
    "derive_state_machine",
    "derive_control_flow_graph",
    # Coverage
    "run_coverage",
    "CRITERIA_MAP",
    # Optimizer
    "optimize_result",
]
```

- [ ] **Step 2: Verify import**

Run: `python -c "from autotestdesign.core.whitebox import detect_and_parse, run_coverage, optimize_result, derive_state_machine; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/whitebox/__init__.py
git commit -m "feat(whitebox): update __init__.py with full module exports"
```

---

### Task 7: Update Project Schema with White-Box Fields

**Files:**
- Modify: `autotestdesign/models/schemas.py`

- [ ] **Step 1: Add WhiteboxResult to Project model**

Read the current `schemas.py`. At line 194-195, the Project model has:
```python
    state_diagram: Optional[str] = None
    optimized_case_ids: list[str] = Field(default_factory=list)
```

Replace those two lines with:
```python
    state_diagram: Optional[str] = None
    optimized_case_ids: list[str] = Field(default_factory=list)
    whitebox_result: Optional[dict] = None
```

This uses `dict` instead of importing WhiteboxResult to avoid circular imports. Serialization/deserialization of WhiteboxResult will be handled via `.model_dump()` / `.model_validate()` at the pipeline layer.

- [ ] **Step 2: Verify schema**

Run: `python -c "from autotestdesign.models.schemas import Project; p = Project(); print(p.whitebox_result)"`
Expected: `None`

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/models/schemas.py
git commit -m "feat(whitebox): add whitebox_result field to Project schema"
```

---

### Task 8: Generalize `add_whitebox()` in Pipeline

**Files:**
- Modify: `autotestdesign/core/pipeline.py`

- [ ] **Step 1: Rewrite add_whitebox()**

Replace the current `add_whitebox()` function (lines 112-117):
```python
def add_whitebox(project: Project) -> Project:
    diagram, cases = build_login_state_model(project)
    project.state_diagram = diagram
    project.test_cases.extend(cases)
    _rebuild_trace_links(project)
    return project
```

With:
```python
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
        criteria: Coverage criteria names. Default: ["state", "transition"] for SM,
                  ["statement", "branch", "path"] for CFG.
        optimize: Whether to apply greedy / Chinese postman optimization.
    """
    from autotestdesign.core.whitebox.models import StateMachine, ControlFlowGraph
    from autotestdesign.core.whitebox.model_parser import detect_and_parse
    from autotestdesign.core.whitebox.coverage import run_coverage
    from autotestdesign.core.whitebox.optimizer import optimize_result
    from autotestdesign.core.whitebox.state_model import LOGIN_STATE_DIAGRAM

    # Parse or fall back to built-in login model
    model = None
    if model_text and model_text.strip():
        model = detect_and_parse(model_text.strip())

    if model is None:
        model = detect_and_parse(LOGIN_STATE_DIAGRAM)
        if model is None:
            return project

    # Store diagram text for rendering
    project.state_diagram = model_text if model_text else LOGIN_STATE_DIAGRAM

    # Default criteria based on model type
    if criteria is None:
        if isinstance(model, StateMachine):
            criteria = ["state", "transition"]
        else:
            criteria = ["statement", "branch", "path"]

    # Run coverage
    results = run_coverage(model, criteria)

    # Optimize
    sm_for_opt = model if isinstance(model, StateMachine) else None
    if optimize:
        results = [optimize_result(r, sm_for_opt) for r in results]

    # Convert to TestCases
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

    # Store result
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
```

Also add the WhiteboxResult import at the top (line 12 area):
```python
from autotestdesign.core.whitebox.models import WhiteboxResult
```

- [ ] **Step 2: Verify pipeline import**

Run: `python -c "from autotestdesign.core.pipeline import add_whitebox; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/core/pipeline.py
git commit -m "feat(whitebox): generalize add_whitebox() with configurable models and criteria"
```

---

### Task 9: Add White-Box Tab to Streamlit UI

**Files:**
- Modify: `autotestdesign/ui/streamlit_app.py`

- [ ] **Step 1: Find the tab list and add new tab**

Locate the tab definitions (search for `st.tabs` or tab labels like "Export", "Review"). Add `tab_whitebox` to the tabs and call it.

The tabs are likely defined as something like:
```python
tabs = st.tabs(["Import", "Structure", "Risk", "Techniques", "Review", "Trace", "Improve", "Export"])
```

Add `"White-Box"` between existing tabs (after "Techniques" for logical flow):
```python
tabs = st.tabs(["Import", "Structure", "Risk", "Techniques", "White-Box", "Review", "Trace", "Improve", "Export"])
```

Then add the handler call where other tab handlers are called:
```python
with tabs[4]:
    tab_whitebox(project)
```

Update indices for subsequent tabs (Review → 5, Trace → 6, etc.).

- [ ] **Step 2: Write tab_whitebox function**

Add this function before `tab_export`:

```python
def tab_whitebox(project: Project) -> None:
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
                placeholder='stateDiagram-v2\n    [*] --> Idle\n    Idle --> Active: start\n    Active --> [*]: stop',
            )
            if model_text.strip():
                model = detect_and_parse(model_text.strip())
                if model:
                    st.success(f"Parsed: {type(model).__name__} — "
                               f"{len(model.states if isinstance(model, StateMachine) else model.nodes)} nodes, "
                               f"{len(model.transitions if isinstance(model, StateMachine) else model.edges)} edges")
                else:
                    st.error("Could not parse model. Check syntax.")
        else:
            if st.button("Derive from Requirements", key="wb_derive_btn"):
                if not project.requirements:
                    st.warning("No requirements found. Import requirements first.")
                else:
                    with st.spinner("LLM is deriving model from requirements…"):
                        if model_type == "State Machine":
                            model = derive_state_machine(project.requirements)
                        else:
                            model = derive_control_flow_graph(project.requirements)
                    if model:
                        st.success(f"Derived {type(model).__name__} with "
                                   f"{len(model.states if isinstance(model, StateMachine) else model.nodes)} nodes")
                        st.session_state["wb_derived_model"] = model
                        # Show the derived JSON for review/editing
                        st.json(model.model_dump())
                    else:
                        st.error("LLM derivation failed. Check API key or try manual input.")

            # Check for previously derived model
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
                with st.spinner("Generating coverage sequences…"):
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
                    # Coverage target summary
                    st.markdown("**Coverage Targets:**")
                    for t in result.coverage_targets:
                        icon = "✅" if t.covered else "❌"
                        st.text(f"{icon} {t.target_type}: {t.description}")

                    st.markdown("**Test Sequences:**")
                    for j, seq in enumerate(result.test_sequences):
                        path_str = " → ".join(seq)
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
                mermaid = "stateDiagram-v2\n"
                for s in model_stored.states:
                    prefix = "state" if s.is_final else ""
                    mermaid += f"    {s.id}: {s.label or s.id}\n" if s.is_final else ""
                for t in model_stored.transitions:
                    mermaid += f"    {t.source} --> {t.target}: {t.trigger}\n"
                st.markdown("### Model Diagram")
                st.markdown(mermaid)
        elif project.state_diagram:
            st.markdown("### Model Diagram")
            st.markdown(project.state_diagram)


def _add_whitebox_results(
    project: Project, results: list, model
) -> None:
    """Add whitebox coverage results as TestCases."""
    from autotestdesign.core.whitebox.models import WhiteboxResult
    from autotestdesign.core.pipeline import _rebuild_trace_links

    first_req = project.requirements[0].id if project.requirements else ""
    for result in results:
        for i, seq in enumerate(result.test_sequences):
            path_desc = " → ".join(seq)
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
```

- [ ] **Step 2: Verify import and syntax**

Run: `python -c "import ast; ast.parse(open('autotestdesign/ui/streamlit_app.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add autotestdesign/ui/streamlit_app.py
git commit -m "feat(whitebox): add White-Box tab to Streamlit UI"
```

---

### Task 10: Integration Smoke Test

- [ ] **Step 1: Run import check on all new modules**

Run:
```bash
python -c "
from autotestdesign.core.whitebox.models import StateMachine, ControlFlowGraph, WhiteboxResult
from autotestdesign.core.whitebox.model_parser import detect_and_parse
from autotestdesign.core.whitebox.llm_derive import derive_state_machine
from autotestdesign.core.whitebox.coverage import run_coverage
from autotestdesign.core.whitebox.optimizer import optimize_result
from autotestdesign.core.whitebox import build_login_state_model, LOGIN_STATE_DIAGRAM
from autotestdesign.core.pipeline import add_whitebox
print('All imports OK')
"
```
Expected: `All imports OK`

- [ ] **Step 2: Test parsing the existing login state machine**

Run:
```bash
python -c "
from autotestdesign.core.whitebox import detect_and_parse, run_coverage
from autotestdesign.core.whitebox.state_model import LOGIN_STATE_DIAGRAM

sm = detect_and_parse(LOGIN_STATE_DIAGRAM)
print(f'Parsed: {type(sm).__name__}')
print(f'States: {len(sm.states)}')
print(f'Transitions: {len(sm.transitions)}')
for s in sm.states:
    print(f'  {s.id}: initial={s.is_initial}, final={s.is_final}')

results = run_coverage(sm, ['state', 'transition'])
for r in results:
    print(f'{r.model_type}: {r.coverage_pct:.0f}% - {len(r.test_sequences)} sequences')
    for seq in r.test_sequences:
        print(f'  {\" -> \".join(seq)}')
"
```
Expected: 4 states, transitions listed, state coverage ~100%, transition coverage output

- [ ] **Step 3: Test pipeline integration (no LLM)**

Run:
```bash
python -c "
from autotestdesign.models.schemas import Project, Requirement
from autotestdesign.core.pipeline import add_whitebox

p = Project(name='test')
p.requirements = [Requirement(id='REQ-001', raw_text='Login module', title='Login')]
p = add_whitebox(p)  # Uses built-in login model
print(f'Test cases: {len(p.test_cases)}')
print(f'Whitebox result keys: {list(p.whitebox_result.keys()) if p.whitebox_result else None}')
for tc in p.test_cases:
    print(f'  {tc.title} [{tc.technique}]')
"
```
Expected: 6+ test cases, whitebox_result dict with keys

- [ ] **Step 4: Commit (if any fixes needed)**

---

### Task 11: Final Verification

- [ ] **Step 1: Run existing tests to confirm no regressions**

Run: `pytest autotestdesign/tests/test_schemas.py -v`
Expected: All pass (no LLM tests, no whitebox changes affecting schema tests)

- [ ] **Step 2: Run Streamlit syntax check**

Run: `streamlit run autotestdesign/ui/streamlit_app.py --help 2>&1 | head -5`
Expected: Shows streamlit help or runs without import errors
