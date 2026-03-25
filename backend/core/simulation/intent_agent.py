"""
IntentAgent for Cascade.
Parses a natural language "what if" prompt into a
structured SeedEvent using the local LLM.
Never receives source code — only node names.
"""

import json
import re
import httpx
from core.simulation.state import SeedEvent, SimulationState

SYSTEM_PROMPT = """You are a code change intent parser for a codebase simulation tool.

Given a natural language description of a code change, extract:
1. change_type: one of [replace, rename, remove, add, refactor]
2. target_names: list of function/class/module names being changed
3. description: clear one-sentence description of the change
4. scope: one of [local, module, cross-module]

Respond ONLY with a valid JSON object. No preamble. No explanation.
No markdown. No code blocks. Just the raw JSON object.

Example input: "replace Redis with Dragonfly in the caching layer"
Example output:
{"change_type":"replace","target_names":["Redis","RedisClient","cache_set","cache_get"],"description":"Replace Redis with Dragonfly as the caching backend","scope":"cross-module"}"""


async def run_intent_agent(state: SimulationState, llama_url: str, api_key: str = "", model_name: str = "local", node_names: list[str] = None) -> SimulationState:
    """
    Zero-shot parse logic.
    1) Determine if the change intends to "refactor", "remove", "add", "modify".
    2) Extract the likely target nodes from the user's string.
    """
    print(f"[IntentAgent] Asking local LLM to parse intent for: {state.prompt[:50]}...")

    val_nodes = ""
    if node_names:
        # Give LLM a hint of valid known nodes
        val_nodes = f"Known valid node names include: {', '.join(node_names[:100])} (truncated if too long)."

    prompt = f"""
    You are an AI tasked with parsing a developer's simulation request.
    {val_nodes}

    User prompt: "{state.prompt}"

    Return JSON matching this schema:
    {{
      "change_type": "refactor" | "remove" | "add" | "modify",
      "target_names": ["list", "of", "exact", "node", "names"],
      "description": "Short reasoning"
    }}

    Output ONLY JSON. Do not output markdown, no backticks, no thinking tags.
    """

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{llama_url}/chat/completions" if "/v1" in llama_url else f"{llama_url}/v1/chat/completions",
                headers=headers,
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 150,
                }
            )
        import re
        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

        # Extract JSON from response (model may add preamble)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON found in LLM response: {raw[:200]}")

        data = json.loads(json_match.group())
        state.seed_event = SeedEvent(
            change_type  = data.get("change_type", "refactor"),
            target_names = data.get("target_names", []),
            description  = data.get("description", state.prompt),
            scope        = data.get("scope", "module")
        )

    except Exception as e:
        # Fallback: simple keyword extraction
        print(f"[IntentAgent] LLM failed ({e}), using keyword fallback")
        import string
        
        # Clean prompt words: remove ?,., etc.
        clean_words = [w.strip(string.punctuation) for w in state.prompt.split() if w]
        
        # Target heuristics: CamelCase, snake_case, kebab-case
        words = [w for w in clean_words
                 if len(w) > 3 and (w[0].isupper() or '_' in w or '-' in w)]
                 
        # Match against known node names
        matched = [n for n in node_names
                   if any(w.lower() in n.lower()
                          for w in clean_words
                          if len(w) > 3)][:10]
                          
        state.seed_event = SeedEvent(
            change_type  = "refactor",
            target_names = matched or words[:5],
            description  = state.prompt,
            scope        = "module"
        )

    return state
