"""
TraversalAgent for Cascade.
Pure Python / NetworkX — no LLM involved.
BFS from seed nodes outward through dependency edges.
Returns all affected nodes ranked by hop distance.
"""

import networkx as nx
from core.simulation.state import SimulationState

MAX_AFFECTED   = 200
MAX_HOP_DEPTH  = 5


def find_seed_nodes(
    G: nx.DiGraph,
    target_names: list[str]
) -> list[str]:
    """
    Find graph node IDs matching the target names.
    Case-insensitive, partial match allowed.
    """
    seeds = []
    for node_id, data in G.nodes(data=True):
        node_name = data.get("name", "").lower()
        for target in target_names:
            if target.lower() in node_name or node_name in target.lower():
                seeds.append(node_id)
                break
    return list(set(seeds))


def run_traversal(
    state: SimulationState,
    G: nx.DiGraph
) -> SimulationState:
    """
    BFS from seed nodes outward.
    Populates state.seed_node_ids and state.traversal_result.
    """
    if not state.seed_event:
        state.error = "No seed event — IntentAgent must run first"
        return state

    # Find seed nodes
    seeds = find_seed_nodes(G, state.seed_event.target_names)

    if not seeds:
        # Broaden search with single words
        for target in state.seed_event.target_names:
            for part in target.split("_"):
                if len(part) > 2:
                    seeds.extend(find_seed_nodes(G, [part]))
        seeds = list(set(seeds))

    if not seeds:
        state.error = (
            f"No nodes found matching: {state.seed_event.target_names}. "
            "Try a different name or check the graph is loaded."
        )
        return state

    state.seed_node_ids = seeds[:10]  # cap seeds

    # BFS traversal
    visited:  dict[str, int] = {}   # node_id → hop_distance
    dynamic_paths: set[str]  = set() # node_ids reached via dynamic edge

    from collections import deque
    queue = deque([(seed, 0) for seed in state.seed_node_ids])
    queued = set(state.seed_node_ids)

    while queue and len(visited) < MAX_AFFECTED:
        node_id, depth = queue.popleft()
        if depth > MAX_HOP_DEPTH:
            continue

        visited[node_id] = depth

        # Walk successors (nodes that depend ON the changed node)
        for successor in G.successors(node_id):
            if successor not in visited and successor not in queued:
                edge_data  = G.edges[node_id, successor]
                is_dynamic = edge_data.get("is_dynamic", False)
                if is_dynamic:
                    dynamic_paths.add(successor)
                queued.add(successor)
                queue.append((successor, depth + 1))

        # Also walk predecessors for call edges
        # (nodes that CALL the changed node also break)
        for pred in G.predecessors(node_id):
            if pred not in visited and pred not in queued:
                edge_data  = G.edges[pred, node_id]
                edge_type  = edge_data.get("edge_type", "")
                if edge_type in ("calls", "imports"):
                    is_dynamic = edge_data.get("is_dynamic", False)
                    if is_dynamic:
                        dynamic_paths.add(pred)
                    queued.add(pred)
                    queue.append((pred, depth + 1))

    # Build result list — exclude seed nodes themselves
    result = []
    for node_id, hop in visited.items():
        if node_id in state.seed_node_ids:
            continue
        data = G.nodes.get(node_id, {})
        if data.get("type") == "module":
            continue  # skip module containers
        result.append({
            "node_id":         node_id,
            "name":            data.get("name", ""),
            "file":            data.get("file", ""),
            "node_type":       data.get("type", "function"),
            "hop_distance":    hop,
            "is_dynamic_path": node_id in dynamic_paths,
            "docstring":       data.get("docstring", ""),
            "last_commit":     data.get("last_commit", ""),
            "primary_author":  data.get("primary_author", ""),
            "history":         data.get("history", [])[:3],
        })

    # Sort by hop distance then name
    result.sort(key=lambda x: (x["hop_distance"], x["name"]))
    state.traversal_result = result[:MAX_AFFECTED]
    return state
