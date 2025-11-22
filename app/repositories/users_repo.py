from typing import Optional, List, Dict, Any

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
            COALESCE(p.puzzles_count, 0)       AS puzzles_count,
            COALESCE(l.likes_received, 0)      AS likes_received,
            COALESCE(f.followers_count, 0)     AS followers_count,
            COALESCE(fo.following_count, 0)    AS following_count
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
        LEFT JOIN (
            SELECT follower_id AS user_id, COUNT(*) AS following_count
            FROM follows
            GROUP BY follower_id
        ) fo ON fo.user_id = u.id
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
            COALESCE(p.puzzles_count, 0)    AS puzzles_count,
            COALESCE(l.likes_received, 0)   AS likes_received,
            COALESCE(f.followers_count, 0)  AS followers_count,
            COALESCE(g.following_count, 0)  AS following_count
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
        LEFT JOIN (
            SELECT follower_id AS user_id, COUNT(*) AS following_count
            FROM follows
            GROUP BY follower_id
        ) g ON g.user_id = u.id
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



def list_followers(followee_id: int, limit: int, cursor: Optional[int]) -> list[dict]:
    """
    Devuelve hasta `limit + 1` filas para detectar next page.
    Retorna:
      - follow_id, follow_created_at
      - user_id (el follower), user_name, user_avatar_key
    """
    base_sql = """
        SELECT
            f.id AS follow_id,
            f.created_at AS follow_created_at,
            u.id AS user_id,
            u.name AS user_name,
            u.avatar_key AS user_avatar_key
        FROM follows f
        JOIN users u ON u.id = f.follower_id
        WHERE f.followee_id = :followee_id
    """
    params = {"followee_id": followee_id, "limit": limit + 1}
    if cursor:
        base_sql += " AND f.id < :cursor"
        params["cursor"] = cursor

    base_sql += " ORDER BY f.id DESC LIMIT :limit"

    with get_conn() as conn:
        rows = conn.execute(text(base_sql), params).mappings().all()

    return [dict(r) for r in rows]


def list_my_puzzle_likes(user_id: int, limit: int, cursor: Optional[int]) -> list[dict]:
    """
    Devuelve hasta limit+1 filas para detectar next page.
    Ordenado por puzzle_likes.id DESC (keyset).
    """
    base_sql = """
        SELECT
            pl.id            AS like_id,
            pl.created_at    AS like_created_at,
            p.id             AS puzzle_id,
            p.title          AS puzzle_title,
            p.size           AS puzzle_size,
            p.difficulty     AS puzzle_difficulty,
            p.created_at     AS puzzle_created_at,
            u.id             AS author_id,
            u.name           AS author_name,
            u.avatar_key     AS author_avatar_key
        FROM puzzle_likes pl
        JOIN puzzles p ON p.id = pl.puzzle_id
        LEFT JOIN users u ON u.id = p.author_id
        WHERE pl.user_id = :user_id
    """
    params = {"user_id": user_id, "limit": limit + 1}
    if cursor:
        base_sql += " AND pl.id < :cursor"
        params["cursor"] = cursor

    base_sql += " ORDER BY pl.id DESC LIMIT :limit"

    with get_conn() as conn:
        rows = conn.execute(text(base_sql), params).mappings().all()

    return [dict(r) for r in rows]



def list_my_solves(
    *, user_id: int, limit: int, cursor_id: Optional[int]
) -> List[Dict[str, Any]]:
    """
    Devuelve solves del usuario (todas los puzzles), ordenados por ps.id DESC.
    Retorna hasta limit+1 para detectar next page.
    """
    sql = """
        SELECT
            ps.id               AS solve_id,
            ps.movements,
            ps.duration_ms,
            ps.solution,
            ps.created_at       AS solve_created_at,
            p.id                AS puzzle_id,
            p.title             AS puzzle_title,
            p.size              AS puzzle_size,
            p.difficulty        AS puzzle_difficulty
        FROM puzzle_solves ps
        JOIN puzzles p ON p.id = ps.puzzle_id
        WHERE ps.user_id = :user_id
    """
    params: Dict[str, Any] = {"user_id": user_id, "limit": limit + 1}

    if cursor_id:
        sql += " AND ps.id < :cursor_id"
        params["cursor_id"] = cursor_id

    sql += " ORDER BY ps.id DESC LIMIT :limit"

    with get_conn() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    return [dict(r) for r in rows]


def browse_users_public(
    *,
    limit: int,
    cursor_id: Optional[int],
    cursor_primary: Optional[Any],
    q: Optional[str],
    sort: str,
    followers_of: Optional[int],
    following_of: Optional[int],
) -> List[Dict[str, Any]]:
    """
    Public user listing with filters and id-based cursor pagination (descending).
    Returns up to limit+1 rows to detect "has_more".
    """

    sql = """
        SELECT
            u.id,
            u.name,
            u.avatar_key,
            u.created_at,
            COALESCE(p.created_count, 0)    AS created_count,
            COALESCE(s.solved_count, 0)     AS solved_count,
            COALESCE(f.followers_count, 0)  AS followers_count
        FROM users u
        LEFT JOIN (
            SELECT author_id AS user_id, COUNT(*) AS created_count
            FROM puzzles
            GROUP BY author_id
        ) p ON p.user_id = u.id
        LEFT JOIN (
            SELECT user_id, COUNT(*) AS solved_count
            FROM puzzle_solves
            GROUP BY user_id
        ) s ON s.user_id = u.id
        LEFT JOIN (
            SELECT followee_id AS user_id, COUNT(*) AS followers_count
            FROM follows
            GROUP BY followee_id
        ) f ON f.user_id = u.id
        WHERE 1=1
    """
    params: Dict[str, Any] = {"limit": limit + 1}

    # búsqueda por nombre
    if q:
        sql += " AND u.name ILIKE :q_like"
        params["q_like"] = f"%{q}%"

    # filtro: usuarios que SIGUEN a followers_of
    if followers_of is not None:
        sql += """
            AND EXISTS (
                SELECT 1
                FROM follows fu
                WHERE fu.follower_id = u.id
                  AND fu.followee_id = :followers_of
            )
        """
        params["followers_of"] = followers_of

    # filtro: usuarios que son seguidos por following_of
    if following_of is not None:
        sql += """
            AND EXISTS (
                SELECT 1
                FROM follows fu
                WHERE fu.follower_id = :following_of
                  AND fu.followee_id = u.id
            )
        """
        params["following_of"] = following_of

    # cursor por id
    # cursor compuesto según el sort actual
    if cursor_primary is not None and cursor_id is not None:
        if sort == "followers_desc":
            sql += """
                AND (
                    COALESCE(f.followers_count, 0) < :cursor_primary
                    OR (
                        COALESCE(f.followers_count, 0) = :cursor_primary
                        AND u.id < :cursor_id
                    )
                )
            """
        elif sort == "created_desc":
            sql += """
                AND (
                    COALESCE(p.created_count, 0) < :cursor_primary
                    OR (
                        COALESCE(p.created_count, 0) = :cursor_primary
                        AND u.id < :cursor_id
                    )
                )
            """
        elif sort == "solved_desc":
            sql += """
                AND (
                    COALESCE(s.solved_count, 0) < :cursor_primary
                    OR (
                        COALESCE(s.solved_count, 0) = :cursor_primary
                        AND u.id < :cursor_id
                    )
                )
            """
        else:  # created_at_desc
            sql += """
                AND (
                    u.created_at < :cursor_primary
                    OR (
                        u.created_at = :cursor_primary
                        AND u.id < :cursor_id
                    )
                )
            """

        params["cursor_primary"] = cursor_primary
        params["cursor_id"] = cursor_id

    # fallback legacy: solo por id si vino un cursor viejo "123"
    elif cursor_id is not None:
        sql += " AND u.id < :cursor_id"
        params["cursor_id"] = cursor_id

    # sort
    if sort == "followers_desc":
        order_clause = "ORDER BY followers_count DESC, u.id DESC"
    elif sort == "created_desc":
        order_clause = "ORDER BY created_count DESC, u.id DESC"
    elif sort == "solved_desc":
        order_clause = "ORDER BY solved_count DESC, u.id DESC"
    else:
        # created_at_desc
        order_clause = "ORDER BY u.created_at DESC, u.id DESC"

    sql += f"""
        {order_clause}
        LIMIT :limit
    """

    with get_conn() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    return [dict(r) for r in rows]