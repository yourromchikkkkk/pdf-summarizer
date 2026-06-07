import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from openai import AsyncOpenAI
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice
from .database import SessionLocal
from .models import Document
from .storage import upload_pdf
from .conversation_store import save_conversation

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pipeline")

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4o-mini")

openai_client = None

def get_openai_client() -> AsyncOpenAI:
    global openai_client
    if openai_client is None:
        openai_client = AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        )
    return openai_client


_progress_queues: dict = {}

def register_progress_queue(document_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _progress_queues[document_id] = q
    return q

def unregister_progress_queue(document_id: str) -> None:
    _progress_queues.pop(document_id, None)

async def emit_progress(document_id: str, data: dict) -> None:
    q = _progress_queues.get(document_id)
    if q:
        await q.put(data)


def chunk_markdown(text: str, max_chunk_size: int = 10000) -> List[str]:
    """
    Split markdown text into chunks of roughly max_chunk_size characters.
    Splits by double newlines (paragraphs) to avoid breaking text blocks.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph_len = len(paragraph)
        
        # If a single paragraph is larger than the max_chunk_size, we might need to split it
        if paragraph_len > max_chunk_size:
            # If we have content in current_chunk, finalize it first
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            
            # Split the oversized paragraph into smaller blocks (e.g. by lines)
            lines = paragraph.split("\n")
            current_line_chunk = []
            current_line_len = 0
            for line in lines:
                if current_line_len + len(line) + 1 > max_chunk_size:
                    if current_line_chunk:
                        chunks.append("\n".join(current_line_chunk))
                    current_line_chunk = [line]
                    current_line_len = len(line)
                else:
                    current_line_chunk.append(line)
                    current_line_len += len(line) + 1
            if current_line_chunk:
                chunks.append("\n".join(current_line_chunk))
            continue

        # Normal grouping
        if current_length + paragraph_len + 2 > max_chunk_size:
            # Finalize current chunk
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [paragraph]
            current_length = paragraph_len
        else:
            current_chunk.append(paragraph)
            current_length += paragraph_len + 2

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    # Strip and filter out empty chunks
    return [c.strip() for c in chunks if c.strip()]


async def summarize_chunk(chunk: str, chunk_index: int, total_chunks: int) -> tuple[str, str]:
    """
    Map Phase: Call OpenAI to summarize an individual chunk.
    Returns (summary, prompt) for data collection.
    """
    logger.info(f"Summarizing chunk {chunk_index + 1}/{total_chunks} (length={len(chunk)})...")

    prompt = (
        "<task>\n"
        "Analyze the document section and produce a structured, bulleted summary covering:\n"
        "- Key arguments and conclusions\n"
        "- Quantitative data, metrics, and statistics (preserve exact numbers)\n"
        "- Important findings, definitions, or structured information\n"
        "Be concise but complete. Do not add interpretation beyond what is stated.\n"
        "</task>\n\n"
        "<document_section>\n"
        f"{chunk}\n"
        "</document_section>"
    )

    client = get_openai_client()
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are an expert document analyst."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    summary = response.choices[0].message.content
    logger.info(f"Finished chunk {chunk_index + 1}/{total_chunks}.")
    return summary, prompt


async def reduce_summaries(summaries: List[str]) -> tuple[str, str]:
    """
    Reduce Phase: Consolidate multiple chunk summaries into a final executive summary.
    Returns (final_summary, prompt) for data collection.
    """
    logger.info(f"Starting Reduce phase for {len(summaries)} summaries...")
    combined_summaries = "\n\n".join(
        f"<section index=\"{i + 1}\">\n{s}\n</section>" for i, s in enumerate(summaries)
    )

    prompt = (
        "<task>\n"
        "Synthesize the section summaries into a single, executive-level final summary.\n"
        "<requirements>\n"
        "- Use Markdown headers: ## Executive Summary, ## Key Findings, ## Conclusions\n"
        "- Add a ## Data & Metrics table if quantitative data is present\n"
        "- Each insight must appear exactly once — eliminate all redundancy\n"
        "- Preserve specific numbers, statistics, and technical terminology\n"
        "- Keep the tone professional and objective\n"
        "</requirements>\n"
        "</task>\n\n"
        "<section_summaries>\n"
        f"{combined_summaries}\n"
        "</section_summaries>"
    )

    client = get_openai_client()
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a professional executive editor and analyst."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    final_summary = response.choices[0].message.content
    logger.info("Successfully completed Reduce phase.")
    return final_summary, prompt


async def convert_pdf_to_markdown(document_id: str, file_path: str) -> str:
    """
    Parses the local PDF file using Docling converter and exports it to Markdown.
    Emits progress stage 'parsing'.
    """
    await emit_progress(document_id, {"stage": "parsing"})
    logger.info(f"Parsing PDF with Docling: {file_path}")
    
    pipeline_options = PdfPipelineOptions()
    # Force CPU to avoid MPS float64 errors on Apple Silicon.
    pipeline_options.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)
    
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    
    # Run conversion inside a pool executor since it's CPU-bound
    loop = asyncio.get_running_loop()
    conversion_result = await loop.run_in_executor(None, converter.convert, file_path)
    markdown_text = conversion_result.document.export_to_markdown()
    
    logger.info(f"PDF parsed successfully. Length of markdown: {len(markdown_text)} characters.")
    
    if not markdown_text.strip():
        raise ValueError("Parsed markdown content is empty or could not be read.")
        
    return markdown_text


async def process_chunks_map_phase(
    document_id: str, chunks: List[str]
) -> tuple[List[str], List[dict]]:
    """
    Executes the concurrent Map Phase to summarize each chunk.
    Returns (summaries, chunk_records) where chunk_records contain text/prompt/summary
    for data collection.
    """
    total_chunks = len(chunks)
    semaphore = asyncio.Semaphore(3)
    completed_count = 0
    counter_lock = asyncio.Lock()

    async def sem_summarize(chunk: str, idx: int) -> tuple[str, str, int]:
        nonlocal completed_count
        async with semaphore:
            summary, prompt = await summarize_chunk(chunk, idx, total_chunks)

        async with counter_lock:
            completed_count += 1
            current_completed = completed_count

        await emit_progress(
            document_id,
            {"stage": "summarizing", "chunk": current_completed, "total_chunks": total_chunks},
        )
        return summary, prompt, idx

    results = await asyncio.gather(*[sem_summarize(chunk, i) for i, chunk in enumerate(chunks)])

    summaries = [r[0] for r in results]
    chunk_records = [
        {"index": r[2], "text": chunks[r[2]]
         
         , "map_prompt": r[1], "summary": r[0]}
        for r in results
    ]
    return summaries, chunk_records


async def update_document_success(db, document_id: str, final_summary: str, storage_key: Optional[str] = None):
    """
    Marks the document as successfully summarized in the database.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc:
        doc.status = "completed"
        doc.summary = final_summary
        if storage_key:
            doc.storage_key = storage_key
        db.commit()
        await emit_progress(document_id, {"stage": "completed"})
        logger.info(f"Updated document_id={document_id} status to COMPLETED.")
    else:
        logger.error(f"Document {document_id} not found in database on success update.")


async def update_document_failure(db, document_id: str, error: Exception):
    """
    Rolls back database state and marks the document as failed.
    """
    db.rollback()
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc:
        doc.status = "failed"
        doc.summary = f"Error during parsing or summarization: {str(error)}"
        db.commit()
        await emit_progress(document_id, {"stage": "failed", "error": str(error)})
        logger.info(f"Updated document_id={document_id} status to FAILED.")
    else:
        logger.error(f"Document {document_id} not found in database on failure update.")


def delete_temporary_file(file_path: str):
    """
    Deletes the uploaded PDF file to avoid storage leakage.
    """
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Cleaned up temporary upload file: {file_path}")
        except Exception as cleanup_err:
            logger.error(f"Failed to remove file {file_path}: {cleanup_err}")


async def run_pipeline(document_id: str, file_path: str, user_id: str, filename: str):
    """
    Orchestrates the entire PDF parsing, chunking, and Map-Reduce summarization pipeline.
    """
    logger.info(f"Pipeline started for document_id={document_id}, file_path={file_path}")

    db = SessionLocal()
    try:
        # 1. Parse PDF using Docling
        markdown_text = await convert_pdf_to_markdown(document_id, file_path)

        # 2. Chunking
        chunks = chunk_markdown(markdown_text, max_chunk_size=10000)
        total_chunks = len(chunks)
        logger.info(f"Split markdown into {total_chunks} chunks.")

        chunk_records: List[dict] = []
        if total_chunks == 1:
            logger.info("Only one chunk detected. Skipping chunking summarization and moving directly to final synthesis.")
            await emit_progress(document_id, {"stage": "reducing"})
            final_summary, reduce_prompt = await reduce_summaries(chunks)
        else:
            # 3. Map Phase: Summarize each chunk concurrently
            await emit_progress(document_id, {"stage": "chunking", "total_chunks": total_chunks})
            chunk_summaries, chunk_records = await process_chunks_map_phase(document_id, chunks)

            # 4. Reduce Phase: Consolidate summaries
            await emit_progress(document_id, {"stage": "reducing"})
            final_summary, reduce_prompt = await reduce_summaries(chunk_summaries)

        # 5. Upload original PDF to MinIO for future analysis
        storage_key: Optional[str] = None
        loop = asyncio.get_running_loop()
        try:
            storage_key = await loop.run_in_executor(
                None, upload_pdf, user_id, document_id, filename, file_path
            )
        except Exception as upload_err:
            logger.warning(f"MinIO upload failed for document {document_id}: {upload_err}")

        # 6. Database Status Update: Success
        await update_document_success(db, document_id, final_summary, storage_key)

        # 7. Save full conversation to MongoDB for data collection / evaluation
        conversation = {
            "_id": document_id,
            "user_id": user_id,
            "filename": filename,
            "created_at": datetime.now(timezone.utc),
            "model": MODEL,
            "markdown_length": len(markdown_text),
            "num_chunks": total_chunks,
            "chunks": chunk_records,
            "reduce_prompt": reduce_prompt,
            "final_summary": final_summary,
        }
        await save_conversation(conversation)

    except Exception as e:
        logger.exception(f"Error in pipeline for document_id={document_id}: {e}")
        await update_document_failure(db, document_id, e)

    finally:
        db.close()
        delete_temporary_file(file_path)
