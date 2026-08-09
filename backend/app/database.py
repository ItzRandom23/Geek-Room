from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def run_migrations() -> None:
    if not settings.auto_migrate:
        return
    from alembic import command
    from alembic.config import Config
    config = Config(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
