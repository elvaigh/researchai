"""
Database module — PostgreSQL via SQLAlchemy + psycopg2
Reads credentials from st.secrets (Streamlit Cloud) or .env (local dev)
via utils/config.py.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

# Load .env for local dev — ignored on Streamlit Cloud (st.secrets takes over)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
load_dotenv(os.path.join(_ROOT, ".env"), override=False)

from utils.config import cfg  # noqa: E402


# ── Engine ─────────────────────────────────────────────────────────────────

def _build_url() -> str:
    """Build the SQLAlchemy PostgreSQL connection URL from cfg."""
    user     = cfg.DB_USER
    password = cfg.DB_PASSWORD
    host     = cfg.DB_HOST
    port     = cfg.DB_PORT
    dbname   = cfg.DB_NAME
    return (
        f"postgresql+psycopg2://{user}:{password}"
        f"@{host}:{port}/{dbname}"
        f"?sslmode=require"
    )


def _get_engine():
    """
    Return a SQLAlchemy engine with NullPool.
    NullPool disables SQLAlchemy's own connection pool — required for Supabase
    poolers which manage connections themselves.
    """
    return create_engine(_build_url(), poolclass=NullPool)


# ── Helpers ────────────────────────────────────────────────────────────────

def _sanitise(value):
    """Recursively strip NUL bytes (\\x00) — PostgreSQL TEXT rejects them."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, (list, tuple)):
        return type(value)(_sanitise(v) for v in value)
    return value


def _clean(value) -> str:
    """Strip NUL bytes from a single string value."""
    return value.replace("\x00", "") if isinstance(value, str) else value


def _row(mapping) -> dict:
    """Convert a SQLAlchemy RowMapping to a plain dict."""
    return dict(mapping) if mapping is not None else None


def _exec(query: str, params: dict = None, fetch: str = None):
    """
    Execute a parameterised SQL query (named :param style).
    fetch: None | 'one' | 'all'
    Returns: None | dict | list[dict]
    """
    if params:
        params = {k: _sanitise(v) for k, v in params.items()}

    engine = _get_engine()
    with engine.begin() as conn:
        result = conn.execute(text(query), params or {})
        if fetch == "one":
            return _row(result.mappings().first())
        if fetch == "all":
            return [_row(r) for r in result.mappings().all()]
    return None


# ── Schema ─────────────────────────────────────────────────────────────────

def init_db():
    """Create all tables, indexes, and run migrations."""
    statements = [
        """CREATE TABLE IF NOT EXISTS users (
            id          SERIAL PRIMARY KEY,
            email       VARCHAR(255) UNIQUE NOT NULL,
            username    VARCHAR(100) NOT NULL,
            password    TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT NOW(),
            plan        VARCHAR(50) DEFAULT 'free'
        )""",
        """CREATE TABLE IF NOT EXISTS workspaces (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name        VARCHAR(255) NOT NULL,
            description TEXT,
            created_at  TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS papers (
            id              SERIAL PRIMARY KEY,
            workspace_id    INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title           TEXT NOT NULL,
            authors         TEXT,
            abstract        TEXT,
            year            VARCHAR(10),
            doi             VARCHAR(255),
            source          VARCHAR(100),
            full_text       TEXT,
            file_name       VARCHAR(255),
            pdf_data        BYTEA,
            tags            TEXT[],
            notes           TEXT,
            citation_apa    TEXT,
            citation_bibtex TEXT,
            created_at      TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS chat_sessions (
            id              SERIAL PRIMARY KEY,
            workspace_id    INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
            paper_id        INTEGER REFERENCES papers(id) ON DELETE SET NULL,
            title           VARCHAR(255),
            created_at      TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS chat_messages (
            id          SERIAL PRIMARY KEY,
            session_id  INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
            role        VARCHAR(20) NOT NULL,
            content     TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS documents (
            id              SERIAL PRIMARY KEY,
            workspace_id    INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title           VARCHAR(255),
            content         TEXT,
            doc_type        VARCHAR(50) DEFAULT 'draft',
            created_at      TIMESTAMP DEFAULT NOW(),
            updated_at      TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS literature_reviews (
            id              SERIAL PRIMARY KEY,
            workspace_id    INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
            query           TEXT NOT NULL,
            report          TEXT,
            paper_ids       INTEGER[],
            created_at      TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS search_history (
            id              SERIAL PRIMARY KEY,
            user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
            query           TEXT NOT NULL,
            results_count   INTEGER,
            created_at      TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS idx_papers_workspace        ON papers(workspace_id)",
        "CREATE INDEX IF NOT EXISTS idx_papers_user             ON papers(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_workspace ON chat_sessions(workspace_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_session   ON chat_messages(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_documents_workspace     ON documents(workspace_id)",
        "CREATE INDEX IF NOT EXISTS idx_reviews_workspace       ON literature_reviews(workspace_id)",
        # Migration: add pdf_data to existing databases
        """DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='papers' AND column_name='pdf_data'
            ) THEN
                ALTER TABLE papers ADD COLUMN pdf_data BYTEA;
            END IF;
        END$$""",
    ]
    engine = _get_engine()
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


# ── Users ──────────────────────────────────────────────────────────────────

def create_user(email: str, username: str, hashed_password: str) -> dict:
    return _exec(
        "INSERT INTO users (email, username, password) "
        "VALUES (:email, :username, :password) RETURNING *",
        {"email": email, "username": username, "password": hashed_password},
        fetch="one",
    )


def get_user_by_email(email: str):
    return _exec(
        "SELECT * FROM users WHERE email = :email",
        {"email": email}, fetch="one",
    )


def get_user_by_id(user_id: int):
    return _exec(
        "SELECT * FROM users WHERE id = :id",
        {"id": user_id}, fetch="one",
    )


# ── Workspaces ─────────────────────────────────────────────────────────────

def create_workspace(user_id: int, name: str, description: str = "") -> dict:
    return _exec(
        "INSERT INTO workspaces (user_id, name, description) "
        "VALUES (:uid, :name, :desc) RETURNING *",
        {"uid": user_id, "name": name, "desc": description},
        fetch="one",
    )


def get_workspaces(user_id: int) -> list:
    return _exec(
        "SELECT * FROM workspaces WHERE user_id = :uid ORDER BY created_at DESC",
        {"uid": user_id}, fetch="all",
    ) or []


def delete_workspace(ws_id: int, user_id: int):
    _exec(
        "DELETE FROM workspaces WHERE id = :id AND user_id = :uid",
        {"id": ws_id, "uid": user_id},
    )


# ── Papers ─────────────────────────────────────────────────────────────────

def save_paper(workspace_id: int, user_id: int, data: dict) -> dict:
    return _exec(
        """
        INSERT INTO papers
            (workspace_id, user_id, title, authors, abstract, year, doi,
             source, full_text, file_name, pdf_data, tags, notes,
             citation_apa, citation_bibtex)
        VALUES
            (:ws, :uid, :title, :authors, :abstract, :year, :doi,
             :source, :full_text, :file_name, :pdf_data, :tags, :notes,
             :apa, :bibtex)
        RETURNING *
        """,
        {
            "ws":        workspace_id,
            "uid":       user_id,
            "title":     _clean(data.get("title", "Untitled")),
            "authors":   _clean(data.get("authors", "")),
            "abstract":  _clean(data.get("abstract", "")),
            "year":      _clean(data.get("year", "")),
            "doi":       _clean(data.get("doi", "")),
            "source":    _clean(data.get("source", "manual")),
            "full_text": _clean(data.get("full_text", "")),
            "file_name": _clean(data.get("file_name", "")),
            "pdf_data":  data.get("pdf_data"),
            "tags":      data.get("tags", []),
            "notes":     _clean(data.get("notes", "")),
            "apa":       _clean(data.get("citation_apa", "")),
            "bibtex":    _clean(data.get("citation_bibtex", "")),
        },
        fetch="one",
    )


def get_papers(workspace_id: int) -> list:
    return _exec(
        "SELECT * FROM papers WHERE workspace_id = :ws ORDER BY created_at DESC",
        {"ws": workspace_id}, fetch="all",
    ) or []


def get_paper(paper_id: int):
    return _exec(
        "SELECT * FROM papers WHERE id = :id",
        {"id": paper_id}, fetch="one",
    )


def update_paper_notes(paper_id: int, notes: str):
    _exec(
        "UPDATE papers SET notes = :notes WHERE id = :id",
        {"notes": notes, "id": paper_id},
    )


def delete_paper(paper_id: int, user_id: int):
    _exec(
        "DELETE FROM papers WHERE id = :id AND user_id = :uid",
        {"id": paper_id, "uid": user_id},
    )


# ── Chat ───────────────────────────────────────────────────────────────────

def create_chat_session(workspace_id: int, user_id: int,
                        paper_id=None, title: str = "New Chat") -> dict:
    return _exec(
        "INSERT INTO chat_sessions (workspace_id, user_id, paper_id, title) "
        "VALUES (:ws, :uid, :pid, :title) RETURNING *",
        {"ws": workspace_id, "uid": user_id, "pid": paper_id, "title": title},
        fetch="one",
    )


def get_chat_sessions(workspace_id: int) -> list:
    return _exec(
        """SELECT cs.*, p.title AS paper_title
           FROM   chat_sessions cs
           LEFT JOIN papers p ON cs.paper_id = p.id
           WHERE  cs.workspace_id = :ws
           ORDER  BY cs.created_at DESC""",
        {"ws": workspace_id}, fetch="all",
    ) or []


def save_message(session_id: int, role: str, content: str) -> dict:
    return _exec(
        "INSERT INTO chat_messages (session_id, role, content) "
        "VALUES (:sid, :role, :content) RETURNING *",
        {"sid": session_id, "role": role, "content": content},
        fetch="one",
    )


def get_messages(session_id: int) -> list:
    return _exec(
        "SELECT * FROM chat_messages WHERE session_id = :sid ORDER BY created_at ASC",
        {"sid": session_id}, fetch="all",
    ) or []


# ── Documents ──────────────────────────────────────────────────────────────

def save_document(workspace_id: int, user_id: int,
                  title: str, content: str, doc_type: str = "draft") -> dict:
    return _exec(
        "INSERT INTO documents (workspace_id, user_id, title, content, doc_type) "
        "VALUES (:ws, :uid, :title, :content, :doc_type) RETURNING *",
        {"ws": workspace_id, "uid": user_id,
         "title": title, "content": content, "doc_type": doc_type},
        fetch="one",
    )


def get_documents(workspace_id: int) -> list:
    return _exec(
        "SELECT * FROM documents WHERE workspace_id = :ws ORDER BY updated_at DESC",
        {"ws": workspace_id}, fetch="all",
    ) or []


def update_document(doc_id: int, title: str, content: str):
    _exec(
        "UPDATE documents SET title=:title, content=:content, updated_at=NOW() WHERE id=:id",
        {"title": title, "content": content, "id": doc_id},
    )


def delete_document(doc_id: int, user_id: int):
    _exec(
        "DELETE FROM documents WHERE id = :id AND user_id = :uid",
        {"id": doc_id, "uid": user_id},
    )


# ── Literature Reviews ─────────────────────────────────────────────────────

def save_literature_review(workspace_id: int, user_id: int,
                            query: str, report: str, paper_ids: list) -> dict:
    return _exec(
        "INSERT INTO literature_reviews (workspace_id, user_id, query, report, paper_ids) "
        "VALUES (:ws, :uid, :query, :report, :pids) RETURNING *",
        {"ws": workspace_id, "uid": user_id,
         "query": query, "report": report, "pids": paper_ids},
        fetch="one",
    )


def get_literature_reviews(workspace_id: int) -> list:
    return _exec(
        "SELECT * FROM literature_reviews WHERE workspace_id = :ws ORDER BY created_at DESC",
        {"ws": workspace_id}, fetch="all",
    ) or []