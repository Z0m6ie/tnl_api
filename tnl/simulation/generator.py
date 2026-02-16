"""Scene simulation generator.

Generates hidden simulation elements for a scene on-demand when the player enters.
"""

import json
import logging
import re
from typing import Optional
from uuid import uuid4

from ..llm import LLMClient
from ..models.campaign import CampaignState
from ..models.simulation import (
    SceneSimulation,
    Watcher,
    HiddenGuard,
    FailCondition,
    Secret,
    TriggerCondition,
    TriggerType,
    Severity,
)

logger = logging.getLogger(__name__)


SCENE_SIMULATION_PROMPT = """Generate HIDDEN simulation elements for this scene as JSON.

LOCATION: {location}
GENRE: {genre} | TONE: {tone}
CHARACTER: {character_summary}
WORLD CONTEXT: {world_context}

Generate pre-existing hidden elements that exist BEFORE the player acts.

IMPORTANT: Output ONLY valid JSON, no explanation text. Start with {{ and end with }}.

Output this exact JSON structure (1-2 of each type):
{{
    "location_description": "Brief hidden notes about this place",

    "watchers": [
        {{
            "name": "Who is watching",
            "description": "How they watch and what they're looking for",
            "faction": "Which faction they serve",
            "reports_to": "Who they report to",
            "trigger_keywords": ["words that draw attention"],
            "probability": 0.7
        }}
    ],

    "hidden_guards": [
        {{
            "name": "Guard description",
            "guard_type": "armed/magical/automated/creature",
            "location_within_scene": "Where exactly they are",
            "trigger_keywords": ["words that trigger them"],
            "weaknesses": ["how to avoid or defeat"]
        }}
    ],

    "fail_conditions": [
        {{
            "name": "What action fails",
            "description": "Why this is dangerous here",
            "trigger_keywords": ["words that trigger"],
            "probability": 0.8,
            "severity": "minor/moderate/severe",
            "consequence_narrative": "What happens if triggered (2-3 sentences)",
            "can_escape": true,
            "escape_conditions": ["ways to mitigate"]
        }}
    ],

    "secrets": [
        {{
            "description": "Something hidden the player could discover",
            "discovery_keywords": ["search", "examine", "look"]
        }}
    ]
}}

Match the {genre} and {tone}. Be creative but consistent with the world context.

CRITICAL: Output ONLY the JSON object. No markdown code blocks, no explanation, no text before or after. Just the raw JSON starting with {{ and ending with }}."""


class SceneSimulationGenerator:
    """Generate hidden elements for a scene on-demand."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_scene_simulation(
        self,
        location: str,
        state: CampaignState,
        world_context: str
    ) -> SceneSimulation:
        """
        Generate hidden elements for this specific scene.

        Called BEFORE the scene description is generated.

        Args:
            location: Name of the location being entered
            state: Current campaign state
            world_context: Relevant world seed chunks

        Returns:
            SceneSimulation with watchers, guards, fail conditions, secrets
        """
        prompt = SCENE_SIMULATION_PROMPT.format(
            location=location,
            genre=state.genre or "Fantasy",
            tone=state.tone or "Gritty",
            character_summary=state.character_sheet.summary(),
            world_context=world_context,
        )

        try:
            logger.debug(f"Generating simulation for location: {location}")
            # GPT-5.2 Thinking model uses internal reasoning tokens, so we need
            # higher max_tokens to ensure the actual output isn't truncated
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=4000,
                temperature=0.7,
            )
            logger.debug(f"Got response of length {len(response) if response else 0}")

            scene = self._parse_response(response, location, state.current_turn)
            logger.info(f"Generated simulation for '{location}': "
                       f"{len(scene.watchers)} watchers, "
                       f"{len(scene.hidden_guards)} guards, "
                       f"{len(scene.fail_conditions)} fail conditions, "
                       f"{len(scene.secrets)} secrets")
            return scene

        except Exception as e:
            logger.error(f"Failed to generate scene simulation for '{location}': {e}")
            # Return empty scene on failure
            return SceneSimulation(
                location=location,
                generated_at_turn=state.current_turn
            )

    def _parse_response(
        self,
        response: str,
        location: str,
        current_turn: int
    ) -> SceneSimulation:
        """Parse LLM response into SceneSimulation."""
        # Extract JSON from response
        json_str = self._extract_json(response)

        if not json_str:
            logger.warning(f"No JSON found in simulation response. Response preview: {response[:200] if response else 'EMPTY'}")
            return SceneSimulation(location=location, generated_at_turn=current_turn)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse simulation JSON: {e}")
            return SceneSimulation(location=location, generated_at_turn=current_turn)

        # Build scene simulation
        scene = SceneSimulation(
            location=location,
            location_description=data.get("location_description", ""),
            generated_at_turn=current_turn,
        )

        # Parse watchers
        for i, w in enumerate(data.get("watchers", [])):
            scene.watchers.append(Watcher(
                id=f"watcher_{location}_{i}_{uuid4().hex[:6]}",
                name=w.get("name", "Unknown Watcher"),
                description=w.get("description", ""),
                faction=w.get("faction", ""),
                reports_to=w.get("reports_to", ""),
                triggers=[TriggerCondition(
                    trigger_type=TriggerType.KEYWORD,
                    keywords=w.get("trigger_keywords", []),
                    probability=w.get("probability", 0.7),
                )],
            ))

        # Parse hidden guards
        for i, g in enumerate(data.get("hidden_guards", [])):
            scene.hidden_guards.append(HiddenGuard(
                id=f"guard_{location}_{i}_{uuid4().hex[:6]}",
                name=g.get("name", "Unknown Guard"),
                guard_type=g.get("guard_type", "armed"),
                location_within_scene=g.get("location_within_scene", ""),
                weaknesses=g.get("weaknesses", []),
                triggers=[TriggerCondition(
                    trigger_type=TriggerType.KEYWORD,
                    keywords=g.get("trigger_keywords", []),
                    probability=g.get("probability", 0.9),
                )],
            ))

        # Parse fail conditions
        for i, f in enumerate(data.get("fail_conditions", [])):
            severity_str = f.get("severity", "moderate").lower()
            try:
                severity = Severity(severity_str)
            except ValueError:
                severity = Severity.MODERATE

            scene.fail_conditions.append(FailCondition(
                id=f"fail_{location}_{i}_{uuid4().hex[:6]}",
                name=f.get("name", "Unknown Condition"),
                description=f.get("description", ""),
                severity=severity,
                consequence_narrative=f.get("consequence_narrative", ""),
                can_escape=f.get("can_escape", True),
                escape_conditions=f.get("escape_conditions", []),
                triggers=[TriggerCondition(
                    trigger_type=TriggerType.KEYWORD,
                    keywords=f.get("trigger_keywords", []),
                    probability=f.get("probability", 0.8),
                )],
            ))

        # Parse secrets
        for i, s in enumerate(data.get("secrets", [])):
            scene.secrets.append(Secret(
                id=f"secret_{location}_{i}_{uuid4().hex[:6]}",
                description=s.get("description", ""),
                discovery_triggers=[TriggerCondition(
                    trigger_type=TriggerType.KEYWORD,
                    keywords=s.get("discovery_keywords", ["search", "examine"]),
                    probability=1.0,
                )],
            ))

        return scene

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from LLM response."""
        # Try code block first
        if "```json" in text:
            match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                return match.group(1)

        if "```" in text:
            match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                return match.group(1)

        # Try to find raw JSON object
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return match.group(0)

        return None
