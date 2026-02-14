"""
Test TNL engine locally without backend persistence.

This tests the core game flow using a mock repository.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Check for OpenAI API key
if not os.getenv("OPENAI_API_KEY"):
    print("ERROR: OPENAI_API_KEY not found in environment")
    print("Please ensure your .env file contains: OPENAI_API_KEY=sk-...")
    exit(1)

from tnl.llm import LLMClient
from tnl.models.campaign import CampaignState, CampaignPhase
from tnl.phases import OnboardingPhase, CharacterPhase


def test_llm_connection():
    """Test that we can connect to OpenAI."""
    print("\n=== Testing LLM Connection ===")
    try:
        llm = LLMClient()
        response = llm.generate(
            prompt="Say 'Hello, adventurer!' in a dramatic fantasy tone. Keep it under 20 words.",
            max_tokens=50,
        )
        print(f"LLM Response: {response}")
        print("LLM connection OK")
        return True
    except Exception as e:
        print(f"ERROR: LLM connection failed: {e}")
        return False


def test_onboarding_phase():
    """Test the onboarding phase."""
    print("\n=== Testing Onboarding Phase ===")
    llm = LLMClient()
    state = CampaignState()
    phase = OnboardingPhase(llm)

    # Enter phase
    welcome = phase.enter(state)
    print(f"Welcome message:\n{welcome[:200]}...")

    # Test "surprise me"
    result = phase.handle_input("surprise me", state)
    print(f"\nSurprise selection result:")
    print(f"Genre: {state.genre}")
    print(f"Tone: {state.tone}")
    print(f"Story Type: {state.story_type}")
    print(f"Next phase: {result.next_phase}")

    return state.genre is not None


def test_character_phase():
    """Test character creation phase."""
    print("\n=== Testing Character Phase ===")
    llm = LLMClient()

    # Set up state as if we came from onboarding
    state = CampaignState()
    state.genre = "Cyberpunk"
    state.tone = "Gritty"
    state.story_type = "Heist thriller"

    phase = CharacterPhase(llm)

    # Enter phase
    prompt = phase.enter(state)
    print(f"Character prompt:\n{prompt[:200]}...")

    # Test character creation
    print("\nTesting character creation with 'surprise me'...")
    result = phase.handle_input("surprise me", state)
    print(f"\nCharacter created:")
    print(result.display_message)

    # Confirm character
    print("\nConfirming character...")
    result = phase.handle_input("yes", state)
    print(f"Result: {result.display_message}")
    print(f"Next phase: {result.next_phase}")

    return state.character_sheet.name != ""


def main():
    print("=" * 50)
    print("TNL Local Test Suite")
    print("=" * 50)

    # Test LLM
    if not test_llm_connection():
        print("\nCannot proceed without LLM connection.")
        return

    # Test phases
    if test_onboarding_phase():
        print("\nOnboarding phase: PASSED")
    else:
        print("\nOnboarding phase: FAILED")

    if test_character_phase():
        print("\nCharacter phase: PASSED")
    else:
        print("\nCharacter phase: FAILED")

    print("\n" + "=" * 50)
    print("Tests completed!")
    print("=" * 50)
    print("\nNote: World generation and gameplay require the backend.")
    print("To test those, you need to:")
    print("1. Revive your Supabase project at https://supabase.com/dashboard")
    print("2. Or run the FastAPI backend locally")


if __name__ == "__main__":
    main()
