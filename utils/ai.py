"""
AI utilities for ResearchAI
────────────────────────────
Search:
  • Parallel queries to Semantic Scholar, OpenAlex, arXiv, CrossRef
  • GPT-4o query expansion: turns natural language into 3 optimised API queries
  • Embedding-based re-ranking: uses text-embedding-3-small to score each
    paper against the original intent and sort by cosine similarity
  • Hard filters: must have title + authors + abstract + at least one URL
  • Deduplication by DOI then normalised title

Other features:
  • TLDR (2-sentence GPT summary)
  • Chat with paper / general research assistant
  • Literature review generator
  • AI Writer (section generator, improve, paraphrase, explain)
  • Citation & BibTeX generation
  • PDF text extraction + abstract extraction
  • Research question suggestions
"""

import os, re, json, time, math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
import requests
from openai import OpenAI
import streamlit as st

# ── OpenAI client (lazy) ───────────────────────────────────────────────────
_client: Optional[OpenAI] = None

def _get_client() -> Optional[OpenAI]:
    global _client
    if _client is None:
        try:
            key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        except Exception:
            key = os.environ.get("OPENAI_API_KEY", "")
        _client = OpenAI(api_key=key) if key else None
    return _client


def _gpt(messages: list, model="gpt-4o-mini", max_tokens=600, temperature=0.3) -> str:
    c = _get_client()
    if not c:
        return "Error: OPENAI_API_KEY not configured."
    try:
        r = c.chat.completions.create(
            model=model, messages=messages,
            max_tokens=max_tokens, temperature=temperature,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        return f"OpenAI error: {e}"


# ── Source constants ───────────────────────────────────────────────────────
SS_URL      = "https://api.semanticscholar.org/graph/v1"
OA_URL      = "https://api.openalex.org/works"
ARXIV_URL   = "http://export.arxiv.org/api/query"
CR_URL      = "https://api.crossref.org/works"
PUBMED_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EPMC_URL    = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
SS_FIELDS   = ("title,authors,abstract,year,externalIds,"
               "openAccessPdf,isOpenAccess,citationCount,influentialCitationCount")

WRITING_SECTIONS = {
    "abstract":     "Write a structured academic abstract (150–250 words): background, objective, methods, results, conclusion.",
    "introduction": "Write an academic introduction (400–600 words): background, problem, gap, objectives, structure.",
    "related_work": "Write a related work section (400–600 words) reviewing existing approaches.",
    "methodology":  "Write a methodology section (400–600 words) describing the approach clearly.",
    "results":      "Write a results section (300–500 words) presenting findings objectively.",
    "discussion":   "Write a discussion section (400–600 words) interpreting results and limitations.",
    "conclusion":   "Write a conclusion (200–300 words) summarising contributions and future work.",
}


# ══════════════════════════════════════════════════════════════════════════
# STEP 1 — Query expansion with GPT
# ══════════════════════════════════════════════════════════════════════════

def _expand_query(query: str) -> list[str]:
    """
    Use GPT to turn one natural-language query into 3 optimised
    academic search strings (different phrasings / keywords).
    Falls back to [query] if GPT is unavailable.
    """
    prompt = f"""You are an academic search expert.
Given this research query: "{query}"

Generate exactly 3 optimised search strings for academic databases.
Each should use different keywords / synonyms to maximise coverage.
Return a JSON array of 3 strings only, e.g. ["query1","query2","query3"]."""
    raw = _gpt([{"role": "user", "content": prompt}], max_tokens=200, temperature=0.4)
    try:
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            variants = json.loads(match.group())
            if isinstance(variants, list) and len(variants) >= 1:
                return list(dict.fromkeys([query] + variants))[:4]
    except Exception:
        pass
    return [query]


# ══════════════════════════════════════════════════════════════════════════
# STEP 2 — Individual source fetchers
# ══════════════════════════════════════════════════════════════════════════

def _norm_paper(title="", authors="", abstract="", year="", doi="",
                source="", citation_count=0, url="",
                paper_id="", is_open_access=False) -> dict:
    return {
        "title":          (title or "").strip(),
        "authors":        (authors or "").strip(),
        "abstract":       (abstract or "").strip(),
        "year":           str(year or "").strip(),
        "doi":            (doi or "").strip(),
        "source":         source,
        "citation_count": int(citation_count or 0),
        "url":            (url or "").strip(),
        "paper_id":       (paper_id or "").strip(),
        "is_open_access": bool(is_open_access),
    }


def _resolve_url(ext_ids: dict, ss_pdf=None) -> str:
    """Best available URL for a paper (prefer open-access PDF, else DOI page)."""
    if ss_pdf:
        u = (ss_pdf or {}).get("url") or ""
        if u:
            return u
    arxiv = (ext_ids or {}).get("ArXiv") or ""
    if arxiv:
        return f"https://arxiv.org/abs/{arxiv}"
    pmc = (ext_ids or {}).get("PubMedCentral") or ""
    if pmc:
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc}/"
    doi = (ext_ids or {}).get("DOI") or ""
    if doi:
        return f"https://doi.org/{doi}"
    return ""


def _fetch_semantic_scholar(query: str, limit: int) -> list:
    try:
        r = requests.get(f"{SS_URL}/paper/search",
                         params={"query": query, "limit": limit, "fields": SS_FIELDS},
                         timeout=12)
        r.raise_for_status()
        out = []
        for p in r.json().get("data", []):
            ext = p.get("externalIds") or {}
            authors = ", ".join(a["name"] for a in (p.get("authors") or [])[:8])
            out.append(_norm_paper(
                title=p.get("title"), authors=authors,
                abstract=p.get("abstract"), year=p.get("year"),
                doi=ext.get("DOI"), source="Semantic Scholar",
                citation_count=p.get("citationCount"),
                url=_resolve_url(ext, p.get("openAccessPdf")),
                paper_id=p.get("paperId"),
                is_open_access=bool(p.get("isOpenAccess")),
            ))
        return out
    except Exception:
        return []


def _fetch_openalex(query: str, limit: int) -> list:
    try:
        r = requests.get(OA_URL, params={
            "search": query, "per-page": limit,
            "select": "title,authorships,abstract_inverted_index,publication_year,"
                      "doi,cited_by_count,open_access,ids,primary_location",
        }, headers={"User-Agent": "ResearchAI/2.0 (mailto:research@example.com)"},
           timeout=12)
        r.raise_for_status()
        out = []
        for w in r.json().get("results", []):
            authors = ", ".join(
                (a.get("author") or {}).get("display_name") or ""
                for a in (w.get("authorships") or [])[:8]
            )
            inv = w.get("abstract_inverted_index") or {}
            abstract = _reconstruct_abstract(inv)
            doi_raw = (w.get("doi") or "").replace("https://doi.org/", "")
            oa = w.get("open_access") or {}
            loc = w.get("primary_location") or {}
            url = oa.get("oa_url") or loc.get("landing_page_url") or ""
            if not url and doi_raw:
                url = f"https://doi.org/{doi_raw}"
            ids = w.get("ids") or {}
            out.append(_norm_paper(
                title=w.get("title"), authors=authors, abstract=abstract,
                year=w.get("publication_year"), doi=doi_raw,
                source="OpenAlex", citation_count=w.get("cited_by_count"),
                url=url, paper_id=ids.get("openalex") or "",
                is_open_access=bool(oa.get("is_oa")),
            ))
        return out
    except Exception:
        return []


def _reconstruct_abstract(inv: dict) -> str:
    if not inv:
        return ""
    try:
        pos = sorted([(p, w) for w, ps in inv.items() for p in ps])
        return " ".join(w for _, w in pos)
    except Exception:
        return ""


def _fetch_arxiv(query: str, limit: int) -> list:
    try:
        import xml.etree.ElementTree as ET
        r = requests.get(ARXIV_URL, params={
            "search_query": f"all:{query}", "max_results": limit, "sortBy": "relevance"
        }, timeout=12)
        r.raise_for_status()
        ns = "http://www.w3.org/2005/Atom"
        root = ET.fromstring(r.content)
        out = []
        for e in root.findall(f"{{{ns}}}entry"):
            arxiv_id = (e.findtext(f"{{{ns}}}id") or "").split("/abs/")[-1].strip()
            title = (e.findtext(f"{{{ns}}}title") or "").replace("\n", " ").strip()
            abstract = (e.findtext(f"{{{ns}}}summary") or "").replace("\n", " ").strip()
            authors = ", ".join(
                (a.findtext(f"{{{ns}}}name") or "")
                for a in e.findall(f"{{{ns}}}author")[:8]
            )
            year = (e.findtext(f"{{{ns}}}published") or "")[:4]
            doi_el = e.find("{http://arxiv.org/schemas/atom}doi")
            doi = (doi_el.text or "") if doi_el is not None else ""
            url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
            out.append(_norm_paper(
                title=title, authors=authors, abstract=abstract, year=year,
                doi=doi, source="arXiv", url=url, paper_id=arxiv_id,
                is_open_access=True,
            ))
        return out
    except Exception:
        return []


def _fetch_crossref(query: str, limit: int) -> list:
    try:
        r = requests.get(CR_URL, params={
            "query": query, "rows": limit,
            "select": "title,author,abstract,published,DOI,is-referenced-by-count",
        }, timeout=12)
        r.raise_for_status()
        out = []
        for item in r.json().get("message", {}).get("items", []):
            title = ((item.get("title") or [""])[0])
            authors = ", ".join(
                f"{a.get('given','')} {a.get('family','')}".strip()
                for a in (item.get("author") or [])[:8]
            )
            pub = item.get("published") or {}
            parts = (pub.get("date-parts") or [[]])[0]
            year = str(parts[0]) if parts else ""
            abstract = re.sub(r"<[^>]+>", " ", item.get("abstract") or "").strip()
            doi = item.get("DOI") or ""
            url = f"https://doi.org/{doi}" if doi else ""
            out.append(_norm_paper(
                title=title, authors=authors, abstract=abstract, year=year,
                doi=doi, source="CrossRef",
                citation_count=item.get("is-referenced-by-count"),
                url=url,
            ))
        return out
    except Exception:
        return []



# ══════════════════════════════════════════════════════════════════════════
# Extra sources: Google Scholar, PubMed, Europe PMC
# ══════════════════════════════════════════════════════════════════════════

def _clean_text(text: str) -> str:
    """Normalise text from any API: strip HTML tags, collapse whitespace,
    remove NUL bytes and stray control characters."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)          # strip HTML/XML tags
    text = re.sub(r"\\x[0-9a-fA-F]{2}", "", text) # hex escapes
    text = text.replace("\x00", "")               # NUL bytes
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"\s+", " ", text)              # collapse whitespace
    return text.strip()


def _fetch_google_scholar(query: str, limit: int) -> list:
    """
    Google Scholar via the `scholarly` library.
    scholarly scrapes Scholar pages; it is best-effort and may be blocked
    by CAPTCHA on high-traffic servers. Returns [] gracefully on any error.
    """
    try:
        from scholarly import scholarly as _sch
        out = []
        for pub in _sch.search_pubs(query):
            if len(out) >= limit:
                break
            bib = pub.get("bib") or {}
            title   = _clean_text(bib.get("title") or "")
            authors = _clean_text(bib.get("author") or "")
            if isinstance(authors, list):
                authors = ", ".join(authors)
            abstract = _clean_text(bib.get("abstract") or "")
            year     = str(bib.get("pub_year") or "").strip()
            url      = pub.get("pub_url") or pub.get("eprint_url") or ""
            doi      = ""
            # Extract DOI from URL if present
            doi_match = re.search(r"10\.\d{4,}/\S+", url)
            if doi_match:
                doi = doi_match.group().rstrip(".,)")
            cites = 0
            try:
                cites = int(pub.get("num_citations") or 0)
            except (ValueError, TypeError):
                pass
            out.append(_norm_paper(
                title=title, authors=authors, abstract=abstract,
                year=year, doi=doi, source="Google Scholar",
                citation_count=cites, url=url,
            ))
        return out
    except Exception:
        return []


def _fetch_pubmed(query: str, limit: int) -> list:
    """PubMed via NCBI E-utilities (free, no key needed for ≤3 req/s)."""
    try:
        # Step 1: search for IDs
        search_r = requests.get(
            f"{PUBMED_URL}/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": limit,
                    "retmode": "json", "usehistory": "y"},
            timeout=12,
        )
        search_r.raise_for_status()
        search_data = search_r.json()
        ids = search_data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        # Step 2: fetch summaries
        summary_r = requests.get(
            f"{PUBMED_URL}/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(ids),
                    "retmode": "json"},
            timeout=12,
        )
        summary_r.raise_for_status()
        summaries = summary_r.json().get("result", {})

        # Step 3: fetch abstracts via efetch
        fetch_r = requests.get(
            f"{PUBMED_URL}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(ids),
                    "rettype": "abstract", "retmode": "xml"},
            timeout=15,
        )
        fetch_r.raise_for_status()

        import xml.etree.ElementTree as ET
        root = ET.fromstring(fetch_r.content)
        abstracts_map = {}
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            if pmid_el is None:
                continue
            pmid = pmid_el.text or ""
            abstract_texts = article.findall(".//AbstractText")
            abstract = " ".join((el.text or "") for el in abstract_texts)
            abstracts_map[pmid] = _clean_text(abstract)

        out = []
        for pmid in ids:
            s = summaries.get(pmid, {})
            if not isinstance(s, dict):
                continue
            title   = _clean_text(s.get("title") or "")
            authors = ", ".join(
                a.get("name", "") for a in (s.get("authors") or [])[:8]
            )
            year = str(s.get("pubdate") or "")[:4]
            doi  = next((
                id_obj.get("value", "")
                for id_obj in (s.get("articleids") or [])
                if id_obj.get("idtype") == "doi"
            ), "")
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            abstract = abstracts_map.get(pmid, "")
            out.append(_norm_paper(
                title=title, authors=authors, abstract=abstract,
                year=year, doi=doi, source="PubMed",
                citation_count=0, url=url,
            ))
        return out
    except Exception:
        return []


def _fetch_europe_pmc(query: str, limit: int) -> list:
    """Europe PMC — open access biomedical literature."""
    try:
        r = requests.get(
            EPMC_URL,
            params={"query": query, "resulttype": "core",
                    "pageSize": limit, "format": "json", "sort_cited": "y"},
            timeout=12,
        )
        r.raise_for_status()
        out = []
        for item in r.json().get("resultList", {}).get("result", []):
            title   = _clean_text(item.get("title") or "")
            authors_raw = item.get("authorList", {}).get("author") or []
            authors = ", ".join(
                (a.get("fullName") or a.get("lastName") or "")
                for a in authors_raw[:8]
            )
            abstract = _clean_text(item.get("abstractText") or "")
            year     = str(item.get("pubYear") or "").strip()
            doi      = (item.get("doi") or "").strip()
            pmid     = (item.get("pmid") or "").strip()
            url      = (f"https://europepmc.org/article/MED/{pmid}" if pmid
                        else (f"https://doi.org/{doi}" if doi else ""))
            cites = 0
            try:
                cites = int(item.get("citedByCount") or 0)
            except (ValueError, TypeError):
                pass
            out.append(_norm_paper(
                title=title, authors=authors, abstract=abstract,
                year=year, doi=doi, source="Europe PMC",
                citation_count=cites, url=url,
            ))
        return out
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════
# STEP 3 — Embedding-based semantic re-ranking
# ══════════════════════════════════════════════════════════════════════════

def _embed(texts: list[str]) -> list[list[float]]:
    """Get text-embedding-3-small embeddings for a list of texts."""
    c = _get_client()
    if not c or not texts:
        return []
    try:
        resp = c.embeddings.create(
            model="text-embedding-3-small",
            input=[t[:8000] for t in texts],
        )
        return [item.embedding for item in resp.data]
    except Exception:
        return []


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _rerank(query: str, papers: list[dict]) -> list[dict]:
    """
    Embed query and each paper's title+abstract, then sort descending by
    cosine similarity. Falls back to original order if embeddings fail.
    """
    if not papers:
        return papers

    texts = [f"{p['title']} {p['abstract']}"[:1000] for p in papers]
    all_texts = [query] + texts
    embeddings = _embed(all_texts)

    if len(embeddings) < 2:
        return papers

    query_emb  = embeddings[0]
    paper_embs = embeddings[1:]

    for i, paper in enumerate(papers):
        paper["_score"] = _cosine(query_emb, paper_embs[i]) if i < len(paper_embs) else 0.0

    papers.sort(key=lambda p: p.get("_score", 0.0), reverse=True)
    return papers


# ══════════════════════════════════════════════════════════════════════════
# STEP 4 — Dedup + quality filter
# ══════════════════════════════════════════════════════════════════════════

def _has_required_fields(p: dict) -> bool:
    """A paper must have title, authors, abstract, and at least one URL."""
    return (
        bool((p.get("title") or "").strip())
        and bool((p.get("authors") or "").strip())
        and bool((p.get("abstract") or "").strip())
        and bool((p.get("url") or p.get("doi") or "").strip())
    )


def _dedup(papers: list[dict]) -> list[dict]:
    seen_doi, seen_title, out = set(), set(), []
    for p in papers:
        doi   = (p.get("doi") or "").strip().lower()
        title = re.sub(r"[^a-z0-9]", "", (p.get("title") or "").lower())
        if doi and doi in seen_doi:
            continue
        if title and title in seen_title:
            continue
        if doi:
            seen_doi.add(doi)
        if title:
            seen_title.add(title)
        out.append(p)
    return out


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC — search_papers
# ══════════════════════════════════════════════════════════════════════════

def search_papers(query: str, limit: int = 20,
                  year_min: int = None, year_max: int = None,
                  sources: list = None) -> tuple[list, str | None]:
    """
    Full pipeline:
      1. GPT query expansion → up to 4 query variants
      2. Parallel fetch from 7 sources (Semantic Scholar, OpenAlex, arXiv,
         CrossRef, Google Scholar, PubMed, Europe PMC)
         Each source fetches `per_variant` results per query variant.
         With 7 sources × 4 variants = up to 28 parallel calls, giving
         hundreds of candidate papers before filtering and dedup.
      3. Clean all text (strip HTML, NUL bytes, whitespace)
      4. Filter: must have title + authors + abstract + URL
      5. Dedup by DOI then normalised title
      6. Embedding re-rank by semantic similarity to original query
      7. Return top `limit` results

    `per_variant` is tuned so that after dedup/filter we always have
    enough candidates to fill `limit`:
      - For limit ≤ 20 : fetch 15 per source per variant
      - For limit ≤ 50 : fetch 25 per source per variant
      - For limit > 50  : fetch 40 per source per variant

    Returns (results_list, error_string | None)
    """
    all_sources = {
        "Semantic Scholar": _fetch_semantic_scholar,
        "OpenAlex":         _fetch_openalex,
        "arXiv":            _fetch_arxiv,
        "CrossRef":         _fetch_crossref,
        "Google Scholar":   _fetch_google_scholar,
        "PubMed":           _fetch_pubmed,
        "Europe PMC":       _fetch_europe_pmc,
    }
    active = {k: v for k, v in all_sources.items()
              if sources is None or k in sources}

    # Step 1: expand query
    variants = _expand_query(query)

    # Tune per-variant fetch count based on desired final count
    if limit <= 20:
        per_variant = 15
    elif limit <= 50:
        per_variant = 25
    else:
        per_variant = 40

    # Step 2: parallel fetch — each source × each query variant
    all_papers = []
    with ThreadPoolExecutor(max_workers=min(16, len(active) * len(variants))) as pool:
        futures = [
            pool.submit(fn, variant, per_variant)
            for fn in active.values()
            for variant in variants
        ]
        for future in as_completed(futures):
            try:
                all_papers.extend(future.result())
            except Exception:
                pass

    if not all_papers:
        return [], "No results from any source. Check your internet connection."

    # Step 3: filter — must have all required fields
    filtered = [p for p in all_papers if _has_required_fields(p)]

    # Step 4: year filter
    if year_min or year_max:
        def _in_range(p):
            y = p.get("year", "")
            if not str(y).isdigit():
                return True
            yi = int(y)
            if year_min and yi < year_min:
                return False
            if year_max and yi > year_max:
                return False
            return True
        filtered = [p for p in filtered if _in_range(p)]

    # Step 5: dedup
    deduped = _dedup(filtered)

    if not deduped:
        total = len(all_papers)
        passed = len(filtered)
        return [], (
            f"Found {total} raw results but {total - passed} were missing "
            f"title/authors/abstract/URL and {passed - len(deduped)} were duplicates. "
            f"Try different keywords."
        )

    # Step 6: semantic re-rank (embed up to 200 candidates for speed)
    candidates = deduped[:200]
    reranked = _rerank(query, candidates)

    # Append any remaining beyond 200 unranked at the end
    if len(deduped) > 200:
        ranked_ids = {id(p) for p in reranked}
        tail = [p for p in deduped[200:] if id(p) not in ranked_ids]
        reranked = reranked + tail

    return reranked[:limit], None


# ══════════════════════════════════════════════════════════════════════════
# TLDR
# ══════════════════════════════════════════════════════════════════════════

def generate_tldr(abstract: str, title: str = "") -> str:
    if not abstract:
        return "No abstract available."
    return _gpt([
        {"role": "system", "content":
         "Summarise this academic paper in exactly 2 sentences. "
         "First sentence: what problem they tackle and their approach. "
         "Second sentence: the key result or contribution."},
        {"role": "user", "content": f"Title: {title}\n\nAbstract: {abstract}"},
    ], max_tokens=180, temperature=0.3)


# ══════════════════════════════════════════════════════════════════════════
# Chat
# ══════════════════════════════════════════════════════════════════════════

def chat_with_paper(messages: list, paper_context: str, user_message: str) -> str:
    system = f"""You are an expert research assistant. You help a researcher understand this paper.

PAPER CONTENT:
{paper_context[:14000]}

Rules:
- Ground all answers strictly in the paper content above.
- If something is not in the paper, say so clearly.
- Use specific sections, quotes or data when helpful.
- Be concise, precise, and academic in tone."""
    msgs = [{"role": "system", "content": system}]
    for m in messages[-12:]:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": user_message})
    return _gpt(msgs, model="gpt-4o", max_tokens=1200, temperature=0.4)


def general_research_chat(messages: list, user_message: str) -> str:
    system = ("You are ResearchAI, an expert academic assistant. Help with "
              "explaining concepts, suggesting research directions, comparing "
              "methodologies, formulating research questions, and academic writing. "
              "Be precise, rigorous, and helpful.")
    msgs = [{"role": "system", "content": system}]
    for m in messages[-12:]:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": user_message})
    return _gpt(msgs, model="gpt-4o", max_tokens=1400, temperature=0.5)


# ══════════════════════════════════════════════════════════════════════════
# Literature review
# ══════════════════════════════════════════════════════════════════════════

def generate_literature_review(query: str, papers: list) -> str:
    if not papers:
        return "No papers provided."
    papers_text = ""
    for i, p in enumerate(papers[:20], 1):
        papers_text += f"\n[{i}] {p.get('title','?')} ({p.get('year','?')})\n"
        papers_text += f"    Authors: {p.get('authors','?')}\n"
        papers_text += f"    Abstract: {(p.get('abstract') or '')[:400]}\n"

    prompt = f"""Write a comprehensive, analytical literature review on:

TOPIC: {query}

PAPERS:
{papers_text}

Structure with these sections:
1. **Introduction** — context and significance
2. **Thematic Analysis** — group papers by themes/approaches
3. **Methodological Trends** — common and contrasting methods
4. **Key Findings & Contributions** — synthesised results
5. **Research Gaps & Future Directions** — what is missing
6. **Conclusion** — synthesis of the field

Requirements: academic style, cite papers as [1],[2]..., be analytical not just descriptive, minimum 900 words."""
    return _gpt([{"role": "user", "content": prompt}],
                model="gpt-4o", max_tokens=3500, temperature=0.5)


# ══════════════════════════════════════════════════════════════════════════
# AI Writer
# ══════════════════════════════════════════════════════════════════════════

def generate_section(section_type: str, context: str, topic: str) -> str:
    instruction = WRITING_SECTIONS.get(section_type, "Write this section in formal academic style.")
    prompt = f"You are an expert academic writer.\n\nPAPER TOPIC: {topic}\nCONTEXT/NOTES: {context}\n\nTASK: {instruction}\n\nWrite in formal academic English."
    return _gpt([{"role": "user", "content": prompt}],
                model="gpt-4o", max_tokens=1400, temperature=0.6)


def improve_writing(text: str, instruction: str = "improve clarity and academic tone") -> str:
    return _gpt([
        {"role": "system", "content": "You are an expert academic editor."},
        {"role": "user",   "content": f"Please {instruction}:\n\n{text}"},
    ], max_tokens=2000, temperature=0.4)


def paraphrase_text(text: str) -> str:
    return _gpt([
        {"role": "system", "content": "Paraphrase the following text in academic style, completely rewording it."},
        {"role": "user",   "content": text},
    ], max_tokens=1200, temperature=0.6)


def explain_concept(concept: str, context: str = "") -> str:
    return _gpt([
        {"role": "system", "content": "You are a research mentor who explains complex concepts clearly."},
        {"role": "user",   "content": f"Explain: '{concept}'\n{'Context: ' + context if context else ''}"},
    ], max_tokens=450, temperature=0.4)


def suggest_research_questions(topic: str, papers: list = None) -> list:
    ctx = "\n".join("- " + p.get("title", "") for p in (papers or [])[:10])
    papers_section = ("Papers:\n" + ctx) if ctx else ""
    prompt = f"Topic: {topic}\n{papers_section}\nGenerate 8 specific, novel research questions. Return ONLY a JSON array: [\"Q1\",\"Q2\",...]"
    raw = _gpt([{"role": "user", "content": prompt}], max_tokens=700, temperature=0.7)
    try:
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return [l.strip("- ").strip() for l in raw.split("\n") if l.strip()]


# ══════════════════════════════════════════════════════════════════════════
# Citations
# ══════════════════════════════════════════════════════════════════════════

def _fallback_citation(paper: dict, style: str) -> str:
    a = paper.get("authors") or "Unknown"
    y = paper.get("year") or "n.d."
    t = paper.get("title") or "Unknown"
    d = f" https://doi.org/{paper['doi']}" if paper.get("doi") else ""
    s = style.upper()
    if s == "APA":   return f"{a} ({y}). {t}.{d}"
    if s == "MLA":   return f'{a}. "{t}." {y}.{d}'
    return f"{a} ({y}). {t}.{d}"


def generate_citation(paper: dict, style: str = "APA") -> str:
    prompt = (f"Generate a {style} citation for:\nTitle: {paper.get('title','?')}\n"
              f"Authors: {paper.get('authors','?')}\nYear: {paper.get('year','n.d.')}\n"
              f"DOI: {paper.get('doi','')}\nReturn ONLY the citation string.")
    r = _gpt([{"role": "user", "content": prompt}], max_tokens=220, temperature=0.1)
    return r if not r.startswith(("OpenAI", "Error")) else _fallback_citation(paper, style)


def generate_bibtex(paper: dict) -> str:
    try:
        authors = (paper.get("authors") or "Unknown").strip()
        last = (authors.split(",")[0] if "," in authors else authors.split()[0]).split()[-1]
        year = (paper.get("year") or "0000").strip() or "0000"
        title = (paper.get("title") or "Unknown").replace("{","").replace("}","").replace("&","\\&")
        key = re.sub(r'\W', '', f"{last}{year}")
        doi = (paper.get("doi") or "").strip()
        authors_clean = authors.replace("&", "\\&")
        lines = [
            f"@article{{{key},",
            f"  title  = {{{title}}},",
            f"  author = {{{authors_clean}}},",
            f"  year   = {{{year}}},",
        ]
        if doi:
            lines.append(f"  doi    = {{{doi}}},")
        lines.append("}")
        return "\n".join(lines)
    except Exception:
        t = paper.get("title", "?")
        a = paper.get("authors", "?")
        y = paper.get("year", "?")
        return ("@article{unknown,\n"
                + f"  title={{{t}}},\n"
                + f"  author={{{a}}},\n"
                + f"  year={{{y}}}\n}}")


# ══════════════════════════════════════════════════════════════════════════
# PDF utilities
# ══════════════════════════════════════════════════════════════════════════

def extract_pdf_text(file_bytes: bytes) -> str:
    try:
        import PyPDF2, io
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        text = text.replace("\x00", "")
        text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        return text.strip()
    except Exception:
        return ""


def extract_metadata_from_text(text: str) -> dict:
    prompt = (f"Extract metadata from this academic paper:\n{text[:3000]}\n\n"
              "Return JSON: {\"title\":\"\",\"authors\":\"\",\"abstract\":\"\",\"year\":\"\",\"doi\":\"\"}\nJSON only.")
    raw = _gpt([{"role": "user", "content": prompt}], max_tokens=600, temperature=0.1)
    try:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {"title": "", "authors": "", "abstract": "", "year": "", "doi": ""}