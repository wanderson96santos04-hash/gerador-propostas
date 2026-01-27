# backend/app/db/session.py
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# 1) Em produção (Render), vamos usar DATABASE_URL do ambiente (Postgres)
# 2) Em dev/local, cai para SQLite (comportamento atual)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Render geralmente fornece Postgres como URL com "postgres://"
    # SQLAlchemy recomenda "postgresql+psycopg2://"
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    # --- SQLite local (como está hoje) ---
    _db_path = settings.sqlite_path
    _db_dir = os.path.dirname(_db_path.replace("\\", "/")) or "."
    os.makedirs(_db_dir, exist_ok=True)

    DATABASE_URL = f"sqlite:///{_db_path}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # necessário p/ SQLite + FastAPI
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
