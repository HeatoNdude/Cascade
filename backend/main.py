import os
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from starlette.responses import StreamingResponse
from core.simulation.pipeline import run_simulation

from core.llm import LLMRouter
from core.settings import load_settings
from core.graph_state import cascade
from core.graph.graph_builder import GraphBuilder
from core.graph.vector_index import VectorIndex
from core.graph.watcher import RepoWatcher

app = FastAPI(title="Cascade Backend", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:1420",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

settings  = load_settings()
llm       = LLMRouter(settings)
CACHE_DIR = r"D:\Projects\cascade\cascade\backend\cache"


# ── LLM routes ──────────────────────────────────────────────────

class PromptRequest(BaseModel):
    prompt: str
    system: str = "You are Cascade, a codebase simulation assistant."

class PromptResponse(BaseModel):
    response:     str
    backend_used: str

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        # Send current state immediately on connect
        await ws.send_json({
            "event": "status",
            "data": {
                "status": cascade.build_progress["status"],
                "stats": cascade.builder.get_stats()
                         if cascade.builder else {}
            }
        })
        while True:
            # Keep connection alive, receive pings
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)

@app.get("/health")
def health():
    return {
        "status":       "ok",
        "llm_backend":  settings["llm_backend"],
        "graph_status": cascade.build_progress["status"],
        "repo":         cascade.repo_path
    }

@app.post("/prompt", response_model=PromptResponse)
async def prompt(req: PromptRequest):
    result = await llm.complete(req.system, req.prompt)
    return PromptResponse(
        response=result["text"],
        backend_used=result["backend"]
    )


# ── Graph routes ─────────────────────────────────────────────────

class OpenRepoRequest(BaseModel):
    repo_path: str


def _do_build(repo_path: str):
    cascade.is_building = True
    cascade.build_progress["status"] = "building"
    try:
        builder = GraphBuilder(
            repo_path=repo_path,
            cache_dir=CACHE_DIR,
            max_files=settings.get("max_repo_files", 5000)
        )

        if not builder.load_cache():
            def progress(current, total, fp):
                cascade.build_progress.update({
                    "current":      current,
                    "total":        total,
                    "current_file": str(fp)
                })
                pass  # WebSocket broadcast handled by polling
            builder.build(progress_callback=progress)

        cascade.builder = builder

        vector = VectorIndex(CACHE_DIR)
        if not vector.load_cache():
            vector.build(builder.G)
        cascade.vector = vector

        def on_file_change(changed_path: str):
            print(f"[Cascade] File changed: {changed_path}")
            builder.update_file(changed_path)
            vector.build(builder.G)

        watcher = RepoWatcher(repo_path, on_file_change)
        watcher.start()
        cascade.watcher   = watcher
        cascade.repo_path = repo_path
        cascade.build_progress["status"] = "ready"
        import asyncio
        asyncio.run(manager.broadcast({
            "event": "ready",
            "data": cascade.builder.get_stats()
        }))

    except Exception as e:
        cascade.build_progress["status"] = f"error: {e}"
        print(f"[Cascade] Build error: {e}")
    finally:
        cascade.is_building = False


@app.post("/graph/open")
async def open_repo(req: OpenRepoRequest, background_tasks: BackgroundTasks):
    if not Path(req.repo_path).exists():
        raise HTTPException(status_code=400, detail="Path does not exist")
    if cascade.is_building:
        raise HTTPException(status_code=409, detail="Already building a graph")
    cascade.reset()
    background_tasks.add_task(_do_build, req.repo_path)
    return {"status": "building", "repo_path": req.repo_path}


@app.get("/graph/status")
def graph_status():
    return {
        "status":   cascade.build_progress["status"],
        "progress": cascade.build_progress,
        "stats":    cascade.builder.get_stats() if cascade.builder else {}
    }


@app.get("/graph/nodes")
def graph_nodes(type: Optional[str] = None, limit: int = 500):
    if not cascade.builder:
        raise HTTPException(status_code=404, detail="No graph loaded")
    nodes = []
    for node_id, data in cascade.builder.G.nodes(data=True):
        if type and data.get("type") != type:
            continue
        nodes.append({
            "id":    node_id,
            "label": data.get("name", node_id),
            **{k: v for k, v in data.items()
               if not k.startswith("_") and k != "history"}
        })
        if len(nodes) >= limit:
            break
    return {"nodes": nodes, "total": cascade.builder.G.number_of_nodes()}


@app.get("/graph/edges")
def graph_edges(limit: int = 2000):
    if not cascade.builder:
        raise HTTPException(status_code=404, detail="No graph loaded")
    edges = []
    for src, dst, data in cascade.builder.G.edges(data=True):
        edges.append({"source": src, "target": dst, **data})
        if len(edges) >= limit:
            break
    return {"edges": edges, "total": cascade.builder.G.number_of_edges()}


@app.get("/graph/node/{node_id:path}")
def get_node(node_id: str):
    if not cascade.builder:
        raise HTTPException(status_code=404, detail="No graph loaded")
    if node_id not in cascade.builder.G:
        raise HTTPException(status_code=404, detail="Node not found")
    data    = dict(cascade.builder.G.nodes[node_id])
    callers = list(cascade.builder.G.predecessors(node_id))
    callees = list(cascade.builder.G.successors(node_id))
    return {
        "id":      node_id,
        "data":    data,
        "callers": callers[:20],
        "callees": callees[:20]
    }


@app.post("/graph/search")
async def search_graph(body: dict):
    query = body.get("query", "")
    top_k = body.get("top_k", 10)
    if not cascade.vector:
        raise HTTPException(status_code=404, detail="No index loaded")
    results  = cascade.vector.search(query, top_k=top_k)
    enriched = []
    for r in results:
        nid  = r["node_id"]
        data = cascade.builder.G.nodes.get(nid, {})
        enriched.append({
            "node_id":   nid,
            "score":     r["score"],
            "name":      data.get("name", ""),
            "type":      data.get("type", ""),
            "file":      data.get("file", ""),
            "docstring": data.get("docstring", "")[:200]
        })
    return {"results": enriched}


@app.get("/graph/stats")
def graph_stats():
    if not cascade.builder:
        return {"status": "no graph loaded"}
    return {
        **cascade.builder.get_stats(),
        "status": cascade.build_progress["status"],
        "repo":   cascade.repo_path
    }


# ── Simulation routes ───────────────────────────────────────────

class SimulateRequest(BaseModel):
    prompt: str
    repo_path: Optional[str] = None


@app.post("/simulate")
async def simulate(req: SimulateRequest):
    """
    Run a what-if simulation. Streams SSE events.
    Events: stage, intent, traversal, blast_radius,
            history, complete, error
    """
    if not cascade.builder:
        raise HTTPException(status_code=404, detail="No graph loaded")
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is empty")

    repo_path = req.repo_path or cascade.repo_path or ""
    llama_url = settings.get("llama_server_url", "http://127.0.0.1:8080")
    api_key   = settings.get("openrouter_key", "")
    model_name= settings.get("openrouter_model", "local")

    async def event_generator():
        async for chunk in run_simulation(
            prompt=req.prompt,
            repo_path=repo_path,
            G=cascade.builder.G,
            llama_url=llama_url,
            api_key=api_key,
            model_name=model_name,
            vector_index=cascade.vector,
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/simulate/history")
def simulation_history():
    """Returns last 20 simulations from in-memory log."""
    return {"history": _sim_history[-20:]}


# In-memory simulation log (last 20)
_sim_history: list[dict] = []
