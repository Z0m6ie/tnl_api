"""Generate analysis reports for Claude to review playthroughs."""

from pathlib import Path
from typing import List
import json

from ..playthrough import Playthrough, MessageSource


class AnalysisReportGenerator:
    """Generate reports formatted for LLM review."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_review_prompt(self, playthroughs: List[Playthrough]) -> str:
        """
        Generate a comprehensive prompt for Claude to review all playthroughs.

        Returns a structured prompt that can be sent to Claude for analysis.
        """
        report = [
            "# TNL Playtest Analysis Request",
            "",
            "## Overview",
            f"You are reviewing {len(playthroughs)} automated playthroughs of The Narrative Loom (TNL).",
            "Each playthrough represents a different AI player with varying play styles and game settings.",
            "",
            "## Summary of Playthroughs",
            "",
            "| # | ID | Personality | Genre | Tone | Story | Character | Turns | Status |",
            "|---|-----|-------------|-------|------|-------|-----------|-------|--------|",
        ]

        for i, pt in enumerate(playthroughs):
            status = "OK" if pt.metadata.completed_normally else "FAILED"
            report.append(
                f"| {i+1} | {pt.metadata.playthrough_id[:8]} | "
                f"{pt.metadata.player_personality} | {pt.metadata.genre} | "
                f"{pt.metadata.tone} | {pt.metadata.story_type} | "
                f"{pt.metadata.character_name or 'N/A'} | {pt.metadata.total_turns} | {status} |"
            )

        report.extend([
            "",
            "## Your Task",
            "",
            "Analyze these playthroughs and identify issues and improvements in the following categories:",
            "",
            "### 1. Narrative Issues",
            "- Contradictions in the story (events, facts, or details that conflict)",
            "- NPCs acting out of character or inconsistently",
            "- Plot holes or loose threads that were never resolved",
            "- Inconsistent world details (locations, rules, history)",
            "- Tone breaks (e.g., comedy in horror, jarring mood shifts)",
            "- Pacing problems (too fast, too slow, anticlimactic)",
            "",
            "### 2. Recall Problems",
            "- AI forgetting previous events that were clearly established",
            "- Characters forgetting what was said earlier in conversation",
            "- Inventory items appearing/disappearing incorrectly",
            "- Location confusion (describing wrong place, inconsistent geography)",
            "- NPC names or details changing without explanation",
            "- Player character traits or abilities being forgotten",
            "",
            "### 3. Simulation Issues",
            "- Hidden elements (watchers, guards, traps) revealing too easily or never triggering",
            "- Consequences not matching the severity of actions",
            "- Timed events progressing incorrectly or not at all",
            "- Scene transitions being awkward or illogical",
            "- Triggers firing at inappropriate times",
            "",
            "### 4. Player Experience Issues",
            "- Confusing or ambiguous game outputs",
            "- Dead ends with no clear options",
            "- Overly punishing or trivially easy challenges",
            "- Lack of agency (player choices don't seem to matter)",
            "- Poor romantic tension buildup (for romance genres)",
            "- Character chemistry falling flat",
            "",
            "### 5. Genre-Specific Issues",
            "- Romance: Does the romantic tension build naturally? Are love interests compelling?",
            "- Mystery: Are clues planted fairly? Is the reveal satisfying?",
            "- Horror: Is tension maintained? Are scares earned?",
            "- Adventure: Is exploration rewarding? Are challenges engaging?",
            "",
            "### 6. Improvements Needed",
            "- Suggest specific prompt changes",
            "- Identify missing mechanics or systems",
            "- Recommend new simulation elements",
            "- Propose better handling of specific situations",
            "",
            "---",
            "",
            "# Full Playthrough Logs",
            "",
        ])

        for i, pt in enumerate(playthroughs):
            report.append(f"## Playthrough {i+1}: {pt.metadata.playthrough_id[:8]}")
            report.append("")
            report.append("### Metadata")
            report.append(f"- **Personality:** {pt.metadata.player_personality}")
            report.append(f"- **Genre:** {pt.metadata.genre} | **Tone:** {pt.metadata.tone} | **Story:** {pt.metadata.story_type}")
            report.append(f"- **Character:** {pt.metadata.character_name} ({pt.metadata.character_profession})")
            report.append(f"- **Background:** {pt.metadata.character_background}")
            report.append(f"- **Turns:** {pt.metadata.total_turns}")
            report.append(f"- **Locations Visited:** {', '.join(pt.metadata.locations_visited) or 'None tracked'}")
            report.append(f"- **NPCs Encountered:** {', '.join(pt.metadata.npcs_encountered) or 'None tracked'}")
            report.append(f"- **Simulation Triggers Fired:** {pt.metadata.simulation_triggers_fired}")
            report.append(f"- **Completed:** {pt.metadata.completed_normally}")
            if pt.metadata.error_message:
                report.append(f"- **Error:** {pt.metadata.error_message}")
            report.append("")

            # Include full conversation
            report.append("### Conversation Log")
            report.append("")

            for msg in pt.messages:
                source_prefix = {
                    MessageSource.SYSTEM: "**[SYSTEM]**",
                    MessageSource.PLAYER_AGENT: "**[PLAYER]**",
                    MessageSource.GAME: "**[GAME]**",
                }[msg.source]

                report.append(f"#### Turn {msg.turn} {source_prefix}")
                report.append("")
                report.append(msg.content)
                report.append("")

                if msg.player_reasoning:
                    report.append(f"*Agent reasoning: {msg.player_reasoning}*")
                    report.append("")

                if msg.triggered_elements:
                    report.append(f"*Simulation triggers: {', '.join(msg.triggered_elements)}*")
                    report.append("")

            report.append("---")
            report.append("")

        report.extend([
            "# Analysis Output Format",
            "",
            "Please provide your analysis in this JSON structure:",
            "",
            "```json",
            "{",
            '  "narrative_issues": [',
            '    {',
            '      "playthrough": "ID (first 8 chars)",',
            '      "turn": "turn number or range",',
            '      "severity": "high/medium/low",',
            '      "category": "contradiction/inconsistency/plot_hole/tone_break/pacing",',
            '      "description": "What went wrong",',
            '      "evidence": "Quote or reference to the problematic text",',
            '      "suggestion": "How to fix it"',
            '    }',
            "  ],",
            '  "recall_problems": [',
            '    {',
            '      "playthrough": "ID",',
            '      "turn": "turn number",',
            '      "what_was_forgotten": "The fact or detail that should have been remembered",',
            '      "original_mention": "Turn number where it was established",',
            '      "evidence": "Quote showing the inconsistency"',
            '    }',
            "  ],",
            '  "simulation_issues": [',
            '    {',
            '      "playthrough": "ID",',
            '      "turn": "turn number",',
            '      "element_type": "watcher/guard/fail_condition/secret/timed_event",',
            '      "issue": "What went wrong",',
            '      "fix": "Suggested fix"',
            '    }',
            "  ],",
            '  "experience_issues": [',
            '    {',
            '      "playthrough": "ID",',
            '      "turn": "turn number or range",',
            '      "issue": "What felt off",',
            '      "impact": "How it affected the experience",',
            '      "suggestion": "How to improve"',
            '    }',
            "  ],",
            '  "genre_issues": [',
            '    {',
            '      "playthrough": "ID",',
            '      "genre": "the genre",',
            '      "issue": "Genre-specific problem",',
            '      "suggestion": "How to fix"',
            '    }',
            "  ],",
            '  "improvements": [',
            '    {',
            '      "category": "prompts/mechanics/simulation/ui/world_gen/character",',
            '      "description": "What should be improved",',
            '      "priority": "high/medium/low",',
            '      "implementation_hint": "How to implement"',
            '    }',
            "  ],",
            '  "highlights": [',
            '    {',
            '      "playthrough": "ID",',
            '      "turn": "turn number",',
            '      "description": "What worked really well"',
            '    }',
            "  ],",
            '  "overall_quality_scores": {',
            '    "narrative_coherence": "1-10",',
            '    "player_agency": "1-10",',
            '    "immersion": "1-10",',
            '    "simulation_quality": "1-10",',
            '    "genre_execution": "1-10",',
            '    "overall": "1-10"',
            "  },",
            '  "summary": "Overall assessment in 3-5 sentences, highlighting the most critical issues and biggest wins"',
            "}",
            "```",
            "",
            "Focus on actionable feedback. If something works well, mention it in highlights. If something is broken, be specific about what and how to fix it.",
        ])

        return "\n".join(report)

    def save_review_prompt(
        self,
        playthroughs: List[Playthrough],
        filename: str = "review_prompt.md"
    ) -> Path:
        """Save the review prompt to a file."""
        prompt = self.generate_review_prompt(playthroughs)
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(prompt)

        return filepath

    def generate_compact_report(self, playthroughs: List[Playthrough]) -> str:
        """
        Generate a more compact report for context-limited scenarios.

        Only includes a sample of turns from each playthrough.
        """
        report = [
            "# TNL Playtest Analysis (Compact)",
            "",
            f"Reviewing {len(playthroughs)} playthroughs.",
            "",
        ]

        for i, pt in enumerate(playthroughs):
            report.append(f"## {i+1}. {pt.metadata.playthrough_id[:8]} ({pt.metadata.personality})")
            report.append(f"Genre: {pt.metadata.genre}, Tone: {pt.metadata.tone}")
            report.append(f"Character: {pt.metadata.character_name}, Turns: {pt.metadata.total_turns}")
            report.append("")

            # Sample: first 5 turns, every 10th turn, last 5 turns
            sample_turns = set()
            sample_turns.update(range(1, min(6, len(pt.messages) + 1)))
            sample_turns.update(range(10, len(pt.messages) + 1, 10))
            sample_turns.update(range(max(1, len(pt.messages) - 4), len(pt.messages) + 1))

            for msg in pt.messages:
                if msg.turn in sample_turns:
                    source = "P" if msg.source == MessageSource.PLAYER_AGENT else "G"
                    content_preview = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                    report.append(f"[T{msg.turn}/{source}] {content_preview}")
                    report.append("")

            report.append("---")
            report.append("")

        return "\n".join(report)

    def save_compact_report(
        self,
        playthroughs: List[Playthrough],
        filename: str = "review_compact.md"
    ) -> Path:
        """Save compact report to file."""
        prompt = self.generate_compact_report(playthroughs)
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(prompt)

        return filepath
