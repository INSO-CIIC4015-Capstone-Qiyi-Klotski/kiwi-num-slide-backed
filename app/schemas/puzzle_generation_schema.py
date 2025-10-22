from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

class PuzzleGenConfig(BaseModel):
    # cuántos puzzles generar en esta llamada
    count: int = Field(ge=1, le=200, default=10)
    # tamaño del tablero
    N: int = Field(ge=2, le=10, default=4)
    # etiqueta opcional para guardar en DB
    difficulty: Optional[int] = None

    # dominio de números permitidos (>=2). Si None -> [2..9]
    allowed_numbers: Optional[List[int]] = None

    # especificación de operadores. Se permite:
    #   ["+", null]  => ilimitado
    #   ["*", 2]     => exactamente 2
    operators_spec: List[Tuple[str, Optional[int]]]

    # si True, intenta que cada puzzle tenga exactamente 1 solución (corta con max_solutions=2)
    require_unique: bool = True
    # intentos máximos para encontrar 'count' puzzles que cumplan
    max_attempts: int = 500

    # NUEVO: incluir soluciones en board_spec
    include_solutions: bool = True
    # NUEVO: límite opcional de soluciones a serializar (None = todas las cacheadas)
    solutions_cap: Optional[int] = None
