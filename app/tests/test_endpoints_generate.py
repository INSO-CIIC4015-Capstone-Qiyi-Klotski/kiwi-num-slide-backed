import os
from fastapi.testclient import TestClient
import pytest


def _payload():
    # JSON que coincide con PuzzleGenConfig
    return {
        "count": 1,
        "N": 3,
        "difficulty": 2,
        "allowed_numbers": [1, 2, 3, 4, 5, 6, 7, 8, 9],
        "operators_spec": [["+", None], ["*", 2]],  # tuples en Python -> arrays JSON
        "require_unique": True,
        "max_attempts": 5,
        "include_solutions": True,
        "solutions_cap": 1,
    }


def test_generate_requires_secret_403(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GENERATION_SECRET", raising=False)

    r = client.post("/puzzles/generate", json=_payload())
    assert r.status_code == 403
    assert r.json()["detail"] == "Forbidden"


def test_generate_201_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GENERATION_SECRET", "top-secret")

    # Mockea la función de generación/almacenamiento para no tocar DB real
    from app.services import puzzle_generation as gen

    def fake_generate_and_store_puzzles(**kw):
        return {
            "requested": kw["count"],
            "inserted": 1,
            "attempts": 2,
            "difficulty": kw["difficulty"],
            "N": kw["N"],
        }

    monkeypatch.setattr(gen, "generate_and_store_puzzles", fake_generate_and_store_puzzles)

    r = client.post("/puzzles/generate?secret=top-secret", json=_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["requested"] == 1
    assert body["inserted"] == 1
    assert body["N"] == 3
