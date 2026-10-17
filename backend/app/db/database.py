from sqlmodel import create_engine, SQLModel, Session
from ..core.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    _ensure_workspace_schema()


def _ensure_workspace_schema():
    """Apply lightweight SQLite migrations for existing local databases."""
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(workspace)").fetchall()
        if not rows:
            return

        columns = {row[1] for row in rows}
        if "completed_stages" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE workspace "
                "ADD COLUMN completed_stages VARCHAR NOT NULL DEFAULT '[]'"
            )


def get_session():
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
