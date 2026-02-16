"""Configuration for automated playtesting."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum


class PlayerPersonality(str, Enum):
    """Different play styles for AI player agents."""

    AGGRESSIVE = "aggressive"      # Combat-focused, direct approach
    CAUTIOUS = "cautious"          # Careful, information-gathering
    CURIOUS = "curious"            # Explores everything, asks questions
    CHAOTIC = "chaotic"            # Unpredictable, tests edge cases
    ROLEPLAYER = "roleplayer"      # Deep character immersion
    SPEEDRUNNER = "speedrunner"    # Tries to advance quickly
    ADVERSARIAL = "adversarial"    # Tries to break the system


# Default pools for genre/tone/story variety
GENRE_POOL = [
    "noir", "fantasy", "sci-fi", "gothic horror", "steampunk",
    "contemporary romance", "romantasy", "historical romance",
    "cyberpunk", "urban fantasy", "post-apocalyptic"
]

TONE_POOL = [
    "gritty", "whimsical", "tense", "melancholic", "quirky",
    "warm", "passionate", "dramatic", "dark", "epic", "bleak"
]

STORY_TYPE_POOL = [
    "mystery", "adventure", "survival", "tragedy", "heist",
    "slow-burn romance", "enemies-to-lovers", "forbidden love",
    "fated mates", "revenge", "conspiracy", "escape"
]

# Default combinations for 10 agents (personality, genre, tone, story_type)
DEFAULT_AGENT_CONFIGS: List[Tuple[PlayerPersonality, str, str, str]] = [
    (PlayerPersonality.CAUTIOUS, "noir", "gritty", "mystery"),
    (PlayerPersonality.CURIOUS, "fantasy", "whimsical", "adventure"),
    (PlayerPersonality.AGGRESSIVE, "sci-fi", "tense", "survival"),
    (PlayerPersonality.ROLEPLAYER, "gothic horror", "melancholic", "tragedy"),
    (PlayerPersonality.CHAOTIC, "steampunk", "quirky", "heist"),
    (PlayerPersonality.ROLEPLAYER, "contemporary romance", "warm", "slow-burn romance"),
    (PlayerPersonality.CURIOUS, "romantasy", "passionate", "enemies-to-lovers"),
    (PlayerPersonality.SPEEDRUNNER, "post-apocalyptic", "bleak", "escape"),
    (PlayerPersonality.ROLEPLAYER, "historical romance", "dramatic", "forbidden love"),
    (PlayerPersonality.CAUTIOUS, "romantasy", "epic", "fated mates"),
]


@dataclass
class AgentConfig:
    """Configuration for a single playtest agent."""

    personality: PlayerPersonality
    genre: str
    tone: str
    story_type: str
    agent_id: int = 0

    def onboarding_input(self) -> str:
        """Generate the onboarding input string for genre/tone/story selection."""
        return f"{self.genre}, {self.tone}, {self.story_type}"


@dataclass
class PlaytestConfig:
    """Configuration for a playtest session."""

    # Execution settings
    num_agents: int = 10
    messages_per_session: int = 100

    # Rate limiting
    max_concurrent_agents: int = 5
    delay_between_messages_ms: int = 100

    # Output settings
    output_dir: str = "./playtest_results"

    # Genre variety
    vary_genres: bool = True
    genre_pool: List[str] = field(default_factory=lambda: GENRE_POOL.copy())
    tone_pool: List[str] = field(default_factory=lambda: TONE_POOL.copy())
    story_type_pool: List[str] = field(default_factory=lambda: STORY_TYPE_POOL.copy())

    # Explicit agent configs (if provided, overrides num_agents)
    agent_configs: Optional[List[AgentConfig]] = None

    # Default personalities (used if agent_configs not provided)
    personalities: List[PlayerPersonality] = field(default_factory=lambda: [
        PlayerPersonality.CAUTIOUS,
        PlayerPersonality.CURIOUS,
        PlayerPersonality.AGGRESSIVE,
        PlayerPersonality.ROLEPLAYER,
        PlayerPersonality.CHAOTIC,
        PlayerPersonality.ROLEPLAYER,
        PlayerPersonality.CURIOUS,
        PlayerPersonality.SPEEDRUNNER,
        PlayerPersonality.ADVERSARIAL,
        PlayerPersonality.ROLEPLAYER,
    ])

    def get_agent_configs(self) -> List[AgentConfig]:
        """Get agent configurations for all agents."""
        if self.agent_configs:
            return self.agent_configs

        if self.vary_genres:
            # Use default varied configurations
            configs = []
            for i in range(self.num_agents):
                if i < len(DEFAULT_AGENT_CONFIGS):
                    personality, genre, tone, story = DEFAULT_AGENT_CONFIGS[i]
                else:
                    # Cycle through defaults for additional agents
                    base = DEFAULT_AGENT_CONFIGS[i % len(DEFAULT_AGENT_CONFIGS)]
                    personality, genre, tone, story = base

                configs.append(AgentConfig(
                    agent_id=i,
                    personality=personality,
                    genre=genre,
                    tone=tone,
                    story_type=story,
                ))
            return configs
        else:
            # All agents use random genre (surprise me)
            configs = []
            for i in range(self.num_agents):
                personality = self.personalities[i % len(self.personalities)]
                configs.append(AgentConfig(
                    agent_id=i,
                    personality=personality,
                    genre="surprise me",
                    tone="",
                    story_type="",
                ))
            return configs
