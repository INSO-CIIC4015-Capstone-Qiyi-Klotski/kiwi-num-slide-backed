import os
import re
from typing import Optional

import unicodedata

from app.repositories import users_repo

AVATAR_CDN_BASE = os.getenv("AVATAR_CDN_BASE", "").rstrip("/")

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