"""
Shared state schema for the Cascade simulation pipeline.
Passed through every agent in the LangGraph pipeline.
"""

from typing import Optional, Any
from dataclasses import dataclass, field


@dataclass
class SeedEvent:
    """Structured output from IntentAgent."""
    change_type: str          # replace|rename|remove|add|refactor
    target_names: list[str]   # function/class/module names to change
    description: str          # human readable change description
    scope: str                # local|module|cross-module


@dataclass
class AffectedNode:
    """One node in the blast radius."""
    node_id: str
    name: str
    file: str
    node_type: str
    risk_score: float          # 0.0 - 1.0
    risk_label: str            # green|amber|red
    hop_distance: int
    is_dynamic_path: bool
    break_reason: str          # why this breaks
    history_note: str          # relevant git history if any


@dataclass
class SimulationState:
    """Full state object passed through the pipeline."""
    # Input
    prompt: str               = ""
    repo_path: str            = ""

    # IntentAgent output
    seed_event: Optional[SeedEvent] = None
    seed_node_ids: list[str]  = field(default_factory=list)

    # TraversalAgent output
    traversal_result: list[dict] = field(default_factory=list)

    # Agent outputs
    affected_nodes: list[AffectedNode] = field(default_factory=list)
    affected_tests: list[dict]         = field(default_factory=list)
    history_notes: list[dict]          = field(default_factory=list)

    # SynthesisAgent output
    report_markdown: str      = ""
    mermaid_graph: str        = ""
    confidence_score: float   = 0.0
    total_breaks: int         = 0

    # Pipeline metadata
    status: str               = "pending"
    error: Optional[str]      = None
    elapsed_ms: int           = 0
