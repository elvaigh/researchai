"""
AI Search — SciSpace-style semantic paper search
• GPT-4o query expansion + multi-source parallel fetch
• Embedding-based semantic re-ranking
• Filters: must have title + authors + abstract + URL
• No PDF download; link to source page only
"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ai import (search_papers, generate_tldr, generate_citation,
                      generate_bibtex, suggest_research_questions)
from utils.db import save_paper, get_papers
from utils.auth import require_auth
from utils import safe_link_button


def _save(ws_id, user_id, paper):
    p = dict(paper)
    p.pop("_score", None)
    p["citation_apa"]    = generate_citation(p, "APA")
    p["citation_bibtex"] = generate_bibtex(p)
    # map 'url' → 'pdf_url' for DB compatibility
    p.setdefault("pdf_url", p.get("url", ""))
    save_paper(ws_id, user_id, p)


def render():
    user = require_auth()
    ws   = st.session_state.workspace

    st.markdown("""
    <div class="app-header">
      <div>
        <h1>🔍 AI Search</h1>
        <p>Semantic Scholar · OpenAlex · arXiv · CrossRef — re-ranked by AI embeddings</p>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── State defaults ─────────────────────────────────────────────────────
    for k, v in [("sr_results", None), ("sr_error", None), ("sr_query", ""),
                 ("sr_pending", ""), ("sr_tldr", {}), ("sr_tldr_idx", None),
                 ("sr_rq", [])]:
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Advanced filters ───────────────────────────────────────────────────
    with st.expander("🎛️ Filters & Sources"):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            year_min = st.number_input("Year from", value=2015,
                                       min_value=1900, max_value=2030, key="yr_min")
        with fc2:
            year_max = st.number_input("Year to", value=2030,
                                       min_value=1900, max_value=2030, key="yr_max")
        with fc3:
            result_count = st.selectbox("Results", [10, 20, 30, 50, 75, 100],
                                        index=1, key="result_count",
                                        label_visibility="collapsed")
        src_options = ["Semantic Scholar", "OpenAlex", "arXiv", "CrossRef",
                         "Google Scholar", "PubMed", "Europe PMC"]
        selected_sources = []
        # Row 1: 4 sources
        row1 = src_options[:4]
        cols1 = st.columns(len(row1))
        for i, src in enumerate(row1):
            with cols1[i]:
                if st.checkbox(src, value=True, key=f"src_{src}"):
                    selected_sources.append(src)
        # Row 2: remaining sources
        row2 = src_options[4:]
        cols2 = st.columns(len(row2))
        for i, src in enumerate(row2):
            with cols2[i]:
                if st.checkbox(src, value=True, key=f"src_{src}"):
                    selected_sources.append(src)
        if not selected_sources:
            selected_sources = src_options

    # ── Search bar ─────────────────────────────────────────────────────────
    col1, col2 = st.columns([5, 1])
    with col1:
        query_input = st.text_input(
            "Search", key="search_input",
            placeholder="e.g. 'How do large language models handle multi-step reasoning?'",
            label_visibility="collapsed",
        )
    with col2:
        search_btn = st.button("Search", type="primary", use_container_width=True)

    # Quick suggestions
    sugg_cols = st.columns(4)
    for i, s in enumerate([
        "transformer attention mechanisms",
        "graph neural networks knowledge",
        "contrastive learning vision",
        "LLM reasoning evaluation",
    ]):
        with sugg_cols[i]:
            if st.button(s, key=f"sug_{i}", use_container_width=True):
                st.session_state.sr_pending = s
                st.session_state.sr_tldr    = {}

    # ── Determine query ────────────────────────────────────────────────────
    run_query = None
    if search_btn and query_input.strip():
        run_query = query_input.strip()
        st.session_state.sr_tldr = {}
    elif st.session_state.sr_pending:
        run_query = st.session_state.sr_pending
        st.session_state.sr_pending = ""

    if run_query:
        with st.status("🤖 Expanding query · Searching 7 sources · Re-ranking by AI…", expanded=False) as status:
            # Fetch more than needed so client-side filters still leave enough results
            results, error = search_papers(run_query, limit=result_count)

            # Client-side filters (source, year)
            if results:
                if selected_sources:
                    results = [r for r in results if r.get("source") in selected_sources]
                if year_min > 1900:
                    results = [r for r in results
                               if not str(r.get("year","")).isdigit()
                               or int(r["year"]) >= year_min]
                if year_max < 2030:
                    results = [r for r in results
                               if not str(r.get("year","")).isdigit()
                               or int(r["year"]) <= year_max]
            status.update(
                label=f"✅ Found {len(results)} papers" if results else "⚠️ No results",
                state="complete" if results else "error",
            )
        st.session_state.sr_results    = results
        st.session_state.sr_error      = error
        st.session_state.sr_query      = run_query
        st.session_state.sr_tldr       = {}
        st.session_state.sr_tldr_idx   = None

    # ── Results ────────────────────────────────────────────────────────────
    if st.session_state.sr_results is not None:
        if st.session_state.sr_error and not st.session_state.sr_results:
            st.error(f"⚠️ {st.session_state.sr_error}")
            return

        results = list(st.session_state.sr_results)
        if not results:
            st.warning("No results with required fields (title + authors + abstract + URL). Try different keywords.")
            return

        # Source breakdown
        src_counts = {}
        for r in results:
            s = r.get("source", "?")
            src_counts[s] = src_counts.get(s, 0) + 1
        src_str = "  ·  ".join(f"{s} {n}" for s, n in sorted(src_counts.items()))
        oa_count = sum(1 for r in results if r.get("is_open_access"))

        st.markdown(
            f"**{len(results)} papers** for *\"{st.session_state.sr_query}\"*  "
            f"<span style='color:#4b5563;font-size:0.75rem;'>[ {src_str} ]  ·  {oa_count} open-access</span>",
            unsafe_allow_html=True,
        )

        _, sort_col = st.columns([4, 1])
        with sort_col:
            sort_by = st.selectbox("Sort", ["Relevance (AI)", "Citations ↓", "Year ↓", "Year ↑"],
                                   key="sort_by", label_visibility="collapsed")

        if sort_by == "Citations ↓":
            results.sort(key=lambda x: x.get("citation_count", 0) or 0, reverse=True)
        elif sort_by == "Year ↓":
            results.sort(key=lambda x: int(x["year"]) if str(x.get("year","")).isdigit() else 0, reverse=True)
        elif sort_by == "Year ↑":
            results.sort(key=lambda x: int(x["year"]) if str(x.get("year","")).isdigit() else 0)
        # "Relevance (AI)" keeps the embedding-sorted order

        # Pending TLDR
        pi = st.session_state.sr_tldr_idx
        if pi is not None and 0 <= pi < len(results):
            p = results[pi]
            with st.spinner(f"🤖 Summarising paper {pi+1}…"):
                tldr = generate_tldr(p.get("abstract",""), p.get("title",""))
            st.session_state.sr_tldr[str(pi)] = tldr
            st.session_state.sr_tldr_idx = None

        saved_titles = {p["title"] for p in get_papers(ws["id"])}
        st.markdown("---")

        for idx, paper in enumerate(results):
            saved    = paper.get("title","") in saved_titles
            abstract = (paper.get("abstract") or "").strip()
            ab_disp  = abstract[:280] + ("…" if len(abstract) > 280 else "")
            authors  = (paper.get("authors") or "Unknown")
            au_disp  = authors[:85] + ("…" if len(authors) > 85 else "")
            title    = paper.get("title") or "Untitled"
            url      = paper.get("url") or ""
            score    = paper.get("_score", 0)
            src      = paper.get("source","")
            oa       = paper.get("is_open_access", False)

            badges = f'<span class="badge badge-indigo">{src}</span>'
            if oa:
                badges += ' <span class="badge badge-green">Open Access</span>'
            if saved:
                badges += ' <span class="badge badge-gray">Saved</span>'
            if score > 0:
                badges += f' <span class="card-score">⚡ {score:.2f}</span>'

            with st.container():
                st.markdown(f"""
                <div class="card">
                  <div class="card-title">{title}</div>
                  <div class="card-meta">
                    👤 {au_disp} &nbsp;·&nbsp;
                    📅 {paper.get('year','N/A')} &nbsp;·&nbsp;
                    📖 {paper.get('citation_count',0)} citations &nbsp;·&nbsp;
                    {badges}
                  </div>
                  <div class="card-abstract">{ab_disp}</div>
                </div>
                """, unsafe_allow_html=True)

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    done = str(idx) in st.session_state.sr_tldr
                    if st.button("✅ TLDR" if done else "🤖 TLDR", key=f"tldr_{idx}"):
                        st.session_state.sr_tldr_idx = idx
                        st.rerun()
                with c2:
                    if st.button("📥 Save", key=f"save_{idx}", disabled=saved):
                        with st.spinner("Saving…"):
                            _save(ws["id"], user["id"], paper)
                        st.success("Saved!")
                        st.rerun()
                with c3:
                    if paper.get("doi"):
                        safe_link_button("🔗 DOI", f"https://doi.org/{paper['doi']}")
                with c4:
                    if url:
                        safe_link_button("🌐 Open", url)

                if str(idx) in st.session_state.sr_tldr:
                    st.markdown(f"""
                    <div class="tldr-box">
                    🤖 <strong>AI Summary:</strong> {st.session_state.sr_tldr[str(idx)]}
                    </div>""", unsafe_allow_html=True)

                st.divider()

    else:
        # ── Landing ────────────────────────────────────────────────────────
        st.markdown("---")

        # Feature highlights
        f1, f2, f3 = st.columns(3)
        for col, icon, title, desc in [
            (f1, "🧠", "AI Query Expansion", "GPT-4o rewrites your query into multiple optimised search strings for maximum recall"),
            (f2, "⚡", "Semantic Re-ranking", "Papers scored by embedding similarity to your intent — most relevant first"),
            (f3, "🌐", "4 Sources in Parallel", "Semantic Scholar, OpenAlex, arXiv and CrossRef queried simultaneously"),
        ]:
            with col:
                st.markdown(f"""
                <div class="card" style="text-align:center;padding:1.5rem;">
                  <div style="font-size:1.8rem;margin-bottom:.6rem;">{icon}</div>
                  <div style="font-weight:700;color:#e0e7ff;font-size:.9rem;margin-bottom:.4rem;">{title}</div>
                  <div style="font-size:.78rem;color:#6b7280;line-height:1.6;">{desc}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("### 🧠 Research Question Generator")
            topic = st.text_input("Topic", placeholder="e.g. 'AI in drug discovery'",
                                  key="rq_topic", label_visibility="collapsed")
            if st.button("Generate Questions", type="primary"):
                if topic:
                    with st.spinner("Generating…"):
                        st.session_state.sr_rq = suggest_research_questions(topic, get_papers(ws["id"]))
                else:
                    st.warning("Enter a topic first.")
            for q in st.session_state.sr_rq:
                st.markdown(f"<div style='color:#9ca3af;font-size:.85rem;padding:.3rem 0;border-bottom:1px solid rgba(99,102,241,.08);'>→ {q}</div>", unsafe_allow_html=True)

        with col_b:
            st.markdown("### 📈 Your Stats")
            lib = get_papers(ws["id"])
            st.metric("Papers in Library", len(lib))
            st.metric("Workspace", ws["name"])
            if lib:
                yrs = [int(p["year"]) for p in lib if str(p.get("year","")).isdigit()]
                if yrs:
                    st.metric("Year Range", f"{min(yrs)} – {max(yrs)}")