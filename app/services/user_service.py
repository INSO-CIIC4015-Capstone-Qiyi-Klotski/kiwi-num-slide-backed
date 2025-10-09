import re

import unicodedata

from app.repositories import users_repo

def _slugify(value: str) -> str:
    # Normaliza acentos y convierte a ASCII
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "user"

def get_ssg_seed(limit: int = 200):
    rows = users_repo.list_ssg_seed(limit)
    items = [{"id": r["id"], "tag": _slugify(r["name"])} for r in rows]
    return {"items": items, "count": len(items)}
