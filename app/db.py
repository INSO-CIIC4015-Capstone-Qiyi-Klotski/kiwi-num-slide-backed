import os
from contextlib import contextmanager
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

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300, future=True)

@contextmanager
def get_conn():
    """Conexión sin transacción (lecturas)."""
    with engine.connect() as conn:
        yield conn

@contextmanager
def get_tx():
    """Con transacción automática (escrituras)."""
    with engine.begin() as conn:
        yield conn
