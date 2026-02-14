"""Character creation phase."""

import json
import logging
from typing import Optional

from pydantic import BaseModel

from ..llm import LLMClient
from ..models.campaign import CampaignPhase, CampaignState
from ..models.character import CharacterSheet
from ..prompts import CHARACTER_CREATION_PROMPT, CHARACTER_SUMMARY_PROMPT
from .base import Phase, PhaseResult

logger = logging.getLogger(__name__)


class CharacterSummaryResponse(BaseModel):
    """Schema for character summary AI response."""
    name: str
    background: str
    profession: str
    traits: list[str]
    personal_goal: str


class CharacterPhase(Phase):
    """Handle character creation."""

    # Short/vague inputs that shouldn't trigger character generation
    NON_CHARACTER_INPUTS = {"ok", "okay", "sure", "yes", "yep", "yeah", "k", "continue", "next", "go", "start", "ready", ""}

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self._awaiting_confirmation = False
        self._pending_character: Optional[CharacterSheet] = None
        self._shown_intro = False

    @property
    def phase_type(self) -> CampaignPhase:
        return CampaignPhase.CHARACTER

    def enter(self, state: CampaignState) -> str:
        """Show character creation prompt."""
        self._awaiting_confirmation = False
        self._pending_character = None
        self._shown_intro = False  # Will show on first input if needed

        return CHARACTER_CREATION_PROMPT.format(
            genre=state.genre or "Fantasy",
            tone=state.tone or "Gritty",
            story_type=state.story_type or "Adventure",
        )

    def handle_input(self, user_input: str, state: CampaignState) -> PhaseResult:
        """Process character description or confirmation."""
        user_lower = user_input.lower().strip()

        # If user gives a short/vague input and we haven't shown intro yet, re-prompt
        if user_lower in self.NON_CHARACTER_INPUTS and not self._awaiting_confirmation:
            self._shown_intro = True
            return PhaseResult(
                display_message=CHARACTER_CREATION_PROMPT.format(
                    genre=state.genre or "Fantasy",
                    tone=state.tone or "Gritty",
                    story_type=state.story_type or "Adventure",
                )
            )

        # If awaiting confirmation
        if self._awaiting_confirmation and self._pending_character:
            if any(word in user_lower for word in ["yes", "lock", "confirm", "ready", "good", "perfect"]):
                # Confirm and move on
                state.character_sheet = self._pending_character
                self._awaiting_confirmation = False
                self._pending_character = None

                return PhaseResult(
                    display_message="Character locked in. Weaving your world...",
                    next_phase=CampaignPhase.WORLD_GEN,
                    complete=True,
                )
            elif any(word in user_lower for word in ["no", "change", "adjust", "redo"]):
                # Let them revise
                self._awaiting_confirmation = False
                self._pending_character = None
                return PhaseResult(
                    display_message="No problem. Tell me what to adjust, or describe your character again.",
                )
            else:
                # Treat as revision input
                pass

        # Generate character from input
        try:
            character = self._generate_character(user_input, state)
            self._pending_character = character
            self._awaiting_confirmation = True

            summary = f"""Here's your character:

**{character.name}**
*{character.profession}*

{character.background}

**Traits:** {', '.join(character.traits)}
**Goal:** {character.personal_goal}

Ready to lock it in? Say "yes" to continue, or tell me what to adjust."""

            return PhaseResult(display_message=summary)

        except Exception as e:
            import traceback
            logger.error(f"Character generation failed: {e}")
            logger.error(traceback.format_exc())
            return PhaseResult(
                display_message=f"Character generation encountered an error: {type(e).__name__}: {e}\n\nPlease try describing your character again.",
                error=str(e),
            )

    def _generate_character(self, user_input: str, state: CampaignState) -> CharacterSheet:
        """Use LLM to generate structured character from input."""
        prompt = CHARACTER_SUMMARY_PROMPT.format(
            genre=state.genre or "Fantasy",
            tone=state.tone or "Gritty",
            story_type=state.story_type or "Adventure",
            player_input=user_input,
        )

        response = self.llm.generate_structured(
            prompt=prompt,
            schema=CharacterSummaryResponse,
            max_tokens=500,
            temperature=0.7,
        )

        return CharacterSheet(
            name=response.name,
            background=response.background,
            profession=response.profession,
            traits=response.traits,
            personal_goal=response.personal_goal,
        )
