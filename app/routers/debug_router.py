# app/routers/debug_router.py
from fastapi import APIRouter, Query
from collections import deque
from typing import Tuple, List
import random

router = APIRouter(prefix="/debug", tags=["debug"])

BOARD_SIZE = 3

# Un estado es una tupla de 9 números (3x3)
State = Tuple[int, ...]


def random_state() -> State:
    """
    Genera un estado aleatorio 3x3.
    No importa que no tenga sentido real, lo usamos para carga de CPU.
    """
    nums = [4, 5, 4, 9, 7, 4, 1, 2, 0]  # ejemplo tipo tu puzzle
    random.shuffle(nums)
    return tuple(nums)


def row_col_sums(state: State) -> Tuple[List[int], List[int]]:
    """
    Calcula la suma de cada fila y cada columna, similar a tus 'Current/Expected'.
    """
    rows = []
    cols = [0] * BOARD_SIZE

    for r in range(BOARD_SIZE):
        row_sum = 0
        for c in range(BOARD_SIZE):
            v = state[r * BOARD_SIZE + c]
            row_sum += v
            cols[c] += v
        rows.append(row_sum)

    return rows, cols


# Valores objetivo inventados, solo para que el solver tenga una condición:
TARGET_ROW_SUMS = [13, 6, 3]
TARGET_COL_SUMS = [0, 38, 27]


def is_goal(state: State) -> bool:
    rows, cols = row_col_sums(state)
    return rows == TARGET_ROW_SUMS and cols == TARGET_COL_SUMS


def neighbors(state: State) -> List[State]:
    """
    Genera estados vecinos simulando movimientos tipo Qiyi Klotski:
    - shift de filas izquierda/derecha
    - shift de columnas arriba/abajo
    """
    s = list(state)
    res: List[State] = []

    # --- shifts de filas ---
    for r in range(BOARD_SIZE):
        base = r * BOARD_SIZE
        row = s[base : base + BOARD_SIZE]

        # izquierda
        left = row[1:] + row[:1]
        new_left = s.copy()
        new_left[base : base + BOARD_SIZE] = left
        res.append(tuple(new_left))

        # derecha
        right = row[-1:] + row[:-1]
        new_right = s.copy()
        new_right[base : base + BOARD_SIZE] = right
        res.append(tuple(new_right))

    # --- shifts de columnas ---
    for c in range(BOARD_SIZE):
        col = [s[c + BOARD_SIZE * r] for r in range(BOARD_SIZE)]

        # arriba
        up = col[1:] + col[:1]
        new_up = s.copy()
        for r in range(BOARD_SIZE):
            new_up[c + BOARD_SIZE * r] = up[r]
        res.append(tuple(new_up))

        # abajo
        down = col[-1:] + col[:-1]
        new_down = s.copy()
        for r in range(BOARD_SIZE):
            new_down[c + BOARD_SIZE * r] = down[r]
        res.append(tuple(new_down))

    return res


def brute_force_solver(max_depth: int) -> int:
    """
    Hace una BFS limitada en profundidad sobre el espacio de estados.
    Devuelve cuántos nodos expandió (para que el endpoint tenga algún output).
    Solo CPU, nada de DB.
    """
    start = random_state()
    visited = {start}
    queue = deque([(start, 0)])
    expansions = 0

    while queue:
        state, depth = queue.popleft()
        expansions += 1

        if depth >= max_depth:
            continue

        for nb in neighbors(state):
            if nb in visited:
                continue
            visited.add(nb)
            # si quisieras parar al encontrar solución:
            # if is_goal(nb): return expansions
            queue.append((nb, depth + 1))

    return expansions


@router.get("/cpu-solver")
def cpu_solver_stress(
    iterations: int = Query(10, ge=1, le=200),
    max_depth: int = Query(7, ge=1, le=12),
):
    """
    Endpoint para pruebas de carga.
    Ejecuta varias veces un "solver" bruto de puzzles tipo Qiyi,
    para forzar uso de CPU en el backend.
    """
    total_expansions = 0
    for _ in range(iterations):
        total_expansions += brute_force_solver(max_depth=max_depth)

    return {
        "status": "ok",
        "iterations": iterations,
        "max_depth": max_depth,
        "nodes_expanded": total_expansions,
    }
