from datetime import date
from fastapi.testclient import TestClient
import pytest


def test_daily_puzzle_404_when_not_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """
    When the service reports no daily puzzle is configured, the endpoint must return 404 with the expected detail.
    """
    from app.services import puzzle_service

    monkeypatch.setattr(puzzle_service, "get_today_daily_puzzle", lambda: None)

    r = client.get("/puzzles/daily-puzzle")
    assert r.status_code == 404
    assert r.json()["detail"] == "Daily puzzle not configured for today"


def test_daily_puzzle_200_ok_and_cache_header(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """
    Returns 200 with a valid DailyPuzzleOut payload and sets CDN-friendly Cache-Control headers.
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
