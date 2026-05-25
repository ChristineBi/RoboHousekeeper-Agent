"""Mock perception — scripted scene changes for end-to-end demos.

The point of this module is to exercise the orchestrator's dynamic
subtask insertion and replan paths without needing a sim or robot.
Each call to :meth:`observe` returns the next scripted snapshot.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

from ..types import Observation, Pose, SceneGraph, SceneObject


def _empty_table_scene() -> SceneGraph:
    g = SceneGraph(timestamp=time.time())
    g.objects["table_1"] = SceneObject(
        object_id="table_1",
        category="table",
        pose=Pose(x=1.0, y=0.0, z=0.75),
        attributes={"surface_dirty": True},
    )
    return g


def _table_with_cup_scene() -> SceneGraph:
    g = _empty_table_scene()
    g.objects["cup_1"] = SceneObject(
        object_id="cup_1",
        category="cup",
        pose=Pose(x=1.0, y=0.0, z=0.78),
        attributes={"is_obstacle": True, "liquid_inside": False, "fragile": True},
    )
    g.relations.append(("cup_1", "on", "table_1"))
    return g


def _table_clean_scene() -> SceneGraph:
    g = _empty_table_scene()
    g.objects["table_1"].attributes["surface_dirty"] = False
    return g


PRESET_SCENARIOS: dict[str, list[SceneGraph]] = {
    # The 'interrupted' scenario is the one we care about for the demo:
    # the agent starts wiping a clean-looking table, but mid-task a cup
    # appears (someone put it down). The orchestrator should insert
    # `pickup_movable_obstacle` and then continue.
    #
    # Frame timeline (each `observe()` consumes one):
    #   0: nav heartbeat → empty table  (planner saw a clean table)
    #   1: wipe heartbeat → cup on table (oh no, blocker appeared)
    #   2: after replan, before pickup → still cup on table
    #   3: after pickup_movable_obstacle's heartbeat → cup gone
    #   4+ : table clean
    "interrupted": [
        _empty_table_scene(),
        _table_with_cup_scene(),
        _table_with_cup_scene(),
        _empty_table_scene(),
        _table_clean_scene(),
    ],
    "clean_run": [
        _empty_table_scene(),
        _empty_table_scene(),
        _table_clean_scene(),
    ],
}


class MockPerception:
    """Plays back a scripted scenario, cycling on the last frame."""

    def __init__(self, scenario: str | Iterable[SceneGraph] = "clean_run"):
        if isinstance(scenario, str):
            if scenario not in PRESET_SCENARIOS:
                raise ValueError(
                    f"unknown scenario {scenario!r}; "
                    f"available: {sorted(PRESET_SCENARIOS)}"
                )
            self._frames = list(PRESET_SCENARIOS[scenario])
        else:
            self._frames = list(scenario)
        self._i = 0

    def observe(self) -> Observation:
        frame = self._frames[min(self._i, len(self._frames) - 1)]
        self._i += 1
        return Observation(
            timestamp=time.time(),
            scene_graph=frame,
        )

    def peek(self) -> Observation:
        """Like :meth:`observe` but does not advance the frame cursor.

        Used by the mock executor — in a real system the cerebellum has
        its own sensor stream and shouldn't consume the brain-level
        perception scan.
        """
        frame = self._frames[min(self._i, len(self._frames) - 1)]
        return Observation(
            timestamp=time.time(),
            scene_graph=frame,
        )
