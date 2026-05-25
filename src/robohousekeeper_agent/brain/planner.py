"""Planner — instruction → list of SubTasks.

M0 implementation is intentionally dumb (regex + trigger matching) so we
can wire up the end-to-end loop without depending on a heavy MLLM. M1
replaces ``decompose`` with a real RoboBrain call.
"""

from __future__ import annotations

from typing import Protocol

from ..skills import SkillLibrary
from ..types import SubTask


class PlannerBackend(Protocol):
    """Pluggable backend. Default is the heuristic one below; M1 swaps in RoboBrain."""

    def decompose(self, instruction: str, world_state: dict) -> list[SubTask]: ...


class Planner:
    """Default planner — heuristic match against skill triggers.

    Good enough to drive the M0 mock demo. The orchestrator does not
    care which backend produced the plan, so swapping this for an LLM
    call is a one-line change.
    """

    def __init__(self, skill_library: SkillLibrary, backend: PlannerBackend | None = None):
        self.skill_library = skill_library
        self.backend = backend

    def decompose(self, instruction: str, world_state: dict | None = None) -> list[SubTask]:
        world_state = world_state or {}
        if self.backend is not None:
            return self.backend.decompose(instruction, world_state)
        return self._heuristic_decompose(instruction, world_state)

    def _heuristic_decompose(self, instruction: str, world_state: dict) -> list[SubTask]:
        """Naive: pick all skills whose triggers match the instruction.

        Adds a ``navigate_to`` step before any manipulation skill that
        needs a target object — so even this dumb planner produces a
        non-trivial sequence.
        """
        matched = self.skill_library.find_by_trigger(instruction)
        if not matched:
            return []
        out: list[SubTask] = []
        for skill in matched:
            # If this skill takes a target_table / obstacle_id / target,
            # pre-navigate. Cheap and good for the demo.
            target_param = next(
                (p for p in ("target_table", "obstacle_id", "target") if p in skill.parameters),
                None,
            )
            if target_param and "navigate_to" in self.skill_library:
                out.append(
                    SubTask(
                        skill_name="navigate_to",
                        args={"target": world_state.get(target_param, "default_target")},
                    )
                )
            out.append(SubTask(skill_name=skill.name, args={}))
        return out

    # ---- Replanning ----

    def replan(
        self,
        original_plan: list[SubTask],
        failed_index: int,
        failure_reason: str,
        world_state: dict,
    ) -> list[SubTask]:
        """Produce a new plan that *replaces* the rest of the original.

        M0 strategy: if the failure mentions an obstacle, insert
        ``pickup_movable_obstacle`` before retrying the failed step.
        Otherwise re-decompose from the failed subtask's intent.
        """
        failed = original_plan[failed_index]
        rest = original_plan[failed_index:]
        if "obstacle" in failure_reason.lower() and "pickup_movable_obstacle" in self.skill_library:
            obstacle_id = world_state.get("blocking_obstacle_id", "unknown_obstacle")
            insert = SubTask(
                skill_name="pickup_movable_obstacle",
                args={"obstacle_id": obstacle_id},
                notes=f"inserted to clear obstacle blocking {failed.skill_name}",
            )
            return [insert, *rest]
        # Fallback: just retry the rest as-is, but reset retry_count.
        for st in rest:
            st.retry_count = 0
        return rest
