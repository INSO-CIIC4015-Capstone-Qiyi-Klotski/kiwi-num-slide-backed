
from fastapi.testclient import TestClient
from app.main import app
from app.services import auth_service
from app.core.cookies import ACCESS_COOKIE, REFRESH_COOKIE

client = TestClient(app)

def test_login_sets_cookies(monkeypatch, client):
    """
        Ensures that the /auth/login endpoint sets authentication cookies correctly.

        This test:
        - Mocks a successful login via auth_service.login_user.
        - Sends a POST request to /auth/login with valid credentials.
        - Asserts that the response has status 200 and returns both tokens and user info.
        - Confirms that cookies for access, refresh, and CSRF tokens are properly set.
        - Optionally checks that Set-Cookie headers include HttpOnly for security.
        """
    fake_login = {
        "access_token": "acc",
        "refresh_token": "ref",
        "token_type": "bearer",
        "user": {"id": 1, "name": "A", "email": "a@b.com", "is_verified": True},
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

    #verifica flags básicos de Set-Cookie en los headers
    set_cookie_headers = [h for h in r.headers.get_list("set-cookie")]
    assert any("HttpOnly" in h for h in set_cookie_headers)

def test_refresh_uses_cookie(monkeypatch):
    """
        Validates that the /auth/refresh endpoint issues a new access token using the refresh cookie.

        This test:
        - Mocks token decoding and creation functions from app.core.security.
        - Inserts a refresh cookie into the test client.
        - Sends a POST request to /auth/refresh.
        - Verifies that the endpoint returns status 200 and a new access token string.
        """
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
