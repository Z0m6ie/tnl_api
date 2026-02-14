"""Simulation layer models - pre-generated hidden world elements.

These models represent hidden elements that exist in scenes BEFORE the player acts.
They're generated on-demand when entering a new location, preserving player freedom
while making each scene feel pre-determined once entered.
"""

import random
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    """Types of triggers that can activate simulation elements."""
    KEYWORD = "keyword"           # Words in player input
    LOCATION = "location"         # Being in a specific location
    NPC_INTERACTION = "npc"       # Interacting with specific NPCs
    ITEM = "item"                 # Possessing/using certain items
    TIME = "time"                 # After N turns


class Severity(str, Enum):
    """Consequence severity levels."""
    MINOR = "minor"           # Small setback, recoverable
    MODERATE = "moderate"     # Significant consequence, complications
    SEVERE = "severe"         # Major consequence, story-changing
    CRITICAL = "critical"     # Potentially game-ending


class TriggerCondition(BaseModel):
    """A condition that can activate a simulation element."""
    trigger_type: TriggerType = TriggerType.KEYWORD
    keywords: List[str] = Field(default_factory=list)
    probability: float = Field(default=1.0, ge=0.0, le=1.0)

    def matches(self, player_input: str) -> bool:
        """Check if this trigger matches the player input."""
        if self.trigger_type != TriggerType.KEYWORD:
            return False

        input_lower = player_input.lower()
        return any(kw.lower() in input_lower for kw in self.keywords)

    def check_probability(self) -> bool:
        """Roll against probability. Returns True if trigger activates."""
        return random.random() <= self.probability


class Watcher(BaseModel):
    """A hidden observer in the scene."""
    id: str
    name: str
    description: str = ""
    faction: str = ""
    reports_to: str = ""
    triggers: List[TriggerCondition] = Field(default_factory=list)
    active: bool = True
    triggered: bool = False


class HiddenGuard(BaseModel):
    """Security elements unknown to the player."""
    id: str
    name: str
    guard_type: str = "armed"
    strength: str = "moderate"
    location_within_scene: str = ""
    triggers: List[TriggerCondition] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    active: bool = True
    triggered: bool = False


class FailCondition(BaseModel):
    """Actions that would cause immediate negative consequences."""
    id: str
    name: str
    description: str = ""
    severity: Severity = Severity.MODERATE
    consequence_narrative: str = ""
    triggers: List[TriggerCondition] = Field(default_factory=list)
    can_escape: bool = True
    escape_conditions: List[str] = Field(default_factory=list)
    active: bool = True
    triggered: bool = False


class Secret(BaseModel):
    """Something hidden the player could discover."""
    id: str
    description: str
    discovery_triggers: List[TriggerCondition] = Field(default_factory=list)
    discovered: bool = False


class TimedEvent(BaseModel):
    """Background events that progress over time."""
    id: str
    name: str
    description: str = ""
    current_stage: int = 0
    max_stages: int = 3
    turns_per_stage: int = 5
    stage_descriptions: List[str] = Field(default_factory=list)
    active: bool = True


class SceneSimulation(BaseModel):
    """Pre-generated simulation data for a scene/location."""
    location: str
    location_description: str = ""
    watchers: List[Watcher] = Field(default_factory=list)
    hidden_guards: List[HiddenGuard] = Field(default_factory=list)
    fail_conditions: List[FailCondition] = Field(default_factory=list)
    secrets: List[Secret] = Field(default_factory=list)
    generated_at_turn: int = 0


class SimulationState(BaseModel):
    """Complete simulation state for a campaign."""
    # Scene-specific simulations (generated on-demand when entering)
    scenes: Dict[str, SceneSimulation] = Field(default_factory=dict)

    # Global elements (always active)
    global_watchers: List[Watcher] = Field(default_factory=list)
    global_fail_conditions: List[FailCondition] = Field(default_factory=list)
    global_timed_events: List[TimedEvent] = Field(default_factory=list)

    # Tracking
    triggered_elements: List[str] = Field(default_factory=list)
    current_turn: int = 0
    current_location: Optional[str] = None

    def get_scene(self, location: str) -> Optional[SceneSimulation]:
        """Get simulation for a location if it exists."""
        return self.scenes.get(location)

    def add_scene(self, scene: SceneSimulation) -> None:
        """Add a scene simulation."""
        self.scenes[scene.location] = scene

    def mark_triggered(self, element_id: str) -> None:
        """Mark an element as triggered."""
        if element_id not in self.triggered_elements:
            self.triggered_elements.append(element_id)


class TriggerResult(BaseModel):
    """Result of evaluating a trigger."""
    triggered: bool = False
    element_id: str = ""
    element_type: str = ""  # watcher, guard, fail_condition, secret
    narrative_injection: str = ""
