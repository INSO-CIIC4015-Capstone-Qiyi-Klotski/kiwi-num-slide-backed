import os
import re
from typing import Optional, Dict, Any

import unicodedata
import requests
from fastapi import HTTPException
from starlette import status

from app.repositories import users_repo

AVATAR_CDN_BASE = os.getenv("AVATAR_CDN_BASE", "").rstrip("/")
REVALIDATE_SECRET = os.getenv("REVALIDATE_SECRET")
REVALIDATE_URL = os.getenv("REVALIDATE_URL")

def _slugify(value: str) -> str:
    # Normaliza acentos y convierte a ASCII
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "user"

def _build_avatar_url(avatar_key: Optional[str]) -> Optional[str]:
    if not avatar_key:
        return None
    if not AVATAR_CDN_BASE:
        return None
    return f"{AVATAR_CDN_BASE}/{avatar_key.lstrip('/')}"

def get_ssg_seed(limit: int = 200):
    rows = users_repo.list_ssg_seed(limit)
    items = [{"id": r["id"], "tag": _slugify(r["name"])} for r in rows]
    return {"items": items, "count": len(items)}


def get_public_profile(user_id: int) -> dict | None:
    row = users_repo.get_public_user_with_stats(user_id)
    if not row:
        return None
    slug = _slugify(row["name"])
    return {
        "id": row["id"],
        "slug": slug,
        "display_name": row["name"],
        "avatar_key": row.get("avatar_key"),
        "avatar_url": _build_avatar_url(row.get("avatar_key")),
        "created_at": row["created_at"].isoformat(),
        "stats": {
            "puzzles": row["puzzles_count"],
            "likes_received": row["likes_received"],
            "followers": row["followers_count"],
        },
    }


def get_my_profile(user_id: int) -> dict | None:
    row = users_repo.get_private_user_with_stats(user_id)
    if not row:
        return None
    slug = _slugify(row["name"])
    return {
        "id": row["id"],
        "slug": slug,
        "display_name": row["name"],
        "email": row["email"],
        "avatar_key": row.get("avatar_key"),
        "avatar_url": _build_avatar_url(row.get("avatar_key")),
        "created_at": row["created_at"].isoformat(),
        "stats": {
            "puzzles": row["puzzles_count"],
            "likes_received": row["likes_received"],
            "followers": row["followers_count"],
        },
    }



def patch_my_profile(user_id: int, name: str | None, avatar_key: str | None) -> dict:
    if name is None and avatar_key is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Provide at least one of: name, avatar_key")

    changed = users_repo.update_user_profile(user_id, name=name, avatar_key=avatar_key)

    if changed and REVALIDATE_URL and REVALIDATE_SECRET:
        try:
            paths = []
            if name:
                paths.append(f"/u/{user_id}-{_slugify(name)}")
            if paths:
                requests.post(REVALIDATE_URL,
                              json={"secret": REVALIDATE_SECRET, "paths": paths},
                              timeout=3)
        except Exception as e:
            print(f"[WARN] Revalidate request failed: {e}")

    return {"ok": True, "changed": bool(changed)}



def follow_user(current_user_id: int, target_user_id: int) -> dict:
    # No te puedes seguir a ti mismo
    if current_user_id == target_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself")

    # Verifica que el target exista
    if not users_repo.user_exists(target_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Intenta crear el follow (idempotente)
    changed = users_repo.create_follow(current_user_id, target_user_id)

    return {"ok": True, "changed": bool(changed)}


def unfollow_user(current_user_id: int, target_user_id: int) -> dict:
    # No puedes dejar de seguirte a ti mismo
    if current_user_id == target_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot unfollow yourself")

    # Verifica que el target exista
    if not users_repo.user_exists(target_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Intenta eliminar el follow (idempotente)
    changed = users_repo.delete_follow(current_user_id, target_user_id)

    return {"ok": True, "changed": bool(changed)}



def list_my_following(current_user_id: int, limit: int, cursor: Optional[str]) -> dict:
    # Normaliza cursor (id de follows)
    cursor_id: Optional[int] = int(cursor) if cursor else None

    rows = users_repo.list_following(current_user_id, limit=limit, cursor=cursor_id)

    has_more = len(rows) > limit
    rows = rows[:limit]

    items = []
    for r in rows:
        slug = _slugify(r["user_name"])
        items.append({
            "id": r["user_id"],
            "slug": slug,
            "display_name": r["user_name"],
            "avatar_key": r.get("user_avatar_key"),
            "avatar_url": _build_avatar_url(r.get("user_avatar_key")),
            "since": r["follow_created_at"].isoformat(),
        })

    next_cursor = str(rows[-1]["follow_id"]) if has_more and rows else None

    return {"items": items, "next_cursor": next_cursor}




def list_my_followers(current_user_id: int, limit: int, cursor: Optional[str]) -> dict:
    cursor_id: Optional[int] = int(cursor) if cursor else None
    rows = users_repo.list_followers(current_user_id, limit=limit, cursor=cursor_id)

    has_more = len(rows) > limit
    rows = rows[:limit]

    items = []
    for r in rows:
        slug = _slugify(r["user_name"])
        items.append({
            "id": r["user_id"],
            "slug": slug,
            "display_name": r["user_name"],
            "avatar_key": r.get("user_avatar_key"),
            "avatar_url": _build_avatar_url(r.get("user_avatar_key")),
            "since": r["follow_created_at"].isoformat(),
        })

    next_cursor = str(rows[-1]["follow_id"]) if has_more and rows else None
    return {"items": items, "next_cursor": next_cursor}


def list_my_puzzle_likes(current_user_id: int, limit: int, cursor: Optional[str]) -> dict:
    cursor_id: Optional[int] = int(cursor) if cursor else None

    rows = users_repo.list_my_puzzle_likes(
        user_id=current_user_id,
        limit=limit,
        cursor=cursor_id,
    )

    has_more = len(rows) > limit
    rows = rows[:limit]

    items = []
    for r in rows:
        # Autor (opcional)
        author_block = None
        if r.get("author_id"):
            display_name = r.get("author_name") or "Unknown"
            author_block = {
                "id": r["author_id"],
                "slug": _slugify(display_name),
                "display_name": display_name,
                "avatar_url": _build_avatar_url(r.get("author_avatar_key")),
            }

        items.append({
            "id": r["puzzle_id"],
            "slug": _slugify(r["puzzle_title"]),
            "title": r["puzzle_title"],
            "size": r["puzzle_size"],
            "difficulty": r["puzzle_difficulty"],
            "created_at": r["puzzle_created_at"].isoformat(),
            "author": author_block,
            "since": r["like_created_at"].isoformat(),
        })

    next_cursor = str(rows[-1]["like_id"]) if has_more and rows else None
    return {"items": items, "next_cursor": next_cursor}


def list_all_my_solves(current_user_id: int, limit: int, cursor: Optional[str]) -> Dict[str, Any]:
    cursor_id = int(cursor) if cursor else None

    rows = users_repo.list_my_solves(
        user_id=current_user_id,
        limit=limit,
        cursor_id=cursor_id,
    )

    has_more = len(rows) > limit
    rows = rows[:limit]

    items = []
    for r in rows:
        items.append({
            "id": r["solve_id"],
            "puzzle": {
                "id": r["puzzle_id"],
                "slug": _slugify(r["puzzle_title"]),
                "title": r["puzzle_title"],
                "size": r["puzzle_size"],
                "difficulty": r["puzzle_difficulty"],
            },
            "movements": r["movements"],
            "duration_ms": r["duration_ms"],
            "solution": r["solution"],  # puede venir None
            "created_at": r["solve_created_at"].isoformat(),
        })

    next_cursor = str(rows[-1]["solve_id"]) if has_more and rows else None
    return {"items": items, "next_cursor": next_cursor}