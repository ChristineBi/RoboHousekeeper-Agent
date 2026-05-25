"""SKILL.md loader.

A SKILL.md file looks like:

    ---
    name: wipe_table
    description: "Wipe a table surface."
    triggers: ["wipe table", "擦桌子"]
    preconditions:
      has_cloth: true
      table_clear: false
    parameters:
      target_table: {type: string, required: true}
    ---

    # Steps
    1. Locate table edge with RGB-D
    2. ...

    # Known Failure Modes
    - Glossy surface causes depth drift → use RGB-only fit
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as e:
    raise ImportError(
        "PyYAML is required to load SKILL.md files. "
        "Install with: pip install pyyaml"
    ) from e


_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<fm>.*?)\n---\s*\n(?P<body>.*)$",
    re.DOTALL,
)


@dataclass
class Skill:
    """In-memory representation of a SKILL.md file."""
    name: str
    description: str = ""
    triggers: list[str] = field(default_factory=list)
    preconditions: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    body: str = ""             # markdown body (Steps, Failure Modes, etc.)
    source_path: Path | None = None
    # Updated by self-improvement loop:
    use_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    lessons: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.use_count == 0:
            return 0.0
        return self.success_count / self.use_count

    def preconditions_satisfied(self, world_state: dict[str, Any]) -> bool:
        """Cheap precondition check against an external 'world_state' dict."""
        for k, expected in self.preconditions.items():
            if world_state.get(k) != expected:
                return False
        return True

    def matches_trigger(self, instruction: str) -> bool:
        """Naive token-overlap trigger match.

        Returns True if all whitespace-separated tokens of any trigger
        appear (in order, possibly with gaps) in the instruction.
        This is good enough for the M0 demo — 'wipe table' matches
        'please wipe the table' but not 'wipe the wall'. M1+ swaps in
        a semantic match.
        """
        ins_tokens = instruction.lower().split()
        for trig in self.triggers:
            trig_tokens = trig.lower().split()
            # Try in-order subsequence match.
            i = 0
            for tok in ins_tokens:
                if i < len(trig_tokens) and tok == trig_tokens[i]:
                    i += 1
            if i == len(trig_tokens):
                return True
        return False


class SkillLibrary:
    """Loads, indexes, and (eventually) patches a directory of SKILL.md files."""

    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir)
        self._skills: dict[str, Skill] = {}
        self.reload()

    def reload(self) -> None:
        """Re-scan the skills directory.

        Called by the heartbeat / cron job — after a skill is patched
        offline, the next reload picks it up without restarting the agent.
        """
        self._skills.clear()
        if not self.skills_dir.exists():
            return
        for path in sorted(self.skills_dir.glob("**/*.md")):
            try:
                skill = self._parse_skill_file(path)
            except Exception as e:  # noqa: BLE001
                # Don't crash the whole library if one file is malformed.
                print(f"[SkillLibrary] failed to parse {path}: {e}")
                continue
            self._skills[skill.name] = skill

    @staticmethod
    def _parse_skill_file(path: Path) -> Skill:
        raw = path.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(raw)
        if not m:
            raise ValueError(f"missing YAML frontmatter in {path}")
        fm_data = yaml.safe_load(m.group("fm")) or {}
        body = m.group("body").strip()
        if "name" not in fm_data:
            raise ValueError(f"skill at {path} missing required 'name' field")
        return Skill(
            name=fm_data["name"],
            description=fm_data.get("description", ""),
            triggers=list(fm_data.get("triggers", [])),
            preconditions=dict(fm_data.get("preconditions", {})),
            parameters=dict(fm_data.get("parameters", {})),
            body=body,
            source_path=path,
        )

    # ---- Read accessors ----

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def all(self) -> Iterable[Skill]:
        return self._skills.values()

    def find_by_trigger(self, instruction: str) -> list[Skill]:
        return [s for s in self._skills.values() if s.matches_trigger(instruction)]

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    # ---- Self-improvement hooks (M4) ----

    def record_outcome(
        self,
        name: str,
        succeeded: bool,
        lesson: str | None = None,
    ) -> None:
        """Lightweight in-memory bookkeeping.

        The actual SKILL.md patch happens in the offline cron job
        (see brain/self_eval.py for the online lesson aggregator).
        """
        skill = self._skills.get(name)
        if skill is None:
            return
        skill.use_count += 1
        if succeeded:
            skill.success_count += 1
        else:
            skill.failure_count += 1
        if lesson:
            skill.lessons.append(lesson)
