import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Locate the database file. If running in container or locally,
# we place it in the same directory as the server, or in server/db path.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pdf_summarizer.db")

# SQLite needs connect_args={"check_same_thread": False} for multi-threaded/async environments
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL, connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get db session in FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
