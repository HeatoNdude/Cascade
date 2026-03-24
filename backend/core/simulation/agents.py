"""
Specialist agents for Cascade simulation pipeline.
All pure Python — no LLM calls except SynthesisAgent.
"""

import json
import re
import httpx
import networkx as nx
from core.simulation.state import SimulationState


# ── TestCoverageAgent ──────────────────────────────────────────

def run_test_coverage_agent(
    state: SimulationState,
    G: nx.DiGraph
) -> tuple[SimulationState, set[str]]:
    """
    Finds test nodes in the graph.
    Returns (updated_state, set_of_test_node_ids).
    """
    test_node_ids = set()
    affected_ids  = {n.node_id for n in state.affected_nodes}

    at_risk_tests = []
    for node_id, data in G.nodes(data=True):
        node_type = data.get("type", "")
        name      = data.get("name", "")

        # Detect test nodes by name convention
        is_test = (
            node_type == "function" and (
                name.startswith("test_") or
                name.startswith("Test") or
                "_test" in name
            )
        )
        if is_test:
            test_node_ids.add(node_id)

        # Check if this test is connected to affected nodes
        if is_test:
            neighbors = set(G.predecessors(node_id)) | set(G.successors(node_id))
            if neighbors & affected_ids:
                at_risk_tests.append({
                    "node_id": node_id,
                    "name":    name,
                    "file":    data.get("file", ""),
                })

    state.affected_tests = at_risk_tests
    return state, test_node_ids


# ── HistoryAgent ───────────────────────────────────────────────

def run_history_agent(
    state: SimulationState,
    G: nx.DiGraph
) -> SimulationState:
    """
    Searches git history of affected nodes for relevant precedents.
    Uses keyword matching on commit messages — no LLM.
    """
    if not state.seed_event:
        return state

    # Extract keywords from seed event
    keywords = []
    for name in state.seed_event.target_names:
        keywords.extend(name.lower().replace("_", " ").split())
    keywords = [k for k in keywords if len(k) > 3]

    notes = []
    seen_hashes = set()

    for node in state.affected_nodes[:20]:  # check top 20 at-risk
        node_data = G.nodes.get(node.node_id, {})
        history   = node_data.get("history", [])

        for commit in history:
            h    = commit.get("hash", "")
            msg  = commit.get("message", "").lower()
            if h in seen_hashes:
                continue
            # Check if commit message mentions relevant keywords
            if any(kw in msg for kw in keywords):
                notes.append({
                    "node":    node.name,
                    "file":    node.file,
                    "hash":    h,
                    "date":    commit.get("date", "")[:10],
                    "author":  commit.get("author", ""),
                    "message": commit.get("message", "")[:150],
                })
                seen_hashes.add(h)

    state.history_notes = notes[:10]  # cap at 10 precedents
    return state


# ── SynthesisAgent ─────────────────────────────────────────────

def _build_mermaid(state: SimulationState) -> str:
    """Generate Mermaid flowchart of impact subgraph."""
    lines = ["flowchart TD"]

    # Seed nodes
    for nid in state.seed_node_ids:
        safe = nid.split("::")[-1].replace("-", "_").replace(".", "_")
        lines.append(f'    {safe}["🎯 {safe}"]:::seed')

    # Affected nodes by risk
    for node in state.affected_nodes[:25]:
        safe  = node.name.replace("-", "_").replace(".", "_")
        label = f"{node.name}\\n{node.file.split('/')[-1]}"
        cls   = node.risk_label
        lines.append(f'    {safe}["{label}"]:::{cls}')

    # Edges from seeds to direct impacts
    for node in state.affected_nodes:
        if node.hop_distance == 1:
            for sid in state.seed_node_ids:
                seed_safe = sid.split("::")[-1].replace("-","_").replace(".","_")
                node_safe = node.name.replace("-","_").replace(".","_")
                arrow     = "-->" if not node.is_dynamic_path else "-.->"
                lines.append(f"    {seed_safe} {arrow} {node_safe}")

    lines.append("")
    lines.append("    classDef seed   fill:#1e40af,stroke:#3b82f6,color:#fff")
    lines.append("    classDef red    fill:#7f1d1d,stroke:#ef4444,color:#fff")
    lines.append("    classDef amber  fill:#78350f,stroke:#f59e0b,color:#fff")
    lines.append("    classDef green  fill:#14532d,stroke:#22c55e,color:#fff")

    return "\n".join(lines)


async def run_synthesis_agent(
    state: SimulationState,
    llama_url: str
) -> SimulationState:
    """
    Writes the cited impact report using local LLM.
    Only receives structured metadata — no source code.
    """
    if not state.seed_event:
        state.report_markdown = "No seed event parsed."
        return state

    # Build structured context for LLM
    red_nodes   = [n for n in state.affected_nodes if n.risk_label == "red"]
    amber_nodes = [n for n in state.affected_nodes if n.risk_label == "amber"]
    green_nodes = [n for n in state.affected_nodes if n.risk_label == "green"]

    context = {
        "change":         state.seed_event.description,
        "total_affected": len(state.affected_nodes),
        "high_risk": [
            {"name": n.name, "file": n.file.split("/")[-1]}
            for n in red_nodes[:5]
        ],
        "medium_risk": [
            {"name": n.name, "file": n.file.split("/")[-1]}
            for n in amber_nodes[:5]
        ],
        "tests_at_risk": [t["name"] for t in state.affected_tests[:5]],
    }

    system = """Code change impact analyst. Write a SHORT markdown report.
Use these sections only: ## Summary, ## High Risk, ## Tests at Risk, ## Recommendation
Max 200 words. Be direct. Cite function names and files. No preamble."""

    user = f"Impact analysis data:\n{json.dumps(context, indent=2)}"

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{llama_url}/v1/chat/completions",
                json={
                    "model": "local",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user}
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.2,
                }
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            state.report_markdown = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
            
            if not state.report_markdown:
                raise ValueError("LLM returned empty response")
    except Exception as e:
        # Fallback: generate report from structured data
        lines = [
            f"## Impact Report: {state.seed_event.description}",
            "",
            f"**{state.total_breaks} functions at risk** across "
            f"{len(state.affected_nodes)} total affected nodes.",
        ]

        if red_nodes:
            lines.extend(["", "### 🔴 High Risk (direct breaks)"])
            for n in red_nodes[:8]:
                lines.append(
                    f"- **{n.name}** `{n.file}` (hop {n.hop_distance})"
                    f" — {n.break_reason}"
                )

        if amber_nodes:
            lines.extend(["", "### 🟡 Medium Risk (indirect breaks)"])
            for n in amber_nodes[:8]:
                lines.append(
                    f"- **{n.name}** `{n.file}` (hop {n.hop_distance})"
                    f" — {n.break_reason}"
                )

        if green_nodes:
            lines.extend([
                "",
                f"### 🟢 Low Risk ({len(green_nodes)} nodes — "
                f"unlikely to break but in dependency chain)"
            ])

        if state.affected_tests:
            lines.extend(["", "### 🧪 Tests at Risk"])
            for t in state.affected_tests[:8]:
                lines.append(f"- `{t['name']}` in `{t['file']}`")

        if state.history_notes:
            lines.extend(["", "### 📜 Historical Precedent"])
            for h in state.history_notes[:3]:
                lines.append(
                    f"- `{h['hash']}` {h['date']} by {h['author']}: "
                    f"{h['message'][:100]}"
                )

        lines.extend([
            "",
            "### 💡 Recommendation",
            f"Update all {len(red_nodes) + len(amber_nodes)} call sites "
            f"before merging. Run the full test suite after renaming."
        ])

        state.report_markdown = "\n".join(lines)
        print(f"[SynthesisAgent] LLM failed ({e}), used fallback report.")

    # Compute confidence score
    total = len(state.affected_nodes)
    dynamic_ratio = sum(
        1 for n in state.affected_nodes if n.is_dynamic_path
    ) / max(total, 1)
    state.confidence_score = round(max(0.4, 1.0 - dynamic_ratio * 0.5), 2)

    # Generate Mermaid graph
    state.mermaid_graph = _build_mermaid(state)

    return state
