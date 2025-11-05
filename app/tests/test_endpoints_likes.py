
from fastapi.testclient import TestClient
from app.main import app
from app.services import puzzle_service
from app.core.cookies import CSRF_COOKIE
import json

client = TestClient(app)

def _auth_headers():
    """Helper function that simulates authenticated headers including a valid Bearer token and CSRF token."""
    # Simula middleware de auth ya probado: inyecta token válido y CSRF
    return {
        "Authorization": "Bearer faketoken",
        "X-CSRF-Token": "csrf123",
    }

def test_like_flow(monkeypatch, client_auth):
    """
        Verifies the full like/unlike flow for puzzles, including like count retrieval.

        This test:
        - Mocks the core puzzle_service functions: like_puzzle, unlike_puzzle, and get_puzzle_like_count.
        - Simulates authenticated requests using a preconfigured TestClient fixture (client_auth).
        - Sends three sequential requests:
            POST /puzzles/{id}/like → to add a like.
            GET /puzzles/{id}/likes/count → to retrieve the like count.
            DELETE /puzzles/{id}/like → to remove the like.
        - Ensures that each endpoint returns HTTP 200 and correct JSON responses.
        - Validates that the `ok`, `changed`, and `count` fields reflect the expected behavior.
        """
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
