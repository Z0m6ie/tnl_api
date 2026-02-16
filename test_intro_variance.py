"""Test intro variance with fixed world/character.

Runs multiple intros with the same genre, tone, story type, and character
to see how the different structural templates produce different results.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from tnl.llm import LLMClient
from tnl.prompts import build_intro_prompt
from tnl.prompts.templates import INTRO_STRUCTURE_TEMPLATES

# Fixed test data (matching user's Streamlit session)
GENRE = "Steampunk"
TONE = "Whimsical"
STORY_TYPE = "Heist thriller"

CHARACTER_SUMMARY = """Lysander "Lark" Quillwren
Clockwork illusionist and master infiltrator (gentleman thief)

Once a celebrated clockwork illusionist in the grand aerodromes of Brassport, Lark vanished after a botched gala performance revealed he'd been using his act to skim secrets from the city's elite. Now he lives between soot-stained rooftops and velvet salons, trading in favors, disguises, and exquisitely timed misdirection. A meticulous thief with a flair for spectacle, he's always one step ahead—until the past catches up.

Traits: Charming and theatrical, Obsessively punctual, Clever improviser under pressure, Secretive but loyal to a chosen few, Addicted to risk and applause
Goal: Steal the Aetherheart Prism from the Imperial Patent Vault to erase his old debts and expose the magnates who framed him—without letting his former partner-turned-inspector catch him first."""

WORLD_CONTEXT = """ATMOSPHERIC SETUP:
Brassport sprawls beneath a copper sky. Airships drift between clocktowers. Steam rises from cobblestones. The air tastes of coal dust and brass polish. Automaton porters clatter through crowded markets. Street performers juggle gears that tick in time with music-box melodies.

FACTIONS:
- The Gilded Aerodrome Consortium (public: airship transport magnates; hidden: controls city patents and buys political favors)
- The Velvet Canal Syndicate (public: dock charity and salvage union; hidden: smuggles contraband and protects working-class secrets)
- The Mechanical Inspectorate (public: patent enforcement and theft prevention; hidden: serves Consortium interests, frames rivals)

KEY FIGURES:
- Inspector Caldrin (former partner, now hunts Lark for the Inspectorate)
- Madame Vesper (Syndicate contact, runs a canal-side automaton repair shop)
- Director Cobb (Consortium puppet, controls the Patent Vault)

ACTIVE EVENTS:
- The Consortium is moving the Aetherheart Prism to a secure vault tomorrow
- Inspector Caldrin has been ordered to capture Lark alive
- The Syndicate is planning a distraction at the docks"""


def test_intro_variance(num_samples: int = 3):
    """Generate multiple intros and compare them."""
    client = LLMClient()

    print("=" * 70)
    print("INTRO VARIANCE TEST")
    print(f"Genre: {GENRE} | Tone: {TONE} | Story: {STORY_TYPE}")
    print("=" * 70)
    print()

    results = []

    for i in range(num_samples):
        print(f"--- Sample {i+1}/{num_samples} ---")

        # Build prompt (this randomizes hook and structure)
        prompt = build_intro_prompt(
            genre=GENRE,
            tone=TONE,
            story_type=STORY_TYPE,
            character_summary=CHARACTER_SUMMARY,
            world_context=WORLD_CONTEXT,
        )

        # Extract which structure was selected (it's embedded in the prompt)
        structure = "unknown"
        for name in INTRO_STRUCTURE_TEMPLATES.keys():
            if name == "standard" and "WHERE and WHEN (2 sentences)" in prompt:
                structure = "standard"
            elif name == "in_media_res" and "ACTION FIRST" in prompt:
                structure = "in_media_res"
            elif name == "atmosphere" and "THE PLACE (3 sentences)" in prompt:
                structure = "atmosphere"
            elif name == "character" and "THE CHARACTER AT WORK" in prompt:
                structure = "character"

        print(f"Structure: {structure}")

        # Generate intro
        response = client.generate(
            prompt=prompt,
            system_prompt="You are a narrative writer for an RPG.",
            max_tokens=600,
        )

        intro = response.strip()
        results.append({
            "structure": structure,
            "intro": intro,
        })

        print(f"\n{intro}\n")
        print()

    # Analysis
    print("=" * 70)
    print("ANALYSIS")
    print("=" * 70)

    # Check for similes/metaphors
    simile_markers = [" like ", " as if ", " as though "]
    for i, r in enumerate(results):
        similes = sum(1 for m in simile_markers if m in r["intro"].lower())
        print(f"Sample {i+1} ({r['structure']}): {similes} potential similes/metaphors")

    # Check structures used
    structures_used = [r["structure"] for r in results]
    print(f"\nStructures used: {structures_used}")

    return results


if __name__ == "__main__":
    test_intro_variance(num_samples=4)
