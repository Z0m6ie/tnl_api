"""World generation models."""

from typing import List, Optional
from pydantic import BaseModel, Field


class Faction(BaseModel):
    """A faction in the game world."""

    name: str = Field(..., description="Faction name")
    public_front: str = Field(..., description="What they appear to be")
    hidden_agenda: str = Field(..., description="Their secret goals")


class NPC(BaseModel):
    """A key figure in the game world."""

    name: str = Field(..., description="NPC name")
    faction: str = Field(..., description="Which faction they belong to")
    loyalties: str = Field(..., description="Who they serve")
    motives: str = Field(..., description="What they want and why")
    relationships: List[str] = Field(default_factory=list, description="Alliances, rivalries")
    assets: List[str] = Field(default_factory=list, description="Resources they command")
    vulnerabilities: List[str] = Field(default_factory=list, description="Flaws, risks, weaknesses")


class WorldEvent(BaseModel):
    """An active event creating tension in the world."""

    name: str = Field(..., description="Event name/title")
    description: str = Field(..., description="What is happening")
    tensions: List[str] = Field(default_factory=list, description="Risks and conflicts created")


class WorldSeed(BaseModel):
    """The hidden world structure generated during campaign creation."""

    atmosphere: str = Field(default="", description="Sensory description of the world")
    factions: List[Faction] = Field(default_factory=list, min_length=3)
    npcs: List[NPC] = Field(default_factory=list, min_length=6)
    world_events: List[WorldEvent] = Field(default_factory=list, min_length=2)
    player_hook: str = Field(default="", description="How the player connects to events")

    def is_complete(self) -> bool:
        """Check if world seed meets minimum requirements."""
        return (
            bool(self.atmosphere)
            and len(self.factions) >= 3
            and len(self.npcs) >= 6
            and len(self.world_events) >= 2
            and bool(self.player_hook)
        )
