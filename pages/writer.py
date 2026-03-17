"""AI Writer — academic writing assistant"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import get_documents, save_document, update_document, delete_document, get_papers
from utils.ai import generate_section, improve_writing, paraphrase_text, explain_concept, WRITING_SECTIONS
from utils.auth import require_auth

def render():
    user = require_auth()
    ws   = st.session_state.workspace
    st.markdown("""<div class="app-header"><div>
      <h1>✍️ AI Writer</h1>
      <p>Draft, improve, and finalise your academic paper with AI</p>
    </div></div>""", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📝 Editor", "🤖 Generator", "🔧 Tools"])

    with tab1:
        docs = get_documents(ws["id"])
        dc, ec = st.columns([1, 3])
        with dc:
            st.markdown("### 📁 Docs")
            if st.button("➕ New", use_container_width=True, type="primary"):
                st.session_state["editing_doc"] = {"id":None,"title":"Untitled","content":""}; st.rerun()
            for d in docs:
                t = d.get("title","Untitled")[:28]+"…" if len(d.get("title",""))>28 else d.get("title","Untitled")
                if st.button(f"📝 {t}", key=f"od_{d['id']}", use_container_width=True):
                    st.session_state["editing_doc"] = d; st.rerun()
        with ec:
            ed = st.session_state.get("editing_doc")
            if not ed:
                st.info("👈 Create or open a document.")
            else:
                ttl = st.text_input("Title", value=ed.get("title","Untitled"), key="doc_title")
                cnt = st.text_area("Content", value=ed.get("content",""), height=450,
                                   key="doc_content", label_visibility="collapsed",
                                   placeholder="Start writing…")
                s1,s2,s3,s4 = st.columns(4)
                with s1:
                    if st.button("💾 Save", type="primary", use_container_width=True):
                        if ed.get("id"):
                            update_document(ed["id"], ttl, cnt); st.success("Saved!")
                        else:
                            doc = save_document(ws["id"], user["id"], ttl, cnt)
                            st.session_state["editing_doc"] = doc; st.success("Created!"); st.rerun()
                with s2:
                    st.download_button("📥 .txt", cnt, file_name=f"{ttl}.txt", use_container_width=True)
                with s3:
                    st.download_button("📥 .md",  cnt, file_name=f"{ttl}.md",  mime="text/markdown", use_container_width=True)
                with s4:
                    if ed.get("id") and st.button("🗑️ Delete", use_container_width=True):
                        delete_document(ed["id"], user["id"])
                        st.session_state.pop("editing_doc",None); st.rerun()

    with tab2:
        st.markdown("### 🤖 Generate Sections")
        c1,c2 = st.columns(2)
        with c1:
            sec  = st.selectbox("Section", list(WRITING_SECTIONS.keys()),
                                format_func=lambda x: x.replace("_"," ").title(),
                                label_visibility="collapsed")
            topic = st.text_input("Paper title / topic",
                                  placeholder="e.g. 'Semantic Art Classification'",
                                  label_visibility="collapsed")
        with c2:
            ctx = st.text_area("Notes / context", placeholder="Specific points to include…",
                               height=120, label_visibility="collapsed")
        papers = get_papers(ws["id"])
        if papers:
            refs = st.multiselect("Include references (optional)",
                                  [f"{p['title'][:55]} ({p.get('year','')})" for p in papers],
                                  max_selections=5)
            if refs: ctx += "\n\nReferences:\n" + "\n".join(refs)

        if st.button("🚀 Generate", type="primary", disabled=not bool(topic)):
            with st.spinner(f"Writing {sec.replace('_',' ')} section…"):
                gen = generate_section(sec, ctx, topic)
            st.session_state["gen_text"] = gen
            st.session_state["gen_sec"]  = sec

        if st.session_state.get("gen_text"):
            h = st.session_state["gen_sec"].replace("_"," ").title()
            st.markdown(f"### {h}")
            edited = st.text_area("Editable result", value=st.session_state["gen_text"],
                                  height=350, key="gen_edit")
            g1,g2 = st.columns(2)
            with g1:
                if st.button("📋 Add to Editor", use_container_width=True):
                    ed = st.session_state.get("editing_doc") or {}
                    new = (ed.get("content","")) + f"\n\n## {h}\n\n{edited}"
                    if ed.get("id"):
                        update_document(ed["id"], ed.get("title","Draft"), new)
                        st.session_state["editing_doc"]["content"] = new
                        st.success("Added!")
                    else:
                        doc = save_document(ws["id"], user["id"], topic or "Draft", new)
                        st.session_state["editing_doc"] = doc; st.success("New doc created!"); st.rerun()
            with g2:
                st.download_button("📥 Download", edited, file_name=f"{sec}.txt", use_container_width=True)

    with tab3:
        st.markdown("### 🔧 Text Tools")
        tool = st.radio("Tool", ["✨ Improve", "🔄 Paraphrase", "💡 Explain"], horizontal=True)
        if tool == "✨ Improve":
            txt = st.text_area("Paste text", height=200, key="imp_in", label_visibility="collapsed")
            itype = st.selectbox("Type", ["improve clarity and academic tone","make more concise",
                                          "strengthen the argument","fix grammar and punctuation"],
                                 label_visibility="collapsed")
            if st.button("✨ Improve", type="primary") and txt:
                with st.spinner("…"):
                    r = improve_writing(txt, itype)
                st.text_area("Result", value=r, height=200, key="imp_out")
        elif tool == "🔄 Paraphrase":
            txt = st.text_area("Paste text", height=200, key="par_in", label_visibility="collapsed")
            if st.button("🔄 Paraphrase", type="primary") and txt:
                with st.spinner("…"):
                    r = paraphrase_text(txt)
                st.text_area("Result", value=r, height=200, key="par_out")
        else:
            concept = st.text_input("Concept", placeholder="e.g. 'contrastive learning'", label_visibility="collapsed")
            context = st.text_input("Context", placeholder="e.g. 'in computer vision'",  label_visibility="collapsed")
            if st.button("💡 Explain", type="primary") and concept:
                with st.spinner("…"):
                    r = explain_concept(concept, context)
                st.info(r)