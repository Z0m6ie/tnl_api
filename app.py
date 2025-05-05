import streamlit as st
import openai
import tnl_assistant as tnl

st.set_page_config(page_title="The Narrative Loom", layout="centered")
st.title("🧵 The Narrative Loom")
st.caption(
    "Simulation‑first Dungeon Master — start a new game or paste a Campaign‑ID "
    "in the sidebar and press **Load** to resume."
)

# ---------------------------------------------------------------------------
# Restore per‑session runtime + campaign‑ID (if they exist)
# ---------------------------------------------------------------------------
if "runtime" in st.session_state:
    tnl.runtime = st.session_state["runtime"]

if "stored_campaign_id" in st.session_state:
    tnl.stored_campaign_id = st.session_state["stored_campaign_id"]  # <- needed by run_assistant

# ---------------------------------------------------------------------------
# Sidebar ‑‑ resume existing campaign
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Resume a Campaign")
    campaign_id_input = st.text_input("Campaign ID")

    if st.button("Load") and campaign_id_input.strip():
        cid = campaign_id_input.strip()
        try:
            state = tnl.load_runtime_state(cid)          # returns previously‑saved JSON
            # ---- OpenAI thread / assistant IDs ----
            st.session_state["assistant_id"] = state["openai"]["assistant_id"]
            st.session_state["thread_id"]    = state["openai"]["thread_id"]

            # ---- Campaign ID ----
            st.session_state["stored_campaign_id"] = cid
            tnl.stored_campaign_id = cid            # 🟢 critical for embed recall
            st.session_state["campaign_loaded"] = True

            # ---- Rehydrate runtime ----
            session_runtime = {
                "character_sheet": tnl._complete_char_sheet(state.get("character_sheet")),
                "inventory"     : tnl._safe_list(state.get("inventory")),
                "abilities"     : tnl._safe_list(state.get("abilities")),
                "locations"     : tnl._safe_list(state.get("locations")),
                "key_people"    : tnl._safe_list(state.get("key_people")),
                "world_events"  : tnl._safe_list(state.get("world_events")),
                "last_msg_id"   : state["openai"].get("last_message_id"),
            }
            st.session_state["runtime"] = session_runtime
            tnl.runtime = session_runtime

            # ---- Chat history ----
            st.session_state.chat_history = [
                ("TNL", "🔄 Campaign loaded. You may now continue.")
            ]
        except Exception as e:
            st.session_state.chat_history = [("TNL", f"❌ Failed to load: {e}")]
            st.session_state["campaign_loaded"] = False

# ---------------------------------------------------------------------------
# First‑time initialisation (new session / new campaign)
# ---------------------------------------------------------------------------
if "assistant_id" not in st.session_state and not st.session_state.get("campaign_loaded"):
    # brand‑new campaign
    tnl.runtime = tnl.fresh_runtime()          # 🔑 start clean
    st.session_state["runtime"] = tnl.runtime
    tnl.stored_campaign_id = None

    st.session_state.assistant_id = tnl.create_tnl_assistant()
    st.session_state.thread_id    = tnl.create_thread()
    st.session_state.chat_history = []
    st.session_state["stored_campaign_id"] = None

# ---------------------------------------------------------------------------
# Chat input / main loop
# ---------------------------------------------------------------------------
user_msg = st.chat_input("Type here to play…")
if user_msg:
    # Save user message + context for embedding search
    tnl.runtime["last_user_msg"] = user_msg
    st.session_state.chat_history.append(("You", user_msg))
    tnl.add_user_message(st.session_state.thread_id, user_msg)

    # Run assistant (embedding recall inside run_assistant now works)
    run_id = tnl.run_assistant(
        st.session_state.thread_id,
        st.session_state.assistant_id
    )
    run = tnl.poll_run_status(st.session_state.thread_id, run_id)

    while run.status == "requires_action":
        tnl.handle_tool_calls(st.session_state.thread_id, run)
        run = tnl.poll_run_status(st.session_state.thread_id, run.id)

    # Collect assistant reply
    if run.status == "completed":
        msgs  = openai.beta.threads.messages.list(thread_id=st.session_state.thread_id)
        reply = sorted(
            [m for m in msgs.data if m.role == "assistant"],
            key=lambda m: m.created_at
        )[-1].content[0].text.value

        st.session_state.chat_history.append(("TNL", reply))
        tnl.runtime["last_msg_id"] = msgs.data[-1].id
        st.session_state["runtime"] = tnl.runtime  # keep session in‑sync

        # If this was a brand‑new campaign, capture its ID
        if not st.session_state.get("stored_campaign_id") and tnl.stored_campaign_id:
            st.session_state["stored_campaign_id"] = tnl.stored_campaign_id

        # Persist runtime & embed message
        cid = st.session_state.get("stored_campaign_id")
        if cid:
            snap = tnl.build_snapshot(reply,
                                      st.session_state.assistant_id,
                                      st.session_state.thread_id)
            tnl.save_runtime_state(cid,
                                   st.session_state.assistant_id,
                                   st.session_state.thread_id,
                                   snap)
            tnl.embed_and_store(cid, reply)

    else:
        st.session_state.chat_history.append(("TNL", "❌ Assistant run failed."))

# ---------------------------------------------------------------------------
# Sidebar ‑‑ show user’s campaign ID
# ---------------------------------------------------------------------------
cid = st.session_state.get("stored_campaign_id")
if cid:
    st.sidebar.success(f"📌 Your Campaign ID:\n{cid}")

# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------
for speaker, msg in st.session_state.get("chat_history", []):
    st.markdown(f"**{speaker}:** {msg}")
