"""Core dataclasses shared across brain / perception / executor.

Keeping the types in one place avoids circular imports and makes it
easier to swap concrete implementations behind a stable interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NEEDS_REPLAN = "needs_replan"
    HUMAN_HANDOVER = "human_handover"


class FailureSeverity(str, Enum):
    """How bad is a failure — drives the 3-tier retry policy.

    See docs/RESEARCH.md § 5.3 for the retry / replan / handover ladder.
    """
    NONE = "none"
    MINOR = "minor"        # same action, just retry
    PARAMETER = "parameter"  # adjust pose / force then retry
    MAJOR = "major"        # bail out, ask brain to replan
    UNRECOVERABLE = "unrecoverable"  # human handover


@dataclass
class Pose:
    """Minimal 6-DoF pose. Real implementation will use a proper SE(3) type."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass
class SceneObject:
    """One entry in the scene graph."""
    object_id: str
    category: str            # e.g. "cup", "trash", "table"
    pose: Pose
    attributes: dict[str, Any] = field(default_factory=dict)
    # e.g. {"liquid_inside": True, "fragile": True, "is_obstacle": True}


@dataclass
class SceneGraph:
    """Lightweight scene representation passed between perception and brain.

    Inspired by Scene Graph-Guided Proactive Replanning (arXiv:2508.11286).
    """
    timestamp: float
    objects: dict[str, SceneObject] = field(default_factory=dict)
    relations: list[tuple[str, str, str]] = field(default_factory=list)
    # relations as (subject_id, predicate, object_id), e.g. ("cup_1", "on", "table_1")

    def diff(self, other: "SceneGraph") -> dict[str, Any]:
        """Quick-and-dirty diff against another scene graph.

        Used to detect "the scene changed mid-execution → maybe replan".
        Returns a dict summarizing added / removed / changed objects.
        """
        added = set(self.objects) - set(other.objects)
        removed = set(other.objects) - set(self.objects)
        changed = {
            oid for oid in set(self.objects) & set(other.objects)
            if self.objects[oid] != other.objects[oid]
        }
        return {"added": added, "removed": removed, "changed": changed}


@dataclass
class Observation:
    """A snapshot from perception — fed into brain on every checkpoint."""
    timestamp: float
    scene_graph: SceneGraph
    # Cheap to keep raw modalities optional — depends on what perception emits.
    rgb_path: str | None = None
    depth_path: str | None = None
    proprioception: dict[str, float] = field(default_factory=dict)
    last_action_succeeded: bool | None = None
    failure_message: str | None = None


@dataclass
class SubTask:
    """One step in the plan produced by the brain.

    Mirrors a Hermes-style 'tool call', but the tool is a robot skill
    rather than a Python function.
    """
    skill_name: str                # which SKILL.md to invoke
    args: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 2
    parent_task: str | None = None  # task id of the parent plan
    notes: str = ""                 # free-form, for self-eval to consume


@dataclass
class ExecutionResult:
    """What the executor returns to the brain for a single SubTask."""
    subtask: SubTask
    status: TaskStatus
    failure_severity: FailureSeverity = FailureSeverity.NONE
    failure_reason: str = ""
    observation_after: Observation | None = None
    # Optional: a short natural-language summary that self-eval can ingest.
    summary: str = ""
