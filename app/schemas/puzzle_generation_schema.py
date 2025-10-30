from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict


class PuzzleGenConfig(BaseModel):
    # cuántos puzzles generar en esta llamada
    count: int = Field(ge=1, le=200, default=10)
    # tamaño del tablero
    N: int = Field(ge=2, le=10, default=4)
    # etiqueta opcional para guardar en DB
    difficulty: Optional[int] = None

    # dominio de números permitidos (>=2). Si None -> [2..9]
    allowed_numbers: Optional[List[int]] = None

    # especificación de operadores:
    #   ["+", null]  => ilimitado
    #   ["*", 2]     => exactamente 2
    operators_spec: List[Tuple[str, Optional[int]]]

    # si True, fuerza unicidad (corta solver con max_solutions=2)
    require_unique: bool = True
    # intentos máximos para encontrar 'count' puzzles que cumplan
    max_attempts: int = 500

    # incluir soluciones en board_spec
    include_solutions: bool = True
    # límite opcional de soluciones a serializar (None = todas las cacheadas)
    solutions_cap: Optional[int] = None

    # 👉 Esto controla el "Example Value" que ves en Swagger
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "count": 1,
            "N": 4,
            "difficulty": None,
            "allowed_numbers": None,
            "operators_spec": [
                ["+"], ["-"]              # arrays porque OpenAPI serializa Tuple como array
            ],
            "require_unique": True,
            "max_attempts": 500,
            "include_solutions": True,
            "solutions_cap": 1
        }
    })




class GenerateAck(BaseModel):
    requested: int
    inserted: int
    attempts: int
    difficulty: Optional[int] = None
    N: int

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "requested": 1,
            "inserted": 1,
            "attempts": 1,
            "difficulty": None,
            "N": 4
        }
    })



generate_puzzles_responses = {
    201: {
        "description": "Puzzles generated",
        "content": {
            "application/json": {
                "example": {
                    "requested": 1,
                    "inserted": 1,
                    "attempts": 1,
                    "difficulty": None,
                    "N": 4
                }
            }
        },
    },
    403: {
        "description": "Forbidden",
        "content": {"application/json": {"example": {"detail": "Forbidden"}}},
    },
    422: {
        "description": "Validation Error"
    },
}