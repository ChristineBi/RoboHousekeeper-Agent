"""Perception layer — scene graph construction.

M0: mock perception driven by a scripted scenario (so the demo is
reproducible). M2: real scene graph from RGB-D + open-vocab detectors.
"""

from .mock import MockPerception

__all__ = ["MockPerception"]
