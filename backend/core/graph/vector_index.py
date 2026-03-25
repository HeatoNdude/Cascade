"""
FAISS vector index for Cascade.
Embeds each graph node for semantic search.
Model: all-MiniLM-L6-v2 (CPU-only, ~80MB).
"""

import os
import pickle
import numpy as np
import faiss
import networkx as nx

MODEL_NAME    = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
ENABLE_LOCAL  = os.getenv("ENABLE_LOCAL_EMBEDDINGS", "false").lower() == "true"


class VectorIndex:
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self.model     = None
        self.index     = None
        self.node_ids  = []

    def _load_model(self):
        if not ENABLE_LOCAL:
            return
        if self.model is None:
            print("[Cascade] Loading embedding model (Local Resources)...")
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(MODEL_NAME)
            print("[Cascade] Embedding model ready.")

    def _node_to_text(self, node_id: str, data: dict) -> str:
        parts = [
            data.get("name", ""),
            data.get("type", ""),
            data.get("file", ""),
            data.get("docstring", ""),
        ]
        for h in data.get("history", [])[:3]:
            parts.append(h.get("message", ""))
        return " ".join(p for p in parts if p).strip()

    def build(self, G: nx.DiGraph):
        if not ENABLE_LOCAL:
            print("[Cascade] Local embeddings disabled. Skipping vector index build.")
            return

        self._load_model()
        self.node_ids = []
        texts         = []

        for node_id, data in G.nodes(data=True):
            text = self._node_to_text(node_id, data)
            if text:
                self.node_ids.append(node_id)
                texts.append(text)

        if not texts:
            return

        print(f"[Cascade] Embedding {len(texts)} nodes...")
        embeddings = self.model.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True
        ).astype(np.float32)

        faiss.normalize_L2(embeddings)
        self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
        self.index.add(embeddings)
        print(f"[Cascade] Vector index built: {self.index.ntotal} vectors.")
        self._save_cache()

    def search(self, query: str, top_k: int = 10) -> list:
        if not ENABLE_LOCAL or self.index is None or not self.node_ids:
            return []
        self._load_model()
        query_vec = self.model.encode(
            [query], convert_to_numpy=True
        ).astype(np.float32)
        faiss.normalize_L2(query_vec)
        scores, indices = self.index.search(
            query_vec, min(top_k, len(self.node_ids))
        )
        return [
            {"node_id": self.node_ids[idx], "score": float(score)}
            for score, idx in zip(scores[0], indices[0])
            if idx != -1
        ]

    def _cache_paths(self):
        return (
            os.path.join(self.cache_dir, "faiss.index"),
            os.path.join(self.cache_dir, "faiss_ids.pkl")
        )

    def _save_cache(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        index_path, ids_path = self._cache_paths()
        faiss.write_index(self.index, index_path)
        with open(ids_path, "wb") as f:
            pickle.dump(self.node_ids, f)

    def load_cache(self) -> bool:
        index_path, ids_path = self._cache_paths()
        if not os.path.exists(index_path) or not os.path.exists(ids_path):
            return False
        try:
            self.index = faiss.read_index(index_path)
            with open(ids_path, "rb") as f:
                self.node_ids = pickle.load(f)
            return True
        except Exception:
            return False
