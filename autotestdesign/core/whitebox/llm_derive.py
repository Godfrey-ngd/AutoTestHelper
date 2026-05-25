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
