"""
Query mode classifier for Cascade.
Routes prompts to simulate or investigate pipeline.
No external dependencies beyond stdlib.
"""

from dataclasses import dataclass
import re
import httpx


SIMULATE_PATTERNS = [
    "what if", "rename", "replace", "remove",
    "refactor", "extract", "migrate", "upgrade",
    "delete", "move", "split", "merge",
    "what happens if", "if i change", "if we change",
    "if i replace", "if we replace", "if i remove",
    "if we remove", "if i add", "if we add",
    "break if", "fail if",
]

INVESTIGATE_PATTERNS = [
    "what does", "what is", "explain",
    "how does", "how is", "how do",
    "why does", "why is", "why was",
    "when is", "when does", "when was",
    "who calls", "what calls", "what uses",
    "where is", "where does",
    "show me", "describe", "tell me",
    "which functions", "which modules", "which nodes",
    "list all", "what are",
]

STOPWORDS = {
    "what", "does", "the", "this", "that", "with",
    "from", "into", "have", "when", "where", "how",
    "why", "who", "can", "will", "would", "should",
    "and", "or", "for", "not", "but", "all", "any",
    "our", "your", "their", "its", "are", "was",
    "function", "method", "class", "module", "file",
    "code", "change", "rename", "replace", "remove",
    "called", "uses", "using", "used", "make", "need",
    "doing", "done", "about", "like", "just", "then",
    "there", "here", "they", "them", "some", "more",
}


@dataclass
class QueryIntent:
    mode:       str   # "simulate" | "investigate"
    target:     str   # extracted target name
    raw_prompt: str


async def classify_query(prompt: str, llama_url: str = None, api_key: str = "", model_name: str = "local") -> QueryIntent:
    lower = prompt.lower().strip()
    target = _extract_target(prompt)

    # 1. Fast heuristic keyword check
    for pattern in SIMULATE_PATTERNS:
        if pattern in lower:
            return QueryIntent(mode="simulate", target=target, raw_prompt=prompt)

    for pattern in INVESTIGATE_PATTERNS:
        if pattern in lower:
            return QueryIntent(mode="investigate", target=target, raw_prompt=prompt)

    # 2. LLM Smart Fallback
    mode = "simulate" # default if everything fails
    if llama_url:
        try:
            system = "You classify developer queries into two categories: 'SIMULATE' (asking what happens if code changes) or 'INVESTIGATE' (asking how existing code works). Reply with exactly 1 word: SIMULATE or INVESTIGATE."
            
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{llama_url}/chat/completions" if "/v1" in llama_url else f"{llama_url}/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 10,
                        "temperature": 0.0,
                    }
                )
                resp.raise_for_status()
                ans = resp.json()["choices"][0]["message"]["content"].upper()
                if "INVESTIGATE" in ans:
                    mode = "investigate"
                elif "SIMULATE" in ans:
                    mode = "simulate"
        except Exception as e:
            print(f"[Classifier] Fast LLM routing failed: {e}")

    return QueryIntent(
        mode=mode,
        target=target,
        raw_prompt=prompt
    )


def _extract_target(prompt: str) -> str:
    # 1. Look for explicit code shapes: camelCase, PascalCase, snake_case
    code_words = re.findall(
        r'\b(?:[a-z]+[A-Z][a-zA-Z0-9]*|[A-Z][a-zA-Z0-9]+|[a-z]+_[a-zA-Z0-9_]+)\b', 
        prompt
    )
    filtered_code = [c for c in code_words if c.lower() not in STOPWORDS]
    if filtered_code:
        return filtered_code[0]

    # 2. Fallback to any word > 2 chars
    words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', prompt)
    filtered = [w for w in words if w.lower() not in STOPWORDS]
    return filtered[0] if filtered else prompt[:40]
