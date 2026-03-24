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


async def run_intent_agent(
    state: SimulationState,
    llama_url: str,
    node_names: list[str]
) -> SimulationState:
    """
    Calls local LLM to parse the prompt into a SeedEvent.
    node_names: list of all node names in the graph (for context).
    """
    # Give the LLM context about what exists in the graph
    # Limit to 150 names to avoid context overflow on 4B model
    name_sample = node_names[:150]
    user_msg = f"""Available code entities in this codebase:
{', '.join(name_sample)}

Change request: {state.prompt}

Extract the intent as JSON:"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{llama_url}/v1/chat/completions",
                json={
                    "model": "local",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": user_msg}
                    ],
                    "max_tokens": 600,
                    "temperature": 0.1,
                }
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            
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
