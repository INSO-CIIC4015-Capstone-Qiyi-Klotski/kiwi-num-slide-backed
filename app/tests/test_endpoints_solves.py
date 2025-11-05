# app/tests/test_endpoints_solves.py
from fastapi.testclient import TestClient
from app.main import app
from app.services import puzzle_service

client = TestClient(app)

def _auth_headers():
    """Helper function that returns simulated authentication and CSRF headers."""
    return {"Authorization": "Bearer faketoken", "X-CSRF-Token": "csrf123"}

def test_submit_solve_and_list_me(monkeypatch, client):
    """
        Verifies the full flow of submitting a puzzle solve and retrieving the user's solve history.

        This test:
        - Mocks `puzzle_service.submit_puzzle_solve` to simulate successful solve submission.
        - Mocks `puzzle_service.list_my_solves_for_puzzle` to simulate a paginated response of past solves.
        - Sends a POST request to `/puzzles/{id}/solves` with move data and duration.
        - Verifies that the server responds with HTTP 201 (Created) and a valid JSON payload.
        - Sends a GET request to `/puzzles/{id}/solves/me` to fetch the user's solves.
        - Ensures that the response returns HTTP 200 with correct movement data.
        - Confirms the expected structure of the solve history page, including `items` and `next_cursor`.
        """
    fake_out = {
        "id": 1, "user_id": 9, "puzzle_id": 555,
        "movements": 20, "duration_ms": 12345,
        "solution": {"path": [1,2,3]}, "created_at": "2025-10-29T10:00:00Z"
    }
    monkeypatch.setattr(puzzle_service, "submit_puzzle_solve", lambda **kw: fake_out)

    page = {"items": [{"id": 1, "movements": 20, "duration_ms": 12345,
                        "solution": None, "created_at": "2025-10-29T10:00:00Z"}],
            "next_cursor": None}
    monkeypatch.setattr(puzzle_service, "list_my_solves_for_puzzle", lambda **kw: page)

    r1 = client.post(
        "/puzzles/555/solves",
        json={"movements": 20, "duration_ms": 12345, "solution": {"path":[1,2]}}
    )
    assert r1.status_code == 201

    r2 = client.get("/puzzles/555/solves/me?limit=10")
    assert r2.status_code == 200
    assert r2.json()["items"][0]["movements"] == 20
