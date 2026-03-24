"""
ExplainAgent for Cascade.
Handles investigative queries — no blast radius.
Uses only httpx (already in venv) and stdlib.
"""

import json
import httpx
import networkx as nx
from core.simulation.classifier import QueryIntent


async def run_explain(
    intent: QueryIntent,
    G: nx.DiGraph,
    vector_index,
    llama_url: str,
) -> dict:
    """
    Finds target node, reads context, generates answer.
    """
    # Find target via semantic search
    target_nodes = []
    if vector_index:
        try:
            results = vector_index.search(intent.target, top_k=5)
            target_nodes = [r["node_id"] for r in results if r["node_id"] in G]
        except Exception:
            pass

    # Fallback: name match in graph
    if not target_nodes:
        for node_id, data in G.nodes(data=True):
            name = data.get("name", "").lower()
            if intent.target.lower() in name:
                target_nodes.append(node_id)
                if len(target_nodes) >= 5:
                    break

    if not target_nodes:
        return {
            "mode":   "investigate",
            "answer": (
                f"No nodes found matching '{intent.target}'. "
                f"Make sure the repo is loaded and try a "
                f"different name."
            ),
            "nodes":  [],
            "prompt": intent.raw_prompt,
        }

    primary_id   = target_nodes[0]
    primary_data = G.nodes.get(primary_id, {})
    callers      = list(G.predecessors(primary_id))[:10]
    callees      = list(G.successors(primary_id))[:10]

    caller_names = [
        G.nodes.get(c, {}).get("name", c.split("::")[-1])
        for c in callers
    ]
    callee_names = [
        G.nodes.get(c, {}).get("name", c.split("::")[-1])
        for c in callees
    ]

    history = primary_data.get("history", [])[:3]

    context = {
        "query":         intent.raw_prompt,
        "target":        primary_data.get("name", intent.target),
        "type":          primary_data.get("type", "function"),
        "file":          primary_data.get("file", ""),
        "line_range":    (
            f"{primary_data.get('line_start','?')}"
            f"–{primary_data.get('line_end','?')}"
        ),
        "docstring":     primary_data.get("docstring", ""),
        "params":        primary_data.get("params", []),
        "is_async":      primary_data.get("is_async", False),
        "called_by":     caller_names,
        "calls":         callee_names,
        "last_author":   primary_data.get("primary_author", ""),
        "last_modified": primary_data.get("last_modified", "")[:10],
        "last_commit":   primary_data.get("last_commit", "")[:120],
        "git_history": [
            f"{h.get('hash','')} {h.get('date','')[:10]}: "
            f"{h.get('message','')[:80]}"
            for h in history
        ],
    }

    system = (
        "You are a code intelligence assistant. "
        "Answer the developer's question directly and concisely. "
        "Cite the file name and line range. "
        "Describe what it does, who calls it, what it calls. "
        "Max 150 words. No preamble."
    )
    user = (
        f"Question: {intent.raw_prompt}\n\n"
        f"Code metadata:\n{json.dumps(context, indent=2)}"
    )

    answer = ""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{llama_url}/v1/chat/completions",
                json={
                    "model":       "local",
                    "messages":    [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user}
                    ],
                    "max_tokens":  600,
                    "temperature": 0.2,
                }
            )
            resp.raise_for_status()
            raw_content = resp.json()["choices"][0]["message"]["content"]
            import re
            answer = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
            
            if not answer:
                answer = _fallback_answer(context)
                print("[ExplainAgent] LLM returned empty string, fallback used.")
                
    except Exception as e:
        answer = _fallback_answer(context)
        print(f"[ExplainAgent] LLM failed ({e}), fallback used.")

    return {
        "mode":         "investigate",
        "answer":       answer,
        "primary_node": primary_id,
        "nodes":        [primary_id] + callers[:5] + callees[:5],
        "context":      context,
        "prompt":       intent.raw_prompt,
    }


def _fallback_answer(ctx: dict) -> str:
    name     = ctx.get("target", "this function")
    file     = ctx.get("file", "").split("/")[-1]
    lines    = ctx.get("line_range", "?")
    doc      = ctx.get("docstring", "")
    callers  = ctx.get("called_by", [])
    callees  = ctx.get("calls", [])
    author   = ctx.get("last_author", "")
    modified = ctx.get("last_modified", "")

    parts = [f"**`{name}`** is in `{file}` (lines {lines})."]
    if doc:
        parts.append(f"{doc[:200]}")
    if callers:
        parts.append(
            f"Called by: {', '.join(f'`{c}`' for c in callers[:5])}."
        )
    if callees:
        parts.append(
            f"Calls: {', '.join(f'`{c}`' for c in callees[:5])}."
        )
    if author:
        parts.append(f"Last modified by {author} ({modified}).")
    return " ".join(parts)
