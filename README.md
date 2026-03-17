# 🔬 ResearchAI — AI-Powered Academic Research Platform

A full-featured SciSpace-like research platform built with **Streamlit + OpenAI + PostgreSQL**.

---

## ✨ Features

| Module | Features |
|--------|----------|
| **🔍 AI Search** | Semantic Scholar (200M+ papers), TLDR summaries, filters, save to library |
| **📚 Library** | PDF upload + auto metadata extraction, notes, tags, organized by workspace |
| **💬 Chat with Papers** | GPT-4o chat with individual papers or general research assistant |
| **📊 Literature Review** | Auto-generate structured reviews from selected papers (800+ words) |
| **✍️ AI Writer** | Generate Introduction / Abstract / Methodology / Results / Discussion / Conclusion |
| **🔖 References** | APA / MLA / Chicago / Harvard / Vancouver / IEEE · BibTeX export · Bulk export |
| **👤 Auth** | Register / Login with bcrypt-hashed passwords stored in PostgreSQL |
| **📁 Workspaces** | Multiple workspaces per user, each with isolated papers, chats, documents |

---

## 🚀 Quick Start

### 1. Clone / download this project

```bash
cd researchai/
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up PostgreSQL

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE researchai;"

# Create tables
psql -U postgres -d researchai -f setup.sql
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
OPENAI_API_KEY=sk-your-key-here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=researchai
DB_USER=postgres
DB_PASSWORD=yourpassword
```

### 5. Run the app

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## 📁 Project Structure

```
researchai/
├── app.py                  # Main entry point, routing, auth UI, sidebar
├── requirements.txt
├── setup.sql               # PostgreSQL schema
├── .env.example
├── pages/
│   ├── search.py           # AI Search (Semantic Scholar + TLDR)
│   ├── library.py          # Paper library + PDF upload
│   ├── chat.py             # Chat with papers (GPT-4o)
│   ├── review.py           # Literature review generator
│   ├── writer.py           # AI Writer + text tools
│   └── references.py       # Reference manager + exports
└── utils/
    ├── db.py               # All PostgreSQL operations
    ├── ai.py               # All OpenAI + Semantic Scholar operations
    └── auth.py             # bcrypt auth helpers
```

---

## 🗄️ Database Schema

```
users           → id, email, username, password (bcrypt), plan
workspaces      → id, user_id, name, description
papers          → id, workspace_id, user_id, title, authors, abstract, year, 
                  doi, source, full_text, tags, notes, citation_apa, citation_bibtex
chat_sessions   → id, workspace_id, user_id, paper_id, title
chat_messages   → id, session_id, role, content
documents       → id, workspace_id, user_id, title, content, doc_type
literature_reviews → id, workspace_id, user_id, query, report, paper_ids
search_history  → id, user_id, query, results_count
```

---

## 🔑 API Keys Required

- **OpenAI API Key** — https://platform.openai.com/api-keys  
  Used for: GPT-4o (chat + review + writer), GPT-4o-mini (TLDR, citations, metadata)

- **Semantic Scholar** — No key required for basic usage (public API)

---

## 💰 Estimated OpenAI Costs

| Feature | Model | Cost per use |
|---------|-------|-------------|
| TLDR | gpt-4o-mini | ~$0.001 |
| Chat message | gpt-4o | ~$0.01 |
| Literature Review | gpt-4o | ~$0.05 |
| Generate Section | gpt-4o | ~$0.02 |
| Citation | gpt-4o-mini | ~$0.001 |

---

## 🔒 Security Notes

- Passwords are hashed with **bcrypt** (salt rounds: 12)
- Never commit your `.env` file
- For production: add HTTPS, rate limiting, and input sanitization
