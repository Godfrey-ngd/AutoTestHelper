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
