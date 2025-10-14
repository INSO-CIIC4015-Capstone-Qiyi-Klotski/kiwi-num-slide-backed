from typing import Optional, Dict, Any, List
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB

from ..db import get_tx, get_conn


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
    *, limit: int, cursor_id: Optional[int], size: Optional[int], q: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Lista puzzles públicos (ligeros) con filtros y paginación por id DESC.
    Retorna hasta limit+1 filas para detectar 'has_more'.
    """
    sql = """
        SELECT
            p.id,
            p.title,
            p.size,
            p.difficulty,
            p.created_at,
            u.id   AS author_id,
            u.name AS author_name,
            u.avatar_key AS author_avatar_key
        FROM puzzles p
        LEFT JOIN users u ON u.id = p.author_id
        WHERE 1=1
    """
    params: Dict[str, Any] = {"limit": limit + 1}

    if size is not None:
        sql += " AND p.size = :size"
        params["size"] = size

    if q:
        sql += " AND p.title ILIKE :q_like"
        params["q_like"] = f"%{q}%"

    if cursor_id:
        sql += " AND p.id < :cursor_id"
        params["cursor_id"] = cursor_id

    sql += " ORDER BY p.id DESC LIMIT :limit"

    with get_conn() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    return [dict(r) for r in rows]