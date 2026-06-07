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
# MinIO API → http://localhost:9000  |  MinIO console → http://localhost:9001
```

## Architecture

**Stack**: React + Vite + TanStack Query (client) / FastAPI + SQLite + MinIO + MongoDB (server) — orchestrated via Docker Compose.

### Request Flow
1. Browser generates a UUID user ID stored in `localStorage`. Every request sends it as `X-User-ID` header.
2. `POST /api/upload` streams the file into `tempfile.mkstemp()`, inserts a `documents` row with `status="processing"`, then enqueues `run_pipeline` as a FastAPI `BackgroundTask`.
3. `run_pipeline` (`pipeline.py`):
   - Docling converts the PDF to Markdown in a thread executor (CPU-bound, avoids blocking the event loop). Forced to `AcceleratorDevice.CPU` to avoid MPS float64 errors on Apple Silicon.
   - `chunk_markdown` splits on `\n\n` into ≤10 000-char blocks.
   - **Map phase**: `asyncio.Semaphore(3)` limits concurrent OpenRouter calls; each chunk gets a bullet-point summary via `openai/gpt-4o-mini`.
   - **Reduce phase**: all chunk summaries are joined and sent for a final structured executive summary.
   - The original PDF is uploaded to MinIO (`storage.py`) under `{user_id}/{document_id}/{filename}`; the resulting `storage_key` is saved to the DB. MinIO failure is non-fatal — pipeline still completes.
   - The full conversation record (markdown, per-chunk prompts/summaries, reduce prompt, final summary) is upserted into MongoDB (`conversation_store.py`, collection `pdf_conversations`). MongoDB failure is non-fatal.
   - DB status is set to `"completed"` or `"failed"`; the temp file is deleted in `finally`.
4. `GET /api/history` returns the last 5 documents for the user. The frontend polls via TanStack Query only while any document has `status === "processing"`.
5. `GET /api/documents/{doc_id}/download` returns a 1-hour presigned MinIO URL for the original PDF (404 if not yet stored).

### Data Model (`models.py`)
Single `documents` table: `id` (UUID PK), `user_id` (indexed), `filename`, `status` (`processing | completed | failed`), `summary` (Text, nullable), `storage_key` (VARCHAR 500, nullable — MinIO object path), `created_at`.

### Database
SQLite by default. Override with `DATABASE_URL` env var. In Docker, DB lives in the `db_data` named volume at `sqlite:////data/pdf_summarizer.db`.

### Object Storage (`storage.py`)
MinIO stores original PDFs for future analysis. The bucket is auto-created on first upload. Objects are keyed as `{user_id}/{document_id}/{filename}`. In Docker, data lives in the `minio_data` named volume. The `storage_key` column on `documents` is set after a successful upload; it's null for documents processed before MinIO was added (or if MinIO is unreachable). Migrations are managed by `app/migrations.py`. SQL files live in `server/migrations/` and are discovered by filename in sorted order (e.g. `0001_add_storage_key.sql`). Applied migrations are tracked in a `_migrations` table so each runs exactly once. `main.py` calls `run_migrations(engine)` at startup. To run migrations standalone: `python -m app.migrations` from the `server/` directory. To add a new migration, drop a new numbered `.sql` file in `server/migrations/`.

### Conversation Store (`conversation_store.py`)
MongoDB stores the full pipeline conversation for data collection and future evaluation. After each successful pipeline run, an upsert is made to the `pdf_conversations` collection keyed by `document_id`. Each record contains:
- `_id`: document UUID
- `user_id`, `filename`, `created_at`, `model`
- `markdown_length`, `num_chunks`
- `chunks`: array of `{index, text, map_prompt, summary}` — the raw chunk, the exact prompt sent, and the LLM response
- `reduce_prompt`: the prompt used for the final synthesis
- `final_summary`: the executive summary text

MongoDB connection is configured via `MONGO_URI` / `MONGO_DB` env vars. The client is lazy and failures are non-fatal (logged as warnings). In Docker, data lives in the `mongo_data` named volume.

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
| `HF_TOKEN` | server | — | Optional. Hugging Face token for higher rate limits and faster model downloads |
| `MINIO_ENDPOINT` | server | `localhost:9000` | MinIO host:port (use `minio:9000` in Docker) |
| `MINIO_ACCESS_KEY` | server | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | server | `minioadmin` | MinIO secret key |
| `MINIO_BUCKET` | server | `pdf-summarizer` | Bucket name for PDF storage |
| `MINIO_SECURE` | server | `false` | Set `true` to use TLS |
| `MINIO_ROOT_USER` | minio | `minioadmin` | Root user for the MinIO container |
| `MINIO_ROOT_PASSWORD` | minio | `minioadmin` | Root password for the MinIO container |
| `MONGO_URI` | server | `mongodb://localhost:27017` | MongoDB connection URI (use `mongodb://mongo:27017` in Docker) |
| `MONGO_DB` | server | `pdf_summarizer` | MongoDB database name |

Vite reads `.env` from the **monorepo root** (configured via `envDir: '..'` in `vite.config.ts`).
