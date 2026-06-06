import os
import logging
from datetime import timedelta
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger("storage")

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "pdf-summarizer")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"

_client: Minio | None = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
    return _client


def ensure_bucket() -> None:
    client = get_client()
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)
        logger.info(f"Created MinIO bucket: {MINIO_BUCKET}")


def upload_pdf(user_id: str, document_id: str, filename: str, file_path: str) -> str:
    ensure_bucket()
    client = get_client()
    storage_key = f"{user_id}/{document_id}/{filename}"
    client.fput_object(MINIO_BUCKET, storage_key, file_path, content_type="application/pdf")
    logger.info(f"Uploaded to MinIO: {storage_key}")
    return storage_key


def get_presigned_url(storage_key: str, expires_seconds: int = 3600) -> str:
    client = get_client()
    return client.presigned_get_object(
        MINIO_BUCKET, storage_key, expires=timedelta(seconds=expires_seconds)
    )
