"""
Database module — PostgreSQL via psycopg2.
Uses a persistent connection pool (ThreadedConnectionPool) so the
expensive TLS handshake to Neon/Supabase only happens once per process,
not on every query.
"""

import os
import psycopg2
import psycopg2.extras
from psycopg2 import pool as _pg_pool
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
load_dotenv(os.path.join(_ROOT, ".env"), override=False)

from utils.config import cfg  # noqa: E402


# ── Connection pool ────────────────────────────────────────────────────────

_pool = None

def _get_pool():
    """Return the singleton connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        kwargs = dict(
            host=cfg.DB_HOST,
            port=cfg.DB_PORT,
            dbname=cfg.DB_NAME,
            user=cfg.DB_USER,
            password=cfg.DB_PASSWORD,
            sslmode="require",
            connect_timeout=15,
        )
        if cfg.DB_OPTIONS:
            kwargs["options"] = cfg.DB_OPTIONS
        _pool = _pg_pool.ThreadedConnectionPool(minconn=1, maxconn=5, **kwargs)
    return _pool


def get_connection():
    """Borrow a connection from the pool."""
    return _get_pool().getconn()


def _return(conn, error=False):
    """Return connection to pool; close it on error so pool gets a fresh one."""
    try:
        _get_pool().putconn(conn, close=error)
    except Exception:
        pass


# ── Helpers ────────────────────────────────────────────────────────────────

def _sanitise(value):
    """Recursively strip NUL bytes — PostgreSQL TEXT rejects \\x00."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, (list, tuple)):
        return type(value)(_sanitise(v) for v in value)
    return value


def _clean(value) -> str:
    return value.replace("\x00", "") if isinstance(value, str) else value


def _exec(query: str, params=None, fetch: str = None):
    """
    Execute a query with %s-style params.
    fetch: None | 'one' | 'all'
    Returns: None | dict | list[dict]
    """
    if params is not None:
        params = _sanitise(params)
    conn = get_connection()
    error = False
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        result = None
        if fetch == "one":
            row = cur.fetchone()
            result = dict(row) if row else None
        elif fetch == "all":
            result = [dict(r) for r in cur.fetchall()]
        conn.commit()
        cur.close()
        return result
    except Exception:
        conn.rollback()
        error = True
        raise
    finally:
        _return(conn, error=error)  # return to pool, don't close


# ── Schema ─────────────────────────────────────────────────────────────────

def init_db():
    """Create all tables, indexes, and run migrations."""
    conn = get_connection()
    error = False
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                username VARCHAR(100) NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                plan VARCHAR(50) DEFAULT 'free'
            );
            CREATE TABLE IF NOT EXISTS workspaces (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS papers (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                authors TEXT, abstract TEXT, year VARCHAR(10),
                doi VARCHAR(255), source VARCHAR(100),
                full_text TEXT, file_name VARCHAR(255), pdf_data BYTEA,
                tags TEXT[], notes TEXT,
                citation_apa TEXT, citation_bibtex TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                paper_id INTEGER REFERENCES papers(id) ON DELETE SET NULL,
                title VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                session_id INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(255), content TEXT,
                doc_type VARCHAR(50) DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS literature_reviews (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                query TEXT NOT NULL, report TEXT,
                paper_ids INTEGER[],
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS search_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                query TEXT NOT NULL, results_count INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_papers_workspace
                ON papers(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_papers_user
                ON papers(user_id);
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_workspace
                ON chat_sessions(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session
                ON chat_messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_documents_workspace
                ON documents(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_workspace
                ON literature_reviews(workspace_id);
        """)
        # Migration: add pdf_data if missing
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='papers' AND column_name='pdf_data'
                ) THEN
                    ALTER TABLE papers ADD COLUMN pdf_data BYTEA;
                END IF;
            END$$;
        """)
        conn.commit()
        cur.close()
    except Exception:
        conn.rollback()
        error = True
        raise
    finally:
        _return(conn, error=error)


# ── Users ──────────────────────────────────────────────────────────────────

def create_user(email, username, hashed_password):
    return _exec(
        "INSERT INTO users (email,username,password) VALUES (%s,%s,%s) RETURNING *",
        (email, username, hashed_password), fetch="one")

def get_user_by_email(email):
    return _exec("SELECT * FROM users WHERE email=%s", (email,), fetch="one")

def get_user_by_id(user_id):
    return _exec("SELECT * FROM users WHERE id=%s", (user_id,), fetch="one")


# ── Workspaces ─────────────────────────────────────────────────────────────

def create_workspace(user_id, name, description=""):
    return _exec(
        "INSERT INTO workspaces (user_id,name,description) VALUES (%s,%s,%s) RETURNING *",
        (user_id, name, description), fetch="one")

def get_workspaces(user_id):
    return _exec(
        "SELECT * FROM workspaces WHERE user_id=%s ORDER BY created_at DESC",
        (user_id,), fetch="all") or []

def delete_workspace(ws_id, user_id):
    _exec("DELETE FROM workspaces WHERE id=%s AND user_id=%s", (ws_id, user_id))


# ── Papers ─────────────────────────────────────────────────────────────────

def save_paper(workspace_id, user_id, data):
    return _exec("""
        INSERT INTO papers
            (workspace_id, user_id, title, authors, abstract, year, doi,
             source, full_text, file_name, pdf_data, tags, notes,
             citation_apa, citation_bibtex)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """, (
        workspace_id, user_id,
        _clean(data.get("title","Untitled")),
        _clean(data.get("authors","")),
        _clean(data.get("abstract","")),
        _clean(data.get("year","")),
        _clean(data.get("doi","")),
        _clean(data.get("source","manual")),
        _clean(data.get("full_text","")),
        _clean(data.get("file_name","")),
        data.get("pdf_data"),
        data.get("tags",[]),
        _clean(data.get("notes","")),
        _clean(data.get("citation_apa","")),
        _clean(data.get("citation_bibtex","")),
    ), fetch="one")

def get_papers(workspace_id):
    return _exec(
        "SELECT * FROM papers WHERE workspace_id=%s ORDER BY created_at DESC",
        (workspace_id,), fetch="all") or []

def get_paper(paper_id):
    return _exec("SELECT * FROM papers WHERE id=%s", (paper_id,), fetch="one")

def update_paper_notes(paper_id, notes):
    _exec("UPDATE papers SET notes=%s WHERE id=%s", (notes, paper_id))

def delete_paper(paper_id, user_id):
    _exec("DELETE FROM papers WHERE id=%s AND user_id=%s", (paper_id, user_id))


# ── Chat ───────────────────────────────────────────────────────────────────

def create_chat_session(workspace_id, user_id, paper_id=None, title="New Chat"):
    return _exec(
        "INSERT INTO chat_sessions (workspace_id,user_id,paper_id,title) VALUES (%s,%s,%s,%s) RETURNING *",
        (workspace_id, user_id, paper_id, title), fetch="one")

def get_chat_sessions(workspace_id):
    return _exec("""
        SELECT cs.*, p.title AS paper_title
        FROM chat_sessions cs
        LEFT JOIN papers p ON cs.paper_id = p.id
        WHERE cs.workspace_id=%s ORDER BY cs.created_at DESC
        """, (workspace_id,), fetch="all") or []

def save_message(session_id, role, content):
    return _exec(
        "INSERT INTO chat_messages (session_id,role,content) VALUES (%s,%s,%s) RETURNING *",
        (session_id, role, content), fetch="one")

def get_messages(session_id):
    return _exec(
        "SELECT * FROM chat_messages WHERE session_id=%s ORDER BY created_at ASC",
        (session_id,), fetch="all") or []


# ── Documents ──────────────────────────────────────────────────────────────

def save_document(workspace_id, user_id, title, content, doc_type="draft"):
    return _exec(
        "INSERT INTO documents (workspace_id,user_id,title,content,doc_type) VALUES (%s,%s,%s,%s,%s) RETURNING *",
        (workspace_id, user_id, title, content, doc_type), fetch="one")

def get_documents(workspace_id):
    return _exec(
        "SELECT * FROM documents WHERE workspace_id=%s ORDER BY updated_at DESC",
        (workspace_id,), fetch="all") or []

def update_document(doc_id, title, content):
    _exec("UPDATE documents SET title=%s,content=%s,updated_at=NOW() WHERE id=%s",
          (title, content, doc_id))

def delete_document(doc_id, user_id):
    _exec("DELETE FROM documents WHERE id=%s AND user_id=%s", (doc_id, user_id))


# ── Literature Reviews ─────────────────────────────────────────────────────

def save_literature_review(workspace_id, user_id, query, report, paper_ids):
    return _exec(
        "INSERT INTO literature_reviews (workspace_id,user_id,query,report,paper_ids) VALUES (%s,%s,%s,%s,%s) RETURNING *",
        (workspace_id, user_id, query, report, paper_ids), fetch="one")

def get_literature_reviews(workspace_id):
    return _exec(
        "SELECT * FROM literature_reviews WHERE workspace_id=%s ORDER BY created_at DESC",
        (workspace_id,), fetch="all") or []