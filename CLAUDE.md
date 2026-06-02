# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

**Stack**: React + Vite + TanStack Query (client) / FastAPI + SQLite (server) — orchestrated via Docker Compose.

### Request Flow
1. Browser generates a UUID user ID stored in `localStorage`. Every request sends it as `X-User-ID` header.
2. `POST /api/upload` streams the file into `tempfile.mkstemp()`, inserts a `documents` row with `status="processing"`, then enqueues `run_pipeline` as a FastAPI `BackgroundTask`.
3. `run_pipeline` (`pipeline.py`):
   - Docling converts the PDF to Markdown in a thread executor (CPU-bound, avoids blocking the event loop). Forced to `AcceleratorDevice.CPU` to avoid MPS float64 errors on Apple Silicon.
   - `chunk_markdown` splits on `\n\n` into ≤10 000-char blocks.
   - **Map phase**: `asyncio.Semaphore(3)` limits concurrent OpenRouter calls; each chunk gets a bullet-point summary via `openai/gpt-4o-mini`.
   - **Reduce phase**: all chunk summaries are joined and sent for a final structured executive summary.
   - DB status is set to `"completed"` or `"failed"`; the temp file is deleted in `finally`.
4. `GET /api/history` returns the last 5 documents for the user. The frontend polls via TanStack Query only while any document has `status === "processing"`.

### Data Model (`models.py`)
Single `documents` table: `id` (UUID PK), `user_id` (indexed), `filename`, `status` (`processing | completed | failed`), `summary` (Text, nullable), `created_at`.

### Database
SQLite by default. Override with `DATABASE_URL` env var. In Docker, DB lives in the `db_data` named volume at `sqlite:////data/pdf_summarizer.db`.

### Key Env Vars
| Variable | Where | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | server | Required — passed to OpenAI-compatible client |
| `DATABASE_URL` | server | SQLite path (default: `sqlite:///./pdf_summarizer.db`) |
| `VITE_API_URL` | client build | Backend origin (default: `http://localhost:8000`) |
