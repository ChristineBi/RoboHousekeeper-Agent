"""Self-Eval — Hermes-style reflection checkpoint.

Hermes Agent fires self-eval every 15 tool calls; the prompt is
roughly *"what did I do, what worked, what failed, is anything worth
remembering?"* We do the same, but the cadence is per-N-subtasks
(subtasks are heavier than digital-world tool calls).

M0 implementation is rule-based and ~free. M1 will call an MLLM with
the trajectory summary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import SubTask
    from .orchestrator import RunReport


class SelfEval:
    """Produces short, plain-text 'lessons' to append to MEMORY.md / skill notes."""

    def checkpoint(
        self,
        report: "RunReport",
        plan: "list[SubTask]",
        current_index: int,
    ) -> str | None:
        """Return a lesson string if anything is worth recording, else None.

        M0 heuristics:
          * High retry ratio → flag the skill that needed retries.
          * Replan happened → record the trigger reason.
          * Otherwise → quiet (silence is golden; don't spam MEMORY.md).
        """
        if report.subtasks_attempted == 0:
            return None
        retry_ratio = report.retries / max(1, report.subtasks_attempted)
        if retry_ratio > 0.5:
            return (
                f"High retry ratio ({retry_ratio:.2f}) up to subtask {current_index}/"
                f"{len(plan)}. Consider lowering preconditions or reviewing the failing skill."
            )
        # Warn only when replanning has caught up with successes — meaning
        # every replan so far has not produced a successful subtask afterward.
        # A healthy replan (inserted pickup → wipe succeeds) has succeeded > replans.
        if report.replans > 0 and report.replans >= report.subtasks_succeeded:
            return (
                f"Replanned {report.replans} time(s) without forward progress — "
                "scene assumptions may be stale, force a heartbeat scan."
            )
        return None

    def episode_summary(self, report: "RunReport") -> str:
        """One-paragraph summary called when an episode finishes.

        Suitable for appending to ``episodes/`` and for later
        consumption by the offline skill-patching cron.
        """
        ok = "✓" if report.status.value == "succeeded" else "✗"
        return (
            f"{ok} '{report.instruction}': "
            f"{report.subtasks_succeeded}/{report.subtasks_attempted} subtasks succeeded, "
            f"{report.retries} retries, {report.replans} replans, "
            f"{report.inserted_subtasks} subtasks inserted. "
            f"Final status: {report.status.value}."
        )