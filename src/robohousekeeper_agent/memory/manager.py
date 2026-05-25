"""Memory manager — the agent's long-term + short-term recall.

Concretely manages three files / collections in ``HOME_DIR``:

* ``MEMORY.md``  : human-readable facts about the home & user
* ``SCENE.json`` : latest scene graph snapshot
* ``episodes/``  : one ``.json`` per finished task episode

Keep this module dependency-light — the brain shouldn't have to install
a vector DB just to recall "the user doesn't want the robot in the bedroom".
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


class MemoryManager:
    def __init__(self, home_dir: str | Path):
        self.home_dir = Path(home_dir)
        self.home_dir.mkdir(parents=True, exist_ok=True)
        (self.home_dir / "episodes").mkdir(exist_ok=True)
        self.memory_md = self.home_dir / "MEMORY.md"
        self.scene_json = self.home_dir / "SCENE.json"
        if not self.memory_md.exists():
            self.memory_md.write_text(_DEFAULT_MEMORY_MD, encoding="utf-8")

    # ---- MEMORY.md (slow facts) ----

    def read_memory(self) -> str:
        return self.memory_md.read_text(encoding="utf-8")

    def append_fact(self, fact: str, section: str = "Facts") -> None:
        """Append a one-liner fact under a section header.

        Mirrors Hermes Agent's pattern of letting the agent itself
        write to MEMORY.md as it learns new things about the user / home.
        """
        current = self.read_memory()
        header = f"## {section}"
        if header in current:
            # Insert under the existing section, before the next ## (or EOF).
            lines = current.splitlines()
            out: list[str] = []
            inserted = False
            for i, line in enumerate(lines):
                out.append(line)
                if not inserted and line.strip() == header:
                    # Look ahead to find the end of this section.
                    j = i + 1
                    while j < len(lines) and not lines[j].startswith("## "):
                        j += 1
                    out.extend(lines[i + 1 : j])
                    out.append(f"- {fact}")
                    if j < len(lines):
                        out.extend(lines[j:])
                    inserted = True
                    break
            if not inserted:
                out.append(f"- {fact}")
            self.memory_md.write_text("\n".join(out) + "\n", encoding="utf-8")
        else:
            with self.memory_md.open("a", encoding="utf-8") as f:
                f.write(f"\n{header}\n- {fact}\n")

    # ---- SCENE.json (fast, replaced) ----

    def update_scene(self, scene_graph: Any) -> None:
        """Persist the latest scene graph. Overwrites previous snapshot.

        Accepts either a dataclass or a plain dict.
        """
        if is_dataclass(scene_graph):
            payload = asdict(scene_graph)
        else:
            payload = dict(scene_graph)
        payload.setdefault("_saved_at", time.time())
        self.scene_json.write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )

    def load_scene(self) -> dict[str, Any] | None:
        if not self.scene_json.exists():
            return None
        return json.loads(self.scene_json.read_text(encoding="utf-8"))

    # ---- Episodes (append-only) ----

    def log_episode(self, episode: dict[str, Any]) -> Path:
        """Append one finished episode for later offline analysis.

        Returns the path written, which the self-eval loop can inspect.
        """
        ts = episode.get("ended_at", time.time())
        fname = self.home_dir / "episodes" / f"episode_{int(ts)}.json"
        fname.write_text(
            json.dumps(episode, indent=2, default=str), encoding="utf-8"
        )
        return fname

    def recent_episodes(self, n: int = 10) -> list[dict[str, Any]]:
        """Return the most recent ``n`` episodes, newest first."""
        files = sorted((self.home_dir / "episodes").glob("episode_*.json"), reverse=True)
        out: list[dict[str, Any]] = []
        for f in files[:n]:
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return out


_DEFAULT_MEMORY_MD = """# Home Memory

> Long-term facts the robot has learned. The agent edits this file itself
> via `MemoryManager.append_fact`. Edit by hand only if you really want to
> reset something — accidental edits will get overwritten over time.

## User Preferences

## Home Layout

## Safety Rules
- Do not enter the bedroom between 22:00 and 07:00.
- Keep speed below 0.3 m/s when within 1m of a person.

## Facts
"""
