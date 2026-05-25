"""Orchestrator — runs a plan, handles failures, drives the 3-tier retry ladder.

This is where most of the Hermes-inspired logic lives:

* **Per-subtask checkpoint** — after each subtask we ask perception to
  refresh the scene graph and we let :class:`SelfEval` decide whether
  there's a lesson worth logging.
* **3-tier retry ladder** — see :data:`docs/RESEARCH.md § 5.3`. Minor →
  retry the same action; Parameter → ask the cerebellum to adjust;
  Major → ask the brain to replan; Unrecoverable → human handover.
* **Dynamic subtask insertion** — if perception reports a blocker that
  wasn't there at planning time, the planner's :meth:`replan` may
  *insert* a new subtask in front of the failed one (e.g. pick up a
  cup before continuing to wipe the table).
* **Heartbeat** — coarse periodic scan, decoupled from the per-action
  observation. Inspired by Hermes' 6-hour maintenance trigger; for the
  robot it runs in seconds.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..memory import MemoryManager
from ..skills import SkillLibrary
from ..types import (
    ExecutionResult,
    FailureSeverity,
    Observation,
    SubTask,
    TaskStatus,
)
from .planner import Planner
from .self_eval import SelfEval


# ---- Executor & Perception are plug-in interfaces -----------------------


class ExecutorProtocol:
    """Anything that can take a SubTask and return an ExecutionResult.

    The M0 mock executor lives in ``executor.mock``; M1 wraps a real VLA model.
    """

    def execute(self, subtask: SubTask) -> ExecutionResult: ...


class PerceptionProtocol:
    """Anything that can produce an Observation on demand."""

    def observe(self) -> Observation: ...


# ---- Orchestrator -------------------------------------------------------


@dataclass
class OrchestratorConfig:
    """Tunables for the run loop. All in seconds."""
    heartbeat_interval: float = 2.0       # how often we force a fresh scan
    self_eval_every_n_subtasks: int = 3   # Hermes uses 15 tool calls; subtasks are heavier
    max_subtask_retries: int = 2
    max_replans_per_task: int = 3


@dataclass
class RunReport:
    """Returned by :meth:`Orchestrator.run` — useful for benchmarking."""
    instruction: str
    status: TaskStatus
    subtasks_attempted: int = 0
    subtasks_succeeded: int = 0
    retries: int = 0
    replans: int = 0
    inserted_subtasks: int = 0
    lessons: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    ended_at: float = 0.0


class Orchestrator:
    def __init__(
        self,
        planner: Planner,
        executor: ExecutorProtocol,
        perception: PerceptionProtocol,
        skill_library: SkillLibrary,
        memory: MemoryManager,
        self_eval: SelfEval | None = None,
        config: OrchestratorConfig | None = None,
    ):
        self.planner = planner
        self.executor = executor
        self.perception = perception
        self.skills = skill_library
        self.memory = memory
        self.self_eval = self_eval or SelfEval()
        self.cfg = config or OrchestratorConfig()
        self._last_heartbeat: float = 0.0

    # ---- Main entry point ----

    def run(self, instruction: str, world_state: dict[str, Any] | None = None) -> RunReport:
        report = RunReport(instruction=instruction, status=TaskStatus.RUNNING)
        world_state = dict(world_state or {})
        plan = self.planner.decompose(instruction, world_state)
        if not plan:
            report.status = TaskStatus.FAILED
            report.lessons.append("Planner produced empty plan — no matching skills.")
            report.ended_at = time.time()
            return report

        i = 0
        replans_done = 0
        while i < len(plan):
            subtask = plan[i]
            self._maybe_heartbeat(world_state)
            result = self._execute_with_retries(subtask, report)

            if result.status == TaskStatus.SUCCEEDED:
                report.subtasks_succeeded += 1
                self.skills.record_outcome(subtask.skill_name, succeeded=True)
                i += 1
            elif result.status == TaskStatus.NEEDS_REPLAN:
                if replans_done >= self.cfg.max_replans_per_task:
                    report.status = TaskStatus.HUMAN_HANDOVER
                    report.lessons.append(
                        f"Gave up after {replans_done} replans on '{subtask.skill_name}'."
                    )
                    break
                old_len = len(plan)
                new_tail = self.planner.replan(plan, i, result.failure_reason, world_state)
                plan = plan[:i] + new_tail
                report.replans += 1
                report.inserted_subtasks += max(0, len(plan) - old_len)
                replans_done += 1
                self.skills.record_outcome(
                    subtask.skill_name,
                    succeeded=False,
                    lesson=f"replanned after: {result.failure_reason}",
                )
                # Don't advance i — try the (possibly new) subtask at this index.
            elif result.status == TaskStatus.HUMAN_HANDOVER:
                report.status = TaskStatus.HUMAN_HANDOVER
                report.lessons.append(
                    f"Hard escalation on '{subtask.skill_name}': {result.failure_reason}"
                )
                self.skills.record_outcome(
                    subtask.skill_name, succeeded=False, lesson=result.failure_reason
                )
                break
            else:
                # FAILED after retries exhausted, no replan available
                report.status = TaskStatus.FAILED
                report.lessons.append(
                    f"Failed permanently on '{subtask.skill_name}': {result.failure_reason}"
                )
                self.skills.record_outcome(
                    subtask.skill_name, succeeded=False, lesson=result.failure_reason
                )
                break

            # Hermes-style periodic self-eval
            if report.subtasks_attempted % self.cfg.self_eval_every_n_subtasks == 0:
                lesson = self.self_eval.checkpoint(report, plan, i)
                if lesson:
                    report.lessons.append(lesson)

        if report.status == TaskStatus.RUNNING:
            report.status = TaskStatus.SUCCEEDED

        report.ended_at = time.time()
        # Final episode log — feeds the offline skill-patching cron later.
        self.memory.log_episode(_report_to_dict(report))
        return report

    # ---- Internals ----

    def _execute_with_retries(
        self, subtask: SubTask, report: RunReport
    ) -> ExecutionResult:
        """3-tier ladder: minor retry → parameter retry → escalate."""
        last_result: ExecutionResult | None = None
        while subtask.retry_count <= self.cfg.max_subtask_retries:
            report.subtasks_attempted += 1
            result = self.executor.execute(subtask)
            last_result = result

            if result.status == TaskStatus.SUCCEEDED:
                return result

            # Failure: route by severity.
            sev = result.failure_severity
            if sev == FailureSeverity.MINOR:
                subtask.retry_count += 1
                report.retries += 1
                continue
            if sev == FailureSeverity.PARAMETER:
                subtask.retry_count += 1
                report.retries += 1
                # In a real system we'd patch subtask.args here based on the
                # failure reason. Mock-friendly: just retry.
                subtask.notes += f" | param-retry: {result.failure_reason}"
                continue
            if sev == FailureSeverity.MAJOR:
                # Bubble up to the orchestrator's replan loop.
                return ExecutionResult(
                    subtask=subtask,
                    status=TaskStatus.NEEDS_REPLAN,
                    failure_severity=sev,
                    failure_reason=result.failure_reason,
                    observation_after=result.observation_after,
                )
            if sev == FailureSeverity.UNRECOVERABLE:
                return ExecutionResult(
                    subtask=subtask,
                    status=TaskStatus.HUMAN_HANDOVER,
                    failure_severity=sev,
                    failure_reason=result.failure_reason,
                    observation_after=result.observation_after,
                )
            # Unknown severity → treat as minor.
            subtask.retry_count += 1
            report.retries += 1

        # Exhausted retries.
        return ExecutionResult(
            subtask=subtask,
            status=TaskStatus.FAILED,
            failure_severity=last_result.failure_severity if last_result else FailureSeverity.MAJOR,
            failure_reason=(
                last_result.failure_reason if last_result else "retries exhausted"
            ),
        )

    def _maybe_heartbeat(self, world_state: dict[str, Any]) -> None:
        """Coarse periodic scan, decoupled from per-action observation.

        The point isn't to *replace* the per-subtask observation — it's
        to catch slow environmental drift that no individual subtask
        would have noticed.
        """
        now = time.time()
        if now - self._last_heartbeat < self.cfg.heartbeat_interval:
            return
        self._last_heartbeat = now
        obs = self.perception.observe()
        self.memory.update_scene(obs.scene_graph)
        # Surface any blocker into world_state so the planner can use it on replan.
        for oid, obj in obs.scene_graph.objects.items():
            if obj.attributes.get("is_obstacle"):
                world_state["blocking_obstacle_id"] = oid
                break


def _report_to_dict(r: RunReport) -> dict[str, Any]:
    return {
        "instruction": r.instruction,
        "status": r.status.value,
        "subtasks_attempted": r.subtasks_attempted,
        "subtasks_succeeded": r.subtasks_succeeded,
        "retries": r.retries,
        "replans": r.replans,
        "inserted_subtasks": r.inserted_subtasks,
        "lessons": r.lessons,
        "started_at": r.started_at,
        "ended_at": r.ended_at,
    }
