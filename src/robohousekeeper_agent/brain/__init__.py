"""High-level cognition (the 'brain').

* :class:`Planner` — turns natural-language goals into a list of SubTasks
  by picking from the SkillLibrary. M0 uses a heuristic; M1+ swaps in RoboBrain.
* :class:`Orchestrator` — runs the plan, handles failures, calls self-eval.
* :class:`SelfEval`   — Hermes-style reflection that produces 'lessons'
  for the offline skill-patching loop.
"""

from .planner import Planner
from .orchestrator import Orchestrator
from .self_eval import SelfEval

__all__ = ["Planner", "Orchestrator", "SelfEval"]
