"""
Cascade MCP Server — standalone bridge.
Runs with GLOBAL Python (not the backend venv).
Makes HTTP calls to the Cascade FastAPI backend.

Install requirements (global Python only):
  python -m pip install mcp httpx

Usage:
  python mcp_server.py --repo D:\Projects\cascade\cascade

Add to Claude Desktop config:
  {
    "mcpServers": {
      "cascade": {
        "command": "python",
        "args": [
          "D:\\Projects\\cascade\\cascade\\mcp_server.py",
          "--repo", "D:\\Projects\\cascade\\cascade"
        ]
      }
    }
  }
"""

import asyncio
import sys
import json
import argparse
import httpx

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

BACKEND_URL  = "http://127.0.0.1:5001"
DEFAULT_REPO = ""
server       = Server("cascade")


# ── Helpers ───────────────────────────────────────────────────

async def ensure_graph(repo_path: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{BACKEND_URL}/graph/status")
            status = r.json().get("status", "")
            if status == "ready":
                return True
            if status != "building" and repo_path:
                await c.post(
                    f"{BACKEND_URL}/graph/open",
                    json={"repo_path": repo_path}
                )
    except Exception:
        pass
    return False


async def call_simulate(prompt: str) -> dict:
    """Stream /simulate and return the complete event."""
    complete = {}
    buffer   = ""
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            async with c.stream(
                "POST",
                f"{BACKEND_URL}/simulate",
                json={"prompt": prompt},
                timeout=120,
            ) as resp:
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    messages = buffer.split("\n\n")
                    buffer   = messages.pop()
                    for msg in messages:
                        lines    = msg.strip().split("\n")
                        evt_name = ""
                        evt_data = ""
                        for line in lines:
                            if line.startswith("event: "):
                                evt_name = line[7:].strip()
                            elif line.startswith("data: "):
                                evt_data = line[6:].strip()
                        if evt_name == "complete" and evt_data:
                            try:
                                complete = json.loads(evt_data)
                            except Exception:
                                pass
    except Exception as e:
        complete = {"error": str(e)}
    return complete


# ── Tool definitions ──────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="cascade_simulate",
            description=(
                "Simulate the impact of a proposed code change. "
                "Returns affected functions with red/amber/green "
                "risk levels and a cited impact report. "
                "Use for: 'what if I rename X', "
                "'what breaks if I replace Y with Z'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": (
                            "Change description in natural language. "
                            "E.g. 'what if we rename parse_file'"
                        )
                    }
                },
                "required": ["prompt"]
            }
        ),
        types.Tool(
            name="cascade_explain",
            description=(
                "Explain a function, class, or module. "
                "Returns what it does, who calls it, "
                "what it calls, and git history. "
                "Use for: 'what does X do', 'explain X', "
                "'who calls X', 'how does X work'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": (
                            "Question about code. "
                            "E.g. 'what does parse_file do'"
                        )
                    }
                },
                "required": ["prompt"]
            }
        ),
        types.Tool(
            name="cascade_search",
            description=(
                "Semantic search across the codebase graph. "
                "Returns relevant functions, classes, modules. "
                "Use to find code before making changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search concept. "
                            "E.g. 'file watching', 'git history'"
                        )
                    },
                    "top_k": {
                        "type":    "integer",
                        "default": 8
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="cascade_context",
            description=(
                "Get graph context for a file and line number. "
                "Returns function at that location, its callers, "
                "callees, and git history."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative file path in repo"
                    },
                    "line": {
                        "type":    "integer",
                        "default": 0
                    }
                },
                "required": ["file_path"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(
    name: str,
    arguments: dict
) -> list[types.TextContent]:

    if name in ("cascade_simulate", "cascade_explain"):
        return await _handle_query(
            arguments.get("prompt", ""), name
        )
    elif name == "cascade_search":
        return await _handle_search(arguments)
    elif name == "cascade_context":
        return await _handle_context(arguments)
    return [types.TextContent(
        type="text", text=f"Unknown tool: {name}"
    )]


async def _handle_query(
    prompt: str,
    tool_name: str
) -> list[types.TextContent]:
    if DEFAULT_REPO:
        await ensure_graph(DEFAULT_REPO)

    result = await call_simulate(prompt)

    if "error" in result:
        return [types.TextContent(
            type="text",
            text=f"Error: {result['error']}\n"
                 f"Make sure the Cascade backend is running "
                 f"on port 5001."
        )]

    mode = result.get("mode", "simulate")

    # Investigate mode — return prose answer
    if mode == "investigate":
        answer = result.get(
            "answer",
            result.get("report_markdown", "No answer.")
        )
        return [types.TextContent(type="text", text=answer)]

    # Simulate mode — format report
    breaks     = result.get("total_breaks", 0)
    report     = result.get("report_markdown", "")
    mermaid    = result.get("mermaid_graph", "")
    nodes      = result.get("affected_nodes", [])
    elapsed    = result.get("elapsed_ms", 0)
    confidence = result.get("confidence_score", 1.0)

    red   = [n for n in nodes if n.get("risk_label") == "red"]
    amber = [n for n in nodes if n.get("risk_label") == "amber"]

    parts = [
        f"## Cascade Impact Simulation",
        f"**{breaks} functions at risk** · "
        f"{elapsed}ms · "
        f"confidence {int(confidence * 100)}%",
        "",
    ]

    if report.strip():
        parts.append(report)
    else:
        if red:
            parts.append("### 🔴 High Risk")
            for n in red[:5]:
                parts.append(
                    f"- `{n['name']}` in "
                    f"`{n.get('file','').split('/')[-1]}` "
                    f"— {n.get('break_reason','')}"
                )
        if amber:
            parts.append("### 🟡 Medium Risk")
            for n in amber[:5]:
                parts.append(
                    f"- `{n['name']}` in "
                    f"`{n.get('file','').split('/')[-1]}`"
                )

    if mermaid.strip():
        parts += ["", "```mermaid", mermaid, "```"]

    return [types.TextContent(
        type="text", text="\n".join(parts)
    )]


async def _handle_search(
    args: dict
) -> list[types.TextContent]:
    query = args.get("query", "")
    top_k = args.get("top_k", 8)
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{BACKEND_URL}/graph/search",
                json={"query": query, "top_k": top_k}
            )
            results = r.json().get("results", [])
        if not results:
            return [types.TextContent(
                type="text",
                text=f"No results for '{query}'."
            )]
        lines = [f"**Search: '{query}'**", ""]
        for r in results:
            score = int(r.get("score", 0) * 100)
            lines.append(
                f"- `{r['name']}` ({r['type']}) "
                f"in `{r['file']}` — {score}%"
            )
            if r.get("docstring"):
                lines.append(f"  _{r['docstring'][:80]}_")
        return [types.TextContent(
            type="text", text="\n".join(lines)
        )]
    except Exception as e:
        return [types.TextContent(
            type="text", text=f"Search error: {e}"
        )]


async def _handle_context(
    args: dict
) -> list[types.TextContent]:
    file_path = args.get("file_path", "")
    line      = args.get("line", 0)
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{BACKEND_URL}/graph/search",
                json={"query": file_path, "top_k": 20}
            )
            results = r.json().get("results", [])

        fp_norm = file_path.replace("\\", "/")
        matches = [
            x for x in results
            if fp_norm in x.get("file", "").replace("\\", "/")
        ]
        if not matches:
            return [types.TextContent(
                type="text",
                text=f"No nodes found in `{file_path}`."
            )]

        node_id  = matches[0]["node_id"]
        enc      = node_id.replace("/", "%2F")
        async with httpx.AsyncClient(timeout=10) as c:
            r2   = await c.get(
                f"{BACKEND_URL}/graph/node/{enc}"
            )
            detail = r2.json()

        data    = detail.get("data", {})
        callers = detail.get("callers", [])
        callees = detail.get("callees", [])

        lines = [
            f"**`{file_path}`"
            f"{f' line {line}' if line else ''}**",
            "",
            f"Function: `{data.get('name','?')}`",
            f"Type: {data.get('type','?')}",
            f"Lines: {data.get('line_start','?')}"
            f"–{data.get('line_end','?')}",
        ]
        if data.get("docstring"):
            lines.append(
                f"Docstring: {data['docstring'][:200]}"
            )
        if callers:
            names = [c.split("::")[-1] for c in callers[:5]]
            lines.append(f"Called by: {', '.join(names)}")
        if callees:
            names = [c.split("::")[-1] for c in callees[:5]]
            lines.append(f"Calls: {', '.join(names)}")
        if data.get("primary_author"):
            lines.append(
                f"Last author: {data['primary_author']} "
                f"({data.get('last_modified','')[:10]})"
            )
        return [types.TextContent(
            type="text", text="\n".join(lines)
        )]
    except Exception as e:
        return [types.TextContent(
            type="text", text=f"Context error: {e}"
        )]


# ── Entry point ───────────────────────────────────────────────

async def main():
    global BACKEND_URL, DEFAULT_REPO

    parser = argparse.ArgumentParser(
        description="Cascade MCP Server (standalone bridge)"
    )
    parser.add_argument(
        "--repo", default="",
        help="Repository path to load on start"
    )
    parser.add_argument(
        "--backend", default="http://127.0.0.1:5001",
        help="Cascade backend URL"
    )
    args         = parser.parse_args()
    BACKEND_URL  = args.backend
    DEFAULT_REPO = args.repo

    if DEFAULT_REPO:
        print(
            f"[Cascade MCP] Repo: {DEFAULT_REPO}",
            file=sys.stderr
        )
        await ensure_graph(DEFAULT_REPO)

    print(
        "[Cascade MCP] Ready on stdio",
        file=sys.stderr
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
