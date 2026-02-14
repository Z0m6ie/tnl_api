"""Character sheet model."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CharacterSheet(BaseModel):
    """Player character data."""

    name: str = Field(default="", description="Character name")
    background: str = Field(default="", description="Where they're from, what shaped them")
    profession: str = Field(default="", description="Profession or skillset")
    traits: List[str] = Field(default_factory=list, description="Temperament, strengths, flaws")
    personal_goal: str = Field(default="", description="What they want")
    stats: Dict[str, int] = Field(default_factory=dict, description="Optional numeric stats")

    @classmethod
    def empty(cls) -> "CharacterSheet":
        """Return an empty character sheet."""
        return cls()

    def is_complete(self) -> bool:
        """Check if minimum required fields are filled."""
        return bool(self.name and self.background and self.profession)

    def summary(self) -> str:
        """Return a brief summary for prompts."""
        traits_str = ", ".join(self.traits) if self.traits else "unspecified"
        return (
            f"{self.name}, a {self.profession} with a background in {self.background}. "
            f"Traits: {traits_str}. Goal: {self.personal_goal or 'unspecified'}."
        )
