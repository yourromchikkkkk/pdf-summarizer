import logging
from .mongo import get_mongo_db

logger = logging.getLogger("conversation_store")

COLLECTION = "pdf_conversations"


async def save_conversation(record: dict) -> None:
    """
    Upserts a pipeline conversation record into MongoDB.
    Non-fatal: logs a warning if MongoDB is unavailable.
    """
    try:
        db = get_mongo_db()
        await db[COLLECTION].replace_one({"_id": record["_id"]}, record, upsert=True)
        logger.info(f"Conversation saved to MongoDB: {record['_id']}")
    except Exception as e:
        logger.warning(f"Failed to save conversation to MongoDB: {e}")
