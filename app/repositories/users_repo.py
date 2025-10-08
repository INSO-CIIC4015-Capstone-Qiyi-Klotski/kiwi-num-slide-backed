from sqlalchemy import text
from ..db import get_tx, get_conn


def insert_user(name: str, email: str, password_hash: str) -> dict:
    sql = text("""
        INSERT INTO users (name, email, password_hash)
        VALUES (:name, LOWER(:email), :password_hash)
        RETURNING id, name, email, is_verified;
    """)
    with get_tx() as conn:
        row = conn.execute(sql, {"name": name, "email": email, "password_hash": password_hash}).mappings().first()
    return dict(row)


def get_user_by_email(email: str) -> dict | None:
    sql = text("""
        SELECT id, name, email, password_hash, is_verified
        FROM users WHERE LOWER(email) = LOWER(:email);
    """)
    with get_conn() as conn:
        row = conn.execute(sql, {"email": email}).mappings().first()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    sql = text("""
        SELECT id, name, email, password_hash, is_verified, avatar_key
        FROM users WHERE id = :id
    """)
    with get_conn() as conn:
        row = conn.execute(sql, {"id": user_id}).mappings().first()
    return dict(row) if row else None


def mark_verified(user_id: int):
    with get_tx() as conn:
        conn.execute(text("UPDATE users SET is_verified = TRUE WHERE id = :id"), {"id": user_id})
