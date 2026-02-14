"""Campaign Engine - main orchestrator for TNL.

This is the core of the refactored architecture. The engine:
- Controls phase transitions (not the AI)
- Manages campaign state
- Coordinates phases, LLM, and persistence
"""

import logging
from typing import Dict, Optional, Type

from .llm import LLMClient
from .models.campaign import CampaignPhase, CampaignState
from .persistence import CampaignRepository
from .phases import (
    CharacterPhase,
    GameplayPhase,
    OnboardingPhase,
    Phase,
    PhaseResult,
    WorldGenPhase,
)

logger = logging.getLogger(__name__)


class CampaignEngine:
    """
    Main orchestrator for TNL campaigns.

    Controls the flow of the game through explicit phase management.
    The AI is called at specific points with focused prompts.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        repository: Optional[CampaignRepository] = None,
    ):
        self.llm = llm_client or LLMClient()
        self.repository = repository or CampaignRepository(llm_client=self.llm)

        # Initialize phase handlers
        self._phases: Dict[CampaignPhase, Phase] = {
            CampaignPhase.ONBOARDING: OnboardingPhase(self.llm),
            CampaignPhase.CHARACTER: CharacterPhase(self.llm),
            CampaignPhase.WORLD_GEN: WorldGenPhase(self.llm, self.repository),
            CampaignPhase.GAMEPLAY: GameplayPhase(self.llm, self.repository),
        }

        # Current campaign state
        self.state: Optional[CampaignState] = None

    def new_campaign(self) -> str:
        """
        Start a new campaign.

        Returns:
            Welcome message from onboarding phase
        """
        self.state = CampaignState()
        logger.info("Starting new campaign")
        return self._enter_phase(CampaignPhase.ONBOARDING)

    def resume_campaign(self, campaign_id: str) -> Optional[str]:
        """
        Resume an existing campaign.

        Args:
            campaign_id: UUID of the campaign to resume

        Returns:
            Status message, or None if campaign not found
        """
        logger.info(f"Attempting to resume campaign: {campaign_id}")

        state = self.repository.load_runtime_state(campaign_id)
        if not state:
            return None

        self.state = state
        self.state.campaign_id = campaign_id

        # Determine appropriate phase
        if state.phase == CampaignPhase.GAMEPLAY:
            # Resume gameplay
            phase_handler = self._phases[CampaignPhase.GAMEPLAY]
            phase_handler._intro_shown = True  # Skip intro on resume
            return f"Welcome back, {state.character_sheet.name}.\n\nYour journey continues..."

        # For other phases, enter them normally
        return self._enter_phase(state.phase)

    def handle_input(self, user_input: str) -> str:
        """
        Process user input in the current phase.

        Args:
            user_input: What the user typed

        Returns:
            Response to display
        """
        if not self.state:
            return self.new_campaign()

        # Handle "ready" phase (waiting for "continue")
        if self.state.phase == CampaignPhase.READY:
            if "continue" in user_input.lower():
                # Transition to gameplay and auto-generate intro
                self.state.phase = CampaignPhase.GAMEPLAY
                gameplay_handler = self._phases[CampaignPhase.GAMEPLAY]
                # Trigger intro generation
                intro_result = gameplay_handler.handle_input("", self.state)
                return intro_result.display_message
            else:
                return "Type **continue** when you're ready to begin your journey."

        # Get current phase handler
        phase_handler = self._phases.get(self.state.phase)
        if not phase_handler:
            logger.error(f"No handler for phase: {self.state.phase}")
            return "Something went wrong. Starting over..."

        # Process input
        result = phase_handler.handle_input(user_input, self.state)

        # Handle phase transition
        if result.next_phase:
            self.state.phase = result.next_phase

            # For character phase, include the character creation prompt
            if result.next_phase == CampaignPhase.CHARACTER:
                char_handler = self._phases[CampaignPhase.CHARACTER]
                char_intro = char_handler.enter(self.state)
                return result.display_message + "\n\n" + char_intro

            # For world_gen, auto-trigger generation immediately
            if result.next_phase == CampaignPhase.WORLD_GEN:
                # Show the transition message, then run world gen
                world_gen_handler = self._phases[CampaignPhase.WORLD_GEN]
                world_gen_result = world_gen_handler.handle_input("", self.state)

                # Handle phase transition from world_gen (to READY)
                if world_gen_result.next_phase:
                    self.state.phase = world_gen_result.next_phase

                # Combine messages: "Character locked in..." + world gen result
                return result.display_message + "\n\n" + world_gen_result.display_message

        return result.display_message

    def _enter_phase(self, phase: CampaignPhase) -> str:
        """Enter a phase and return its welcome message."""
        self.state.phase = phase

        handler = self._phases.get(phase)
        if not handler:
            return f"Entering phase: {phase.value}"

        return handler.enter(self.state)

    @property
    def current_phase(self) -> Optional[CampaignPhase]:
        """Get current phase."""
        return self.state.phase if self.state else None

    @property
    def campaign_id(self) -> Optional[str]:
        """Get current campaign ID."""
        return self.state.campaign_id if self.state else None

    def get_state_summary(self) -> Dict:
        """Get a summary of current state for debugging."""
        if not self.state:
            return {"status": "no_campaign"}

        return {
            "campaign_id": self.state.campaign_id,
            "phase": self.state.phase.value,
            "character": self.state.character_sheet.name if self.state.character_sheet else None,
            "genre": self.state.genre,
            "tone": self.state.tone,
            "inventory_count": len(self.state.inventory),
            "message_count": len(self.state.message_history),
        }
