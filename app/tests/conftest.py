import os, sys
from dotenv import load_dotenv   # <-- añade esto
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# .../kiwi-num-slide-backed/app/tests -> subir dos niveles hasta la raíz del repo
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Cargar variables de entorno desde tu .env.local (ajusta el nombre si usas otro)
load_dotenv(os.path.join(ROOT, ".env.local"))

# Para los tests queremos que el scheduler nunca arranque
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app.main import app
# Routers reales en tu árbol:
from app.routers.auth_router import router as auth_router
from app.routers.puzzles_router import router as puzzles_router
from app.routers.users_router import router as users_router
from app.routers.health_router import router as health_router

# Dependencias que vamos a sobrescribir:
from app.core.security import get_current_token_cookie_or_header
from app.core.cookies import require_csrf



@pytest.fixture
def client_auth(monkeypatch):
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")  # evita scheduler y prints
    app.dependency_overrides[get_current_token_cookie_or_header] = lambda: {"sub": "9", "email": "a@b.com"}
    app.dependency_overrides[require_csrf] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(scope="session")
def test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(puzzles_router)
    app.include_router(users_router)
    return app

@pytest.fixture(scope="session")
def client(test_app: FastAPI) -> TestClient:
    return TestClient(test_app)

@pytest.fixture(autouse=True)
def override_auth_csrf(test_app: FastAPI):
    """
    Desactiva autenticación y CSRF para poder llamar rutas protegidas
    sin necesidad de tokens reales.
    """
    test_app.dependency_overrides[get_current_token_cookie_or_header] = lambda: {
        "sub": "1",
        "email": "tester@example.com",
    }
    test_app.dependency_overrides[require_csrf] = lambda: True
    yield
    test_app.dependency_overrides.clear()