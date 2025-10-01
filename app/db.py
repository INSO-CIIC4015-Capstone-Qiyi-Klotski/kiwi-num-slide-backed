import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(".env.prod.local")

# Construye la URL desde variables de entorno (más seguro/flexible)
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD", ""))
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "")

DATABASE_URL = os.getenv("DATABASE_URL") or f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

def ping_db() -> bool:
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1")).scalar() == 1


def insert_health(note: str):
    with engine.begin() as conn:  # begin = abre transacción automática
        conn.execute(text("INSERT INTO app_health (note) VALUES (:note)"), {"note": note})


def read_health():
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, note, created_at FROM app_health ORDER BY created_at DESC")
        ).fetchall()
    return [
        {"id": str(r[0]), "note": r[1], "created_at": r[2].isoformat()}
        for r in rows
    ]
