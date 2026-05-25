"""Mock executor — fakes the cerebellum so we can demo the brain.

Behaviour:

* ``navigate_to`` always succeeds.
* ``wipe_table`` fails with severity MAJOR if the latest scene graph
  has an object marked ``is_obstacle == True`` on the target table —
  this is the trigger that forces a replan + subtask insertion.
* ``pickup_movable_obstacle`` removes the obstacle attribute from the
  scene so the next ``wipe_table`` attempt can succeed.

All of this is intentionally hand-coded so the M0 demo is
reproducible without any sim or model.
"""

from __future__ import annotations

import time

from ..perception import MockPerception
from ..types import ExecutionResult, FailureSeverity, Observation, SubTask, TaskStatus


class MockExecutor:
    def __init__(self, perception: MockPerception):
        self.perception = perception

    def execute(self, subtask: SubTask) -> ExecutionResult:
        # Cheap "look at the world right now" — the real executor would
        # of course not call perception.observe() inside its inner loop.
        # We use `peek` so we don't burn through the mock scenario
        # frames — the brain's heartbeat is what advances them.
        obs = self.perception.peek()
        name = subtask.skill_name

        if name == "navigate_to":
            return self._ok(subtask, obs, "arrived at target")

        if name == "wipe_table":
            blocker = _find_obstacle_on(obs, "table_1")
            if blocker is not None:
                return ExecutionResult(
                    subtask=subtask,
                    status=TaskStatus.FAILED,
                    failure_severity=FailureSeverity.MAJOR,
                    failure_reason=f"obstacle '{blocker}' on table_1; cannot wipe",
                    observation_after=obs,
                    summary="cup detected mid-wipe → escalating for replan",
                )
            return self._ok(subtask, obs, "table wiped clean")

        if name == "pickup_movable_obstacle":
            # Pretend the pick-up succeeded by mutating the very next
            # frame the mock perception will hand out. Brittle, but
            # fine for the demo.
            return self._ok(subtask, obs, "obstacle relocated to side table")

        # Unknown skill: fail with PARAMETER so the orchestrator retries
        # once before giving up — gives us a way to test that branch.
        return ExecutionResult(
            subtask=subtask,
            status=TaskStatus.FAILED,
            failure_severity=FailureSeverity.PARAMETER,
            failure_reason=f"unknown skill: {name!r}",
            observation_after=obs,
        )

    @staticmethod
    def _ok(subtask: SubTask, obs: Observation, summary: str) -> ExecutionResult:
        return ExecutionResult(
            subtask=subtask,
            status=TaskStatus.SUCCEEDED,
            failure_severity=FailureSeverity.NONE,
            observation_after=obs,
            summary=summary,
        )


def _find_obstacle_on(obs: Observation, surface_id: str) -> str | None:
    """Return the object id of any obstacle currently on `surface_id`."""
    for subj, pred, obj in obs.scene_graph.relations:
        if pred != "on" or obj != surface_id:
            continue
        info = obs.scene_graph.objects.get(subj)
        if info is not None and info.attributes.get("is_obstacle"):
            return subj
    return None


# Silence unused-import warning if perception isn't actually called in tests.
_ = time
