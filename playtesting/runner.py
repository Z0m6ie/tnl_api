"""Playthrough runner - executes a single automated playthrough."""

import logging
import time
from datetime import datetime
from typing import Optional

from tnl import CampaignEngine
from tnl.llm import LLMClient
from tnl.models.campaign import CampaignPhase

from .config import PlaytestConfig, AgentConfig
from .playthrough import Playthrough, PlaythroughMetadata, MessageSource
from .player_agent import PlayerAgent

logger = logging.getLogger(__name__)


class PlaythroughRunner:
    """Executes a single automated playthrough."""

    def __init__(
        self,
        config: PlaytestConfig,
        agent_config: AgentConfig,
        llm_client: Optional[LLMClient] = None,
    ):
        self.config = config
        self.agent_config = agent_config
        self.llm = llm_client or LLMClient()

        # Create engine and player agent
        self.engine = CampaignEngine(llm_client=self.llm)
        self.player = PlayerAgent(
            llm_client=self.llm,
            personality=agent_config.personality,
        )

        # Initialize playthrough data
        self.playthrough = Playthrough(
            metadata=PlaythroughMetadata(
                player_personality=agent_config.personality.value,
                agent_model=self.llm.model,
                genre=agent_config.genre,
                tone=agent_config.tone,
                story_type=agent_config.story_type,
            )
        )

    def run(self) -> Playthrough:
        """
        Execute a complete playthrough.

        Returns:
            Playthrough with all data for analysis
        """
        logger.info(
            f"Agent {self.agent_config.agent_id} starting: "
            f"personality={self.agent_config.personality.value}, "
            f"genre={self.agent_config.genre}"
        )

        try:
            # Phase 1: Start campaign and handle onboarding
            self._run_onboarding()

            # Phase 2: Character creation
            self._run_character_creation()

            # Phase 3: World generation (automatic, happens after character)
            # Just need to handle the ready phase

            # Phase 4: Ready phase
            self._run_ready_phase()

            # Phase 5: Gameplay loop
            self._run_gameplay_loop()

            # Mark as completed
            self.playthrough.metadata.completed_normally = True

        except Exception as e:
            logger.error(f"Agent {self.agent_config.agent_id} playthrough failed: {e}")
            self.playthrough.metadata.error_message = str(e)
            self.playthrough.metadata.completed_normally = False

        finally:
            # Capture final state
            self.playthrough.metadata.completed_at = datetime.utcnow()
            if self.engine.state:
                self.playthrough.final_state = self.engine.state.model_dump()
                self.playthrough.metadata.locations_visited = list(
                    self.engine.state.discovered_locations
                )
                self.playthrough.metadata.npcs_encountered = list(
                    self.engine.state.known_npcs
                )

        logger.info(
            f"Agent {self.agent_config.agent_id} completed: "
            f"turns={self.playthrough.metadata.total_turns}, "
            f"success={self.playthrough.metadata.completed_normally}"
        )

        return self.playthrough

    def _run_onboarding(self) -> None:
        """Handle genre/tone selection."""
        logger.debug(f"Agent {self.agent_config.agent_id}: Starting onboarding")

        # Start campaign - get welcome message
        intro = self.engine.new_campaign()
        self.playthrough.add_message(MessageSource.GAME, intro)

        # Generate genre selection based on agent config
        onboarding_input = self.agent_config.onboarding_input()

        self.playthrough.add_message(
            MessageSource.PLAYER_AGENT,
            onboarding_input,
            player_reasoning=f"Selected: {self.agent_config.genre}, {self.agent_config.tone}, {self.agent_config.story_type}",
        )

        # Submit to engine
        response = self.engine.handle_input(onboarding_input)
        self.playthrough.add_message(MessageSource.GAME, response)

        # Update metadata from engine state
        if self.engine.state:
            self.playthrough.metadata.genre = self.engine.state.genre
            self.playthrough.metadata.tone = self.engine.state.tone
            self.playthrough.metadata.story_type = self.engine.state.story_type

        self._delay()

    def _run_character_creation(self) -> None:
        """Handle character creation phase."""
        logger.debug(f"Agent {self.agent_config.agent_id}: Character creation")

        # Check if we're in CHARACTER phase
        if self.engine.current_phase != CampaignPhase.CHARACTER:
            logger.warning(f"Expected CHARACTER phase, got {self.engine.current_phase}")
            return

        # Generate character description based on genre/tone
        agent_response = self.player.generate_character_description(
            genre=self.playthrough.metadata.genre or "fantasy",
            tone=self.playthrough.metadata.tone or "dramatic",
            story_type=self.playthrough.metadata.story_type or "adventure",
        )

        self.playthrough.add_message(
            MessageSource.PLAYER_AGENT,
            agent_response.action,
            player_reasoning=agent_response.reasoning,
        )

        # Submit to engine
        response = self.engine.handle_input(agent_response.action)
        self.playthrough.add_message(MessageSource.GAME, response)

        self._delay()

        # Character confirmation (if needed)
        # The engine shows a character summary and asks for confirmation
        if self.engine.current_phase == CampaignPhase.CHARACTER:
            confirm_response = self.player.generate_confirmation()

            self.playthrough.add_message(
                MessageSource.PLAYER_AGENT,
                confirm_response.action,
                player_reasoning=confirm_response.reasoning,
            )

            response = self.engine.handle_input(confirm_response.action)
            self.playthrough.add_message(MessageSource.GAME, response)

            self._delay()

        # Update player agent with character info
        if self.engine.state and self.engine.state.character_sheet:
            char = self.engine.state.character_sheet
            self.player.set_character(
                f"{char.name}, {char.profession}. {char.background}"
            )
            self.playthrough.metadata.character_name = char.name
            self.playthrough.metadata.character_profession = char.profession
            self.playthrough.metadata.character_background = char.background

    def _run_ready_phase(self) -> None:
        """Handle the 'ready' phase (just say continue)."""
        if self.engine.current_phase == CampaignPhase.READY:
            logger.debug(f"Agent {self.agent_config.agent_id}: Ready phase")

            continue_response = self.player.generate_continue()

            self.playthrough.add_message(
                MessageSource.PLAYER_AGENT,
                continue_response.action,
                player_reasoning=continue_response.reasoning,
            )

            response = self.engine.handle_input("continue")
            self.playthrough.add_message(MessageSource.GAME, response)

            # Capture initial state after world gen
            if self.engine.state:
                self.playthrough.initial_state = self.engine.state.model_dump()

            self._delay()

    def _run_gameplay_loop(self) -> None:
        """Run the main gameplay loop."""
        logger.info(
            f"Agent {self.agent_config.agent_id}: Starting gameplay loop "
            f"for {self.config.messages_per_session} turns"
        )

        turns_remaining = self.config.messages_per_session
        last_game_output = self.playthrough.messages[-1].content if self.playthrough.messages else ""

        while turns_remaining > 0 and self.engine.current_phase == CampaignPhase.GAMEPLAY:
            # Get recent context for the agent
            recent_context = self._build_agent_context()

            # Generate player action
            try:
                agent_response = self.player.generate_action(
                    game_output=last_game_output,
                    recent_context=recent_context,
                )
            except Exception as e:
                logger.error(f"Agent {self.agent_config.agent_id} failed to generate action: {e}")
                break

            # Record player action
            self.playthrough.add_message(
                MessageSource.PLAYER_AGENT,
                agent_response.action,
                player_reasoning=agent_response.reasoning,
            )

            # Get game response
            try:
                game_response = self.engine.handle_input(agent_response.action)
            except Exception as e:
                logger.warning(
                    f"Agent {self.agent_config.agent_id} game error on turn "
                    f"{self.config.messages_per_session - turns_remaining}: {e}"
                )
                game_response = f"[ERROR: {e}]"

            # Track triggered elements
            triggered = []
            if self.engine.state and self.engine.state.simulation:
                triggered = list(self.engine.state.simulation.triggered_elements[-5:])
                self.playthrough.metadata.simulation_triggers_fired = len(
                    self.engine.state.simulation.triggered_elements
                )

            # Record game response
            self.playthrough.add_message(
                MessageSource.GAME,
                game_response,
                triggered_elements=triggered,
            )

            # Update counters
            last_game_output = game_response
            turns_remaining -= 1
            current_turn = self.config.messages_per_session - turns_remaining

            # Periodic state snapshots (every 20 turns)
            if current_turn % 20 == 0:
                if self.engine.state:
                    self.playthrough.simulation_snapshots.append({
                        "turn": current_turn,
                        "simulation": self.engine.state.simulation.model_dump() if self.engine.state.simulation else None,
                        "locations": list(self.engine.state.discovered_locations),
                        "npcs": list(self.engine.state.known_npcs),
                        "inventory": list(self.engine.state.inventory),
                    })

            logger.debug(f"Agent {self.agent_config.agent_id}: Turn {current_turn} complete")

            self._delay()

    def _build_agent_context(self) -> list:
        """Build conversation context for the player agent."""
        # Get last 10 messages in OpenAI format
        context = []
        for msg in self.playthrough.messages[-10:]:
            role = "assistant" if msg.source == MessageSource.GAME else "user"
            context.append({"role": role, "content": msg.content})
        return context

    def _delay(self) -> None:
        """Add delay between messages to respect rate limits."""
        if self.config.delay_between_messages_ms > 0:
            time.sleep(self.config.delay_between_messages_ms / 1000)
