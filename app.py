import streamlit as st
import openai
import tnl_assistant as tnl

st.set_page_config(page_title="The Narrative Loom", layout="centered")
st.title("🧵 The Narrative Loom")
st.caption("Simulation‑first Dungeon Master — Play or resume persistent, consequence-driven stories. To start a new game type 'New' or load a campaigne id to your left and type 'Resume'")

# === SIDEBAR ===
with st.sidebar:
    st.header("Resume a Campaign")
    campaign_id_input = st.text_input("Campaign ID")

    if st.button("Load") and campaign_id_input.strip():
        cid = campaign_id_input.strip()
        try:
            state = tnl.load_runtime_state(cid)
            st.session_state["assistant_id"] = state["openai"]["assistant_id"]
            st.session_state["thread_id"] = state["openai"]["thread_id"]
            st.session_state["stored_campaign_id"] = cid
            st.session_state["campaign_loaded"] = True  # ✅ set flag to prevent overwriting
            tnl.runtime = {
                "character_sheet": tnl._complete_char_sheet(state.get("character_sheet")),
                "inventory": tnl._safe_list(state.get("inventory")),
                "abilities": tnl._safe_list(state.get("abilities")),
                "locations": tnl._safe_list(state.get("locations")),
                "key_people": tnl._safe_list(state.get("key_people")),
                "world_events": tnl._safe_list(state.get("world_events")),
                "last_msg_id": state["openai"].get("last_message_id"),
            }
            st.session_state.chat_history = [("TNL", "🔄 Campaign loaded. You may now continue.")]
        except Exception as e:
            st.session_state.chat_history = [("TNL", f"❌ Failed to load: {e}")]
            st.session_state["campaign_loaded"] = False

# === INITIALIZATION ===
if "assistant_id" not in st.session_state and not st.session_state.get("campaign_loaded"):
    st.session_state.assistant_id = tnl.create_tnl_assistant()
    st.session_state.thread_id = tnl.create_thread()
    st.session_state.chat_history = []
    st.session_state["stored_campaign_id"] = None

# === CHAT HANDLING ===
user_msg = st.chat_input("Type here to play…")
if user_msg:
    # 1. Save user message and prepare context
    tnl.runtime["last_user_msg"] = user_msg
    st.session_state.chat_history.append(("You", user_msg))
    tnl.add_user_message(st.session_state.thread_id, user_msg)

    # 2. Run the assistant
    run_id = tnl.run_assistant(st.session_state.thread_id, st.session_state.assistant_id)
    run = tnl.poll_run_status(st.session_state.thread_id, run_id)

    while run.status == "requires_action":
        tnl.handle_tool_calls(st.session_state.thread_id, run)
        run = tnl.poll_run_status(st.session_state.thread_id, run.id)

    # 3. Get response
    if run.status == "completed":
        msgs = openai.beta.threads.messages.list(thread_id=st.session_state.thread_id)
        last = sorted([m for m in msgs.data if m.role == "assistant"], key=lambda m: m.created_at)[-1]
        reply = last.content[0].text.value
        st.session_state.chat_history.append(("TNL", reply))
        tnl.runtime["last_msg_id"] = last.id

        # 4. Store campaign ID if it was just created
        if not st.session_state.get("stored_campaign_id") and tnl.stored_campaign_id:
            st.session_state["stored_campaign_id"] = tnl.stored_campaign_id

        # 5. Save full state and embed entire message
        cid = st.session_state.get("stored_campaign_id")
        if cid:
            snap = tnl.build_snapshot(reply, st.session_state.assistant_id, st.session_state.thread_id)
            tnl.save_runtime_state(cid, st.session_state.assistant_id, st.session_state.thread_id, snap)
            tnl.embed_and_store(cid, reply)

    elif run.status == "failed":
        st.session_state.chat_history.append(("TNL", "❌ Assistant run failed."))

# === DISPLAY CAMPAIGN ID TO USER ONLY ===
cid = st.session_state.get("stored_campaign_id")
if cid:
    st.sidebar.success(f"📌 Your Campaign ID:\n{cid}")

# === DISPLAY CHAT ===
for speaker, msg in st.session_state.get("chat_history", []):
    st.markdown(f"**{speaker}:** {msg}")
