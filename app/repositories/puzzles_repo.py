from typing import Optional, Dict, Any
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB

from ..db import get_tx

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
