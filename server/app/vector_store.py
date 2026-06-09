import os
import logging
from typing import Optional
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

logger = logging.getLogger("vector_store")

CHROMA_PATH = os.environ.get("CHROMA_PATH", "./chroma_data")

_client: Optional[chromadb.PersistentClient] = None


def get_chroma_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client


def _get_collection() -> chromadb.Collection:
    return get_chroma_client().get_or_create_collection(
        name="document_chunks",
        embedding_function=DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


def index_document(document_id: str, chunks: list[str]) -> None:
    collection = _get_collection()
    try:
        existing = collection.get(where={"document_id": document_id})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    ids = [f"{document_id}_{i}" for i in range(len(chunks))]
    metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]
    collection.add(documents=chunks, ids=ids, metadatas=metadatas)
    logger.info(f"Indexed {len(chunks)} chunks for document {document_id}")


def query_chunks(document_id: str, query: str, n_results: int = 5) -> list[str]:
    collection = _get_collection()
    # Clamp n_results to the number of indexed chunks for this document
    count = collection.count()
    safe_n = min(n_results, max(count, 1))
    results = collection.query(
        query_texts=[query],
        n_results=safe_n,
        where={"document_id": document_id},
    )
    return results["documents"][0] if results["documents"] else []
