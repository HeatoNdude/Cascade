import urllib.request
import os

url = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
out_path = "C:\\llm\\models\\Qwen2.5-0.5B-Instruct-Q4_K_M.gguf"

print(f"Downloading {url} to {out_path}...")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
urllib.request.urlretrieve(url, out_path)
print("Download complete!")
