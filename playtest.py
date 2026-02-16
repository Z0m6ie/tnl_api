"""CLI Playtest Script for TNL.

Run with: python playtest.py
"""

from dotenv import load_dotenv
load_dotenv()

from tnl import CampaignEngine

def main():
    engine = CampaignEngine()

    print("=" * 60)
    print("TNL PLAYTEST SESSION")
    print("=" * 60)
    print("Commands: 'quit' to exit, 'state' to show current state")
    print("=" * 60)
    print()

    # Start new campaign
    response = engine.new_campaign()
    print(response)
    print()

    while True:
        try:
            user_input = input("\n> ").strip()

            if user_input.lower() == 'quit':
                print("Exiting playtest.")
                break

            if user_input.lower() == 'state':
                print("\n--- STATE ---")
                print(engine.get_state_summary())
                print("-------------")
                continue

            if not user_input:
                continue

            print()
            response = engine.handle_input(user_input)
            print(response)

        except KeyboardInterrupt:
            print("\nExiting playtest.")
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()
