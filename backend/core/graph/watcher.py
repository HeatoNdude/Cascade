"""
File watcher for Cascade.
Watches repo dir and triggers incremental graph updates.
Debounce: 800ms after last change event.
"""

import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

SUPPORTED_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}
DEBOUNCE_SECONDS     = 0.8
IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv",
    "venv", "dist", "build", ".next", "target"
}


class RepoEventHandler(FileSystemEventHandler):
    def __init__(self, on_change_callback):
        super().__init__()
        self.on_change  = on_change_callback
        self._pending: dict[str, float] = {}
        self._lock      = threading.Lock()
        self._timer     = None

    def on_modified(self, event):
        if not event.is_directory:
            self._queue(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._queue(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._queue(event.src_path)

    def _queue(self, path: str):
        p = Path(path)
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        for part in p.parts:
            if part in IGNORE_DIRS:
                return
        with self._lock:
            self._pending[path] = time.time()
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(DEBOUNCE_SECONDS, self._flush)
        self._timer.daemon = True
        self._timer.start()

    def _flush(self):
        with self._lock:
            changed = list(self._pending.keys())
            self._pending.clear()
        for path in changed:
            try:
                self.on_change(path)
            except Exception as e:
                print(f"[Cascade Watcher] Error on {path}: {e}")


class RepoWatcher:
    def __init__(self, repo_path: str, on_change_callback):
        self.repo_path = repo_path
        self.handler   = RepoEventHandler(on_change_callback)
        self.observer  = Observer()

    def start(self):
        self.observer.schedule(
            self.handler, self.repo_path, recursive=True
        )
        self.observer.start()
        print(f"[Cascade] Watching {self.repo_path}")

    def stop(self):
        self.observer.stop()
        self.observer.join()
        print("[Cascade] Watcher stopped.")
