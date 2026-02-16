"""Playtest orchestrator - coordinates parallel playthrough execution."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List
from pathlib import Path

from tnl.llm import LLMClient

from .config import PlaytestConfig, AgentConfig
from .playthrough import Playthrough
from .runner import PlaythroughRunner

logger = logging.getLogger(__name__)


class PlaytestOrchestrator:
    """Coordinates parallel playthrough execution."""

    def __init__(self, config: PlaytestConfig):
        self.config = config
        self.results: List[Playthrough] = []
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_all(self) -> List[Playthrough]:
        """
        Run all configured playthroughs in parallel.

        Returns:
            List of completed Playthrough objects
        """
        agent_configs = self.config.get_agent_configs()
        logger.info(
            f"Starting {len(agent_configs)} parallel playtests "
            f"(max {self.config.max_concurrent_agents} concurrent)"
        )
        start_time = datetime.utcnow()

        # Run with thread pool (better for I/O-bound LLM calls)
        with ThreadPoolExecutor(max_workers=self.config.max_concurrent_agents) as executor:
            futures = {
                executor.submit(self._run_single, agent_config): agent_config.agent_id
                for agent_config in agent_configs
            }

            for future in as_completed(futures):
                agent_id = futures[future]
                try:
                    playthrough = future.result()
                    self.results.append(playthrough)

                    # Save immediately
                    self._save_playthrough(playthrough)

                    logger.info(
                        f"Agent {agent_id} completed: "
                        f"{playthrough.metadata.total_turns} turns, "
                        f"personality={playthrough.metadata.player_personality}, "
                        f"genre={playthrough.metadata.genre}"
                    )
                except Exception as e:
                    logger.error(f"Agent {agent_id} failed: {e}")

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"All playtests complete in {elapsed:.1f}s")

        # Generate summary report
        self._generate_summary()

        return self.results

    def run_single(self, agent_id: int = 0) -> Playthrough:
        """
        Run a single playthrough (useful for testing).

        Args:
            agent_id: Which agent config to use (default: 0)

        Returns:
            Completed Playthrough
        """
        agent_configs = self.config.get_agent_configs()
        if agent_id >= len(agent_configs):
            agent_id = 0

        agent_config = agent_configs[agent_id]
        playthrough = self._run_single(agent_config)

        self.results.append(playthrough)
        self._save_playthrough(playthrough)
        self._generate_summary()

        return playthrough

    def _run_single(self, agent_config: AgentConfig) -> Playthrough:
        """Run a single playthrough."""
        logger.info(
            f"Agent {agent_config.agent_id} starting: "
            f"personality={agent_config.personality.value}, "
            f"genre={agent_config.genre}"
        )

        # Each agent gets its own LLM client
        llm_client = LLMClient()

        runner = PlaythroughRunner(
            config=self.config,
            agent_config=agent_config,
            llm_client=llm_client,
        )

        return runner.run()

    def _save_playthrough(self, playthrough: Playthrough) -> None:
        """Save a playthrough to disk."""
        try:
            # Save JSON
            json_path = playthrough.save_json(str(self.output_dir))
            logger.debug(f"Saved JSON: {json_path}")

            # Save Markdown
            md_path = playthrough.save_markdown(str(self.output_dir))
            logger.debug(f"Saved Markdown: {md_path}")

        except Exception as e:
            logger.error(f"Failed to save playthrough: {e}")

    def _generate_summary(self) -> None:
        """Generate a summary report of all playthroughs."""
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "config": {
                "num_agents": self.config.num_agents,
                "messages_per_session": self.config.messages_per_session,
                "max_concurrent_agents": self.config.max_concurrent_agents,
                "vary_genres": self.config.vary_genres,
            },
            "total_playthroughs": len(self.results),
            "successful": sum(1 for p in self.results if p.metadata.completed_normally),
            "failed": sum(1 for p in self.results if not p.metadata.completed_normally),
            "playthroughs": [
                {
                    "id": p.metadata.playthrough_id[:8],
                    "personality": p.metadata.player_personality,
                    "genre": p.metadata.genre,
                    "tone": p.metadata.tone,
                    "story_type": p.metadata.story_type,
                    "character": p.metadata.character_name,
                    "turns": p.metadata.total_turns,
                    "locations": len(p.metadata.locations_visited),
                    "npcs": len(p.metadata.npcs_encountered),
                    "triggers_fired": p.metadata.simulation_triggers_fired,
                    "completed": p.metadata.completed_normally,
                    "error": p.metadata.error_message,
                }
                for p in self.results
            ],
            "genre_distribution": self._count_by_field("genre"),
            "personality_distribution": self._count_by_field("player_personality"),
        }

        summary_path = self.output_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Summary written to {summary_path}")

    def _count_by_field(self, field: str) -> dict:
        """Count playthroughs by a metadata field."""
        counts = {}
        for p in self.results:
            value = getattr(p.metadata, field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts

    def load_results(self) -> List[Playthrough]:
        """Load all playthroughs from the output directory."""
        self.results = []
        for json_file in self.output_dir.glob("*.json"):
            if json_file.name == "summary.json":
                continue
            try:
                playthrough = Playthrough.load_json(str(json_file))
                self.results.append(playthrough)
            except Exception as e:
                logger.warning(f"Failed to load {json_file}: {e}")

        logger.info(f"Loaded {len(self.results)} playthroughs from {self.output_dir}")
        return self.results
