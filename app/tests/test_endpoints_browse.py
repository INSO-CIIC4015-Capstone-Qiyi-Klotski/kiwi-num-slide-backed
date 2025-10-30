
from fastapi.testclient import TestClient
from app.main import app
from app.services import puzzle_service

client = TestClient(app)

def test_browse_puzzles_ok(monkeypatch):
    fake_page = {
        "items": [
            {
                "id": 10, "slug": "auto-10", "title": "AutoGen 4x4",
                "size": 4, "difficulty": 2, "created_at": "2025-10-29T10:00:00Z",
                "author": {"id": -1, "slug": "system", "display_name": "system"}
            }
        ],
        "next_cursor": "10"
    }
    monkeypatch.setattr(puzzle_service, "browse_puzzles_public",
                        lambda limit, cursor, size, q, sort: fake_page)

    res = client.get("/puzzles?limit=1&sort=created_at_desc")
    assert res.status_code == 200
    data = res.json()
    assert data["items"][0]["id"] == 10
    assert data["next_cursor"] == "10"
