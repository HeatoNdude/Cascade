"""
Global singleton state for Cascade.
Shared across all FastAPI routes.
"""

from typing import Optional
from core.graph.graph_builder import GraphBuilder
from core.graph.vector_index import VectorIndex
from core.graph.watcher import RepoWatcher


class CascadeState:
    def __init__(self):
        self.builder:        Optional[GraphBuilder] = None
        self.vector:         Optional[VectorIndex]  = None
        self.watcher:        Optional[RepoWatcher]  = None
        self.repo_path:      Optional[str]          = None
        self.is_building:    bool                   = False
        self.build_progress: dict = {
            "current":      0,
            "total":        0,
            "current_file": "",
            "status":       "idle"
        }

    def reset(self):
        if self.watcher:
            self.watcher.stop()
        self.builder        = None
        self.vector         = None
        self.watcher        = None
        self.repo_path      = None
        self.is_building    = False
        self.build_progress = {
            "current":      0,
            "total":        0,
            "current_file": "",
            "status":       "idle"
        }


# Singleton imported by all route modules
cascade = CascadeState()
