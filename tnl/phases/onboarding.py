"""Onboarding phase - genre/tone selection."""

import random
from typing import Tuple

from ..llm import LLMClient
from ..models.campaign import CampaignPhase, CampaignState
from ..prompts import ONBOARDING_WELCOME
from .base import Phase, PhaseResult


# Predefined options for "surprise me"
GENRES = ["Cyberpunk", "Dark Fantasy", "Noir", "Sci-Fi Horror", "Post-Apocalyptic", "Steampunk", "Gothic", "Mythic"]
TONES = ["Gritty", "Bleak", "Whimsical", "Tense", "Melancholic", "Sardonic", "Dreamlike"]
STORY_TYPES = ["Heist thriller", "Revenge tale", "Mystery", "Survival", "Political intrigue", "Coming-of-age", "Escape"]


class OnboardingPhase(Phase):
    """Handle genre/tone/story type selection."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    @property
    def phase_type(self) -> CampaignPhase:
        return CampaignPhase.ONBOARDING

    def enter(self, state: CampaignState) -> str:
        """Show welcome message."""
        return ONBOARDING_WELCOME

    def handle_input(self, user_input: str, state: CampaignState) -> PhaseResult:
        """Parse user selection or generate random."""
        user_lower = user_input.lower().strip()

        if "surprise" in user_lower:
            # Random selection
            genre, tone, story_type = self._random_selection()
        else:
            # Try to parse user input
            genre, tone, story_type = self._parse_selection(user_input)

        # Store in state
        state.genre = genre
        state.tone = tone
        state.story_type = story_type

        # Confirmation message
        message = f"""Your world is set:

**Genre:** {genre}
**Tone:** {tone}
**Story Type:** {story_type}

Moving to character creation..."""

        return PhaseResult(
            display_message=message,
            next_phase=CampaignPhase.CHARACTER,
            complete=True,
        )

    def _random_selection(self) -> Tuple[str, str, str]:
        """Generate random genre/tone/story."""
        return (
            random.choice(GENRES),
            random.choice(TONES),
            random.choice(STORY_TYPES),
        )

    def _parse_selection(self, user_input: str) -> Tuple[str, str, str]:
        """
        Parse user input to extract genre, tone, story type.

        Falls back to inferring from the input if not clearly structured.
        """
        # Simple parsing - look for common patterns
        parts = [p.strip() for p in user_input.replace(",", " ").replace("/", " ").split()]

        # Try to identify each component
        genre = None
        tone = None
        story_type = None

        for part in parts:
            part_lower = part.lower()
            # Check against known values
            for g in GENRES:
                if g.lower() in part_lower or part_lower in g.lower():
                    genre = g
                    break
            for t in TONES:
                if t.lower() in part_lower or part_lower in t.lower():
                    tone = t
                    break
            for s in STORY_TYPES:
                if part_lower in s.lower():
                    story_type = s
                    break

        # Fill in missing parts - use the full input as context
        if not genre:
            genre = self._infer_from_input(user_input, "genre") or random.choice(GENRES)
        if not tone:
            tone = self._infer_from_input(user_input, "tone") or random.choice(TONES)
        if not story_type:
            story_type = self._infer_from_input(user_input, "story") or user_input[:50]

        return genre, tone, story_type

    def _infer_from_input(self, user_input: str, category: str) -> str | None:
        """Try to infer a category from freeform input."""
        user_lower = user_input.lower()

        if category == "genre":
            if any(w in user_lower for w in ["cyber", "tech", "neon", "hacker"]):
                return "Cyberpunk"
            if any(w in user_lower for w in ["fantasy", "magic", "dragon", "sword"]):
                return "Dark Fantasy"
            if any(w in user_lower for w in ["noir", "detective", "crime"]):
                return "Noir"
            if any(w in user_lower for w in ["horror", "alien", "space"]):
                return "Sci-Fi Horror"

        if category == "tone":
            if any(w in user_lower for w in ["gritty", "dark", "brutal"]):
                return "Gritty"
            if any(w in user_lower for w in ["bleak", "hopeless", "doom"]):
                return "Bleak"
            if any(w in user_lower for w in ["fun", "light", "whimsy"]):
                return "Whimsical"

        return None
