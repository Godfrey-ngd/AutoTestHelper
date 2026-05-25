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
        # Strip shape annotations so A[Start] --> B{Decision} → A --> B
        stripped = re.sub(r'[\[\(\{].*?[\]\)\}]', '', line)
        for m in re.finditer(
            r'(\w+)\s*(-->|---)\s*(?:\|(.+?)\||(\w+))?\s*(-->)?\s*(\w+)',
            stripped,
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

    # Mark entry (node with no incoming edges) and exit (node with no outgoing edges)
    if cfg.nodes:
        outgoing = {e["source"] for e in edges_raw}
        all_targets = {e["target"] for e in edges_raw}
        # Entry: node that has outgoing but no incoming edges
        for n in cfg.nodes:
            if n.id in outgoing and n.id not in all_targets:
                n.node_type = "entry"
                break
        else:
            # Fallback: first node
            cfg.nodes[0].node_type = "entry"
        # Exit: node that has incoming but no outgoing edges
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
