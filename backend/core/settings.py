import json
import os
from dotenv import load_dotenv

# Load from .env file if it exists in backend/
load_dotenv()

SETTINGS_PATH = r"D:\Projects\cascade\cascade\settings.json"

DEFAULT_SETTINGS = {
    "llm_backend": "local",
    "openrouter_key": os.getenv("LLM_API_KEY", ""),
    "openrouter_model": os.getenv("LLM_MODEL", "qwen/qwen-2.5-72b-instruct"),
    "local_model_path": r"C:\llm\models\Qwen2.5-0.5B-Instruct-Q4_K_M.gguf",
    "llama_cpp_path": r"C:\llm",
    "llama_server_url": os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080"),
    "n_gpu_layers": 28,
    "max_repo_files": 5000,
    "supported_langs": ["python", "typescript", "javascript"],
    "send_code_to_cloud": False
}


def load_settings() -> dict:
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    with open(SETTINGS_PATH, "r") as f:
        stored = json.load(f)
    merged = DEFAULT_SETTINGS.copy()
    merged.update(stored)
    return merged


def save_settings(settings: dict):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
