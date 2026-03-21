"""
Cascade Simulation Pipeline.
Orchestrates all agents in sequence.
Yields SSE events as each stage completes.
Uses asyncio.Queue to ensure each event is flushed to the client immediately.
"""

import time
import json
import asyncio
import networkx as nx
from typing import AsyncGenerator

from core.simulation.state import SimulationState
from core.simulation.intent_agent import run_intent_agent
from core.simulation.traversal import run_traversal
from core.simulation.scoring import run_scoring
from core.simulation.agents import (
    run_test_coverage_agent,
    run_history_agent,
    run_synthesis_agent,
)


def _sse(event: str, data: dict) -> str:
    """Format a single SSE message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def run_simulation(
    prompt: str,
    repo_path: str,
    G: nx.DiGraph,
    llama_url: str,
) -> AsyncGenerator[str, None]:
    """
    Full simulation pipeline.
    Yields SSE-formatted strings at each stage.
    Uses a Queue so that synchronous agents (traversal, scoring)
    don't block SSE delivery to the client.
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _run():
        """Pipeline runner — pushes events into the queue."""
        start = time.time()
        state = SimulationState(prompt=prompt, repo_path=repo_path)

        await queue.put(_sse("stage", {"stage": "intent", "message": "Parsing change intent…"}))

        # ── Stage 1: IntentAgent ──────────────────────────────────
        try:
            node_names = [
                d.get("name", "") for _, d in G.nodes(data=True)
                if d.get("type") != "module"
            ]
            state = await run_intent_agent(state, llama_url, node_names)
            if state.error:
                await queue.put(_sse("error", {"message": state.error}))
                return

            await queue.put(_sse("intent", {
                "change_type":  state.seed_event.change_type,
                "targets":      state.seed_event.target_names,
                "description":  state.seed_event.description,
                "scope":        state.seed_event.scope,
            }))
        except Exception as e:
            await queue.put(_sse("error", {"message": f"IntentAgent failed: {e}"}))
            return

        await queue.put(_sse("stage", {"stage": "traversal", "message": "Traversing dependency graph…"}))

        # ── Stage 2: TraversalAgent ───────────────────────────────
        try:
            state = run_traversal(state, G)
            if state.error:
                await queue.put(_sse("error", {"message": state.error}))
                return

            await queue.put(_sse("traversal", {
                "seed_nodes":     state.seed_node_ids,
                "affected_count": len(state.traversal_result),
            }))
        except Exception as e:
            await queue.put(_sse("error", {"message": f"TraversalAgent failed: {e}"}))
            return

        await queue.put(_sse("stage", {"stage": "scoring", "message": "Scoring blast radius…"}))

        # ── Stage 3: TestCoverage + Scoring ───────────────────────
        try:
            state, test_node_ids = run_test_coverage_agent(state, G)
            state = run_scoring(state, test_node_ids)

            blast = [
                {
                    "node_id":    n.node_id,
                    "risk_label": n.risk_label,
                    "risk_score": n.risk_score,
                    "hop":        n.hop_distance,
                }
                for n in state.affected_nodes
            ]
            await queue.put(_sse("blast_radius", {
                "seed_node_ids":  state.seed_node_ids,
                "affected_nodes": blast,
                "total_breaks":   state.total_breaks,
            }))
        except Exception as e:
            await queue.put(_sse("error", {"message": f"Scoring failed: {e}"}))
            return

        await queue.put(_sse("stage", {"stage": "history", "message": "Searching git history…"}))

        # ── Stage 4: HistoryAgent ─────────────────────────────────
        try:
            state = run_history_agent(state, G)
            await queue.put(_sse("history", {
                "precedents_found": len(state.history_notes)
            }))
        except Exception as e:
            print(f"[Pipeline] HistoryAgent warning: {e}")

        await queue.put(_sse("stage", {"stage": "synthesis", "message": "Writing impact report…"}))

        # ── Stage 5: SynthesisAgent ───────────────────────────────
        try:
            state = await run_synthesis_agent(state, llama_url)
        except Exception as e:
            state.report_markdown = f"Report generation failed: {e}"
            state.confidence_score = 0.5

        state.elapsed_ms = int((time.time() - start) * 1000)
        state.status     = "complete"

        # Final result event
        await queue.put(_sse("complete", {
            "status":           "complete",
            "elapsed_ms":       state.elapsed_ms,
            "total_breaks":     state.total_breaks,
            "confidence_score": state.confidence_score,
            "affected_nodes": [
                {
                    "node_id":      n.node_id,
                    "name":         n.name,
                    "file":         n.file,
                    "risk_label":   n.risk_label,
                    "risk_score":   n.risk_score,
                    "hop_distance": n.hop_distance,
                    "break_reason": n.break_reason,
                    "history_note": n.history_note,
                }
                for n in state.affected_nodes
            ],
            "affected_tests": state.affected_tests,
            "report_markdown": state.report_markdown,
            "mermaid_graph":   state.mermaid_graph,
            "seed_node_ids":   state.seed_node_ids,
        }))

    # Launch the pipeline as a background task
    task = asyncio.create_task(_run())

    # Yield SSE events from the queue as they arrive
    try:
        while True:
            # Wait for next event with a timeout
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # Send a keep-alive comment to prevent connection timeout
                if task.done():
                    break
                yield ": keepalive\n\n"
                continue

            if event is None:
                break
            yield event

            # If pipeline is done and queue is empty, stop
            if task.done() and queue.empty():
                break
    finally:
        if not task.done():
            task.cancel()

    # Drain any remaining events
    while not queue.empty():
        event = queue.get_nowait()
        if event is not None:
            yield event
