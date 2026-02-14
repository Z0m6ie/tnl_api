"""Simulation layer - on-demand scene simulation for TNL.

This module provides:
- SceneDetector: Detects when player enters a new location
- SceneSimulationGenerator: Generates hidden elements for scenes
- SimulationEvaluator: Evaluates triggers against player actions
"""

from .detector import SceneDetector
from .generator import SceneSimulationGenerator
from .evaluator import SimulationEvaluator

__all__ = [
    "SceneDetector",
    "SceneSimulationGenerator",
    "SimulationEvaluator",
]
