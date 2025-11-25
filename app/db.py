
from contextlib import contextmanager
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from app.core.config import settings

# Construye la URL desde variables de entorno (más seguro/flexible)
DB_USER = settings.db_user
DB_PASSWORD = quote_plus(settings.db_password)
DB_HOST = settings.db_host
DB_PORT = settings.db_port
DB_NAME = settings.db_name

DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

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
