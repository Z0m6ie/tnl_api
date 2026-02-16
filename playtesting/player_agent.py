"""AI player agent that generates plausible player actions."""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from tnl.llm import LLMClient
from .config import PlayerPersonality


PLAYER_AGENT_SYSTEM_PROMPT = """You are an AI playing a text-based RPG game called The Narrative Loom.

YOUR PERSONALITY: {personality_description}

YOUR CHARACTER: {character_summary}

YOUR GOAL: Play through this game as a real player would, making choices that feel natural for your personality type. You are NOT trying to "win" - you are exploring the experience.

IMPORTANT RULES:
1. Respond with ONLY your action/dialogue - no meta-commentary
2. Keep actions concise (1-3 sentences typically)
3. Stay in character for your assigned personality
4. Reference things mentioned in recent game context
5. Sometimes make mistakes or suboptimal choices - real players do
6. Occasionally ask questions or request clarification
7. React emotionally to events (excitement, fear, curiosity, attraction, nervousness)

OUTPUT FORMAT:
First, briefly explain your reasoning in [REASONING: ...] tags.
Then provide your actual player input.

Example:
[REASONING: The bartender mentioned a back room - my curious personality wants to investigate]
I lean closer to the bartender. "You mentioned a back room earlier. What goes on back there?"
"""

PERSONALITY_DESCRIPTIONS = {
    PlayerPersonality.AGGRESSIVE: """You are an AGGRESSIVE player. You prefer direct action over subtlety.
You solve problems with force when possible, confront NPCs directly, and don't shy away from combat or confrontation.
You get impatient with lengthy conversations and prefer to cut to the chase.""",

    PlayerPersonality.CAUTIOUS: """You are a CAUTIOUS player. You gather information before acting.
You look for traps, ask questions, scout ahead, and avoid unnecessary risks.
You prefer to have a plan before engaging with dangerous situations.""",

    PlayerPersonality.CURIOUS: """You are a CURIOUS player. You want to explore everything.
You examine objects, talk to NPCs extensively, follow side threads, and investigate mysteries.
You sometimes get distracted from the main quest by interesting details.""",

    PlayerPersonality.CHAOTIC: """You are a CHAOTIC player. You make unpredictable choices.
You might steal from allies, start fights randomly, or try absurd solutions.
You test the boundaries of what's possible and don't follow obvious paths.""",

    PlayerPersonality.ROLEPLAYER: """You are a ROLEPLAYER. You stay deeply in character.
You make choices based on your character's personality and backstory, not optimal gameplay.
You engage in detailed dialogue, care about NPC relationships, and express emotions.
In romantic scenarios, you lean into the tension and chemistry between characters.""",

    PlayerPersonality.SPEEDRUNNER: """You are a SPEEDRUNNER. You want to advance the story quickly.
You skip optional content, choose efficient paths, and don't linger on details.
You try to identify and pursue the main objective as directly as possible.""",

    PlayerPersonality.ADVERSARIAL: """You are an ADVERSARIAL tester. You try to break the game.
You attempt impossible actions, try to confuse the AI, input edge cases.
You test what happens when you ignore prompts or go against expectations.""",
}

# Character generation prompts based on personality and genre
CHARACTER_PROMPTS = {
    PlayerPersonality.AGGRESSIVE: "a tough, combat-ready character with a chip on their shoulder",
    PlayerPersonality.CAUTIOUS: "a careful, observant character who thinks before acting",
    PlayerPersonality.CURIOUS: "an inquisitive character fascinated by the world around them",
    PlayerPersonality.CHAOTIC: "an unpredictable wild card who doesn't play by the rules",
    PlayerPersonality.ROLEPLAYER: "a complex character with emotional depth and clear motivations",
    PlayerPersonality.SPEEDRUNNER: "a focused, goal-oriented character who cuts through nonsense",
    PlayerPersonality.ADVERSARIAL: "an unusual character who tests boundaries",
}


@dataclass
class PlayerAgentResponse:
    """Response from the player agent."""

    action: str
    reasoning: str


class PlayerAgent:
    """AI agent that plays as a human player would."""

    def __init__(
        self,
        llm_client: LLMClient,
        personality: PlayerPersonality,
        character_summary: str = "",
    ):
        self.llm = llm_client
        self.personality = personality
        self.character_summary = character_summary
        self._conversation_context: List[Dict[str, str]] = []

    def set_character(self, character_summary: str) -> None:
        """Update character info after character creation."""
        self.character_summary = character_summary

    def generate_action(
        self,
        game_output: str,
        recent_context: Optional[List[Dict[str, str]]] = None,
    ) -> PlayerAgentResponse:
        """
        Generate the next player action based on game output.

        Args:
            game_output: The latest output from the game
            recent_context: Recent conversation history

        Returns:
            PlayerAgentResponse with action and reasoning
        """
        system_prompt = PLAYER_AGENT_SYSTEM_PROMPT.format(
            personality_description=PERSONALITY_DESCRIPTIONS[self.personality],
            character_summary=self.character_summary or "Not yet created",
        )

        # Build context from recent game history
        context = recent_context or self._conversation_context[-10:]

        prompt = f"""The game just showed you:

---
{game_output}
---

What do you do or say? Remember to include [REASONING: ...] first, then your action."""

        response = self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            context=context,
            max_tokens=300,
            temperature=0.9,  # Higher for more varied responses
        )

        # Parse response
        action, reasoning = self._parse_response(response)

        return PlayerAgentResponse(action=action, reasoning=reasoning)

    def generate_character_description(self, genre: str, tone: str, story_type: str) -> PlayerAgentResponse:
        """Generate a character description appropriate for the setting."""
        personality_hint = CHARACTER_PROMPTS.get(
            self.personality,
            "an interesting character"
        )

        prompt = f"""Generate a brief character description for a {genre} {story_type} story with a {tone} tone.

The character should be {personality_hint}.

Include:
- Name
- Brief background (1 sentence)
- Profession or role
- 2-3 personality traits
- A personal goal or motivation

Keep it to 3-5 sentences total. Output ONLY the character description, nothing else."""

        response = self.llm.generate(
            prompt=prompt,
            max_tokens=250,
            temperature=0.9,
        )

        return PlayerAgentResponse(
            action=response.strip(),
            reasoning=f"Generated {self.personality.value}-style character for {genre} {story_type}"
        )

    def generate_confirmation(self) -> PlayerAgentResponse:
        """Generate a confirmation response (yes to character)."""
        # Roleplayers might add flavor, others just confirm
        if self.personality == PlayerPersonality.ROLEPLAYER:
            return PlayerAgentResponse(
                action="Yes, that captures them perfectly.",
                reasoning="Confirming character with enthusiasm"
            )
        elif self.personality == PlayerPersonality.CHAOTIC:
            return PlayerAgentResponse(
                action="sure whatever lets go",
                reasoning="Chaotic quick confirmation"
            )
        else:
            return PlayerAgentResponse(
                action="yes",
                reasoning="Simple confirmation"
            )

    def generate_continue(self) -> PlayerAgentResponse:
        """Generate a continue response for the ready phase."""
        return PlayerAgentResponse(
            action="continue",
            reasoning="Ready to begin the adventure"
        )

    def _parse_response(self, response: str) -> Tuple[str, str]:
        """Parse response to extract reasoning and action."""
        # Try to extract reasoning
        reasoning_match = re.search(r'\[REASONING:\s*(.*?)\]', response, re.DOTALL | re.IGNORECASE)
        reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

        # Remove reasoning tags to get action
        action = re.sub(r'\[REASONING:.*?\]', '', response, flags=re.DOTALL | re.IGNORECASE).strip()

        # If no action after removing reasoning, use the whole response
        if not action:
            action = response.strip()

        return action, reasoning
