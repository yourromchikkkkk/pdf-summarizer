import os
import uuid
import json
import asyncio
import logging
import tempfile
from typing import Optional
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())  # walks up from cwd to find root .env

from fastapi import FastAPI, UploadFile, File, Header, Query, Depends, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .database import get_db, engine, Base
from .models import Document
from .pipeline import run_pipeline, register_progress_queue, unregister_progress_queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="PDF Summarizer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: Session = Depends(get_db)
):
    if not x_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-User-ID header is required")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF documents are allowed")

    # Write upload to a temp file; pipeline deletes it in its finally block
    fd, file_path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                buffer.write(chunk)
    except Exception as e:
        os.unlink(file_path)
        logger.error(f"Error saving uploaded file: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not save file: {str(e)}")

    document_id = str(uuid.uuid4())
    doc = Document(id=document_id, user_id=x_user_id, filename=file.filename, status="processing", summary=None)

    try:
        db.add(doc)
        db.commit()
        db.refresh(doc)
    except Exception as e:
        logger.error(f"Database insertion error: {e}")
        os.unlink(file_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while saving document metadata")

    background_tasks.add_task(run_pipeline, document_id, file_path)

    return {"id": doc.id, "filename": doc.filename, "status": doc.status, "created_at": doc.created_at}


@app.get("/api/history")
def get_history(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    uid = x_user_id or user_id
    if not uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User ID must be provided in X-User-ID header or user_id query parameter")

    try:
        documents = (
            db.query(Document)
            .filter(Document.user_id == uid)
            .order_by(Document.created_at.desc())
            .limit(5)
            .all()
        )
        return [
            {"id": doc.id, "filename": doc.filename, "status": doc.status, "summary": doc.summary, "created_at": doc.created_at}
            for doc in documents
        ]
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve history")


@app.get("/api/document/{doc_id}")
def get_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return {"id": doc.id, "user_id": doc.user_id, "filename": doc.filename, "status": doc.status, "summary": doc.summary, "created_at": doc.created_at}


@app.get("/api/documents/{doc_id}/events")
async def document_events(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    sse_headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

    if doc.status in ("completed", "failed"):
        async def terminal_stream():
            yield f"data: {json.dumps({'stage': doc.status})}\n\n"
        return StreamingResponse(terminal_stream(), media_type="text/event-stream", headers=sse_headers)

    async def event_stream():
        q = register_progress_queue(doc_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("stage") in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            unregister_progress_queue(doc_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=sse_headers)


@app.get("/health")
def health_check():
    return {"status": "ok"}
