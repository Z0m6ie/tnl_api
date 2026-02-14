"""Campaign state model."""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from .character import CharacterSheet
from .world import WorldSeed
from .simulation import SimulationState


class CampaignPhase(str, Enum):
    """Campaign lifecycle phases."""

    ONBOARDING = "onboarding"  # Genre/tone selection
    CHARACTER = "character"  # Character creation
    WORLD_GEN = "world_gen"  # AI generates world (code-controlled)
    READY = "ready"  # Waiting for "continue"
    GAMEPLAY = "gameplay"  # Active play
    PAUSED = "paused"  # Campaign suspended


class CampaignState(BaseModel):
    """Complete campaign state - managed by code, not AI."""

    # Identity
    campaign_id: Optional[str] = None
    phase: CampaignPhase = CampaignPhase.ONBOARDING

    # Onboarding selections
    genre: Optional[str] = None
    tone: Optional[str] = None
    story_type: Optional[str] = None

    # Character
    character_sheet: CharacterSheet = Field(default_factory=CharacterSheet.empty)

    # World (hidden from player)
    seed_chunks: List[str] = Field(default_factory=list)
    world_seed: Optional[WorldSeed] = None

    # Simulation layer (hidden, on-demand generated)
    simulation: SimulationState = Field(default_factory=SimulationState)
    current_location: Optional[str] = None
    current_turn: int = 0

    # Runtime state (mutable during gameplay)
    inventory: List[str] = Field(default_factory=list)
    abilities: List[str] = Field(default_factory=list)
    discovered_locations: List[str] = Field(default_factory=list)
    known_npcs: List[str] = Field(default_factory=list)
    active_events: List[str] = Field(default_factory=list)

    # Conversation history (for context)
    message_history: List[Dict[str, str]] = Field(default_factory=list)

    # Display messages (shown to user)
    pending_display: Optional[str] = None

    def add_message(self, role: str, content: str) -> None:
        """Add a message to history."""
        self.message_history.append({"role": role, "content": content})

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent message history for context."""
        return self.message_history[-limit:]

    def to_runtime_dict(self) -> Dict[str, Any]:
        """Convert to runtime state dict for persistence."""
        return {
            "character_sheet": self.character_sheet.model_dump(),
            "inventory": self.inventory,
            "abilities": self.abilities,
            "locations": self.discovered_locations,
            "key_people": self.known_npcs,
            "world_events": self.active_events,
        }

    @classmethod
    def from_saved(cls, data: Dict[str, Any]) -> "CampaignState":
        """Restore campaign state from saved data."""
        # Handle character_sheet
        char_data = data.get("character_sheet", {})
        if isinstance(char_data, dict):
            character_sheet = CharacterSheet(**char_data)
        else:
            character_sheet = CharacterSheet.empty()

        # Handle simulation state
        sim_data = data.get("simulation")
        if sim_data and isinstance(sim_data, dict):
            simulation = SimulationState(**sim_data)
        else:
            simulation = SimulationState()

        return cls(
            campaign_id=data.get("campaign_id"),
            phase=CampaignPhase(data.get("phase", "gameplay")),
            genre=data.get("genre"),
            tone=data.get("tone"),
            story_type=data.get("story_type"),
            character_sheet=character_sheet,
            seed_chunks=data.get("seed_chunks", []),
            inventory=data.get("inventory", []),
            abilities=data.get("abilities", []),
            discovered_locations=data.get("locations", []),
            known_npcs=data.get("key_people", []),
            active_events=data.get("world_events", []),
            message_history=data.get("message_history", []),
            # Simulation layer
            simulation=simulation,
            current_location=data.get("current_location"),
            current_turn=data.get("current_turn", 0),
        )
