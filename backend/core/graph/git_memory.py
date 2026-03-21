"""
Git memory extraction for Cascade.
Extracts per-file commit history and blame data.
Attaches temporal context to graph nodes.
"""

from pathlib import Path
from typing import Optional
import git


def get_repo(repo_path: str) -> Optional[git.Repo]:
    try:
        return git.Repo(repo_path, search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        return None


def get_file_history(
    repo: git.Repo, file_path: str, max_commits: int = 20
) -> list:
    """Last max_commits commits touching file_path."""
    try:
        rel = Path(file_path).relative_to(Path(repo.working_dir))
        commits = list(repo.iter_commits(paths=str(rel), max_count=max_commits))
        return [
            {
                "hash":    c.hexsha[:8],
                "author":  c.author.name,
                "date":    c.committed_datetime.isoformat(),
                "message": c.message.strip()[:200]
            }
            for c in commits
        ]
    except Exception:
        return []


def get_last_modified(repo: git.Repo, file_path: str) -> Optional[str]:
    try:
        rel = Path(file_path).relative_to(Path(repo.working_dir))
        commits = list(repo.iter_commits(paths=str(rel), max_count=1))
        if commits:
            return commits[0].committed_datetime.isoformat()
    except Exception:
        pass
    return None


def get_blame_summary(repo: git.Repo, file_path: str) -> dict:
    """Most frequent committer + last commit info."""
    try:
        rel = Path(file_path).relative_to(Path(repo.working_dir))
        commits = list(repo.iter_commits(paths=str(rel), max_count=30))
        if not commits:
            return {}
        from collections import Counter
        authors = [c.author.name for c in commits]
        primary = Counter(authors).most_common(1)[0][0]
        last    = commits[0]
        return {
            "primary_author":      primary,
            "authors":             list(set(authors)),
            "last_commit_hash":    last.hexsha[:8],
            "last_commit_message": last.message.strip()[:200]
        }
    except Exception:
        return {}


def get_node_history(
    repo: git.Repo,
    file_path: str,
    line_start: int,
    line_end: int,
    max_commits: int = 10
) -> list:
    """
    Commits that touched lines [line_start, line_end].
    Uses git log -L; falls back to file-level history.
    """
    try:
        rel = str(
            Path(file_path).relative_to(Path(repo.working_dir))
        ).replace("\\", "/")
        result = repo.git.log(
            f"-L{line_start},{line_end}:{rel}",
            "--no-patch",
            "--format=%H|%an|%ai|%s",
            f"-n{max_commits}"
        )
        commits = []
        for line in result.strip().split("\n"):
            if not line.strip() or "|" not in line:
                continue
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commits.append({
                    "hash":    parts[0][:8],
                    "author":  parts[1],
                    "date":    parts[2],
                    "message": parts[3][:200]
                })
        return commits
    except Exception:
        return get_file_history(repo, file_path, max_commits)
