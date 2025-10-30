
from fastapi.testclient import TestClient
from app.main import app
from app.services import puzzle_service
from app.core.cookies import CSRF_COOKIE
import json

client = TestClient(app)

def _auth_headers():
    # Simula middleware de auth ya probado: inyecta token válido y CSRF
    return {
        "Authorization": "Bearer faketoken",
        "X-CSRF-Token": "csrf123",
    }

def test_like_flow(monkeypatch, client_auth):
    monkeypatch.setattr(puzzle_service, "like_puzzle",
                        lambda current_user_id, puzzle_id: {"ok": True, "changed": True})
    monkeypatch.setattr(puzzle_service, "unlike_puzzle",
                        lambda current_user_id, puzzle_id: {"ok": True, "changed": True})
    monkeypatch.setattr(puzzle_service, "get_puzzle_like_count",
                        lambda puzzle_id: {"count": 1})

    # like
    r1 = client_auth.post("/puzzles/555/like")
    assert r1.status_code == 200
    assert r1.json()["ok"] is True

    # count
    r2 = client_auth.get("/puzzles/555/likes/count")
    assert r2.status_code == 200
    assert r2.json()["count"] == 1

    # unlike
    r3 = client_auth.delete("/puzzles/555/like")
    assert r3.status_code == 200
    assert r3.json()["changed"] is True
