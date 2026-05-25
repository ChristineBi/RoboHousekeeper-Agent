"""Hermes-style SKILL.md library for the robot.

A skill is a markdown file with YAML frontmatter that describes
*when* the skill should fire, *what* preconditions must hold, and
the procedural steps. The frontmatter is machine-readable; the
body is for both the LLM (planner) and humans (debug / patch).

See docs/RESEARCH.md § 6.2 for the design rationale.
"""

from .loader import Skill, SkillLibrary

__all__ = ["Skill", "SkillLibrary"]
