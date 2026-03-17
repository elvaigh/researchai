"""
Reference Manager — Manage citations in multiple formats
Features: view, export BibTeX / APA / Markdown, copy, filter, delete
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import get_papers, delete_paper
from utils.ai import generate_citation
from utils.auth import require_auth
from utils import safe_link_button

STYLES = ["APA","MLA","Chicago","Harvard","Vancouver","IEEE"]

def render():
    user = require_auth()
    ws   = st.session_state.workspace
    st.markdown("""<div class="app-header"><div>
      <h1>🔖 References</h1>
      <p>Manage and export citations in 6 academic styles</p>
    </div></div>""", unsafe_allow_html=True)

    papers = get_papers(ws["id"])
    if not papers:
        st.info("📭 No papers yet. Search and save papers first.")
        return

    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("Total", len(papers))
    with c2:
        yrs = [int(p["year"]) for p in papers if str(p.get("year","")).isdigit()]
        st.metric("Oldest", min(yrs) if yrs else "—")
    with c3: st.metric("Newest", max(yrs) if yrs else "—")
    with c4:
        style = st.selectbox("Style", STYLES, key="ref_style", label_visibility="collapsed")

    st.markdown("---")
    with st.expander("📦 Bulk Export"):
        b1,b2,b3 = st.columns(3)
        with b1:
            bib = "\n\n".join(p.get("citation_bibtex","") for p in papers if p.get("citation_bibtex"))
            st.download_button("📥 All BibTeX", bib or "% empty",
                               file_name="references.bib", mime="text/plain", use_container_width=True)
        with b2:
            apa = "".join(f"[{i}] {p.get('citation_apa') or p.get('title','?')}\n\n"
                          for i,p in enumerate(papers,1))
            st.download_button("📥 APA List", apa, file_name="references_apa.txt", use_container_width=True)
        with b3:
            md = "## References\n\n" + "".join(
                f"{i}. {p.get('citation_apa') or p.get('title','?')}"
                + (f" https://doi.org/{p['doi']}" if p.get("doi") else "") + "\n\n"
                for i,p in enumerate(papers,1))
            st.download_button("📥 Markdown", md, file_name="references.md",
                               mime="text/markdown", use_container_width=True)

    sf = st.text_input("Filter", placeholder="Search…", label_visibility="collapsed")
    filtered = [p for p in papers if not sf or sf.lower() in p.get("title","").lower()
                or sf.lower() in p.get("authors","").lower()] if sf else papers

    st.markdown(f"**{len(filtered)} references**")
    st.markdown("---")

    for i, paper in enumerate(filtered, 1):
        with st.container():
            r1,r2 = st.columns([5,1])
            with r1:
                t = paper.get("title","Untitled")
                t_d = t[:85]+"…" if len(t)>85 else t
                a = paper.get("authors","Unknown") or "Unknown"
                a_d = a[:60]+"…" if len(a)>60 else a
                st.markdown(f"**[{i}] {t_d}**")
                st.markdown(f"<span style='color:#6b7280;font-size:.78rem;'>👤 {a_d} · 📅 {paper.get('year','N/A')}</span>", unsafe_allow_html=True)
                ck = f"cite_{paper['id']}_{style}"
                if ck not in st.session_state:
                    st.session_state[ck] = paper.get("citation_apa","") if style=="APA" else generate_citation(paper, style)
                st.code(st.session_state[ck], language=None)
            with r2:
                st.markdown("<br>", unsafe_allow_html=True)
                if paper.get("citation_bibtex"):
                    st.download_button("BibTeX", paper["citation_bibtex"],
                                       file_name=f"ref_{paper['id']}.bib",
                                       key=f"bib_{paper['id']}", use_container_width=True)
                if paper.get("doi"):
                    safe_link_button("DOI 🔗", f"https://doi.org/{paper['doi']}", use_container_width=True)
                if st.button("🗑️", key=f"rdel_{paper['id']}", use_container_width=True):
                    delete_paper(paper["id"], user["id"])
                    for s in STYLES: st.session_state.pop(f"cite_{paper['id']}_{s}", None)
                    st.rerun()
            st.divider()