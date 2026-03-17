"""Library — saved papers management"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import get_papers, save_paper, delete_paper, update_paper_notes
from utils.ai import extract_pdf_text, extract_metadata_from_text, generate_citation, generate_bibtex, generate_tldr
from utils.auth import require_auth
from utils import safe_link_button

def render():
    user = require_auth()
    ws   = st.session_state.workspace
    st.markdown("""<div class="app-header"><div>
      <h1>📚 My Library</h1><p>All your saved papers in one place</p>
    </div></div>""", unsafe_allow_html=True)

    papers = get_papers(ws["id"])
    tab1, tab2 = st.tabs(["📋 Papers", "📤 Upload PDF"])

    with tab1:
        if not papers:
            st.info("📭 Your library is empty. Search for papers to get started.")
            return
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Total Papers", len(papers))
        with c2:
            yrs = [int(p["year"]) for p in papers if str(p.get("year","")).isdigit()]
            st.metric("Year Range", f"{min(yrs)}–{max(yrs)}" if yrs else "—")
        with c3:
            st.metric("Sources", len({p.get("source","manual") for p in papers}))
        st.markdown("---")
        ft = st.text_input("Filter", placeholder="Search title, author…",
                           key="lib_filter", label_visibility="collapsed")
        filtered = [p for p in papers if not ft or
                    ft.lower() in (p.get("title","")).lower() or
                    ft.lower() in (p.get("authors","")).lower()] if ft else papers
        st.markdown(f"Showing **{len(filtered)}** of {len(papers)} papers")
        st.markdown("---")
        for paper in filtered:
            with st.expander(f"📄 **{paper['title'][:85]}** — {(paper.get('authors') or '')[:45]} ({paper.get('year','')})"):
                cm, ca = st.columns([3,1])
                with cm:
                    if paper.get("abstract"):
                        ab = paper["abstract"]
                        st.markdown(f"**Abstract:** {ab[:500]}{'…' if len(ab)>500 else ''}")
                    if paper.get("citation_apa"):
                        st.markdown("**Citation (APA):**"); st.code(paper["citation_apa"], language=None)
                    st.markdown("**📝 Notes:**")
                    notes = st.text_area("Notes", value=paper.get("notes",""),
                                         key=f"notes_{paper['id']}", label_visibility="collapsed", height=90)
                    if st.button("💾 Save Notes", key=f"sn_{paper['id']}"):
                        update_paper_notes(paper["id"], notes); st.success("Saved!")
                with ca:
                    st.markdown("**Actions**")
                    if st.button("🤖 TLDR", key=f"tldr_{paper['id']}"):
                        with st.spinner("…"):
                            tldr = generate_tldr(paper.get("abstract",""), paper.get("title",""))
                        st.info(tldr)
                    if paper.get("doi"): safe_link_button("🔗 DOI", f"https://doi.org/{paper['doi']}")
                    if paper.get("citation_bibtex"):
                        st.download_button("📥 BibTeX", paper["citation_bibtex"],
                                           file_name=f"{paper['id']}.bib", mime="text/plain",
                                           key=f"bib_{paper['id']}")
                    if st.button("💬 Chat", key=f"chat_{paper['id']}"):
                        st.session_state.page = "chat"; st.rerun()
                    if st.button("🗑️ Delete", key=f"del_{paper['id']}"):
                        delete_paper(paper["id"], user["id"]); st.rerun()

    with tab2:
        st.markdown("### 📤 Upload a PDF")
        uploaded = st.file_uploader("Choose PDF", type=["pdf"])
        if not uploaded: return
        with st.spinner("Extracting text…"):
            full_text = extract_pdf_text(uploaded.read())
        if not full_text:
            st.error("Could not extract text from this PDF."); return
        st.success(f"✅ {len(full_text):,} characters extracted")
        with st.spinner("🤖 Extracting metadata…"):
            meta = extract_metadata_from_text(full_text)
        st.markdown("### Metadata (edit if needed)")
        c1, c2 = st.columns(2)
        with c1:
            title   = st.text_input("Title",   value=meta.get("title",""))
            authors = st.text_input("Authors", value=meta.get("authors",""))
            year    = st.text_input("Year",    value=meta.get("year",""))
        with c2:
            doi      = st.text_input("DOI", value=meta.get("doi",""))
            abstract = st.text_area("Abstract", value=meta.get("abstract",""), height=120)
        if st.button("💾 Save to Library", type="primary"):
            data = {"title": title or "Untitled", "authors": authors or "Unknown",
                    "abstract": abstract, "year": year, "doi": doi,
                    "source": "upload", "full_text": full_text[:50000],
                    "file_name": uploaded.name}
            data["citation_apa"]    = generate_citation(data, "APA")
            data["citation_bibtex"] = generate_bibtex(data)
            save_paper(ws["id"], user["id"], data)
            st.success(f"✅ Saved: **{title}**"); st.rerun()