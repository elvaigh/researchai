"""Literature Review — AI-generated structured review"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import get_papers, save_literature_review, get_literature_reviews
from utils.ai import generate_literature_review, search_papers
from utils.auth import require_auth

def render():
    user = require_auth()
    ws   = st.session_state.workspace
    st.markdown("""<div class="app-header"><div>
      <h1>📊 Literature Review</h1>
      <p>AI-generated structured review from your papers</p>
    </div></div>""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["✨ Generate", "📋 Saved"])

    with tab1:
        st.markdown("### 1. Research question")
        query = st.text_area("Topic", placeholder="e.g. 'How do graph neural networks improve artwork classification?'",
                              height=80, label_visibility="collapsed")
        st.markdown("### 2. Select papers")
        papers = get_papers(ws["id"])
        mode   = st.radio("Source", ["From my library", "Auto-search"], horizontal=True)
        selected = []
        if mode == "From my library":
            if not papers:
                st.warning("Library is empty."); return
            sel_all = st.checkbox("Select all")
            for p in papers:
                t = p.get("title","")[:70]+"…" if len(p.get("title",""))>70 else p.get("title","")
                if st.checkbox(f"**{t}** ({p.get('year','')})", value=sel_all, key=f"lr_{p['id']}"):
                    selected.append(p)
        else:
            if query:
                n = st.slider("Papers to fetch", 5, 30, 15)
                if st.button("🔍 Fetch"):
                    with st.spinner("Searching…"):
                        fetched, _ = search_papers(query, limit=n)
                    st.session_state["lr_fetched"] = fetched
                    st.success(f"{len(fetched)} papers found")
            selected = st.session_state.get("lr_fetched", [])
            for p in selected:
                st.markdown(f"• {p.get('title','')[:80]} ({p.get('year','')})")

        st.markdown("### 3. Generate")
        if st.button("🚀 Generate Review", type="primary", disabled=not bool(query)):
            if not selected:
                st.error("Select at least 1 paper.")
            else:
                with st.spinner("✍️ Writing literature review… (30–60 seconds)"):
                    text = generate_literature_review(query, selected)
                pids = [p.get("id") or 0 for p in selected]
                save_literature_review(ws["id"], user["id"], query, text, pids)
                st.session_state["cur_review"] = text
                st.session_state["cur_review_q"] = query
                st.rerun()

        if st.session_state.get("cur_review"):
            st.markdown("---")
            st.markdown(f"### 📖 *{st.session_state.get('cur_review_q','')}*")
            st.markdown(st.session_state["cur_review"])
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📥 Markdown", st.session_state["cur_review"],
                                   file_name="review.md", mime="text/markdown")
            with c2:
                st.download_button("📄 Text", st.session_state["cur_review"],
                                   file_name="review.txt", mime="text/plain")

    with tab2:
        reviews = get_literature_reviews(ws["id"])
        if not reviews:
            st.info("No saved reviews yet.")
            return
        for rev in reviews:
            date = rev["created_at"].strftime("%Y-%m-%d") if rev.get("created_at") else ""
            with st.expander(f"📖 {rev['query'][:75]} — {date}"):
                st.markdown(rev.get("report","No content."))
                st.download_button("📥 Download", rev.get("report",""),
                                   file_name=f"review_{rev['id']}.md",
                                   mime="text/markdown", key=f"dl_{rev['id']}")