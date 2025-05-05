import streamlit as st
import openai
import tnl_assistant as tnl

st.set_page_config(page_title="The Narrative Loom", layout="centered")
st.title("🧵 The Narrative Loom")
st.caption(
    "Simulation‑first Dungeon Master — Play or resume persistent, consequence-driven stories. To start a new game type 'New' or load a campaigne id to your left and type 'Resume'"
)

# ---------------------------------------------------------------------------
# Restore per‑session runtime + campaign‑ID (if they exist)
# ---------------------------------------------------------------------------
if "runtime" in st.session_state:
    tnl.runtime = st.session_state["runtime"]

if "stored_campaign_id" in st.session_state:
    tnl.stored_campaign_id = st.session_state["stored_campaign_id"]  # Needed by run_assistant

# ---------------------------------------------------------------------------
# Sidebar ‑‑ resume existing campaign
# ---------------------------------------------------------------------------
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
            tnl.stored_campaign_id = cid
            st.session_state["campaign_loaded"] = True

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

            st.session_state.chat_history = [
                ("TNL", "🔄 Campaign loaded. You may now continue.")
            ]
        except Exception as e:
            st.session_state.chat_history = [("TNL", f"❌ Failed to load: {e}")]
            st.session_state["campaign_loaded"] = False

# ---------------------------------------------------------------------------
# First‑time initialization
# ---------------------------------------------------------------------------
if "assistant_id" not in st.session_state and not st.session_state.get("campaign_loaded"):
    tnl.runtime = tnl.fresh_runtime()
    st.session_state["runtime"] = tnl.runtime
    tnl.stored_campaign_id = None

    st.session_state.assistant_id = tnl.create_tnl_assistant()
    st.session_state.thread_id    = tnl.create_thread()
    st.session_state.chat_history = []
    st.session_state["stored_campaign_id"] = None

# ---------------------------------------------------------------------------
# Chat input loop
# ---------------------------------------------------------------------------
user_msg = st.chat_input("Type here to play…")
if user_msg:
    tnl.runtime["last_user_msg"] = user_msg
    st.session_state.chat_history.append(("You", user_msg))
    tnl.add_user_message(st.session_state.thread_id, user_msg)

    # Run assistant and handle tool calls
    run_id = tnl.run_assistant(
        st.session_state.thread_id,
        st.session_state.assistant_id,
        st.session_state.get("stored_campaign_id")
    )
    run = tnl.poll_run_status(st.session_state.thread_id, run_id)

    while run.status == "requires_action":
        tnl.handle_tool_calls(st.session_state.thread_id, run)
        run = tnl.poll_run_status(st.session_state.thread_id, run.id)

    if run.status == "completed":
        msgs = openai.beta.threads.messages.list(thread_id=st.session_state.thread_id)
        reply = sorted(
            [m for m in msgs.data if m.role == "assistant"],
            key=lambda m: m.created_at
        )[-1].content[0].text.value

        # TEMP: Show matched embedding chunks
        if hasattr(tnl, "last_embedding_matches") and tnl.last_embedding_matches:
            reply += "\n\n🔍 Matched Context:\n" + "\n".join(
                f"{i+1}. {m['chunk'][:120]}{'...' if len(m['chunk']) > 120 else ''}"
                for i, m in enumerate(tnl.last_embedding_matches[:3])
            )

        st.session_state.chat_history.append(("TNL", reply))
        tnl.runtime["last_msg_id"] = msgs.data[-1].id
        st.session_state["runtime"] = tnl.runtime

        # Capture campaign ID if it was just created
        if not st.session_state.get("stored_campaign_id") and tnl.stored_campaign_id:
            st.session_state["stored_campaign_id"] = tnl.stored_campaign_id

        # Save runtime and embed
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
