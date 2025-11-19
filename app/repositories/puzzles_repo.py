from datetime import date
from typing import Optional, Dict, Any, List
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB

from ..db import get_tx, get_conn
ALGORITHM_AUTHOR_ID = 1  # puzzles generados por el algoritmo (usuario Kiwi)


def insert_puzzle(
    *, author_id: int, title: str, size: int,
    board_spec: Dict[str, Any], difficulty: Optional[int],
    num_solutions: Optional[int]
) -> dict:
    sql = text("""
        INSERT INTO puzzles (author_id, title, size, board_spec, difficulty, num_solutions)
        VALUES (:author_id, :title, :size, :board_spec, :difficulty, :num_solutions)
        RETURNING id, author_id, title, size, board_spec, difficulty, num_solutions, created_at;
    """).bindparams(
        bindparam("board_spec", type_=JSONB)  # <- clave: tipa el parámetro como JSONB
    )

    with get_tx() as conn:
        row = conn.execute(sql, {
            "author_id": author_id,
            "title": title,
            "size": size,
            "board_spec": board_spec,        # dict -> JSONB
            "difficulty": difficulty,
            "num_solutions": num_solutions,
        }).mappings().first()

    return dict(row)



def list_puzzles_ssg_seed(limit: int = 200) -> list[dict]:
    sql = text("""
        SELECT id, title
        FROM puzzles
        ORDER BY id
        LIMIT :limit
    """)
    with get_conn() as conn:
        rows = conn.execute(sql, {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]


def get_puzzle_by_id(puzzle_id: int) -> dict | None:
    sql = text("""
        SELECT
            p.id,
            p.author_id,
            p.title,
            p.size,
            p.board_spec,
            p.num_solutions,
            p.difficulty,
            p.created_at,
            u.name  AS author_name,
            u.avatar_key AS author_avatar_key
        FROM puzzles p
        LEFT JOIN users u ON u.id = p.author_id
        WHERE p.id = :puzzle_id
    """)
    with get_conn() as conn:
        row = conn.execute(sql, {"puzzle_id": puzzle_id}).mappings().first()
    return dict(row) if row else None



def get_puzzle_author_id(puzzle_id: int) -> Optional[int]:
    sql = text("SELECT author_id FROM puzzles WHERE id = :id")
    with get_conn() as conn:
        row = conn.execute(sql, {"id": puzzle_id}).first()
    return None if not row else row[0]

def update_puzzle_owned(
    *, puzzle_id: int, author_id: int,
    title: Optional[str], size: Optional[int],
    board_spec: Optional[Dict[str, Any]],
    difficulty: Optional[int], num_solutions: Optional[int],
) -> Optional[dict]:
    """
    Actualiza solo si el puzzle pertenece a 'author_id'.
    Devuelve la fila actualizada con campos mínimos (o None si no coincidió).
    """
    sets = []
    params: Dict[str, Any] = {"id": puzzle_id, "author_id": author_id}

    if title is not None:
        sets.append("title = :title")
        params["title"] = title
    if size is not None:
        sets.append("size = :size")
        params["size"] = size
    if board_spec is not None:
        sets.append("board_spec = :board_spec")
        params["board_spec"] = board_spec
    if difficulty is not None:
        sets.append("difficulty = :difficulty")
        params["difficulty"] = difficulty
    if num_solutions is not None:
        sets.append("num_solutions = :num_solutions")
        params["num_solutions"] = num_solutions

    if not sets:
        return None  # nada que actualizar

    sql = text(f"""
        UPDATE puzzles
        SET {', '.join(sets)}
        WHERE id = :id AND author_id = :author_id
        RETURNING id, author_id, title
    """)
    # tipa JSONB si corresponde
    if board_spec is not None:
        sql = sql.bindparams(bindparam("board_spec", type_=JSONB))

    with get_tx() as conn:
        row = conn.execute(sql, params).mappings().first()
    return None if not row else dict(row)


def puzzle_has_daily_reference(puzzle_id: int) -> bool:
    sql = text("SELECT 1 FROM daily_puzzles WHERE puzzle_id = :pid LIMIT 1")
    with get_conn() as conn:
        row = conn.execute(sql, {"pid": puzzle_id}).first()
    return row is not None

def delete_puzzle_owned(puzzle_id: int, author_id: int) -> bool:
    """
    Borra el puzzle si pertenece al author_id. Devuelve True si eliminó 1 fila.
    """
    sql = text("""
        DELETE FROM puzzles
        WHERE id = :id AND author_id = :author_id
        RETURNING id
    """)
    with get_tx() as conn:
        row = conn.execute(sql, {"id": puzzle_id, "author_id": author_id}).first()
    return row is not None




def browse_puzzles_public(
    *,
    limit: int,
    cursor_id: Optional[int],
    size: Optional[int],
    q: Optional[str],
    sort: str,
    min_likes: Optional[int],
    author_id: Optional[int],
    generated_by: Optional[str],
    operators: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """
    Public puzzle listing with filters and id-based cursor pagination (descending).
    Returns up to limit+1 rows to detect "has_more".
    """

    sql = """
        SELECT
            p.id,
            p.title,
            p.size,
            p.difficulty,
            p.created_at,
            u.id          AS author_id,
            u.name        AS author_name,
            u.avatar_key  AS author_avatar_key,
            COUNT(DISTINCT pl.id) AS likes_count,
            COUNT(DISTINCT ps.id) AS solves_count,
            p.board_spec->'operators' AS operators_raw
        FROM puzzles p
        LEFT JOIN users u          ON u.id = p.author_id
        LEFT JOIN puzzle_likes pl  ON pl.puzzle_id = p.id
        LEFT JOIN puzzle_solves ps ON ps.puzzle_id = p.id
        WHERE 1=1
    """
    params: Dict[str, Any] = {"limit": limit + 1}

    # size filter
    if size is not None:
        sql += " AND p.size = :size"
        params["size"] = size

    # free-text search by title
    if q:
        sql += " AND p.title ILIKE :q_like"
        params["q_like"] = f"%{q}%"

    # author filter
    if author_id is not None:
        sql += " AND p.author_id = :author_id"
        params["author_id"] = author_id

    # generatedBy filter: algorithm vs user
    if generated_by == "algorithm":
        sql += " AND p.author_id = :algo_author_id"
        params["algo_author_id"] = ALGORITHM_AUTHOR_ID
    elif generated_by == "user":
        sql += " AND (p.author_id IS NULL OR p.author_id <> :algo_author_id)"
        params["algo_author_id"] = ALGORITHM_AUTHOR_ID

    # operators filter using board_spec->'operators'
    if operators:
        op_map = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
        all_ops_pg = ["+", "-", "*", "/"]

        # operators selected in JSON symbol form
        selected_pg_ops = [op_map[o] for o in operators if o in op_map]

        if selected_pg_ops:
            # disallow any operator that is not selected
            disallowed = [op for op in all_ops_pg if op not in selected_pg_ops]
            if disallowed:
                sql += " AND NOT ((p.board_spec->'operators') ?| :disallowed_ops)"
                params["disallowed_ops"] = disallowed

            # require that all selected operators are present
            sql += " AND (p.board_spec->'operators') ?& :required_ops"
            params["required_ops"] = selected_pg_ops

    # cursor-based pagination
    if cursor_id:
        sql += " AND p.id < :cursor_id"
        params["cursor_id"] = cursor_id

    sql += """
        GROUP BY
            p.id,
            p.title,
            p.size,
            p.difficulty,
            p.created_at,
            u.id,
            u.name,
            u.avatar_key,
            p.board_spec->'operators'
    """

    # minimum likes filter
    if min_likes is not None:
        sql += " HAVING COUNT(DISTINCT pl.id) >= :min_likes"
        params["min_likes"] = min_likes

    # sort clause
    if sort == "likes_desc":
        order_clause = "ORDER BY likes_count DESC, p.id DESC"
    elif sort == "difficulty_desc":
        order_clause = "ORDER BY p.difficulty DESC NULLS LAST, p.id DESC"
    elif sort == "difficulty_asc":
        order_clause = "ORDER BY p.difficulty ASC NULLS LAST, p.id DESC"
    elif sort == "size_desc":
        order_clause = "ORDER BY p.size DESC, p.id DESC"
    else:
        order_clause = "ORDER BY p.created_at DESC, p.id DESC"

    sql += f"""
        {order_clause}
        LIMIT :limit
    """

    with get_conn() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    return [dict(r) for r in rows]


def puzzle_exists(puzzle_id: int) -> bool:
    sql = text("SELECT 1 FROM puzzles WHERE id = :id")
    with get_conn() as conn:
        row = conn.execute(sql, {"id": puzzle_id}).first()
    return row is not None

def create_puzzle_like(user_id: int, puzzle_id: int) -> bool:
    """
    Crea el like si no existe. Devuelve True si se insertó, False si ya existía.
    """
    sql = text("""
        INSERT INTO puzzle_likes (user_id, puzzle_id)
        VALUES (:user_id, :puzzle_id)
        ON CONFLICT (user_id, puzzle_id) DO NOTHING
        RETURNING id;
    """)
    with get_tx() as conn:
        row = conn.execute(sql, {"user_id": user_id, "puzzle_id": puzzle_id}).first()
    return row is not None


def delete_puzzle_like(user_id: int, puzzle_id: int) -> bool:
    """
    Elimina el like si existe.
    Devuelve True si borró una fila (changed), False si no existía (idempotente).
    """
    sql = text("""
        DELETE FROM puzzle_likes
        WHERE user_id = :user_id AND puzzle_id = :puzzle_id
        RETURNING id;
    """)
    with get_tx() as conn:
        row = conn.execute(sql, {"user_id": user_id, "puzzle_id": puzzle_id}).first()
    return row is not None


def count_puzzle_likes(puzzle_id: int) -> int:
    sql = text("SELECT COUNT(*) AS c FROM puzzle_likes WHERE puzzle_id = :pid")
    with get_conn() as conn:
        row = conn.execute(sql, {"pid": puzzle_id}).mappings().first()
    return int(row["c"]) if row else 0


def insert_puzzle_solve(
    *, user_id: int, puzzle_id: int, movements: int, duration_ms: int, solution: Optional[Dict[str, Any]]
) -> dict:
    sql = text("""
        INSERT INTO puzzle_solves (user_id, puzzle_id, movements, duration_ms, solution)
        VALUES (:user_id, :puzzle_id, :movements, :duration_ms, :solution)
        RETURNING id, user_id, puzzle_id, movements, duration_ms, solution, created_at;
    """)
    # Tipar JSONB para evitar problemas de binding
    if solution is not None:
        sql = sql.bindparams(bindparam("solution", type_=JSONB))

    with get_tx() as conn:
        row = conn.execute(sql, {
            "user_id": user_id,
            "puzzle_id": puzzle_id,
            "movements": movements,
            "duration_ms": duration_ms,
            "solution": solution,
        }).mappings().first()
    return dict(row)



def list_my_solves_for_puzzle(
    *, user_id: int, puzzle_id: int, limit: int, cursor_id: Optional[int]
) -> List[Dict[str, Any]]:
    """
    Lista solves del usuario para un puzzle, ordenados por puzzle_solves.id DESC (keyset).
    Retorna hasta limit+1 filas para detectar next page.
    """
    sql = """
        SELECT
            ps.id,
            ps.movements,
            ps.duration_ms,
            ps.solution,
            ps.created_at
        FROM puzzle_solves ps
        WHERE ps.user_id = :user_id
          AND ps.puzzle_id = :puzzle_id
    """
    params: Dict[str, Any] = {
        "user_id": user_id,
        "puzzle_id": puzzle_id,
        "limit": limit + 1,
    }

    if cursor_id:
        sql += " AND ps.id < :cursor_id"
        params["cursor_id"] = cursor_id

    sql += " ORDER BY ps.id DESC LIMIT :limit"

    with get_conn() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    return [dict(r) for r in rows]



def get_daily_puzzle_by_date(d: date) -> dict | None:
    sql = text("""
        SELECT
            dp.date                         AS dp_date,
            p.id                            AS puzzle_id,
            p.title                         AS puzzle_title,
            p.size                          AS puzzle_size,
            p.difficulty                    AS puzzle_difficulty,
            p.created_at                    AS puzzle_created_at,
            u.id                            AS author_id,
            u.name                          AS author_name,
            u.avatar_key                    AS author_avatar_key
        FROM daily_puzzles dp
        JOIN puzzles p ON p.id = dp.puzzle_id
        LEFT JOIN users u ON u.id = p.author_id
        WHERE dp.date = :d
        LIMIT 1
    """)
    with get_conn() as conn:
        row = conn.execute(sql, {"d": d}).mappings().first()
    return dict(row) if row else None



def get_daily_puzzle_by_date(d: date) -> dict | None:
    sql = text("""
        SELECT
            dp.id               AS dp_id,
            dp.date             AS dp_date,
            dp.created_at       AS dp_created_at,
            p.id                AS puzzle_id,
            p.title             AS puzzle_title,
            p.size              AS puzzle_size,
            p.difficulty        AS puzzle_difficulty,
            p.created_at        AS puzzle_created_at,
            u.id                AS author_id,
            u.name              AS author_name,
            u.avatar_key        AS author_avatar_key
        FROM daily_puzzles dp
        JOIN puzzles p ON p.id = dp.puzzle_id
        LEFT JOIN users u ON u.id = p.author_id
        WHERE dp.date = :d
        LIMIT 1
    """)
    with get_conn() as conn:
        row = conn.execute(sql, {"d": d}).mappings().first()
    return dict(row) if row else None


def pick_unused_generated_puzzle(limit: int = 50) -> Optional[int]:
    """
    Devuelve un puzzle.id cuyo author_id = -1 y que NO esté referenciado en daily_puzzles.
    Se prefiere uno reciente. Si no hay, retorna None.
    """
    sql = text("""
        SELECT p.id
        FROM puzzles p
        LEFT JOIN daily_puzzles dp ON dp.puzzle_id = p.id
        WHERE p.author_id = -1
          AND dp.puzzle_id IS NULL
        ORDER BY p.created_at DESC
        LIMIT :limit
    """)
    with get_conn() as conn:
        rows = conn.execute(sql, {"limit": limit}).fetchall()
    if not rows:
        return None
    # elige el primero (más reciente). Si prefieres aleatorio,
    # usa ORDER BY RANDOM() LIMIT 1 en la query.
    return int(rows[0][0])


def upsert_daily_puzzle(d: date, puzzle_id: int) -> bool:
    """
    Inserta (date, puzzle_id) en daily_puzzles si la fecha no existe todavía.
    Devuelve True si insertó, False si ya existía.
    """
    sql = text("""
        INSERT INTO daily_puzzles (date, puzzle_id)
        VALUES (:d, :pid)
        ON CONFLICT (date) DO NOTHING
        RETURNING id
    """)
    with get_tx() as conn:
        row = conn.execute(sql, {"d": d, "pid": puzzle_id}).first()
    return row is not None