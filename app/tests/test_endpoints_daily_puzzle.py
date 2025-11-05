from datetime import date
from fastapi.testclient import TestClient
import pytest


def test_daily_puzzle_404_when_not_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """
    Ensures that the /puzzles/daily-puzzle endpoint returns 404 when no daily puzzle is configured.

    This test:
    - Mocks puzzle_service.get_today_daily_puzzle() to return None.
    - Sends a GET request to /puzzles/daily-puzzle.
    - Verifies that the endpoint responds with HTTP 404.
    - Confirms that the response JSON includes the correct 'detail' message:
      "Daily puzzle not configured for today".
    """
    from app.services import puzzle_service

    monkeypatch.setattr(puzzle_service, "get_today_daily_puzzle", lambda: None)

    r = client.get("/puzzles/daily-puzzle")
    assert r.status_code == 404
    assert r.json()["detail"] == "Daily puzzle not configured for today"


def test_daily_puzzle_200_ok_and_cache_header(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """
    Verifies that the /puzzles/daily-puzzle endpoint returns a valid daily puzzle
    and sets appropriate caching headers for CDN optimization.

    This test:
    - Mocks puzzle_service.get_today_daily_puzzle() to return a fake DailyPuzzleOut payload.
    - Sends a GET request to /puzzles/daily-puzzle.
    - Confirms that the response has status 200 and includes the correct JSON structure.
    - Validates that puzzle attributes (id, size, difficulty, author) match the mock payload.
    - Asserts that the 'Cache-Control' header is properly set to
      "public, s-maxage=300, stale-while-revalidate=60".
    """
    from app.services import puzzle_service

    today = date.today().isoformat()

    fake_payload = {
        "date": today,
        "puzzle": {
            "id": 123,
            "slug": "autogen-4x4",
            "title": "AutoGen 4x4",
            "size": 4,
            "difficulty": 3,
            "created_at": f"{today}T12:00:00Z",
            "author": {
                "id": 1,
                "slug": "system",
                "display_name": "System",
                "avatar_key": None,
                "avatar_url": None,
            },
        },
    }

    monkeypatch.setattr(puzzle_service, "get_today_daily_puzzle", lambda: fake_payload)

    r = client.get("/puzzles/daily-puzzle")
    assert r.status_code == 200

    body = r.json()
    assert body["date"] == today
    assert body["puzzle"]["id"] == 123
    assert body["puzzle"]["size"] == 4
    assert body["puzzle"]["difficulty"] == 3
    assert body["puzzle"]["author"]["display_name"] == "System"

    # Header exacto que el router establece
    assert r.headers.get("Cache-Control") == "public, s-maxage=300, stale-while-revalidate=60"
