import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import text


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")


class Base(DeclarativeBase):
    pass


connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_sqlite_schema() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    # SQLite-миграции: в текущей версии проекта схема приведена к MySQL dump.
    # Для чистого SQLite файла достаточно Base.metadata.create_all().
    return


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

