from typing import Optional

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



def get_private_user_with_stats(user_id: int) -> dict | None:
    sql = text("""
        SELECT
            u.id,
            u.name,
            u.email,
            u.avatar_key,
            u.created_at,
            COALESCE(p.puzzles_count, 0)   AS puzzles_count,
            COALESCE(l.likes_received, 0)  AS likes_received,
            COALESCE(f.followers_count, 0) AS followers_count
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



def update_user_profile(user_id: int, name: Optional[str], avatar_key: Optional[str]) -> bool:
    sets, params = [], {"id": user_id}
    if name is not None:
        sets.append("name = :name")
        params["name"] = name
    if avatar_key is not None:
        sets.append("avatar_key = :avatar_key")
        params["avatar_key"] = avatar_key
    if not sets:
        return False  # nada que actualizar

    sql = text(f"UPDATE users SET {', '.join(sets)} WHERE id = :id")
    with get_tx() as conn:
        result = conn.execute(sql, params)
        # En SQLAlchemy 2.x, rowcount puede ser -1 con algunos drivers; si pasa, asumimos True
        return (result.rowcount is None) or (result.rowcount < 0) or (result.rowcount > 0)



def user_exists(user_id: int) -> bool:
    sql = text("SELECT 1 FROM users WHERE id = :id")
    with get_conn() as conn:
        row = conn.execute(sql, {"id": user_id}).first()
    return row is not None

def create_follow(follower_id: int, followee_id: int) -> bool:
    """
    Crea el follow si no existe. Devuelve True si se insertó, False si ya existía.
    """
    sql = text("""
        INSERT INTO follows (follower_id, followee_id)
        VALUES (:follower_id, :followee_id)
        ON CONFLICT (follower_id, followee_id) DO NOTHING
        RETURNING id;
    """)
    with get_tx() as conn:
        row = conn.execute(sql, {"follower_id": follower_id, "followee_id": followee_id}).first()
    return row is not None


def delete_follow(follower_id: int, followee_id: int) -> bool:
    """
    Elimina el follow si existe.
    Devuelve True si se borró, False si no existía (idempotente).
    """
    sql = text("""
        DELETE FROM follows
        WHERE follower_id = :follower_id AND followee_id = :followee_id
        RETURNING id;
    """)
    with get_tx() as conn:
        row = conn.execute(sql, {"follower_id": follower_id, "followee_id": followee_id}).first()
    return row is not None



def list_following(follower_id: int, limit: int, cursor: Optional[int]) -> list[dict]:
    """
    Devuelve hasta `limit + 1` filas para detectar si hay siguiente página.
    Campos: follow_id, follow_created_at, user.*
    """
    base_sql = """
        SELECT
            f.id AS follow_id,
            f.created_at AS follow_created_at,
            u.id AS user_id,
            u.name AS user_name,
            u.avatar_key AS user_avatar_key
        FROM follows f
        JOIN users u ON u.id = f.followee_id
        WHERE f.follower_id = :follower_id
    """
    params = {"follower_id": follower_id, "limit": limit + 1}
    if cursor:
        base_sql += " AND f.id < :cursor"
        params["cursor"] = cursor

    base_sql += " ORDER BY f.id DESC LIMIT :limit"

    with get_conn() as conn:
        rows = conn.execute(text(base_sql), params).mappings().all()

    return [dict(r) for r in rows]

