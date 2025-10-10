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


def list_ssg_seed(limit: int = 200):
    sql = text("""
        SELECT id, name
        FROM users
        ORDER BY id
        LIMIT :limit
    """)
    with get_conn() as conn:
        rows = conn.execute(sql, {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]



def get_public_user_with_stats(user_id: int) -> dict | None:
    sql = text("""
        SELECT
            u.id,
            u.name,
            u.avatar_key,
            u.created_at,
            COALESCE(p.puzzles_count, 0)      AS puzzles_count,
            COALESCE(l.likes_received, 0)     AS likes_received,
            COALESCE(f.followers_count, 0)    AS followers_count
        FROM users u
        LEFT JOIN (
            SELECT author_id AS user_id, COUNT(*) AS puzzles_count
            FROM puzzles
            GROUP BY author_id
        ) p ON p.user_id = u.id
        LEFT JOIN (
            SELECT pu.author_id AS user_id, COUNT(pl.id) AS likes_received
            FROM puzzles pu
            JOIN puzzle_likes pl ON pl.puzzle_id = pu.id
            GROUP BY pu.author_id
        ) l ON l.user_id = u.id
        LEFT JOIN (
            SELECT followee_id AS user_id, COUNT(*) AS followers_count
            FROM follows
            GROUP BY followee_id
        ) f ON f.user_id = u.id
        WHERE u.id = :id
    """)
    with get_conn() as conn:
        row = conn.execute(sql, {"id": user_id}).mappings().first()
    return dict(row) if row else None