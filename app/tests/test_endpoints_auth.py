
from fastapi.testclient import TestClient
from app.main import app
from app.services import auth_service
from app.core.cookies import ACCESS_COOKIE, REFRESH_COOKIE

client = TestClient(app)

def test_login_sets_cookies(monkeypatch, client):
    fake_login = {
        "access_token": "acc",
        "refresh_token": "ref",
        "token_type": "bearer",
        "user": {"id": 1, "name": "A", "email": "a@b.com", "is_verified": True},  # <-- faltaba
        "needs_verification": False,
    }
    monkeypatch.setattr(auth_service, "login_user", lambda email, password: fake_login)

    r = client.post("/auth/login", json={"email": "a@b.com", "password": "x"})
    assert r.status_code == 200

    # Verifica que el cuerpo cumpla el schema
    data = r.json()
    assert data["access_token"] == "acc"
    assert data["refresh_token"] == "ref"
    assert data["user"]["is_verified"] is True

    # Verifica cookies seteadas (access/refresh y csrf)
    # TestClient consolida cookies en client.cookies
    assert "access_token" in client.cookies
    assert "refresh_token" in client.cookies
    assert "csrf_token" in client.cookies

    # (Opcional) verifica flags básicos de Set-Cookie en los headers
    set_cookie_headers = [h for h in r.headers.get_list("set-cookie")]
    assert any("HttpOnly" in h for h in set_cookie_headers)

def test_refresh_uses_cookie(monkeypatch):
    # Decodificar/validar token lo hace security internamente; aquí solo verificamos flujo del endpoint
    from app.core import security
    monkeypatch.setattr(security, "decode_token", lambda t: {"sub":"1","email":"a@b.com","type":"refresh"})
    monkeypatch.setattr(security, "require_token_type", lambda data, t: None)
    monkeypatch.setattr(security, "create_access_token", lambda uid, email: "new-acc")

    # setear cookie de refresh en la request del TestClient
    client.cookies.set(REFRESH_COOKIE, "ref-cookie")
    r = client.post("/auth/refresh")
    assert r.status_code == 200
    assert r.json()["access_token"] == "new-acc"
