"""Smoke tests for the M0 pipeline.

Run with:  pytest tests/
"""

from pathlib import Path

from robohousekeeper_agent.brain import Orchestrator, Planner, SelfEval
from robohousekeeper_agent.brain.orchestrator import OrchestratorConfig
from robohousekeeper_agent.executor import MockExecutor
from robohousekeeper_agent.memory import MemoryManager
from robohousekeeper_agent.perception import MockPerception
from robohousekeeper_agent.skills import SkillLibrary


SKILLS_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "robohousekeeper_agent" / "skills" / "library"
)


def _build_orch(tmp_path, scenario):
    library = SkillLibrary(SKILLS_DIR)
    perception = MockPerception(scenario)
    executor = MockExecutor(perception)
    memory = MemoryManager(tmp_path)
    planner = Planner(library)
    return Orchestrator(
        planner=planner,
        executor=executor,
        perception=perception,
        skill_library=library,
        memory=memory,
        self_eval=SelfEval(),
        config=OrchestratorConfig(heartbeat_interval=0.0),
    ), library


def test_skill_library_loads_all_skills(tmp_path):
    lib = SkillLibrary(SKILLS_DIR)
    names = {s.name for s in lib.all()}
    expected = {"wipe_table", "pickup_movable_obstacle", "navigate_to", "improve_policy"}
    assert expected.issubset(names)


def test_clean_run_succeeds(tmp_path):
    orch, _ = _build_orch(tmp_path, "clean_run")
    report = orch.run(
        "please wipe the table",
        world_state={"target_table": "table_1", "target": "table_1"},
    )
    assert report.status.value == "succeeded"
    assert report.replans == 0
    assert report.inserted_subtasks == 0


def test_interrupted_scenario_triggers_replan_and_insertion(tmp_path):
    """The cup-on-table scenario should cause a replan + 1 inserted subtask."""
    orch, _ = _build_orch(tmp_path, "interrupted")
    report = orch.run(
        "please wipe the table",
        world_state={"target_table": "table_1", "target": "table_1"},
    )
    # We don't strictly require success — the point is that the
    # orchestrator detected the obstacle and inserted a subtask.
    assert report.replans >= 1
    assert report.inserted_subtasks >= 1


def test_memory_logs_episode(tmp_path):
    orch, _ = _build_orch(tmp_path, "clean_run")
    orch.run(
        "please wipe the table",
        world_state={"target_table": "table_1", "target": "table_1"},
    )
    eps = list((tmp_path / "episodes").glob("episode_*.json"))
    assert len(eps) >= 1


# ---- training module (M4 stubs) ----

def test_training_config_is_a_clean_dataclass(tmp_path):
    """Cheap smoke test that TrainingConfig stays dependency-free."""
    from robohousekeeper_agent.training import TrainingConfig
    cfg = TrainingConfig(dataset_path=tmp_path, output_dir=tmp_path / "ckpt")
    assert cfg.base_model == "lerobot/smolvla_base"
    assert cfg.steps > 0


def test_ab_eval_promotion_rules():
    """The worst-task floor that diverges from hermes-embodied must hold."""
    from robohousekeeper_agent.training import EvalResult, should_promote

    inc = EvalResult(
        checkpoint="/tmp/old",
        per_task_success={"task_a": 0.50, "task_b": 0.50, "task_c": 0.80},
        mean_reward=0.0,
        n_episodes_per_task=25,
    )
    # incumbent mean = 0.60

    # Challenger improves the mean (+0.067) by buying gains on a/b at
    # the cost of tanking task_c (0.80 → 0.50, -0.30). Pure mean A/B
    # would say "promote!" — our floor must say no.
    bad = EvalResult(
        checkpoint="/tmp/new_bad",
        per_task_success={"task_a": 0.80, "task_b": 0.70, "task_c": 0.50},
        mean_reward=0.0,
        n_episodes_per_task=25,
    )
    # bad mean = 0.667 (passes min_improvement), but task_c regressed -0.30 > 0.10 floor.
    decision = should_promote(inc, bad)
    assert not decision.promote, decision.reason
    assert "regressed" in decision.reason

    # Challenger improves mean AND doesn't regress any task → accept.
    good = EvalResult(
        checkpoint="/tmp/new_good",
        per_task_success={"task_a": 0.60, "task_b": 0.55, "task_c": 0.82},
        mean_reward=0.0,
        n_episodes_per_task=25,
    )
    decision = should_promote(inc, good)
    assert decision.promote, decision.reason
