"""Executor (cerebellum-side) — turns SubTasks into hardware / sim actions.

M0: mock executor that pretends to execute and reports outcomes based
on the perception scenario. M1: wraps a RoboCasa env. M3: wraps a real
VLA policy (RoboBrain-X0 / OpenVLA / pi-0).
"""

from .mock import MockExecutor

__all__ = ["MockExecutor"]
