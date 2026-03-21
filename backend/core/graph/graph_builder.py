"""
Graph Builder for Cascade.
Walks a repository, parses every supported file,
builds a NetworkX directed graph of entities,
attaches git memory, and persists to cache.
"""

import os
import pickle
from pathlib import Path
import networkx as nx

from core.graph.ast_parser import parse_file
from core.graph.git_memory import (
    get_repo, get_file_history, get_last_modified,
    get_blame_summary, get_node_history
)

SUPPORTED_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}
IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "target", "coverage",
    ".cache", "migrations", ".mypy_cache", ".pytest_cache"
}


def make_node_id(file_path: str, name: str, repo_root: str) -> str:
    rel = Path(file_path).relative_to(repo_root)
    return f"{str(rel).replace(os.sep, '/')}::{name}"


def make_module_id(file_path: str, repo_root: str) -> str:
    rel = Path(file_path).relative_to(repo_root)
    return f"{str(rel).replace(os.sep, '/')}::__module__"


class GraphBuilder:
    def __init__(self, repo_path: str, cache_dir: str, max_files: int = 5000):
        self.repo_path = str(Path(repo_path).resolve())
        self.cache_dir = cache_dir
        self.max_files = max_files
        self.G    = nx.DiGraph()
        self.repo = get_repo(self.repo_path)
        self.stats = {
            "files_parsed":  0,
            "files_skipped": 0,
            "nodes":         0,
            "edges":         0,
            "errors":        []
        }

    # ── Public API ──────────────────────────────────────────────

    def build(self, progress_callback=None) -> nx.DiGraph:
        """
        Full build: walk repo, parse all files, build graph.
        progress_callback(current, total, file_path) called per file.
        """
        all_files = self._collect_files()
        total     = min(len(all_files), self.max_files)

        if total == 0:
            return self.G

        for i, fp in enumerate(all_files[:total]):
            if progress_callback:
                progress_callback(i + 1, total, fp)
            self._process_file(fp)

        self._resolve_import_edges()
        self.stats["nodes"] = self.G.number_of_nodes()
        self.stats["edges"] = self.G.number_of_edges()
        self._save_cache()
        return self.G

    def update_file(self, file_path: str):
        """Incremental update: re-parse one changed file."""
        try:
            rel = str(
                Path(file_path).relative_to(self.repo_path)
            ).replace(os.sep, "/")
        except ValueError:
            return
        # Remove stale nodes from this file
        stale = [
            n for n, d in self.G.nodes(data=True)
            if d.get("file") == rel
        ]
        self.G.remove_nodes_from(stale)
        self._process_file(file_path)
        self._resolve_import_edges()
        self.stats["nodes"] = self.G.number_of_nodes()
        self.stats["edges"] = self.G.number_of_edges()
        self._save_cache()

    def load_cache(self) -> bool:
        cache_path = self._cache_path()
        if not os.path.exists(cache_path):
            return False
        try:
            with open(cache_path, "rb") as f:
                self.G = pickle.load(f)
            self.stats["nodes"] = self.G.number_of_nodes()
            self.stats["edges"] = self.G.number_of_edges()
            return True
        except Exception:
            return False

    def get_stats(self) -> dict:
        return {
            **self.stats,
            "nodes": self.G.number_of_nodes(),
            "edges": self.G.number_of_edges()
        }

    # ── Internal ────────────────────────────────────────────────

    def _collect_files(self) -> list:
        files = []
        for root, dirs, filenames in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for fn in filenames:
                if Path(fn).suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append(os.path.join(root, fn))
        return sorted(files)

    def _process_file(self, file_path: str):
        parsed = parse_file(file_path)
        if parsed["error"]:
            self.stats["errors"].append(f"{file_path}: {parsed['error']}")
            self.stats["files_skipped"] += 1
            return

        rel_path = str(
            Path(file_path).relative_to(self.repo_path)
        ).replace(os.sep, "/")

        # Git memory
        blame         = {}
        last_modified = None
        file_history  = []
        if self.repo:
            blame         = get_blame_summary(self.repo, file_path)
            last_modified = get_last_modified(self.repo, file_path)
            file_history  = get_file_history(self.repo, file_path, max_commits=10)

        # Module node
        module_id = make_module_id(file_path, self.repo_path)
        self.G.add_node(module_id, **{
            "type":           "module",
            "name":           Path(file_path).stem,
            "file":           rel_path,
            "language":       parsed["language"],
            "primary_author": blame.get("primary_author", ""),
            "last_modified":  last_modified or "",
            "last_commit":    blame.get("last_commit_message", ""),
            "history":        file_history[:5],
            "_imports":       parsed["imports"],
            "_calls":         parsed["calls"]
        })

        # Function nodes
        for fn in parsed["functions"]:
            node_id      = make_node_id(file_path, fn["name"], self.repo_path)
            node_history = []
            if self.repo:
                node_history = get_node_history(
                    self.repo, file_path,
                    fn["line_start"], fn["line_end"],
                    max_commits=5
                )
            self.G.add_node(node_id, **{
                "type":           "method" if fn["is_method"] else "function",
                "name":           fn["name"],
                "file":           rel_path,
                "language":       parsed["language"],
                "line_start":     fn["line_start"],
                "line_end":       fn["line_end"],
                "docstring":      fn["docstring"],
                "params":         fn["params"],
                "is_async":       fn["is_async"],
                "primary_author": blame.get("primary_author", ""),
                "last_modified":  last_modified or "",
                "history":        node_history
            })
            self.G.add_edge(module_id, node_id, edge_type="contains")

        # Class nodes
        for cls in parsed["classes"]:
            cls_id = make_node_id(file_path, cls["name"], self.repo_path)
            self.G.add_node(cls_id, **{
                "type":           "class",
                "name":           cls["name"],
                "file":           rel_path,
                "language":       parsed["language"],
                "line_start":     cls["line_start"],
                "line_end":       cls["line_end"],
                "docstring":      cls["docstring"],
                "bases":          cls["bases"],
                "methods":        cls["methods"],
                "primary_author": blame.get("primary_author", ""),
                "last_modified":  last_modified or "",
                "history":        []
            })
            self.G.add_edge(module_id, cls_id, edge_type="contains")

        self.stats["files_parsed"] += 1

    def _resolve_import_edges(self):
        """
        Second pass: resolve import statements to actual module nodes.
        Adds import and call edges between nodes.
        """
        # Build name → node_id lookup
        name_lookup: dict[str, str] = {}
        for node_id, data in self.G.nodes(data=True):
            if data.get("type") == "module":
                name_lookup[data.get("name", "")] = node_id
                file_stem = Path(data.get("file", "")).stem
                name_lookup[file_stem] = node_id

        for node_id, data in list(self.G.nodes(data=True)):
            if data.get("type") != "module":
                continue

            imports = data.pop("_imports", [])
            calls   = data.pop("_calls", [])

            for imp in imports:
                module_name = imp["module"].split(".")[-1]
                target = name_lookup.get(module_name)
                if target and target != node_id:
                    self.G.add_edge(
                        node_id, target,
                        edge_type="imports",
                        names=imp.get("names", []),
                        is_wildcard="*" in imp.get("names", [])
                    )

            for call in calls:
                if call["is_dynamic"]:
                    continue
                callee_name = call["callee"]
                for candidate_id, cdata in self.G.nodes(data=True):
                    if (
                        cdata.get("name") == callee_name
                        and cdata.get("type") in ("function", "method")
                        and candidate_id != node_id
                    ):
                        self.G.add_edge(
                            node_id, candidate_id,
                            edge_type="calls",
                            is_dynamic=False
                        )
                        break

    def _cache_path(self) -> str:
        safe = (self.repo_path
                .replace(":", "_")
                .replace("\\", "_")
                .replace("/", "_"))
        return os.path.join(self.cache_dir, f"{safe}.pkl")

    def _save_cache(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self._cache_path(), "wb") as f:
            pickle.dump(self.G, f)
