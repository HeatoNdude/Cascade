"""
Blast radius scoring for Cascade.
Computes risk scores and labels for affected nodes.
Pure Python — no LLM, no network calls.
"""

import math
from core.simulation.state import SimulationState, AffectedNode


def score_node(
    hop_distance: int,
    is_dynamic_path: bool,
    has_tests: bool,
    call_frequency: int = 1,
) -> float:
    """
    Risk score formula [0.0 - 1.0]:
    hop 1 → red   (0.75+)
    hop 2 → amber (0.35-0.64)
    hop 3 → green (0.10-0.34)
    Dynamic paths get amber floor (0.40)
    """
    # Hard tiers by hop distance
    if hop_distance == 1:
        base = 0.80
    elif hop_distance == 2:
        base = 0.45
    else:
        base = 0.15

    # Test coverage reduces risk slightly
    test_factor = 1.0 if not has_tests else 0.85

    score = base * test_factor

    # Dynamic path floor — uncertain but not safe
    if is_dynamic_path:
        score = max(score, 0.40)

    return min(round(score, 3), 1.0)


def score_to_label(score: float, is_dynamic: bool) -> str:
    if is_dynamic and score < 0.35:
        return "amber"
    if score >= 0.65:
        return "red"
    elif score >= 0.30:
        return "amber"
    else:
        return "green"


def build_break_reason(
    node: dict,
    seed_event,
    hop_distance: int,
    is_dynamic: bool
) -> str:
    """
    Generate a human-readable break reason without LLM.
    The SynthesisAgent will enrich this later.
    """
    change = seed_event.description if seed_event else "the change"
    name   = node.get("name", "this function")
    file   = node.get("file", "").split("/")[-1]

    if hop_distance == 1:
        if is_dynamic:
            return (f"{name} in {file} calls the changed code via a "
                    f"dynamic reference — simulation may be incomplete.")
        return (f"{name} in {file} directly calls or imports the "
                f"changed code and will break.")
    elif hop_distance == 2:
        return (f"{name} in {file} depends on a direct caller of the "
                f"changed code (hop {hop_distance}).")
    else:
        return (f"{name} in {file} is {hop_distance} hops from the "
                f"change via the dependency chain.")


def run_scoring(
    state: SimulationState,
    test_node_ids: set[str]
) -> SimulationState:
    """
    Convert traversal_result into scored AffectedNode list.
    test_node_ids: set of node IDs that are test functions.
    """
    affected = []
    for node in state.traversal_result:
        node_id     = node["node_id"]
        hop         = node["hop_distance"]
        is_dynamic  = node["is_dynamic_path"]
        has_tests   = node_id in test_node_ids
        history     = node.get("history", [])

        score = score_node(
            hop_distance=hop,
            is_dynamic_path=is_dynamic,
            has_tests=has_tests,
        )
        label = score_to_label(score, is_dynamic)

        # Pull most relevant history note
        history_note = ""
        if history:
            history_note = history[0].get("message", "")[:120]

        break_reason = build_break_reason(
            node, state.seed_event, hop, is_dynamic
        )

        affected.append(AffectedNode(
            node_id         = node_id,
            name            = node["name"],
            file            = node["file"],
            node_type       = node["node_type"],
            risk_score      = score,
            risk_label      = label,
            hop_distance    = hop,
            is_dynamic_path = is_dynamic,
            break_reason    = break_reason,
            history_note    = history_note,
        ))

    # Sort: red first, then amber, then green
    order = {"red": 0, "amber": 1, "green": 2}
    affected.sort(key=lambda n: (order[n.risk_label], n.hop_distance))
    state.affected_nodes  = affected
    state.total_breaks    = sum(
        1 for n in affected if n.risk_label in ("red", "amber")
    )
    return state
