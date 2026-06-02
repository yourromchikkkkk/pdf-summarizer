# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (server/)
```bash
cd server
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend (client/)
```bash
cd client
npm install
npm run dev          # Vite dev server on :5173
npm run build        # tsc + vite build → dist/
npm run lint         # ESLint
```

### Docker (full stack)
```bash
# Requires root .env with OPENROUTER_API_KEY=...
docker-compose up --build
# client → http://localhost:5173  |  API docs → http://localhost:8000/docs
```

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

### Frontend structure
```
client/src/
  api.ts              # fetchHistory, uploadDocument
  types.ts            # DocumentRecord interface
  App.tsx             # orchestration only — state, React Query, event wiring
  components/
    Header.tsx
    ProcessingBanner.tsx
    UploadCard.tsx     # owns drag state and file validation
    HistoryPanel.tsx
    SummaryPanel.tsx   # owns copy/download state
```

`App.tsx` wires `useQuery` (polls only when processing) and `useMutation` (upload → `invalidateQueries`). Components own only their local UI state.

### Key Env Vars
| Variable | Where | Default | Purpose |
|---|---|---|---|
| `OPENROUTER_API_KEY` | server | — | Required |
| `OPENROUTER_BASE_URL` | server | `https://openrouter.ai/api/v1` | API base URL |
| `LLM_MODEL` | server | `openai/gpt-4o-mini` | Model used for Map and Reduce phases |
| `DATABASE_URL` | server | `sqlite:///./pdf_summarizer.db` | SQLite path |
| `VITE_API_URL` | client build | `http://localhost:8000` | Backend origin |

Vite reads `.env` from the **monorepo root** (configured via `envDir: '..'` in `vite.config.ts`).
