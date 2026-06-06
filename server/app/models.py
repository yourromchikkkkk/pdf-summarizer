import datetime
import uuid
from sqlalchemy import Column, String, Text, DateTime
from .database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    status = Column(String(50), default="processing", nullable=False) # 'processing', 'completed', 'failed'
    summary = Column(Text, nullable=True)
    storage_key = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
