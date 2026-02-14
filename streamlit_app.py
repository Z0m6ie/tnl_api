"""
The Narrative Loom - Streamlit UI

Refactored UI using the code-controlled CampaignEngine.
"""

import streamlit as st
from dotenv import load_dotenv

from tnl import CampaignEngine, CampaignPhase

load_dotenv()

# Page config
st.set_page_config(
    page_title="The Narrative Loom",
    page_icon="🧵",
    layout="centered",
)

# Custom CSS
st.markdown("""
<style>
    .stChatMessage {
        padding: 1rem;
    }
    .campaign-id {
        font-family: monospace;
        background-color: #f0f0f0;
        padding: 0.5rem;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "engine" not in st.session_state:
        st.session_state.engine = CampaignEngine()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "campaign_started" not in st.session_state:
        st.session_state.campaign_started = False


def display_sidebar():
    """Display sidebar with campaign controls."""
    with st.sidebar:
        st.title("🧵 The Narrative Loom")
        st.markdown("---")

        # Campaign resume
        st.subheader("Resume Campaign")
        campaign_id = st.text_input(
            "Campaign ID",
            placeholder="Enter your campaign ID...",
            key="resume_id",
        )

        if st.button("Resume", use_container_width=True, key="sidebar_resume"):
            if campaign_id:
                resume_campaign(campaign_id)
            else:
                st.error("Please enter a campaign ID")

        st.markdown("---")

        # New campaign button
        if st.button("New Campaign", use_container_width=True, type="primary", key="sidebar_new"):
            start_new_campaign()

        st.markdown("---")

        # Status
        engine = st.session_state.engine
        if engine.state:
            st.subheader("Status")
            st.write(f"**Phase:** {engine.current_phase.value if engine.current_phase else 'N/A'}")
            if engine.campaign_id:
                st.write(f"**Campaign ID:**")
                st.code(engine.campaign_id, language=None)

            if engine.state.character_sheet.name:
                st.write(f"**Character:** {engine.state.character_sheet.name}")

            if engine.state.inventory:
                with st.expander("Inventory"):
                    for item in engine.state.inventory:
                        st.write(f"• {item}")


def start_new_campaign():
    """Start a fresh campaign."""
    st.session_state.engine = CampaignEngine()
    st.session_state.messages = []
    st.session_state.campaign_started = True

    # Get welcome message
    welcome = st.session_state.engine.new_campaign()
    st.session_state.messages.append({"role": "assistant", "content": welcome})


def resume_campaign(campaign_id: str):
    """Resume an existing campaign."""
    st.session_state.engine = CampaignEngine()

    message = st.session_state.engine.resume_campaign(campaign_id)
    if message:
        st.session_state.messages = []
        st.session_state.campaign_started = True
        st.session_state.messages.append({"role": "assistant", "content": message})
        st.success("Campaign resumed!")
    else:
        st.error("Campaign not found. Check your ID and try again.")


def display_chat():
    """Display chat messages and handle input."""
    # Display existing messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Type here to play..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get response from engine
        with st.chat_message("assistant"):
            with st.spinner(""):
                response = st.session_state.engine.handle_input(prompt)
                st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})

        # Rerun to update sidebar state
        st.rerun()


def display_landing():
    """Display landing page for new users."""
    st.title("🧵 The Narrative Loom")
    st.markdown("""
    *Your simulation-first Dungeon Master*

    Play anything from a cyberpunk heist-thriller to a dark fairytale revenge story.
    The world exists independently of your actions. Consequences matter.

    ---

    **How it works:**
    1. Choose a genre, tone, and story type
    2. Create your character
    3. The world is woven around you
    4. Your choices shape your fate

    ---
    """)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🆕 Start New Campaign", use_container_width=True, type="primary", key="landing_new"):
            start_new_campaign()
            st.rerun()

    with col2:
        st.markdown("**Resume existing campaign:**")
        campaign_id = st.text_input("Campaign ID", key="landing_campaign_id", label_visibility="collapsed")
        if st.button("Resume", use_container_width=True, key="landing_resume"):
            if campaign_id:
                resume_campaign(campaign_id)
                st.rerun()


def main():
    """Main app entry point."""
    init_session_state()
    display_sidebar()

    if st.session_state.campaign_started:
        display_chat()
    else:
        display_landing()


if __name__ == "__main__":
    main()
