from fastapi.testclient import TestClient
import pytest


def test_get_puzzle_404_not_found(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """
    Returns 404 when the service doesn't find the puzzle by ID.
    """
    from app.services import puzzle_service

    # 🔧 Simulamos que el puzzle no existe
    monkeypatch.setattr(puzzle_service, "get_puzzle_details", lambda puzzle_id: None)

    r = client.get("/puzzles/539")
    assert r.status_code == 404
    assert r.json()["detail"] == "Puzzle not found"


def test_get_puzzle_200_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """
    Returns 200 with valid puzzle details and sets proper cache headers.
    """
    from app.services import puzzle_service

    # 🔧 Creamos un puzzle simulado (lo que devolvería la DB)
    fake_puzzle = {
        "id": 539,
        "author_id": 1,
        "title": "Arithmetic 4x4",
        "size": 4,
        "board_spec": {
            "N": 4,
            "numbers": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
            "operators": ["+", "-", "*", "/"],
            "expected": ["10", "15", "20", "25", "30", "35", "40", "45"],
        },
        "difficulty": 3,
        "num_solutions": 1,
        "created_at": "2025-10-30T12:00:00Z",
        "author": {
            "id": 1,
            "slug": "tester",
            "display_name": "Test User",
            "avatar_key": None,
            "avatar_url": None,
        },
    }

    # Monkeypatch para devolver el puzzle simulado
    monkeypatch.setattr(puzzle_service, "get_puzzle_details", lambda puzzle_id: fake_puzzle)

    r = client.get("/puzzles/539")
    assert r.status_code == 200

    body = r.json()
    assert body["id"] == 539
    assert body["title"] == "Arithmetic 4x4"
    assert body["size"] == 4
    assert body["difficulty"] == 3
    assert body["author"]["display_name"] == "Test User"

    # Verifica cabecera de cache (ISR-friendly)
    assert r.headers.get("Cache-Control") == "public, s-maxage=300, stale-while-revalidate=60"
