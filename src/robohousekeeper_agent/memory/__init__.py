"""Persistent memory for the robot agent.

Three layers, inspired by Hermes Agent's MEMORY.md / USER.md split:

* ``MEMORY.md`` — slow, structured facts about the home (rooms, fixed
  furniture, user preferences, safety rules).
* ``SCENE.json`` — fast, dynamic scene graph snapshot. Replaced often.
* ``EPISODES`` — append-only log of past task trajectories with self-eval
  notes. Source material for the offline skill-patching cron.
"""

from .manager import MemoryManager

__all__ = ["MemoryManager"]
