"""Base phase class and result type."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from ..models.campaign import CampaignPhase, CampaignState


@dataclass
class PhaseResult:
    """Result of processing a phase action."""

    # Message to display to the user
    display_message: str

    # Next phase (None = stay in current phase)
    next_phase: Optional[CampaignPhase] = None

    # Whether the phase is complete
    complete: bool = False

    # Error message if something went wrong
    error: Optional[str] = None


class Phase(ABC):
    """Abstract base class for campaign phases."""

    @property
    @abstractmethod
    def phase_type(self) -> CampaignPhase:
        """Return the phase type this handler manages."""
        pass

    @abstractmethod
    def enter(self, state: CampaignState) -> str:
        """
        Called when entering this phase.

        Args:
            state: Current campaign state

        Returns:
            Welcome/intro message to display
        """
        pass

    @abstractmethod
    def handle_input(self, user_input: str, state: CampaignState) -> PhaseResult:
        """
        Process user input in this phase.

        Args:
            user_input: What the user typed
            state: Current campaign state (will be mutated)

        Returns:
            PhaseResult with display message and optional next phase
        """
        pass

    def can_skip(self) -> bool:
        """Whether this phase can be skipped (e.g., on resume)."""
        return False
