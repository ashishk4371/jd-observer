# JD Glance

**AI-powered resume ↔ job description matcher**, delivered as a Chrome extension backed by a local FastAPI service. Upload one or more resumes, paste (or select) a job description, and get a holistic fit score — not just keyword overlap, but an LLM-driven read of whether your actual experience satisfies each requirement, with specific suggested edits for the gaps.

## Overview

Most "resume matcher" tools stop at keyword counting. JD Glance does that too (fast, free, works offline), but layers a deeper pipeline on top:

1. **Understand the resume once.** On upload, an LLM extracts a structured profile — skills, roles, seniority, key achievements — cached by a hash of the resume's own text, so re-analyzing against a new job description never re-reads or re-summarizes the resume from scratch.
2. **Understand the job description.** The JD is broken into distinct requirements (skills, scope, seniority, leadership expectations).
3. **Match holistically.** Each requirement is classified **Met / Partial / Missing** against the resume profile, with evidence for what's covered and a concrete, quantified bullet suggestion for what isn't — not just "you're missing Kubernetes."
4. **Score two ways, blended.** A fast keyword + local-embedding semantic score (free, instant, works with zero configuration) is blended with the LLM's holistic alignment score, so the LLM can't rate a resume highly if it shares almost no real substance with the JD, and the tool still works meaningfully with no API key at all.
5. **Compare resume versions.** Keep more than one resume on file (backend-focused, fullstack, leadership-focused…) and rank them against a job description using the same full pipeline, not a cheap approximation.

Everything — resumes, extracted profiles, job descriptions, and every analysis you run — persists locally in a single SQLite database, so your history survives restarts and repeated comparisons don't repeat work.

## Features

- 📄 **Multi-resume library** — upload multiple resume versions (PDF/DOCX/TXT), keep them all, select any combination to analyze or compare
- 🧠 **Holistic AI matching** — requirement-by-requirement Met/Partial/Missing breakdown with evidence and tailored bullet suggestions, not just a keyword score
- 🏆 **Resume ranking** — compare 2+ resumes against one job description and see which one actually fits best
- 🔌 **Five LLM providers** — Claude, Gemini, OpenAI, Groq, or a fully local Ollama model, switchable per request, each with its own key (or model name) stored separately
- 🧭 **Local semantic search** — embeddings generated locally (no API key, nothing leaves your machine) via `fastembed`, stored and compared with `sqlite-vec`
- 💾 **Durable history** — every resume, profile, job description, and analysis persists in SQLite (`~/.jd_glance_cache/jd_glance.db`), not in memory
- 🌐 **Works offline** — no backend running, no API key configured? The extension falls back to a client-side keyword-matching engine so it's never fully broken
- 🖱️ **Grab-and-go** — select job description text on any webpage (LinkedIn, Indeed, Greenhouse, Lever…) and analyze it directly from the browser

## Architecture

```
Chrome Extension (Manifest V3)
  ├─ Side panel UI — resume library, JD input, results, comparison ranking
  ├─ Content script — grab selected JD text from any webpage
  └─ Client-side PDF/DOCX parsing (pdf.js, mammoth.js) — works even offline
        │
        │  REST (localhost:8000)
        ▼
FastAPI backend (src/jd_glance/)
  ├─ extractor.py    — file → text, text → skills/years (regex)
  ├─ similarity.py   — fast keyword/embedding score
  ├─ embeddings.py   — local embedding generation (fastembed)
  ├─ llm.py          — provider registry (Claude/Gemini/OpenAI/Groq) + prompts
  ├─ db.py           — SQLite + sqlite-vec, one file for relational + vector data
  └─ main.py         — endpoints, orchestration
        │
        ▼
~/.jd_glance_cache/jd_glance.db
  (resumes, resume_profiles, job_descriptions, analyses + vector tables)
```

If the FastAPI backend isn't reachable, the extension degrades to a pure client-side keyword-matching engine instead of failing outright.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI + Uvicorn |
| LLM orchestration | LangChain (`langchain-anthropic`, `-google-genai`, `-groq`, `-openai`) |
| Local embeddings | `fastembed` (ONNX runtime, `BAAI/bge-small-en-v1.5`, 384-dim, no API key) |
| Storage | SQLite + `sqlite-vec` (relational tables and vector search in one file) |
| Keyword/semantic scoring | scikit-learn (TF-IDF), NumPy |
| Document parsing | PyMuPDF (PDF), python-docx (DOCX) |
| Extension | Manifest V3, vanilla JS, pdf.js, Mammoth.js |
| Package management | [uv](https://github.com/astral-sh/uv) |

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`
- Google Chrome (or a Chromium-based browser supporting Manifest V3 side panels)
- An API key for at least one LLM provider — **optional**. Without one, the app falls back to a heuristic/keyword-based engine.

## Getting Started

### 1. Backend

```bash
git clone <this-repo>
cd jd-glance

# Install dependencies
uv sync
# or: pip install -r requirements.txt

# Configure API keys (optional but recommended)
cp .env.example .env
# edit .env and add at least one provider key — see Configuration below

# Start the server
python run_server.py
# or: uv run jd-glance
```

The API is now running at `http://127.0.0.1:8000`. Visit `http://127.0.0.1:8000/docs` for interactive API docs (FastAPI's auto-generated Swagger UI).

### 2. Chrome Extension

1. Open `chrome://extensions` in Chrome
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked** and select the `extension/` folder
4. Click the extension icon in your toolbar to open the side panel

The extension talks to `http://localhost:8000` by default — change this in the extension's Settings panel (⚙️) if your backend runs elsewhere.

## Configuration

Copy `.env.example` to `.env` and add keys for whichever provider(s) you want to use server-side. Any provider without a key simply won't be selectable via `provider="auto"`, and the app falls back to the heuristic engine if none are configured:

```bash
ANTHROPIC_API_KEY=your_key_here    # Claude Opus 5
GEMINI_API_KEY=your_key_here       # or GOOGLE_API_KEY — Gemini 2.5 Flash
OPENAI_API_KEY=your_key_here       # GPT-4o mini
GROQ_API_KEY=your_key_here         # Llama 3.3 70B
```

Alternatively (or in addition), each provider's key can be entered directly in the extension's Settings panel — stored per-provider in the browser, sent only with your own requests, never persisted server-side beyond the request that used it.

### Fully local mode (Ollama) — zero cost, nothing leaves your machine

No API key, no cloud provider, no hosting bill. Install [Ollama](https://ollama.com), pull a model, and point the extension at it:

```bash
ollama pull llama3.1     # or qwen2.5:7b, mistral, etc. — any instruction-tuned model
ollama serve              # runs on http://localhost:11434 by default
```

Then in the extension's Settings panel, select **Ollama (Local, Free)** as the provider and type the model name (`llama3.1`) in place of an API key. The FastAPI backend, the SQLite database, and the LLM itself all run on your own machine — the resume and job description text never leave it. To make Ollama the server-side default/fallback instead of a per-request choice, set `OLLAMA_MODEL` (and `OLLAMA_BASE_URL` if not on the default port) in `.env`.

## Usage

1. **Add resumes** — drag and drop (or browse for) a PDF/DOCX/TXT resume in the side panel. Each upload adds to your library rather than replacing the last one.
2. **Add a job description** — paste it directly, or highlight text on any webpage and click **Grab Selection** (or use the right-click context menu).
3. **Analyze** — with one resume selected, click Analyze for a full breakdown: match score, skill gaps, requirement-by-requirement AI review, and tailored bullet suggestions.
4. **Compare** — select two or more resumes and the same button becomes **Compare N Resumes**: each one is run through the full holistic pipeline against the same job description and ranked, with one click to drill into any result's full detail.

## API Reference

All endpoints are served from the FastAPI backend at `http://127.0.0.1:8000`. Full interactive schema at `/docs`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/upload_resume` | Upload a resume file; extracts text and builds (or reuses a cached) structured profile |
| `GET` | `/resumes` | List every resume in the library with its profile summary |
| `DELETE` | `/resumes/{resume_id}` | Remove a resume and its profile/embedding (analysis history is preserved) |
| `POST` | `/analyze` | Analyze one resume (`resume_id` or raw `resume_text`) against a job description |
| `POST` | `/analyze_direct` | Upload + analyze in a single call |
| `POST` | `/compare` | Rank multiple resumes (`resume_ids[]`) against one job description |

`provider` on any request accepts `"auto"`, `"claude"`, `"gemini"`, `"openai"`, or `"groq"`. `api_key` is optional per-request and overrides the server's `.env` value for that provider only.

## Project Structure

```
jd-glance/
├── src/jd_glance/
│   ├── main.py         # FastAPI app, endpoints, request orchestration
│   ├── db.py           # SQLite + sqlite-vec schema and queries
│   ├── llm.py          # Provider registry, prompts, requirement matching
│   ├── embeddings.py   # Local embedding generation (fastembed)
│   ├── similarity.py   # Keyword/TF-IDF/embedding scoring
│   ├── extractor.py    # PDF/DOCX text extraction, skill/experience regex
│   └── models.py       # Pydantic request/response schemas
├── extension/
│   ├── manifest.json
│   ├── background.js   # Service worker, context menu
│   ├── content.js      # Grabs selected text from the active page
│   ├── sidepanel/      # Side panel UI (HTML/CSS/JS)
│   └── lib/             # Bundled pdf.js, Mammoth.js
├── run_server.py
├── pyproject.toml
└── .env.example
```

## Known Limitations

This is a personal/local-first project, not a hardened multi-user service:

- No authentication — anything with access to the backend can read/analyze any stored resume
- No automated test suite yet
- SQLite is a single-writer database — fine at personal scale, not built for concurrent multi-user load
- Data (resumes, profiles, analysis history) is stored unencrypted on local disk with no retention/expiry policy

None of this matters for local, single-user use; it matters if you ever expose the backend beyond `localhost`.

## License

No license has been specified yet — all rights reserved by default until one is added.
