"""Gameplay phase - active play with context retrieval and simulation."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from ..llm import LLMClient
from ..models.campaign import CampaignPhase, CampaignState
from ..models.simulation import TriggerResult
from ..persistence import CampaignRepository
from ..prompts import CAMPAIGN_INTRO_PROMPT, GAMEPLAY_RESPONSE_PROMPT, GAMEPLAY_SYSTEM_PROMPT
from ..simulation import SceneDetector, SceneSimulationGenerator, SimulationEvaluator
from .base import Phase, PhaseResult

logger = logging.getLogger(__name__)


class GameplayPhase(Phase):
    """Handle active gameplay with simulation layer."""

    def __init__(self, llm_client: LLMClient, repository: CampaignRepository):
        self.llm = llm_client
        self.repository = repository
        self._intro_shown = False

        # Simulation components
        self.scene_detector = SceneDetector()
        self.scene_generator = SceneSimulationGenerator(llm_client)
        self.evaluator = SimulationEvaluator()

    @property
    def phase_type(self) -> CampaignPhase:
        return CampaignPhase.GAMEPLAY

    def enter(self, state: CampaignState) -> str:
        """Generate and show campaign introduction."""
        self._intro_shown = False
        return "Entering the world..."

    def handle_input(self, user_input: str, state: CampaignState) -> PhaseResult:
        """Process player action and generate world response."""
        # First turn: generate intro
        if not self._intro_shown:
            intro = self._generate_intro(state)
            self._intro_shown = True
            state.add_message("assistant", intro)
            self._save_state(state)
            return PhaseResult(display_message=intro)

        # Regular gameplay turn
        state.add_message("user", user_input)

        try:
            response = self._generate_response(user_input, state)

            # Parse any state changes from response
            self._parse_state_changes(response, state)

            state.add_message("assistant", response)
            self._save_state(state)

            return PhaseResult(display_message=response)

        except Exception as e:
            logger.error(f"Gameplay response failed: {e}")
            return PhaseResult(
                display_message="The world shimmers uncertainly... (Error - try again)",
                error=str(e),
            )

    def _generate_intro(self, state: CampaignState) -> str:
        """Generate the campaign opening scene."""
        world_context = "\n\n".join(state.seed_chunks)

        prompt = CAMPAIGN_INTRO_PROMPT.format(
            character_summary=state.character_sheet.summary(),
            world_context=world_context,
        )

        return self.llm.generate(
            prompt=prompt,
            max_tokens=600,
            temperature=0.8,
        )

    def _generate_response(self, user_input: str, state: CampaignState) -> str:
        """Generate response to player action with simulation layer."""
        # STEP 1: Detect scene transition
        new_location = self.scene_detector.detect_scene_transition(
            user_input, state.current_location
        )

        # STEP 2: Generate simulation for new scene (if transitioning)
        if new_location and new_location not in state.simulation.scenes:
            logger.info(f"Player entering new location: {new_location}")
            world_context_for_sim = "\n\n".join(state.seed_chunks[:3])
            scene_sim = self.scene_generator.generate_scene_simulation(
                location=new_location,
                state=state,
                world_context=world_context_for_sim,
            )
            # Store simulation - now "pre-exists" for this scene
            state.simulation.add_scene(scene_sim)
            state.current_location = new_location
            state.simulation.current_location = new_location

            # Add to discovered locations
            if new_location not in state.discovered_locations:
                state.discovered_locations.append(new_location)

        # STEP 3: Evaluate triggers against player action
        trigger_results = self.evaluator.evaluate_action(user_input, state)
        timed_results = self.evaluator.advance_timed_events(state)
        all_triggers = trigger_results + timed_results

        # STEP 4: Build simulation injection
        simulation_injection = self._build_simulation_injection(all_triggers)

        # Mark triggered elements
        for result in all_triggers:
            if result.triggered:
                state.simulation.mark_triggered(result.element_id)

        # Get relevant context from embeddings
        context_chunks = self._get_context(user_input, state)
        world_context = "\n\n".join(context_chunks) if context_chunks else "\n\n".join(state.seed_chunks[:2])

        # Build system prompt with current state
        system = GAMEPLAY_SYSTEM_PROMPT.format(
            genre=state.genre,
            tone=state.tone,
            world_context=world_context,
            character_summary=state.character_sheet.summary(),
            inventory=", ".join(state.inventory) or "empty",
            abilities=", ".join(state.abilities) or "none",
            locations=", ".join(state.discovered_locations) or "unknown",
            known_npcs=", ".join(state.known_npcs) or "none",
        )

        # STEP 5: Inject simulation context if any triggers activated
        if simulation_injection:
            system += simulation_injection

        # Build conversation context (last few exchanges)
        context = state.get_recent_history(limit=6)

        # Generate response
        prompt = GAMEPLAY_RESPONSE_PROMPT.format(player_input=user_input)

        return self.llm.generate(
            prompt=prompt,
            system_prompt=system,
            context=context,
            max_tokens=600,
            temperature=0.8,
        )

    def _build_simulation_injection(self, triggers: List[TriggerResult]) -> str:
        """Build simulation context to inject into system prompt."""
        active_triggers = [t for t in triggers if t.triggered]

        if not active_triggers:
            return ""

        parts = ["\n\n=== SIMULATION LAYER (hidden - apply naturally, never reveal) ==="]

        for trigger in active_triggers:
            parts.append(trigger.narrative_injection)

        parts.append("=== END SIMULATION ===")

        return "\n\n".join(parts)

    def _get_context(self, query: str, state: CampaignState) -> List[str]:
        """Retrieve relevant context chunks via embedding similarity."""
        if not state.campaign_id:
            return []

        try:
            matches = self.repository.query_similar_chunks(
                campaign_id=state.campaign_id,
                query_text=query,
                top_k=5,
            )
            return [m.get("chunk", "") for m in matches if m.get("chunk")]
        except Exception as e:
            logger.warning(f"Context retrieval failed: {e}")
            return []

    def _parse_state_changes(self, response: str, state: CampaignState) -> None:
        """Extract and apply state changes from AI response."""
        # Look for JSON block in response
        json_match = re.search(r"```json\s*(\{[^`]+\})\s*```", response, re.DOTALL)
        if not json_match:
            # Try without code block
            json_match = re.search(r"\{[^{}]*\"(?:inventory|abilities|locations|npcs)_(?:add|remove)\"[^{}]*\}", response)

        if not json_match:
            return

        try:
            changes = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))

            # Apply changes
            if "inventory_add" in changes:
                for item in changes["inventory_add"]:
                    if item not in state.inventory:
                        state.inventory.append(item)

            if "inventory_remove" in changes:
                for item in changes["inventory_remove"]:
                    if item in state.inventory:
                        state.inventory.remove(item)

            if "abilities_add" in changes:
                for ability in changes["abilities_add"]:
                    if ability not in state.abilities:
                        state.abilities.append(ability)

            if "locations_add" in changes:
                for loc in changes["locations_add"]:
                    if loc not in state.discovered_locations:
                        state.discovered_locations.append(loc)

            if "npcs_add" in changes:
                for npc in changes["npcs_add"]:
                    if npc not in state.known_npcs:
                        state.known_npcs.append(npc)

            logger.info(f"Applied state changes: {changes}")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse state changes: {e}")

    def _save_state(self, state: CampaignState) -> None:
        """Persist current state."""
        if state.campaign_id:
            try:
                self.repository.save_runtime_state(state.campaign_id, state)
            except Exception as e:
                logger.warning(f"Failed to save state: {e}")
