"""Simulation trigger evaluator.

Evaluates player actions against pre-generated simulation elements to determine
which triggers activate.
"""

import logging
from typing import List, Optional

from ..models.campaign import CampaignState
from ..models.simulation import (
    TriggerResult,
    Watcher,
    HiddenGuard,
    FailCondition,
    Secret,
    TimedEvent,
    SceneSimulation,
)

logger = logging.getLogger(__name__)


class SimulationEvaluator:
    """Evaluates player actions against pre-generated simulation triggers."""

    def evaluate_action(
        self,
        player_input: str,
        state: CampaignState,
    ) -> List[TriggerResult]:
        """
        Evaluate player action against all active simulation elements.

        Checks both global and location-specific elements.

        Args:
            player_input: What the player typed
            state: Current campaign state

        Returns:
            List of triggered results (could be empty or multiple)
        """
        results = []
        input_lower = player_input.lower()

        # Check global watchers
        for watcher in state.simulation.global_watchers:
            if watcher.active and not watcher.triggered:
                result = self._check_watcher(watcher, input_lower)
                if result.triggered:
                    results.append(result)

        # Check global fail conditions
        for fail_cond in state.simulation.global_fail_conditions:
            if fail_cond.active and not fail_cond.triggered:
                result = self._check_fail_condition(fail_cond, input_lower)
                if result.triggered:
                    results.append(result)

        # Check location-specific elements
        current_location = state.current_location
        if current_location:
            scene = state.simulation.get_scene(current_location)
            if scene:
                results.extend(self._evaluate_scene(scene, input_lower))

        return results

    def _evaluate_scene(
        self,
        scene: SceneSimulation,
        input_lower: str
    ) -> List[TriggerResult]:
        """Evaluate triggers for a specific scene."""
        results = []

        # Check watchers
        for watcher in scene.watchers:
            if watcher.active and not watcher.triggered:
                result = self._check_watcher(watcher, input_lower)
                if result.triggered:
                    results.append(result)

        # Check hidden guards
        for guard in scene.hidden_guards:
            if guard.active and not guard.triggered:
                result = self._check_guard(guard, input_lower)
                if result.triggered:
                    results.append(result)

        # Check fail conditions
        for fail_cond in scene.fail_conditions:
            if fail_cond.active and not fail_cond.triggered:
                result = self._check_fail_condition(fail_cond, input_lower)
                if result.triggered:
                    results.append(result)

        # Check secrets
        for secret in scene.secrets:
            if not secret.discovered:
                result = self._check_secret(secret, input_lower)
                if result.triggered:
                    results.append(result)

        return results

    def _check_watcher(self, watcher: Watcher, input_lower: str) -> TriggerResult:
        """Check if a watcher's triggers match."""
        for trigger in watcher.triggers:
            if trigger.matches(input_lower) and trigger.check_probability():
                watcher.triggered = True
                logger.info(f"Watcher triggered: {watcher.name}")
                return TriggerResult(
                    triggered=True,
                    element_id=watcher.id,
                    element_type="watcher",
                    narrative_injection=self._build_watcher_narrative(watcher),
                )
        return TriggerResult(triggered=False)

    def _check_guard(self, guard: HiddenGuard, input_lower: str) -> TriggerResult:
        """Check if a hidden guard's triggers match."""
        for trigger in guard.triggers:
            if trigger.matches(input_lower) and trigger.check_probability():
                guard.triggered = True
                logger.info(f"Hidden guard triggered: {guard.name}")
                return TriggerResult(
                    triggered=True,
                    element_id=guard.id,
                    element_type="hidden_guard",
                    narrative_injection=self._build_guard_narrative(guard),
                )
        return TriggerResult(triggered=False)

    def _check_fail_condition(
        self,
        fail_cond: FailCondition,
        input_lower: str
    ) -> TriggerResult:
        """Check if a fail condition's triggers match."""
        for trigger in fail_cond.triggers:
            if trigger.matches(input_lower) and trigger.check_probability():
                fail_cond.triggered = True
                logger.info(f"Fail condition triggered: {fail_cond.name}")
                return TriggerResult(
                    triggered=True,
                    element_id=fail_cond.id,
                    element_type="fail_condition",
                    narrative_injection=self._build_fail_narrative(fail_cond),
                )
        return TriggerResult(triggered=False)

    def _check_secret(self, secret: Secret, input_lower: str) -> TriggerResult:
        """Check if a secret's discovery triggers match."""
        for trigger in secret.discovery_triggers:
            if trigger.matches(input_lower) and trigger.check_probability():
                secret.discovered = True
                logger.info(f"Secret discovered: {secret.id}")
                return TriggerResult(
                    triggered=True,
                    element_id=secret.id,
                    element_type="secret",
                    narrative_injection=self._build_secret_narrative(secret),
                )
        return TriggerResult(triggered=False)

    def advance_timed_events(self, state: CampaignState) -> List[TriggerResult]:
        """
        Advance all timed events by one turn.

        Called at the end of each gameplay turn.

        Args:
            state: Current campaign state

        Returns:
            List of timed event trigger results (stage advances or completions)
        """
        state.current_turn += 1
        results = []

        for event in state.simulation.global_timed_events:
            if not event.active:
                continue

            # Check if it's time to advance the stage
            if state.current_turn % event.turns_per_stage == 0:
                if event.current_stage < event.max_stages - 1:
                    event.current_stage += 1
                    stage_desc = ""
                    if event.current_stage < len(event.stage_descriptions):
                        stage_desc = event.stage_descriptions[event.current_stage]

                    logger.info(f"Timed event advanced: {event.name} -> stage {event.current_stage}")
                    results.append(TriggerResult(
                        triggered=True,
                        element_id=event.id,
                        element_type="timed_event",
                        narrative_injection=self._build_timed_event_narrative(event, stage_desc),
                    ))
                elif event.current_stage >= event.max_stages - 1:
                    # Event reached final stage
                    event.active = False
                    logger.info(f"Timed event completed: {event.name}")

        return results

    def _build_watcher_narrative(self, watcher: Watcher) -> str:
        """Build narrative injection for a triggered watcher."""
        return f"""[SIMULATION - WATCHER TRIGGERED]
Name: {watcher.name}
{watcher.description}
Faction: {watcher.faction}
Reports to: {watcher.reports_to}

The watcher has noticed the player's action. Show this subtly through environmental
details - perhaps a glance, a sudden departure, a whispered message. Do NOT
explicitly tell the player they are being watched."""

    def _build_guard_narrative(self, guard: HiddenGuard) -> str:
        """Build narrative injection for a triggered hidden guard."""
        return f"""[SIMULATION - HIDDEN GUARD REVEALED]
Name: {guard.name}
Type: {guard.guard_type}
Strength: {guard.strength}
Location: {guard.location_within_scene}
Weaknesses: {', '.join(guard.weaknesses) if guard.weaknesses else 'Unknown'}

The hidden guard/security has been triggered. Describe their emergence dramatically.
The player can still try to fight, flee, or negotiate - show the threat but
don't dictate the outcome."""

    def _build_fail_narrative(self, fail_cond: FailCondition) -> str:
        """Build narrative injection for a triggered fail condition."""
        escape_info = ""
        if fail_cond.can_escape and fail_cond.escape_conditions:
            escape_info = f"\nEscape possible via: {', '.join(fail_cond.escape_conditions)}"

        return f"""[SIMULATION - FAIL CONDITION TRIGGERED]
Condition: {fail_cond.name}
Severity: {fail_cond.severity.value}
{fail_cond.description}

Consequence: {fail_cond.consequence_narrative}
Can escape: {fail_cond.can_escape}{escape_info}

Apply this consequence in your response. The situation should feel dangerous
but not hopeless. If escape is possible, leave room for the player to attempt it."""

    def _build_secret_narrative(self, secret: Secret) -> str:
        """Build narrative injection for a discovered secret."""
        return f"""[SIMULATION - SECRET DISCOVERED]
{secret.description}

The player has found or noticed this secret. Reveal it through their observation
or investigation. Make it feel like a reward for their curiosity."""

    def _build_timed_event_narrative(
        self,
        event: TimedEvent,
        stage_description: str
    ) -> str:
        """Build narrative injection for a timed event stage advance."""
        return f"""[SIMULATION - BACKGROUND EVENT PROGRESSION]
Event: {event.name}
Stage: {event.current_stage + 1}/{event.max_stages}

{stage_description}

Weave this background event into your response naturally. It should feel like
the world is progressing independently of the player's actions - news reaches
them, they notice changes in the environment, NPCs mention it in passing."""
