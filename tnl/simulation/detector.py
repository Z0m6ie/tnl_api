"""Scene transition detector.

Detects when a player is entering a new scene/location from their input.
"""

import re
from typing import Optional


class SceneDetector:
    """Detect scene transitions from player input."""

    # Keywords indicating location change
    MOVEMENT_KEYWORDS = [
        "go to",
        "walk to",
        "walk into",
        "enter",
        "head to",
        "head into",
        "visit",
        "step into",
        "step inside",
        "approach",
        "leave for",
        "exit to",
        "travel to",
        "make my way to",
        "head inside",
        "go inside",
        "walk inside",
        "go in",
        "walk in",
    ]

    # Words to strip from extracted locations
    STRIP_WORDS = ["the", "a", "an", "to", "into", "inside"]

    def detect_scene_transition(
        self,
        player_input: str,
        current_location: Optional[str] = None
    ) -> Optional[str]:
        """
        Detect if player is transitioning to a new location.

        Args:
            player_input: What the player typed
            current_location: Current location (to avoid detecting same location)

        Returns:
            New location name if transitioning, None otherwise
        """
        input_lower = player_input.lower()

        for keyword in self.MOVEMENT_KEYWORDS:
            if keyword in input_lower:
                location = self._extract_location(input_lower, keyword)
                if location:
                    # Normalize the location name
                    location = self._normalize_location(location)

                    # Check if it's actually a new location
                    if current_location is None:
                        return location
                    if location.lower() != current_location.lower():
                        return location

        return None

    def _extract_location(self, text: str, keyword: str) -> Optional[str]:
        """Extract location name from text after movement keyword."""
        idx = text.find(keyword)
        if idx < 0:
            return None

        # Get text after the keyword
        after = text[idx + len(keyword):].strip()

        if not after:
            return None

        # Take up to punctuation or reasonable word limit
        # Split on common sentence endings
        after = re.split(r'[.!?,;:]', after)[0].strip()

        # Take first 5 words max
        words = after.split()[:5]

        if not words:
            return None

        return " ".join(words)

    def _normalize_location(self, location: str) -> str:
        """Clean up and normalize a location name."""
        words = location.lower().split()

        # Remove leading articles and prepositions
        while words and words[0] in self.STRIP_WORDS:
            words = words[1:]

        if not words:
            return location.title()

        # Capitalize each word
        return " ".join(word.capitalize() for word in words)
