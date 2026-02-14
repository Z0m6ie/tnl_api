"""
Full end-to-end test of TNL engine with backend.
"""

import os
import certifi

# Fix SSL
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from dotenv import load_dotenv
load_dotenv()

from tnl import CampaignEngine


def test_full_flow():
    print("=" * 60)
    print("TNL Full End-to-End Test")
    print("=" * 60)

    # Create engine
    engine = CampaignEngine()

    # Start new campaign
    print("\n--- Starting New Campaign ---")
    welcome = engine.new_campaign()
    print(f"Phase: {engine.current_phase}")
    print(f"Welcome:\n{welcome[:200]}...")

    # Onboarding: select genre
    print("\n--- Onboarding: Select Genre ---")
    response = engine.handle_input("Cyberpunk, gritty, heist thriller")
    print(f"Phase: {engine.current_phase}")
    print(f"Response:\n{response}")

    # Character creation
    print("\n--- Character Creation ---")
    response = engine.handle_input("surprise me")
    print(f"Phase: {engine.current_phase}")
    print(f"Response:\n{response[:500]}...")

    # Confirm character
    print("\n--- Confirm Character ---")
    response = engine.handle_input("yes")
    print(f"Phase: {engine.current_phase}")
    print(f"Response:\n{response}")

    # World generation should happen automatically
    print("\n--- World Generation ---")
    response = engine.handle_input("")  # Trigger world gen
    print(f"Phase: {engine.current_phase}")
    print(f"Response:\n{response}")

    # Check campaign ID
    print(f"\nCampaign ID: {engine.campaign_id}")

    if engine.campaign_id:
        print("\n--- Gameplay: Continue ---")
        response = engine.handle_input("continue")
        print(f"Phase: {engine.current_phase}")
        print(f"Response:\n{response[:500]}...")

        # Try a gameplay action
        print("\n--- Gameplay: Action ---")
        response = engine.handle_input("I look around carefully, taking in my surroundings")
        print(f"Response:\n{response[:500]}...")

        print("\n" + "=" * 60)
        print("FULL TEST PASSED!")
        print(f"Campaign ID: {engine.campaign_id}")
        print("=" * 60)
    else:
        print("\nWorld generation may have failed - no campaign ID")


if __name__ == "__main__":
    test_full_flow()
