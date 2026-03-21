import json
import httpx
from typing import Optional, Dict

class LLMRouter:
    def __init__(self, settings: dict):
        self.settings = settings
        self.backend = settings.get("llm_backend", "local")
        
        self.local_server_url = settings.get("local_server_url", "http://127.0.0.1:8080")
        self.openrouter_key = settings.get("openrouter_key", "")

    async def complete(self, system: str, prompt: str) -> dict:
        if self.backend == "local":
            return await self._generate_local(system, prompt)
        elif self.backend == "openrouter":
            if not self.openrouter_key:
                return {"text": "Error: OpenRouter key not configured.", "backend": "openrouter"}
            return await self._generate_openrouter(system, prompt)
        else:
            return {"text": f"Error: Unknown backend '{self.backend}'", "backend": "error"}

    async def _generate_local(self, system: str, prompt: str) -> dict:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.local_server_url}/v1/chat/completions",
                    json={
                        "model": "local",
                        "messages": messages,
                        "max_tokens": 1024,
                        "temperature": 0.7
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                if 'choices' in data and len(data['choices']) > 0:
                    answer = data['choices'][0]['message'].get('content', '')
                    return {"text": answer + "\n\n*(via local-qwen native server)*", "backend": "local"}
                
                return {"text": str(data), "backend": "local"}
        except Exception as e:
            return {"text": f"Error communicating with local llama-server: {e}\nIs llama-server.exe running on {self.local_server_url}?", "backend": "local"}

    async def _generate_openrouter(self, system: str, prompt: str) -> dict:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "HTTP-Referer": "http://localhost:1420",
            "X-Title": "Cascade Local"
        }
        data = {
            "model": "qwen/qwen-2.5-coder-32b-instruct",
            "messages": messages
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://api.openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=data
                )
                response.raise_for_status()
                res_json = response.json()
                
                if 'choices' in res_json and len(res_json['choices']) > 0:
                    answer = res_json['choices'][0]['message'].get('content', '')
                    return {"text": answer + "\n\n*(via OpenRouter cloud)*", "backend": "openrouter"}
                
                return {"text": str(res_json), "backend": "openrouter"}
        except Exception as e:
            return {"text": f"OpenRouter Error: {str(e)}", "backend": "openrouter"}
