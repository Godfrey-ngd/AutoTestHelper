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

    # Compute degree imbalance
    in_deg: dict[str, int] = Counter()
    out_deg: dict[str, int] = Counter()
    for t in sm.transitions:
        out_deg[t.source] += 1
        in_deg[t.target] += 1

    # Find surplus (out > in) and deficit (in > out) nodes
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

    # Balance the graph by adding edges from surplus to deficit nodes
    balanced_edges: list[tuple[str, str]] = []
    used_deficit = [False] * len(deficit)
    for src in surplus:
        for di, dst in enumerate(deficit):
            if not used_deficit[di]:
                balanced_edges.append((src, dst))
                used_deficit[di] = True
                break

    # Build extended adjacency with original + balanced edges
    extended: dict[str, list[str]] = {s.id: [] for s in sm.states}
    for t in sm.transitions:
        extended[t.source].append(t.target)
    for src, dst in balanced_edges:
        extended[src].append(dst)

    start = sm.initial_state.id if sm.initial_state else sm.states[0].id

    # Hierholzer's algorithm for Eulerian circuit
    remaining = {k: list(v) for k, v in extended.items()}
    stack = [start]
    result: list[str] = []

    while stack:
        v = stack[-1]
        if remaining.get(v):
            next_v = remaining[v].pop()
            stack.append(next_v)
        else:
            result.append(stack.pop())

    result.reverse()
    return result if result else None


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
        best_priority = 2
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
        if seq and seq[0] == last[-1]:
            last.extend(seq[1:])
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

    # Recalculate coverage after optimization
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
