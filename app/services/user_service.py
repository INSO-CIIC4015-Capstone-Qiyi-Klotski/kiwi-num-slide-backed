import os
import re
from typing import Optional

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