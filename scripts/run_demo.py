#!/usr/bin/env python3
"""End-to-end demo of the M0 mock pipeline.

Run from the repo root after `pip install -e .`:

    python scripts/run_demo.py --scenario interrupted
    python scripts/run_demo.py --scenario clean_run

The "interrupted" scenario is the interesting one — it exercises the
dynamic subtask insertion path (a cup appears on the table mid-task,
the orchestrator inserts `pickup_movable_obstacle` ahead of the
failing `wipe_table`, and then resumes).
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from robohousekeeper_agent.brain import Orchestrator, Planner, SelfEval
from robohousekeeper_agent.brain.orchestrator import OrchestratorConfig
from robohousekeeper_agent.executor import MockExecutor
from robohousekeeper_agent.memory import MemoryManager
from robohousekeeper_agent.perception import MockPerception
from robohousekeeper_agent.skills import SkillLibrary


SKILLS_DIR = Path(__file__).resolve().parent.parent / "src" / "robohousekeeper_agent" / "skills" / "library"

# Shorthand task names → instruction strings.
# Add new entries here as the skill library grows.
TASK_INSTRUCTIONS: dict[str, str] = {
    "wipe_table":      "please wipe the table",
    "pickup_obstacle": "please move the obstacle",
    "navigate":        "please navigate to the target",
    "improve_policy":  "please improve the policy",
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--task",
        choices=sorted(TASK_INSTRUCTIONS),
        default=None,
        help="Shorthand task name. Overrides --instruction when set.",
    )
    p.add_argument(
        "--instruction",
        default="please wipe the table",
        help="Natural-language goal (ignored if --task is set).",
    )
    p.add_argument(
        "--scenario",
        choices=["clean_run", "interrupted"],
        default="interrupted",
        help="Which mock perception scenario to play back.",
    )
    p.add_argument("--home-dir", default=None, help="Where to store MEMORY.md etc.")
    args = p.parse_args()

    instruction = TASK_INSTRUCTIONS[args.task] if args.task else args.instruction

    home_dir = Path(args.home_dir) if args.home_dir else Path(tempfile.mkdtemp(prefix="rhk_"))
    print(f"[demo] home dir: {home_dir}")
    print(f"[demo] scenario: {args.scenario}")
    print(f"[demo] instruction: {instruction!r}")
    print()

    library = SkillLibrary(SKILLS_DIR)
    print(f"[demo] loaded {len(library)} skills: {[s.name for s in library.all()]}")

    perception = MockPerception(args.scenario)
    executor = MockExecutor(perception)
    memory = MemoryManager(home_dir)
    planner = Planner(library)
    self_eval = SelfEval()

    orch = Orchestrator(
        planner=planner,
        executor=executor,
        perception=perception,
        skill_library=library,
        memory=memory,
        self_eval=self_eval,
        config=OrchestratorConfig(
            heartbeat_interval=0.0,  # fire every loop in the demo
            self_eval_every_n_subtasks=2,
        ),
    )

    world_state = {"target_table": "table_1", "target": "table_1"}
    report = orch.run(instruction, world_state=world_state)

    print()
    print("=" * 60)
    print("RUN REPORT")
    print("=" * 60)
    print(json.dumps(_report_view(report), indent=2, ensure_ascii=False))
    print()
    print(self_eval.episode_summary(report))
    return 0 if report.status.value == "succeeded" else 1


def _report_view(r) -> dict:
    return {
        "status": r.status.value,
        "subtasks_attempted": r.subtasks_attempted,
        "subtasks_succeeded": r.subtasks_succeeded,
        "retries": r.retries,
        "replans": r.replans,
        "inserted_subtasks": r.inserted_subtasks,
        "lessons": r.lessons,
    }


if __name__ == "__main__":
    raise SystemExit(main())