from typing import Optional, Dict, Any
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