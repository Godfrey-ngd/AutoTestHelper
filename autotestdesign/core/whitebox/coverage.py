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

    start = sm.initial_state
    if not start:
        return result

    uncovered = {s.id for s in sm.states}
    current = start.id

    while uncovered:
        uncovered.discard(current)
        # Find nearest uncovered state
        nearest_path = None
        for target_id in uncovered:
            path = _shortest_path(sm, current, target_id)
            if path and (nearest_path is None or len(path) < len(nearest_path)):
                nearest_path = path

        if nearest_path:
            sequences.append(nearest_path)
            current = nearest_path[-1]
            for node in nearest_path:
                uncovered.discard(node)
        else:
            break

    # Mark coverage
    for t in targets:
        for s in sm.states:
            if t.description.endswith(s.label or s.id):
                for seq in sequences:
                    if s.id in seq:
                        t.covered = True
                        break
                if t.covered:
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

def _bfs_path(cfg: ControlFlowGraph, start: str, targets: set[str]) -> list[str] | None:
    """BFS shortest path from start to any target node."""
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

    sequences: list[list[str]] = []
    uncovered = {n.id for n in statement_nodes}
    current = entry.id

    while uncovered:
        uncovered.discard(current)
        if not uncovered:
            break
        path = _bfs_path(cfg, current, uncovered)
        if path:
            sequences.append(path)
            current = path[-1]
            for n in path:
                uncovered.discard(n)
        else:
            break

    result.test_sequences = sequences
    result.coverage_targets = targets
    for t in targets:
        for seq in sequences:
            if any(n.id in seq for n in statement_nodes if t.description.endswith(n.label or n.id)):
                t.covered = True
                break

    covered_count = sum(1 for t in targets if t.covered)
    result.coverage_pct = (covered_count / len(targets) * 100) if targets else 100
    return result


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
            if t.covered:
                break

    result.coverage_targets = targets
    result.test_sequences = sequences
    covered_count = sum(1 for t in targets if t.covered)
    result.coverage_pct = (covered_count / len(targets) * 100) if targets else 100
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
            return
        if not cfg.get_outgoing(node) and not exit_id:
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


def path_coverage(cfg: ControlFlowGraph) -> WhiteboxResult:
    """McCabe basis path coverage using cyclomatic complexity."""
    result = WhiteboxResult(model_type="control_flow_graph")

    entry = cfg.entry
    exit_node = cfg.exit
    if not entry:
        return result

    all_paths = _enumerate_paths(cfg, entry.id, exit_node.id if exit_node else None)
    cc = cfg.cyclomatic_complexity()
    basis_paths = _select_independent_paths(all_paths, max_count=cc)

    targets: list[CoverageTarget] = []
    for i, path in enumerate(basis_paths):
        node_labels = []
        for nid in path:
            node = next((n for n in cfg.nodes if n.id == nid), None)
            node_labels.append(node.label if node else nid)
        desc = " -> ".join(node_labels[:4])
        if len(node_labels) > 4:
            desc += "..."
        targets.append(CoverageTarget(
            target_type="path",
            description=f"Path {i + 1}: {desc}",
        ))

    result.coverage_targets = targets
    result.test_sequences = basis_paths
    result.coverage_pct = len(basis_paths) / cc * 100 if cc else 100
    return result


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
    """Modified Condition/Decision Coverage: for each decision node,
    verify both true and false branches can be exercised."""
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

        outgoing = cfg.get_outgoing(dn.id)
        for e in outgoing:
            prefix = _bfs_path(cfg, entry.id, {e.source})
            if prefix:
                seq = prefix + [e.target]
                sequences.append(seq)

    result.coverage_targets = targets
    result.test_sequences = sequences

    for t in targets:
        for dn in cfg.decision_nodes:
            edges = cfg.get_outgoing(dn.id)
            true_branch_exists = any(e.condition.lower() == "true" for e in edges)
            false_branch_exists = any(
                e.condition.lower() != "true" for e in edges
            )
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
