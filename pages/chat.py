"""Chat with Papers — GPT-4o powered paper Q&A"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import get_papers, get_paper, create_chat_session, get_chat_sessions, save_message, get_messages
from utils.ai import chat_with_paper, general_research_chat
from utils.auth import require_auth

PRESETS = [
    "What is the main contribution?",
    "Summarise the methodology",
    "What are the key results?",
    "What are the limitations?",
    "How does this compare to related work?",
    "What datasets were used?",
    "Explain the mathematical formulation",
    "What future work is suggested?",
]

def render():
    user = require_auth()
    ws   = st.session_state.workspace
    st.markdown("""<div class="app-header"><div>
      <h1>💬 Chat with Papers</h1>
      <p>Ask questions about your papers — powered by GPT-4o</p>
    </div></div>""", unsafe_allow_html=True)

    papers   = get_papers(ws["id"])
    sessions = get_chat_sessions(ws["id"])
    sb, main = st.columns([1, 3])

    with sb:
        st.markdown("### 📂 Chats")
        opts = {"🌐 General Research Assistant": None}
        opts.update({f"📄 {p['title'][:40]}": p["id"] for p in papers})
        sel_label = st.selectbox("Paper", list(opts.keys()), key="chat_paper_select", label_visibility="collapsed")
        if st.button("➕ New Chat", type="primary", use_container_width=True):
            sess = create_chat_session(ws["id"], user["id"], opts[sel_label], sel_label[:50])
            st.session_state.chat_session_id = sess["id"]
            st.session_state.chat_messages   = []
            st.rerun()
        st.markdown("---")
        for sess in sessions[:15]:
            icon = "📄" if sess.get("paper_id") else "🌐"
            if st.button(f"{icon} {sess.get('title','Chat')[:28]}", key=f"sess_{sess['id']}", use_container_width=True):
                st.session_state.chat_session_id = sess["id"]
                st.session_state.chat_messages   = get_messages(sess["id"])
                st.rerun()

    with main:
        if not st.session_state.get("chat_session_id"):
            st.info("👈 Start a new chat or select one from the sidebar.")
            for p in PRESETS[:4]:
                st.markdown(f"<div style='color:#6b7280;font-size:.85rem;padding:.25rem 0;'>• {p}</div>", unsafe_allow_html=True)
            return

        sid = st.session_state.chat_session_id
        paper_context = ""
        current_paper = None
        for sess in sessions:
            if sess["id"] == sid and sess.get("paper_id"):
                current_paper = get_paper(sess["paper_id"])
                if current_paper:
                    paper_context = current_paper.get("full_text") or current_paper.get("abstract") or ""
                    t = current_paper["title"]
                    st.markdown(f"**📄 Paper:** {t[:90]}{'…' if len(t)>90 else ''}")
                break

        if current_paper:
            cols = st.columns(4)
            for i, p in enumerate(PRESETS):
                with cols[i % 4]:
                    if st.button(p[:28]+"…", key=f"pre_{i}", use_container_width=True):
                        st.session_state["pending_msg"] = p

        st.markdown("---")
        if not st.session_state.get("chat_messages"):
            st.session_state.chat_messages = get_messages(sid)

        for msg in st.session_state.chat_messages:
            cls = "chat-user" if msg["role"] == "user" else "chat-ai"
            st.markdown(f'<div class="{cls}">{msg["content"]}</div>', unsafe_allow_html=True)

        st.markdown("---")
        pending   = st.session_state.pop("pending_msg", None)
        user_inp  = st.chat_input("Ask anything about this paper…")
        to_send   = user_inp or pending
        if to_send:
            save_message(sid, "user", to_send)
            st.session_state.chat_messages.append({"role":"user","content":to_send})
            with st.spinner("🤖 Thinking…"):
                hist = [{"role":m["role"],"content":m["content"]} for m in st.session_state.chat_messages]
                reply = chat_with_paper(hist, paper_context, to_send) if paper_context else general_research_chat(hist, to_send)
            save_message(sid, "assistant", reply)
            st.session_state.chat_messages.append({"role":"assistant","content":reply})
            st.rerun()