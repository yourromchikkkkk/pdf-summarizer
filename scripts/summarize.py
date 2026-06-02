#!/usr/bin/env python3
"""
Standalone PDF summarization script.
Runs the full Docling → chunk → OpenRouter Map-Reduce pipeline
directly on a local file — no web server required.

Usage (from repo root, with server venv active):
    python scripts/summarize.py path/to/file.pdf
"""
import sys
import asyncio
import os
import tempfile
from pathlib import Path

# Load .env from repo root
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# Ensure server package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from app.pipeline import chunk_markdown, summarize_chunk, reduce_summaries
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice


async def run(pdf_path: str) -> None:
    print(f"\n[1/4] Parsing PDF: {pdf_path}")
    pipeline_options = PdfPipelineOptions()
    pipeline_options.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, converter.convert, pdf_path)
    markdown = result.document.export_to_markdown()
    print(f"    Parsed {len(markdown):,} characters of markdown.")

    print("\n[2/4] Chunking...")
    chunks = chunk_markdown(markdown, max_chunk_size=10_000)
    print(f"    {len(chunks)} chunk(s).")

    print("\n[3/4] Map phase — summarizing chunks...")
    semaphore = asyncio.Semaphore(3)

    async def sem_summarize(chunk: str, idx: int) -> str:
        async with semaphore:
            return await summarize_chunk(chunk, idx, len(chunks))

    summaries = await asyncio.gather(*[sem_summarize(c, i) for i, c in enumerate(chunks)])

    print("\n[4/4] Reduce phase — synthesizing final summary...")
    final = await reduce_summaries(summaries)

    print("\n" + "=" * 60)
    print(final)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/summarize.py <path-to-pdf>")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        sys.exit(1)

    asyncio.run(run(path))
