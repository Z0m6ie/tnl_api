"""World generation phase - code-controlled chunk generation."""

import logging
from typing import List, Optional

from ..llm import LLMClient
from ..models.campaign import CampaignPhase, CampaignState
from ..persistence import CampaignRepository
from ..prompts import WORLD_CHUNK_PROMPTS
from .base import Phase, PhaseResult

logger = logging.getLogger(__name__)

# Ordered list of chunks to generate
CHUNK_TYPES = [
    "atmospheric_setup",
    "factions_overview",
    "key_figures",
    "world_events",
    "player_hook",
]


class WorldGenPhase(Phase):
    """
    Generate the hidden world seed.

    This is the CRITICAL FIX - code controls the generation loop,
    not the AI. Each chunk is generated, saved, then we move to the next.
    """

    def __init__(self, llm_client: LLMClient, repository: CampaignRepository):
        self.llm = llm_client
        self.repository = repository
        self._generation_started = False
        self._generation_complete = False

    @property
    def phase_type(self) -> CampaignPhase:
        return CampaignPhase.WORLD_GEN

    def enter(self, state: CampaignState) -> str:
        """Start world generation (this phase is non-interactive)."""
        self._generation_started = False
        self._generation_complete = False
        return "Weaving your world... This may take a moment."

    def handle_input(self, user_input: str, state: CampaignState) -> PhaseResult:
        """
        Generate the world.

        This phase doesn't really process user input - it auto-generates.
        The handle_input is called once to trigger generation.
        """
        if self._generation_complete:
            # Already done, move to ready
            return PhaseResult(
                display_message=f"Your world is ready.\n\n**Campaign ID:** `{state.campaign_id}`\n\nSave this ID to resume later. Type **continue** to begin.",
                next_phase=CampaignPhase.READY,
                complete=True,
            )

        if self._generation_started:
            # Still generating, shouldn't happen in sync flow
            return PhaseResult(
                display_message="Still weaving... please wait.",
            )

        # Start generation
        self._generation_started = True

        try:
            self._generate_world(state)
            self._generation_complete = True

            message = f"""Your world has been fully woven.

**Campaign ID:** `{state.campaign_id}`

Keep this safe - it allows you to resume your journey anytime.

Type **continue** when you're ready to begin."""

            return PhaseResult(
                display_message=message,
                next_phase=CampaignPhase.READY,
                complete=True,
            )

        except Exception as e:
            logger.error(f"World generation failed: {e}")
            self._generation_started = False
            return PhaseResult(
                display_message=f"World generation encountered an issue. Retrying... ({e})",
                error=str(e),
            )

    def _generate_world(self, state: CampaignState) -> None:
        """
        Generate all 5 world chunks sequentially.

        THIS IS THE KEY CHANGE: Code controls the loop, not AI.
        """
        character_summary = state.character_sheet.summary()
        campaign_id: Optional[str] = None
        previous_chunks: List[str] = []

        for i, chunk_type in enumerate(CHUNK_TYPES):
            logger.info(f"Generating chunk {i + 1}/5: {chunk_type}")

            # Build prompt with context
            prompt = WORLD_CHUNK_PROMPTS[chunk_type].format(
                genre=state.genre,
                tone=state.tone,
                character_summary=character_summary,
                previous_chunks="\n\n".join(previous_chunks) if previous_chunks else "(none yet)",
            )

            # Generate chunk
            chunk_text = self.llm.generate(
                prompt=prompt,
                max_tokens=500,
                temperature=0.8,
            )

            # Save chunk (first call creates campaign)
            campaign_id = self.repository.save_seed_chunk(
                chunk_order=i,
                seed_chunk=chunk_text,
                campaign_id=campaign_id,
            )

            # Track for context
            state.seed_chunks.append(chunk_text)
            previous_chunks.append(chunk_text)

            logger.info(f"Saved chunk {i + 1} to campaign {campaign_id}")

        # Store campaign ID in state
        state.campaign_id = campaign_id

        # Save full state
        self.repository.save_runtime_state(campaign_id, state)

    def generate_sync(self, state: CampaignState) -> str:
        """
        Synchronous generation for non-interactive use.

        Returns the campaign ID.
        """
        self._generate_world(state)
        return state.campaign_id
