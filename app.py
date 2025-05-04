import streamlit as st
import openai
import tnl_assistant as tnl   # import the module, not just the functions

# ---- Streamlit page config ----
st.set_page_config(page_title="The Narrative Loom", layout="centered")
st.title("🧵 The Narrative Loom")
st.caption("Simulation‑first Dungeon Master • Start a new campaign or paste a Campaign ID in the sidebar to resume.")

# ---- Sidebar (optional resume) ----
with st.sidebar:
    st.header("Resume a Campaign")
    existing_id = st.text_input("Campaign ID")
    if st.button("Load") and existing_id.strip():
        st.session_state.campaign_id = existing_id.strip()
        st.session_state.assistant_id = None  # force re‑initialise

# ---- One‑time initialisation ----
if "assistant_id" not in st.session_state or st.session_state.get("campaign_id_loaded") != st.session_state.get("campaign_id"):
    # Fresh assistant & thread every app reload *unless* we loaded a campaign.
    st.session_state.assistant_id = tnl.create_tnl_assistant()
    st.session_state.thread_id   = tnl.create_thread()
    st.session_state.chat_history = []
    st.session_state.campaign_id_loaded = st.session_state.get("campaign_id")  # marker

# ---- Chat input ----
user_msg = st.chat_input("Type here to play…")
if user_msg:
    # 1 Store user msg
    tnl.add_user_message(st.session_state.thread_id, user_msg)
    tnl.runtime["last_user_msg"] = user_msg            # <- gives embedding recall a chance
    st.session_state.chat_history.append(("You", user_msg))

    # 2 Run assistant
    run_id = tnl.run_assistant(st.session_state.thread_id, st.session_state.assistant_id)
    run    = tnl.poll_run_status(st.session_state.thread_id, run_id)

    while run.status == "requires_action":
        tnl.handle_tool_calls(st.session_state.thread_id, run)
        run = tnl.poll_run_status(st.session_state.thread_id, run.id)

    # 3 Collect assistant reply
    if run.status == "completed":
        msgs = openai.beta.threads.messages.list(thread_id=st.session_state.thread_id)
        last = sorted([m for m in msgs.data if m.role == "assistant"], key=lambda m: m.created_at)[-1]
        reply = last.content[0].text.value
        st.session_state.chat_history.append(("TNL", reply))
    else:
        st.session_state.chat_history.append(("TNL", "❌ Assistant run failed."))

    # 4 Show newly created Campaign‑ID, if any
    if tnl.stored_campaign_id:
        st.sidebar.success(f"📌 Campaign ID:\n{tnl.stored_campaign_id}")

# ---- Conversation transcript ----
for speaker, msg in st.session_state.get("chat_history", []):
    st.markdown(f"**{speaker}:** {msg}")
