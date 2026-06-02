import os
import logging
import asyncio
from typing import List
from openai import AsyncOpenAI
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice
from .database import SessionLocal
from .models import Document

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


async def summarize_chunk(chunk: str, chunk_index: int, total_chunks: int) -> str:
    """
    Map Phase: Call OpenAI to summarize an individual chunk.
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

    # Call OpenAI Async API
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
    return summary


async def reduce_summaries(summaries: List[str]) -> str:
    """
    Reduce Phase: Consolidate multiple chunk summaries into a final executive summary.
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
    return final_summary


async def run_pipeline(document_id: str, file_path: str):
    """
    Executes the parsing, chunking, and Map-Reduce summarization pipeline.
    Updates the database based on results.
    Cleans up the source file in a finally block.
    """
    logger.info(f"Pipeline started for document_id={document_id}, file_path={file_path}")
    
    db = SessionLocal()
    try:
        # 1. Parse PDF using Docling
        logger.info(f"Parsing PDF with Docling: {file_path}")
        pipeline_options = PdfPipelineOptions()
        # Force CPU to avoid MPS float64 errors on Apple Silicon.
        pipeline_options.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
        
        # Use run_in_executor to avoid blocking the asyncio event loop since conversion is CPU-bound
        loop = asyncio.get_running_loop()
        conversion_result = await loop.run_in_executor(None, converter.convert, file_path)
        markdown_text = conversion_result.document.export_to_markdown()
        
        logger.info(f"PDF parsed successfully. Length of markdown: {len(markdown_text)} characters.")
        
        if not markdown_text.strip():
            raise ValueError("Parsed markdown content is empty or could not be read.")

        # 2. Chunking
        chunks = chunk_markdown(markdown_text, max_chunk_size=10000)
        total_chunks = len(chunks)
        logger.info(f"Split markdown into {total_chunks} chunks.")

        # 3. Map Phase: Summarize each chunk
        # To avoid exceeding OpenAI rate limits, we limit concurrency to 3 simultaneous calls
        semaphore = asyncio.Semaphore(3)

        async def sem_summarize(chunk: str, idx: int) -> str:
            async with semaphore:
                return await summarize_chunk(chunk, idx, total_chunks)

        tasks = [sem_summarize(chunk, i) for i, chunk in enumerate(chunks)]
        chunk_summaries = await asyncio.gather(*tasks)

        # 4. Reduce Phase: Consolidate summaries
        final_summary = await reduce_summaries(chunk_summaries)

        # 5. State Machine Update: Success
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = "completed"
            doc.summary = final_summary
            db.commit()
            logger.info(f"Updated document_id={document_id} status to COMPLETED.")
        else:
            logger.error(f"Document {document_id} not found in database on success update.")

    except Exception as e:
        logger.exception(f"Error in pipeline for document_id={document_id}: {e}")
        db.rollback()
        # State Machine Update: Failure
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = "failed"
            doc.summary = f"Error during parsing or summarization: {str(e)}"
            db.commit()
            logger.info(f"Updated document_id={document_id} status to FAILED.")
        else:
            logger.error(f"Document {document_id} not found in database on failure update.")
            
    finally:
        db.close()
        # Clean up local PDF file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up temporary upload file: {file_path}")
            except Exception as cleanup_err:
                logger.error(f"Failed to remove file {file_path}: {cleanup_err}")
