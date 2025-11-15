import os
import re
from datetime import datetime, date as _date
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

import requests
import unicodedata
from fastapi import HTTPException, status

from app.repositories import puzzles_repo
from app.services import puzzle_generation
from app.services.user_service import _build_avatar_url

import json
from typing import Any, Dict, List, Optional

REVALIDATE_URL = os.getenv("REVALIDATE_URL")
REVALIDATE_SECRET = os.getenv("REVALIDATE_SECRET")
DAILY_TZ = os.getenv("DAILY_TZ", "UTC")  # p.ej. "America/Puerto_Rico"

def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "puzzle"

def _today_local_date():
    try:
        tz = ZoneInfo(DAILY_TZ)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date()

def _map_daily_row(row: dict) -> dict:
    author_block = None
    if row.get("author_id"):
        display_name = row.get("author_name") or "Unknown"
        author_block = {
            "id": row["author_id"],
            "slug": _slugify(display_name),
            "display_name": display_name,
            "avatar_key": row.get("author_avatar_key"),
            "avatar_url": _build_avatar_url(row.get("author_avatar_key")),
        }
    return {
        "date": row["dp_date"].isoformat(),
        "puzzle": {
            "id": row["puzzle_id"],
            "slug": _slugify(row["puzzle_title"]),
            "title": row["puzzle_title"],
            "size": row["puzzle_size"],
            "difficulty": row["puzzle_difficulty"],
            "created_at": row["puzzle_created_at"].isoformat(),
            "author": author_block,
        },
    }


def _normalize_operators(raw: Any) -> List[str]:
    """
    Normalizes board_spec operators into API-friendly tokens.

    Input is expected to come from PostgreSQL as either:
      - a Python list like ["+", "-", "*"]
      - or a JSON string representing that list.

    Output is a de-duplicated list of tokens:
      ["add", "sub", "mul", "div"]
    """
    if raw is None:
        return []

    if isinstance(raw, list):
        ops = raw
    else:
        try:
            ops = json.loads(raw)
        except Exception:
            return []

    symbol_to_token = {"+": "add", "-": "sub", "*": "mul", "/": "div"}
    result: List[str] = []
    for sym in ops:
        token = symbol_to_token.get(sym)
        if token and token not in result:
            result.append(token)
    return result


def ensure_daily_puzzle_for_today(auto_generate_fallback: bool = True) -> dict:
    """
    Publica un puzzle de autor -1 no usado aún en daily_puzzles para la fecha local de hoy.
    Si ya existe daily para hoy, no hace nada.
    Si no hay puzzles disponibles y auto_generate_fallback=True, genera uno y lo publica.
    """
    today = _today_local_date()

    # Si ya existe, no repetimos
    if puzzles_repo.get_daily_puzzle_by_date(today):
        return {"ok": True, "skipped": True, "reason": "already_set", "date": today.isoformat()}

    # Intentar elegir uno disponible
    pid = puzzles_repo.pick_unused_generated_puzzle(limit=50)

    # Fallback opcional: generar uno si no hay
    if pid is None and auto_generate_fallback:
        gen = puzzle_generation.generate_and_store_puzzles(
            count=1,
            N=4,
            difficulty=3,
            allowed_numbers=[2, 3, 4, 5, 6],
            operators_spec=[("+", None), ("-", None), ("*", 2), ("/", 2)],
            require_unique=True,
            max_attempts=300,
            include_solutions=True,
            solutions_cap=1,
        )
        # vuelve a buscar uno libre
        pid = puzzles_repo.pick_unused_generated_puzzle(limit=1)

    if pid is None:
        # No se pudo asignar daily
        raise HTTPException(status_code=409, detail="No available generated puzzles to schedule for daily")

    inserted = puzzles_repo.upsert_daily_puzzle(today, pid)
    return {
        "ok": inserted,
        "date": today.isoformat(),
        "puzzle_id": pid,
        "skipped": not inserted,
    }

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




def delete_puzzle(*, current_user_id: int, puzzle_id: int) -> dict:
    # 1) Existe y autor correcto
    owner = puzzles_repo.get_puzzle_author_id(puzzle_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Puzzle not found")
    if owner != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the author")

    # 2) Lee el título/slug ANTES de borrar, para invalidar la ruta exacta
    row = puzzles_repo.get_puzzle_by_id(puzzle_id)
    if not row:
        # raro: existía para author_id pero no al leer; tratamos como 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Puzzle not found")

    title = row.get("title") or "puzzle"
    slug = _slugify(title)
    path_to_invalidate = f"/p/{puzzle_id}-{slug}"

    # 3) Bloqueo por daily_puzzles
    if puzzles_repo.puzzle_has_daily_reference(puzzle_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Puzzle is referenced by daily_puzzles")

    # 4) Borrar
    deleted = puzzles_repo.delete_puzzle_owned(puzzle_id, current_user_id)

    # 5) Revalidate: invalidar la ruta pública exacta del puzzle
    if deleted and REVALIDATE_URL and REVALIDATE_SECRET:
        try:
            requests.post(
                REVALIDATE_URL,
                json={"secret": REVALIDATE_SECRET, "paths": [path_to_invalidate]},
                timeout=3,
            )
        except Exception as e:
            print(f"[WARN] Revalidate request failed: {e}")

    return {"ok": True, "deleted": bool(deleted)}




def browse_puzzles_public(
    *,
    limit: int,
    cursor: Optional[str],
    size: Optional[int],
    q: Optional[str],
    sort: str,
    min_likes: Optional[int],
    author_id: Optional[int],
    generated_by: Optional[str],
    operators: Optional[str],
) -> Dict[str, Any]:

    # --- validar sort ---
    allowed_sorts = {
        "created_at_desc",
        "likes_desc",
        "difficulty_desc",
        "difficulty_asc",
        "size_desc",
    }
    if sort not in allowed_sorts:
        raise ValueError("Unsupported sort; allowed: " + ", ".join(sorted(allowed_sorts)))

    cursor_id = int(cursor) if cursor else None

    # --- normalizar operators (string "add,sub" -> ["add","sub"]) ---
    operators_list: Optional[List[str]] = None
    if operators:
        raw = [op.strip().lower() for op in operators.split(",") if op.strip()]
        allowed_ops = {"add", "sub", "mul", "div"}
        filtered = [op for op in raw if op in allowed_ops]
        operators_list = filtered or None

    rows = puzzles_repo.browse_puzzles_public(
        limit=limit,
        cursor_id=cursor_id,
        size=size,
        q=q,
        sort=sort,
        min_likes=min_likes,
        author_id=author_id,
        generated_by=generated_by,
        operators=operators_list,
    )

    has_more = len(rows) > limit
    rows = rows[:limit]

    items: List[Dict[str, Any]] = []
    for r in rows:
        author_block = None
        if r.get("author_id"):
            display_name = r.get("author_name") or "Unknown"
            author_block = {
                "id": r["author_id"],
                "slug": _slugify(display_name),
                "display_name": display_name,
                "avatar_url": _build_avatar_url(r.get("author_avatar_key")),
            }

        generated_by = "user" if r.get("author_id") else "algorithm"

        operators = _normalize_operators(r.get("operators_raw"))

        items.append(
            {
                "id": r["id"],
                "slug": _slugify(r["title"]),
                "title": r["title"],
                "size": r["size"],
                "difficulty": r["difficulty"],
                "created_at": r["created_at"].isoformat(),
                "author": author_block,
                "likes_count": r.get("likes_count", 0),
                "solves_count": r.get("solves_count", 0),
                "generated_by": generated_by,
                "operators": operators,
            }
        )

    next_cursor = str(rows[-1]["id"]) if has_more and rows else None
    return {"items": items, "next_cursor": next_cursor}



def like_puzzle(*, current_user_id: int, puzzle_id: int) -> dict:
    if not puzzles_repo.puzzle_exists(puzzle_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Puzzle not found")

    changed = puzzles_repo.create_puzzle_like(current_user_id, puzzle_id)
    return {"ok": True, "changed": bool(changed)}


def unlike_puzzle(*, current_user_id: int, puzzle_id: int) -> dict:
    if not puzzles_repo.puzzle_exists(puzzle_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Puzzle not found")

    changed = puzzles_repo.delete_puzzle_like(current_user_id, puzzle_id)
    return {"ok": True, "changed": bool(changed)}


def get_puzzle_like_count(puzzle_id: int) -> dict:
    if not puzzles_repo.puzzle_exists(puzzle_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Puzzle not found")
    return {"count": puzzles_repo.count_puzzle_likes(puzzle_id)}


def submit_puzzle_solve(
    *, current_user_id: int, puzzle_id: int, movements: int, duration_ms: int, solution: Optional[Dict[str, Any]]
) -> dict:
    # Validar existencia del puzzle
    if not puzzles_repo.puzzle_exists(puzzle_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Puzzle not found")

    # (Opcional) validar que movements/duration sean razonables, anti-cheat, etc.

    try:
        row = puzzles_repo.insert_puzzle_solve(
            user_id=current_user_id,
            puzzle_id=puzzle_id,
            movements=movements,
            duration_ms=duration_ms,
            solution=solution,
        )
    except Exception as e:
        # Mantén el detalle limpio hacia el cliente
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid solve payload") from e

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "puzzle_id": row["puzzle_id"],
        "movements": row["movements"],
        "duration_ms": row["duration_ms"],
        "solution": row["solution"],
        "created_at": row["created_at"].isoformat(),
    }


def list_my_solves_for_puzzle(
    *, current_user_id: int, puzzle_id: int, limit: int, cursor: Optional[str]
) -> Dict[str, Any]:
    # 404 si el puzzle no existe
    if not puzzles_repo.puzzle_exists(puzzle_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Puzzle not found")

    cursor_id = int(cursor) if cursor else None
    rows = puzzles_repo.list_my_solves_for_puzzle(
        user_id=current_user_id,
        puzzle_id=puzzle_id,
        limit=limit,
        cursor_id=cursor_id,
    )

    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [{
        "id": r["id"],
        "movements": r["movements"],
        "duration_ms": r["duration_ms"],
        "solution": r["solution"],  # puede ser None
        "created_at": r["created_at"].isoformat(),
    } for r in rows]

    next_cursor = str(rows[-1]["id"]) if has_more and rows else None
    return {"items": items, "next_cursor": next_cursor}



def get_today_daily_puzzle() -> dict | None:
    today = _today_local_date()
    row = puzzles_repo.get_daily_puzzle_by_date(today)
    return None if not row else _map_daily_row(row)

def get_daily_puzzle_for_date(d: _date) -> dict | None:
    row = puzzles_repo.get_daily_puzzle_by_date(d)
    return None if not row else _map_daily_row(row)