import os
import re
from typing import Dict, Any, Optional

import requests
import unicodedata
from fastapi import HTTPException, status

from app.repositories import puzzles_repo
from app.services.user_service import _build_avatar_url

REVALIDATE_URL = os.getenv("REVALIDATE_URL")
REVALIDATE_SECRET = os.getenv("REVALIDATE_SECRET")

def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "puzzle"

def create_puzzle(
    *, author_id: int, title: str, size: int,
    board_spec: Dict[str, Any], difficulty: Optional[int],
    num_solutions: Optional[int]
) -> dict:

    try:
        row = puzzles_repo.insert_puzzle(
            author_id=author_id,
            title=title,
            size=size,
            board_spec=board_spec,
            difficulty=difficulty,
            num_solutions=num_solutions,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid puzzle payload") from e

    return {
        "id": row["id"],
        "author_id": row["author_id"],
        "title": row["title"],
        "size": row["size"],
        "board_spec": row["board_spec"],
        "difficulty": row["difficulty"],
        "num_solutions": row["num_solutions"],
        "created_at": row["created_at"].isoformat(),
    }

def get_puzzles_ssg_seed(limit: int = 200) -> dict:
    rows = puzzles_repo.list_puzzles_ssg_seed(limit)
    items = [{"id": r["id"], "tag": _slugify(r["title"])} for r in rows]
    return {"items": items, "count": len(items)}


def get_puzzle_details(puzzle_id: int) -> dict | None:
    row = puzzles_repo.get_puzzle_by_id(puzzle_id)
    if not row:
        return None

    author_block = None
    if row.get("author_id"):
        display_name = row.get("author_name") or "Unknown"
        avatar_key = row.get("author_avatar_key")
        author_block = {
            "id": row["author_id"],
            "slug": _slugify(display_name),
            "display_name": display_name,
            "avatar_key": avatar_key,
            "avatar_url": _build_avatar_url(avatar_key),
        }

    return {
        "id": row["id"],
        "author_id": row["author_id"],
        "title": row["title"],
        "size": row["size"],
        "board_spec": row["board_spec"],
        "difficulty": row["difficulty"],
        "num_solutions": row["num_solutions"],
        "created_at": row["created_at"].isoformat(),
        "author": author_block,
    }




def patch_puzzle(
    *, current_user_id: int, puzzle_id: int,
    title: Optional[str], size: Optional[int],
    board_spec: Optional[dict], difficulty: Optional[int],
    num_solutions: Optional[int],
) -> dict:
    # 1) Al menos un campo
    if all(v is None for v in (title, size, board_spec, difficulty, num_solutions)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Provide at least one field to update")

    # 2) Verifica que exista y su autor
    owner = puzzles_repo.get_puzzle_author_id(puzzle_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Puzzle not found")
    if owner != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the author")

    # 3) Ejecuta el update
    updated = puzzles_repo.update_puzzle_owned(
        puzzle_id=puzzle_id, author_id=current_user_id,
        title=title, size=size, board_spec=board_spec,
        difficulty=difficulty, num_solutions=num_solutions,
    )

    # Si no hay fila devuelta, no cambió nada (mismos valores)
    changed = bool(updated)

    # 4) Revalidación ISR cuando cambia el título (slug cambia)
    if changed and title and REVALIDATE_URL and REVALIDATE_SECRET:
        try:
            new_slug = _slugify(title)
            requests.post(
                REVALIDATE_URL,
                json={"secret": REVALIDATE_SECRET, "paths": [f"/p/{puzzle_id}-{new_slug}"]},
                timeout=3,
            )
        except Exception as e:
            print(f"[WARN] Revalidate request failed: {e}")

    return {"ok": True, "changed": changed}
