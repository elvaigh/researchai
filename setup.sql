-- ResearchAI PostgreSQL Setup Script
-- Run this to create the database before launching the app

-- Create database (run as superuser)
-- psql -U postgres -c "CREATE DATABASE researchai;"

-- Then connect and create tables:
-- psql -U postgres -d researchai -f setup.sql

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    username    VARCHAR(100) NOT NULL,
    password    TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW(),
    plan        VARCHAR(50) DEFAULT 'free'
);

CREATE TABLE IF NOT EXISTS workspaces (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS papers (
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
    tags            TEXT[],
    notes           TEXT,
    citation_apa    TEXT,
    citation_bibtex TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id              SERIAL PRIMARY KEY,
    workspace_id    INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    paper_id        INTEGER REFERENCES papers(id) ON DELETE SET NULL,
    title           VARCHAR(255),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          SERIAL PRIMARY KEY,
    session_id  INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS documents (
    id              SERIAL PRIMARY KEY,
    workspace_id    INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(255),
    content         TEXT,
    doc_type        VARCHAR(50) DEFAULT 'draft',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS literature_reviews (
    id              SERIAL PRIMARY KEY,
    workspace_id    INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    query           TEXT NOT NULL,
    report          TEXT,
    paper_ids       INTEGER[],
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS search_history (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    query           TEXT NOT NULL,
    results_count   INTEGER,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_papers_workspace ON papers(workspace_id);
CREATE INDEX IF NOT EXISTS idx_papers_user ON papers(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_workspace ON chat_sessions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace_id);
CREATE INDEX IF NOT EXISTS idx_reviews_workspace ON literature_reviews(workspace_id);

SELECT 'ResearchAI database setup complete!' AS status;
