import logging
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("migrations")

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def _load_migrations() -> list[tuple[str, str]]:
    """Return (migration_id, sql) pairs sorted by filename."""
    files = sorted(MIGRATIONS_DIR.glob("*. "))
    return [(f.stem, f.read_text()) for f in files]


def run_migrations(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS _migrations ("
            "  id VARCHAR(100) PRIMARY KEY,"
            "  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
        conn.commit()

        for migration_id, sql in _load_migrations():
            already_applied = conn.execute(
                text("SELECT 1 FROM _migrations WHERE id = :id"),
                {"id": migration_id},
            ).fetchone()

            if already_applied:
                continue

            try:
                conn.execute(text(sql))
                conn.execute(
                    text("INSERT INTO _migrations (id) VALUES (:id)"),
                    {"id": migration_id},
                )
                conn.commit()
                logger.info(f"Applied migration: {migration_id}")
            except Exception as exc:
                conn.rollback()
                logger.error(f"Migration {migration_id} failed: {exc}")
                raise


if __name__ == "__main__":
    from .database import engine as _engine
    logging.basicConfig(level=logging.INFO)
    run_migrations(_engine)
    print("Migrations complete.")
