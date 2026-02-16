"""Playthrough data model for storing complete session data."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
from uuid import uuid4
import json
from pathlib import Path


class MessageSource(str, Enum):
    """Source of a message in a playthrough."""

    SYSTEM = "system"
    PLAYER_AGENT = "player_agent"
    GAME = "game"


@dataclass
class PlaythroughMessage:
    """A single message in a playthrough."""

    turn: int
    source: MessageSource
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Optional metadata for analysis
    player_reasoning: Optional[str] = None  # Why agent chose this action
    triggered_elements: List[str] = field(default_factory=list)
    state_changes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "turn": self.turn,
            "source": self.source.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "player_reasoning": self.player_reasoning,
            "triggered_elements": self.triggered_elements,
            "state_changes": self.state_changes,
        }


@dataclass
class PlaythroughMetadata:
    """Metadata about a playthrough session."""

    playthrough_id: str = field(default_factory=lambda: uuid4().hex)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Campaign settings
    genre: Optional[str] = None
    tone: Optional[str] = None
    story_type: Optional[str] = None

    # Character info
    character_name: Optional[str] = None
    character_profession: Optional[str] = None
    character_background: Optional[str] = None

    # Agent settings
    player_personality: str = "cautious"
    agent_model: str = "gpt-5.2"

    # Stats
    total_turns: int = 0
    locations_visited: List[str] = field(default_factory=list)
    npcs_encountered: List[str] = field(default_factory=list)
    simulation_triggers_fired: int = 0

    # Completion status
    completed_normally: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "playthrough_id": self.playthrough_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "genre": self.genre,
            "tone": self.tone,
            "story_type": self.story_type,
            "character_name": self.character_name,
            "character_profession": self.character_profession,
            "character_background": self.character_background,
            "player_personality": self.player_personality,
            "agent_model": self.agent_model,
            "total_turns": self.total_turns,
            "locations_visited": self.locations_visited,
            "npcs_encountered": self.npcs_encountered,
            "simulation_triggers_fired": self.simulation_triggers_fired,
            "completed_normally": self.completed_normally,
            "error_message": self.error_message,
        }


@dataclass
class Playthrough:
    """Complete playthrough data for storage and analysis."""

    metadata: PlaythroughMetadata = field(default_factory=PlaythroughMetadata)
    messages: List[PlaythroughMessage] = field(default_factory=list)

    # Full state snapshots at key points
    initial_state: Optional[Dict[str, Any]] = None
    final_state: Optional[Dict[str, Any]] = None

    # Simulation data (for debugging)
    simulation_snapshots: List[Dict[str, Any]] = field(default_factory=list)

    def add_message(
        self,
        source: MessageSource,
        content: str,
        player_reasoning: Optional[str] = None,
        triggered_elements: Optional[List[str]] = None,
        state_changes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a message to the playthrough."""
        self.metadata.total_turns = len(self.messages) + 1
        self.messages.append(PlaythroughMessage(
            turn=self.metadata.total_turns,
            source=source,
            content=content,
            player_reasoning=player_reasoning,
            triggered_elements=triggered_elements or [],
            state_changes=state_changes or {},
        ))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "metadata": self.metadata.to_dict(),
            "messages": [m.to_dict() for m in self.messages],
            "initial_state": self.initial_state,
            "final_state": self.final_state,
            "simulation_snapshots": self.simulation_snapshots,
        }

    def save_json(self, output_dir: str) -> Path:
        """Save playthrough to JSON file."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filepath = output_path / f"{self.metadata.playthrough_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

        return filepath

    def save_markdown(self, output_dir: str) -> Path:
        """Save playthrough as readable markdown."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filepath = output_path / f"{self.metadata.playthrough_id}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_markdown_report())

        return filepath

    def to_markdown_report(self) -> str:
        """Generate readable markdown for human/LLM review."""
        lines = [
            f"# Playthrough Report: {self.metadata.playthrough_id[:8]}",
            "",
            "## Metadata",
            f"- **Genre:** {self.metadata.genre}",
            f"- **Tone:** {self.metadata.tone}",
            f"- **Story Type:** {self.metadata.story_type}",
            f"- **Character:** {self.metadata.character_name} ({self.metadata.character_profession})",
            f"- **Player Personality:** {self.metadata.player_personality}",
            f"- **Total Turns:** {self.metadata.total_turns}",
            f"- **Locations Visited:** {', '.join(self.metadata.locations_visited) or 'None'}",
            f"- **NPCs Encountered:** {', '.join(self.metadata.npcs_encountered) or 'None'}",
            f"- **Completed:** {self.metadata.completed_normally}",
            "",
            "## Conversation",
            "",
        ]

        for msg in self.messages:
            source_label = {
                MessageSource.SYSTEM: "[SYSTEM]",
                MessageSource.PLAYER_AGENT: "[PLAYER]",
                MessageSource.GAME: "[GAME]",
            }[msg.source]

            lines.append(f"### Turn {msg.turn} {source_label}")
            lines.append("")
            lines.append(msg.content)
            lines.append("")

            if msg.player_reasoning:
                lines.append(f"*Agent reasoning: {msg.player_reasoning}*")
                lines.append("")

            if msg.triggered_elements:
                lines.append(f"*Triggered: {', '.join(msg.triggered_elements)}*")
                lines.append("")

        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Playthrough":
        """Deserialize from dictionary."""
        metadata_data = data.get("metadata", {})
        metadata = PlaythroughMetadata(
            playthrough_id=metadata_data.get("playthrough_id", uuid4().hex),
            started_at=datetime.fromisoformat(metadata_data["started_at"]) if metadata_data.get("started_at") else datetime.utcnow(),
            completed_at=datetime.fromisoformat(metadata_data["completed_at"]) if metadata_data.get("completed_at") else None,
            genre=metadata_data.get("genre"),
            tone=metadata_data.get("tone"),
            story_type=metadata_data.get("story_type"),
            character_name=metadata_data.get("character_name"),
            character_profession=metadata_data.get("character_profession"),
            character_background=metadata_data.get("character_background"),
            player_personality=metadata_data.get("player_personality", "cautious"),
            agent_model=metadata_data.get("agent_model", "gpt-5.2"),
            total_turns=metadata_data.get("total_turns", 0),
            locations_visited=metadata_data.get("locations_visited", []),
            npcs_encountered=metadata_data.get("npcs_encountered", []),
            simulation_triggers_fired=metadata_data.get("simulation_triggers_fired", 0),
            completed_normally=metadata_data.get("completed_normally", False),
            error_message=metadata_data.get("error_message"),
        )

        messages = []
        for msg_data in data.get("messages", []):
            messages.append(PlaythroughMessage(
                turn=msg_data["turn"],
                source=MessageSource(msg_data["source"]),
                content=msg_data["content"],
                timestamp=datetime.fromisoformat(msg_data["timestamp"]) if msg_data.get("timestamp") else datetime.utcnow(),
                player_reasoning=msg_data.get("player_reasoning"),
                triggered_elements=msg_data.get("triggered_elements", []),
                state_changes=msg_data.get("state_changes", {}),
            ))

        return cls(
            metadata=metadata,
            messages=messages,
            initial_state=data.get("initial_state"),
            final_state=data.get("final_state"),
            simulation_snapshots=data.get("simulation_snapshots", []),
        )

    @classmethod
    def load_json(cls, filepath: str) -> "Playthrough":
        """Load playthrough from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
