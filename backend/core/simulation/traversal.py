"""
TraversalAgent for Cascade.
Pure Python / NetworkX — no LLM involved.
BFS from seed nodes outward through dependency edges.
Returns all affected nodes ranked by hop distance.
"""

import os
from collections import deque
import networkx as nx

from core.simulation.state import SimulationState
from core.graph.ast_parser import parse_file

MAX_AFFECTED   = 200
MAX_HOP_DEPTH  = 3


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

    dynamic_paths = set()
    visited:  dict[str, int] = {}   # node_id → hop_distance
    queued = set(state.seed_node_ids)
    
    queue = deque([(seed, 0) for seed in state.seed_node_ids])

    # To track callers of specific functions accurately, we need a reverse lookup map.
    # We will build a cached mapping of which file modules call which targets on the fly.
    parsed_modules = {}

    while queue:
        node_id, depth = queue.popleft()
        
        if node_id in visited and visited[node_id] <= depth:
            continue
        visited[node_id] = depth

        if depth >= MAX_HOP_DEPTH:
            continue

        node_data = G.nodes.get(node_id, {})
        is_module = node_data.get("type") == "module"

        # Walk successors (downstream dependencies, e.g. what this node calls)
        for successor in G.successors(node_id):
            if successor not in visited and successor not in queued:
                edge_data  = G.edges[node_id, successor]
                # Avoid bleeding blast radius into all sibling functions within a module
                if edge_data.get("edge_type") == "contains" and node_id not in state.seed_node_ids:
                    continue
                    
                is_dynamic = edge_data.get("is_dynamic", False)
                if is_dynamic:
                    dynamic_paths.add(successor)
                queued.add(successor)
                queue.append((successor, depth + 1))

        # We must find the functions that call THIS node_id.
        # But GraphBuilder points 'calls' edges from the caller MODULE to this node.
        # We need to intercept module-level calls and map them to the specific caller functions.
        target_name = node_data.get("name")
        
        # 1. Standard module-to-node predecessors
        for pred in G.predecessors(node_id):
            edge_data = G.edges[pred, node_id]
            edge_type = edge_data.get("edge_type", "")
            
            if edge_type in ("calls", "imports"):
                is_dynamic = edge_data.get("is_dynamic", False)
                if is_dynamic:
                    dynamic_paths.add(pred)
                
                pred_data = G.nodes.get(pred, {})
                if pred_data.get("type") == "module" and target_name:
                    file_path = pred_data.get("file", "")
                    # Fetch or generate AST mappings for this module
                    if file_path not in parsed_modules:
                        abs_path = os.path.join(state.repo_path, file_path)
                        parsed = {"calls": []}
                        if os.path.exists(abs_path):
                            try:
                                parsed = parse_file(abs_path)
                            except Exception:
                                pass
                        parsed_modules[file_path] = parsed
                    
                    parsed = parsed_modules[file_path]
                    
                    call_lines = [
                        c["line"] for c in parsed.get("calls", [])
                        if c.get("callee") == target_name
                    ]
                    
                    found_specific_caller = False
                    if call_lines:
                        # Find exactly which functions contain these lines
                        for cand in G.successors(pred):
                            cdata = G.nodes.get(cand, {})
                            if cdata.get("type") not in ("function", "method", "class"):
                                continue
                            c_start = cdata.get("line_start", 0)
                            c_end   = cdata.get("line_end", float('inf'))
                            
                            if any(c_start <= line <= c_end for line in call_lines):
                                if cand not in visited and cand not in queued:
                                    queued.add(cand)
                                    queue.append((cand, depth + 1))
                                found_specific_caller = True
                                
                    if found_specific_caller:
                        continue # We successfully mapped the call; omit the generic module.
                
                if pred not in visited and pred not in queued:
                    queued.add(pred)
                    queue.append((pred, depth + 1))
                    
        # 2. But wait! If `node_id` is a Function, its parent Module is what holds the incoming calls!
        # If we just change parse_file, `node_id` is parse_file. We handled its module predecessors above.
        # BUT if `node_id` is _process_file (Hop 1), it has NO predecessors!
        # Its parent module `core/graph_builder.py::__module__` holds its callers!
        if node_data.get("type") in ("function", "method"):
            # Find the parent module via contains edge backwards
            for pred in G.predecessors(node_id):
                if G.edges[pred, node_id].get("edge_type") == "contains":
                    # pred is the Module. Let's see who calls the Module, looking for OUR function name!
                    for mod_pred in G.predecessors(pred):
                        mod_edge = G.edges[mod_pred, pred]
                        if mod_edge.get("edge_type") in ("calls", "imports"):
                            # Someone called our module! Are they calling US?
                            mod_pred_data = G.nodes.get(mod_pred, {})
                            if mod_pred_data.get("type") == "module":
                                # We parse that caller module
                                file_path = mod_pred_data.get("file", "")
                                if file_path not in parsed_modules:
                                    abs_path = os.path.join(state.repo_path, file_path)
                                    p = {"calls": []}
                                    if os.path.exists(abs_path):
                                        try: p = parse_file(abs_path)
                                        except Exception: pass
                                    parsed_modules[file_path] = p
                                
                                call_lines = [
                                    c["line"] for c in parsed_modules[file_path].get("calls", [])
                                    if c.get("callee") == target_name
                                ]
                                
                                if call_lines:
                                    # We found the caller module. Now find the exact caller function in IT!
                                    for cand in G.successors(mod_pred):
                                        cdata = G.nodes.get(cand, {})
                                        c_start = cdata.get("line_start", 0)
                                        c_end   = cdata.get("line_end", float('inf'))
                                        if any(c_start <= line <= c_end for line in call_lines):
                                            if cand not in visited and cand not in queued:
                                                if mod_edge.get("is_dynamic"): dynamic_paths.add(cand)
                                                queued.add(cand)
                                                queue.append((cand, depth + 1))


    # Compile results, filtering out structural modules
    result = []
    
    for node_id, hop in visited.items():
        if node_id in state.seed_node_ids:
            continue
            
        data = G.nodes.get(node_id, {})
        if data.get("type") == "module":
            continue  # skip module containers
            
        result.append({
            "node_id":         node_id,
            "name":            data.get("name", "unknown"),
            "file":            data.get("file", "unknown"),
            "node_type":       data.get("type", "function"),
            "hop_distance":    hop,
            "is_dynamic_path": node_id in dynamic_paths,
            "docstring":       data.get("docstring", ""),
            "last_commit":     data.get("last_commit", ""),
            "primary_author":  data.get("primary_author", ""),
            "history":         data.get("history", [])[:3],
        })

    # Sort tightly by hop distance then name
    result.sort(key=lambda x: (x["hop_distance"], x["name"]))
    
    state.traversal_result = result[:MAX_AFFECTED]
    return state
