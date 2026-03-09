from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "bettingbyte.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"


def resolve_database_url(raw_url: str | None = None) -> str:
    if not raw_url:
        return DEFAULT_DATABASE_URL

    if raw_url.startswith("sqlite:///./"):
        relative_path = raw_url.removeprefix("sqlite:///./")
        return f"sqlite:///{(PROJECT_ROOT / relative_path).as_posix()}"

    return raw_url


DATABASE_URL = resolve_database_url(os.getenv("DATABASE_URL"))

engine_kwargs: dict[str, object] = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, future=True, **engine_kwargs)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    pass


@contextmanager
def session_scope() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    with session_scope() as session:
        yield session


def init_db() -> None:
    # Load the ORM metadata for callers that need the registry available.
    # Schema creation and evolution should go through Alembic migrations.
    from database import models  # noqa: F401
