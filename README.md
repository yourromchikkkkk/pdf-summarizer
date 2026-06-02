# Docling PDF Summarizer Monorepo

A production-grade monorepo web application that allows users to upload large PDF files (up to 50MB, ~100 pages), parses them into structured markdown using IBM's Docling document parsing engine, and generates executive-level summaries via OpenRouter's API using an asynchronous Map-Reduce pipeline.

## Project Topology

```text
├── client/                 # React + Vite + Tailwind CSS SPA
│   ├── src/
│   │   ├── App.tsx         # Main UI (Dropzone, history polling, Reading panel)
│   │   ├── index.css       # Tailwind imports & custom Markdown CSS styles
│   │   └── main.tsx        # React entrypoint
│   ├── vite.config.ts      # Vite configuration with Tailwind CSS v4 support
│   └── package.json        # Frontend dependencies
│
├── server/                 # Python + FastAPI Backend
│   ├── app/
│   │   ├── main.py         # FastAPI routes, CORS, and startup DB initialization
│   │   ├── database.py     # SQLite engine and SQLAlchemy session setup
│   │   ├── models.py       # DB schema for 'documents' table
│   │   └── pipeline.py     # Docling PDF parser + OpenAI Map-Reduce execution logic
│   └── requirements.txt    # Python dependencies
│
├── scripts/
│   └── summarize.py        # Standalone CLI — runs the pipeline without the web server
└── README.md               # Setup and execution guide (this file)
```

---

## Technical Features

1. **Docling Engine Integration**: Converts complex PDFs (including tabular data and multi-column layouts) into cleanly formatted Markdown.
2. **Asynchronous Map-Reduce Pipeline**:
   - **Map Phase**: Splits Markdown text into chunks of ~10,000 characters and processes them concurrently (up to 3 parallel requests using an `asyncio.Semaphore`) to avoid rate limits.
   - **Reduce Phase**: Synthesizes chunk summaries into a highly structured, non-redundant Executive Summary. Model is configurable via `LLM_MODEL` env var (default: `openai/gpt-4o-mini` via OpenRouter).
3. **Database State Machine**: Tracks files through `processing`, `completed`, and `failed` phases with automatic DB transaction commits and rollback safety.
4. **Vite + Tailwind CSS v4 Client**: Sleek dark mode design with glassmorphism dropzone cards, interactive Toast states (`sonner`), polling updates every 4 seconds, copy-to-clipboard actions, and markdown-formatted report export.
5. **Docker Optimization**:
   - Uses CPU-only PyTorch, reducing image size by ~2GB.
   - Pre-downloads Docling AI model weights at Docker image build-time to ensure runs are fast and do not require external Hugging Face downloads at runtime.

---

## Local Development Setup

Run the backend and frontend in **two separate terminals**.

> **Prerequisites**: Python 3.11+, Node.js 20+

### 1. Environment

Copy the example env file and add your OpenAI key:

```bash
cp .env.example .env
# then edit .env and set OPENROUTER_API_KEY=your-openrouter-key
```

### 2. Backend — Terminal 1

```bash
cd server
uv venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
uv run uvicorn app.main:app --reload --port 8000
```

> **First run**: Docling will download its AI model weights (~1 GB) on the first PDF conversion. This is a one-time cost; subsequent runs are fast.

API available at `http://localhost:8000` — interactive docs at `http://localhost:8000/docs`.

### 3. Frontend — Terminal 2

```bash
cd client
npm install
npm run dev
```

App available at `http://localhost:5173`.

> If your backend runs on a different port, set `VITE_API_URL` before starting Vite:
> ```bash
> VITE_API_URL=http://localhost:8000 npm run dev
> ```

---

## CLI Script — `scripts/summarize.py`

A standalone script that runs the full Docling → chunk → Map-Reduce pipeline on a local PDF and prints the summary to stdout. Useful for quickly testing the pipeline without starting the web server.

### Setup

The script reuses the server's virtual environment:

```bash
cd server
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Run

```bash
# from the repo root, with the server venv active
python scripts/summarize.py path/to/document.pdf
```

### Output

```
[1/4] Parsing PDF: path/to/document.pdf
      Parsed 42,318 characters of markdown.

[2/4] Chunking...
      5 chunk(s).

[3/4] Map phase — summarizing chunks...

[4/4] Reduce phase — synthesizing final summary...

============================================================
## Executive Summary
...
============================================================
```

The same `OPENROUTER_API_KEY`, `LLM_MODEL`, and `OPENROUTER_BASE_URL` values from your root `.env` are used automatically.

---

## API Endpoints

### `POST /api/upload`
- **Description**: Accepts a PDF file and schedules it for background parsing and summarization.
- **Headers**:
  - `X-User-ID`: (Required) String UUID identifying the user session.
- **Payload**: `multipart/form-data` containing the PDF file.
- **Response Code**: `202 Accepted`
- **Response JSON**:
  ```json
  {
    "id": "uuid-document-string",
    "filename": "annual_report.pdf",
    "status": "processing",
    "created_at": "2026-06-02T18:00:00.000000"
  }
  ```

### `GET /api/history`
- **Description**: Returns the top 5 latest documents for a specific user, sorted by creation date.
- **Headers**:
  - `X-User-ID`: (Required or via query parameter `user_id`) The user session identifier.
- **Response JSON**:
  ```json
  [
    {
      "id": "uuid-document-string",
      "filename": "annual_report.pdf",
      "status": "completed",
      "summary": "## Executive Summary\n- Key revenue was...",
      "created_at": "2026-06-02T18:00:00.000000"
    }
  ]
  ```

### `GET /api/document/{id}`
- **Description**: Retrieves details for a specific document including its status and final summary.
- **Response JSON**:
  ```json
  {
    "id": "uuid-document-string",
    "user_id": "uuid-user-string",
    "filename": "annual_report.pdf",
    "status": "completed",
    "summary": "## Executive Summary\n- Key revenue was...",
    "created_at": "2026-06-02T18:00:00.000000"
  }
  ```
