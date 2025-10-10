import re
from typing import Dict, Any, Optional

import unicodedata
from fastapi import HTTPException, status

from app.repositories import puzzles_repo
from app.services.user_service import _build_avatar_url


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
