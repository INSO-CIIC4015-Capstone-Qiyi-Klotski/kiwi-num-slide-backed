# app/services/puzzle_generation.py

from __future__ import annotations

import random
from collections import Counter
from datetime import date
from fractions import Fraction
from hashlib import sha256
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.repositories import puzzles_repo


# =========================
# Fraction <-> String I/O
# =========================

def _fraction_to_string(fr: Fraction) -> str:
    """
    Convert a Fraction into a canonical string form for JSON storage.

    Rules:
      - If denominator is 1, return just the integer part (e.g., 10/1 -> "10").
      - Otherwise return "numerator/denominator" (e.g., -11/4 -> "-11/4").
    """
    return str(fr.numerator) if fr.denominator == 1 else f"{fr.numerator}/{fr.denominator}"


def _string_to_fraction(s: str) -> Fraction:
    """
    Parse a canonical fraction string ("a/b" or "a") back into a Fraction.

    Raises:
      ValueError if the format is invalid.
    """
    s = s.strip()
    if "/" in s:
        n, d = s.split("/", 1)
        return Fraction(int(n), int(d))
    return Fraction(int(s), 1)


# =========================
# Core Puzzle Generator
# =========================

class Puzzle:
    """
    N×N arithmetic-slide puzzle generator WITHOUT storing '1' as a blank tile.
    The cell at (N-1, N-1) is ALWAYS the empty space in the solution.

    Board encoding:
      - numbers: flat list with N*N-1 integers (the blank cell is not included).
      - operators: flat list with (2*N*(N-1) - 2) operators because the two operators
                   adjacent to the bottom-right blank are removed:
          * between-columns (horizontals): N rows → (N-1) per row EXCEPT the last row
            which has (N-2).
          * between-rows (vertical levels between row r and r+1): (N-1) levels →
            N per level EXCEPT the last level which has (N-1) (no operator in the last
            column at the bottom level).
      - expected: list of length 2*N with row targets followed by column targets.
                  The last row/last column are evaluated with N-1 values and N-2 operators
                  (because the bottom-right corner is the blank).

    Notes:
      - This class builds a puzzle instance and can solve it via backtracking.
      - Uniqueness (exactly one solution) is decided externally by limiting the solver.
    """

    # Default operator spec if none is provided: unlimited '+' and '-'.
    DEFAULT_OP_SPEC: List[Tuple[str, ...]] = [('+',), ('-',)]

    def __init__(
        self,
        N: int,
        *,
        seed: Optional[int] = None,
        use_daily_seed: bool = True,
        shuffle_after_expected: bool = True,
        operators_spec: Optional[List[Tuple[str, Optional[int]]]] = None,
        numbers_choices: Optional[List[int]] = None,
    ) -> None:
        """
        Initialize a puzzle instance.

        Args:
          N: Board size (N×N).
          seed: Optional random seed. If None and use_daily_seed=True, a deterministic
                daily seed is derived from (today, N).
          use_daily_seed: If True and seed=None, the same inputs reproduce the same
                          puzzle on that day.
          shuffle_after_expected: If True, shuffle 'numbers' after computing expected,
                                  to randomize the visual layout while preserving math.
          operators_spec: Operator specification:
                            [ ('+', None), ('-', None), ('*', 2), ('/', 2) ]
                          A 1-tuple ('+',) or ('*',) also means unlimited.
                          A 2-tuple with an integer count means an exact amount.
          numbers_choices: Allowed domain for numbers (>=2). If None, uses [2..9].
        """
        if N < 2:
            raise ValueError("N must be >= 2 in this fixed-blank mode.")

        if seed is None and use_daily_seed:
            seed = self._daily_seed(f"{date.today().isoformat()}-{N}")
        self._rng = random.Random(seed)

        self.N = N
        self.op_exact, self.op_unlimited = self._normalize_op_spec(
            operators_spec or self.DEFAULT_OP_SPEC
        )
        self._numbers_choices = self._normalize_number_choices(numbers_choices)

        # (1) Generate numbers WITHOUT the blank.
        self.numbers = self._gen_numbers_without_blank()

        # (2) Generate operators respecting the two missing ones adjacent to the bottom-right blank.
        #     Internally we keep per-row/per-level structures and also a flattened view.
        self._hops_per_row: List[List[str]] = []     # lengths: [N-1, N-1, ..., N-2]
        self._vops_per_level: List[List[str]] = []   # lengths: [N,   N,   ..., N-1]
        self.operators = self._gen_operators()

        # (3) Compute expected targets with standard precedence and truncated edges.
        self.expected = self._compute_expected()  # List[Fraction]

        if shuffle_after_expected:
            self._rng.shuffle(self.numbers)

        # Cache for solved boards (each is a flat N*N-1 list laid row-wise, omitting the final blank).
        self.solutions: List[List[int]] = []

    # ---------- Seeds & Normalization ----------

    @staticmethod
    def _daily_seed(key: str) -> int:
        return int(sha256(key.encode()).hexdigest(), 16) % (2**32)

    @staticmethod
    def _normalize_op_spec(
        spec: List[Tuple[str, Optional[int]]]
    ) -> Tuple[Dict[str, int], List[str]]:
        valid_ops = {'+', '-', '*', '/'}
        op_exact: Dict[str, int] = {}
        op_unlimited: List[str] = []

        if not spec:
            raise ValueError("operators_spec cannot be empty.")

        for tup in spec:
            if not (1 <= len(tup) <= 2):
                raise ValueError(f"Invalid tuple in operators_spec: {tup}")

            op = tup[0]
            if op not in valid_ops:
                raise ValueError(f"Invalid operator '{op}'. Allowed: {sorted(valid_ops)}")

            if len(tup) == 1:
                op_unlimited.append(op)
            else:
                count = tup[1]
                if count is None:
                    op_unlimited.append(op)
                else:
                    if not isinstance(count, int) or count < 0:
                        raise ValueError(
                            f"Invalid count for '{op}': {count}. Must be int >= 0 or null."
                        )
                    op_exact[op] = count

        for op in list(op_exact.keys()):
            if op in op_unlimited:
                raise ValueError(f"'{op}' cannot be both exact and unlimited.")

        if not op_exact and not op_unlimited:
            raise ValueError("At least one operator must be defined (exact or unlimited).")

        return op_exact, op_unlimited

    @staticmethod
    def _normalize_number_choices(choices: Optional[List[int]]) -> List[int]:
        if choices is None:
            return list(range(2, 10))
        if not isinstance(choices, list) or len(choices) == 0:
            raise ValueError("numbers_choices must be a non-empty list or None.")
        cleaned = []
        for v in choices:
            if not isinstance(v, int):
                raise ValueError(f"numbers_choices contains a non-integer value: {v}")
            if v < 2:
                raise ValueError(f"numbers_choices contains a value < 2: {v}")
            cleaned.append(v)
        return cleaned

    # ---------- Generation ----------

    def _gen_numbers_without_blank(self) -> List[int]:
        """
        Sample N*N-1 numbers from the domain (with replacement).
        The cell (N-1, N-1) IS the space; no '1' or any placeholder is added.
        """
        total = self.N * self.N - 1
        return [self._rng.choice(self._numbers_choices) for _ in range(total)]

    def _gen_operators(self) -> List[str]:
        """
        Build the operator mesh with TWO operators missing adjacent to the blank:
          - Last row: (N-2) between-columns operators (the rightmost one is missing).
          - Last vertical level (between last two rows): (N-1) between-rows operators
            (the one in the last column is missing).

        Process:
          1) Compute total: total = 2*N*(N-1) - 2.
          2) Place exact-count operators.
          3) Fill the remaining with unlimited operators.
          4) Distribute into:
             - self._hops_per_row  (N lists; lengths [N-1]*(N-1) + [N-2])
             - self._vops_per_level (N-1 lists; lengths [N]*(N-2) + [N-1])
          5) Flatten using the same pattern as the visual layout:
             for r in 0..N-2: between-columns of row r, then between-rows of level r;
             finally: between-columns of the last row.
        """
        N = self.N
        if N < 2:
            return []

        total = 2 * N * (N - 1) - 2
        if total == 0:
            self._hops_per_row = [[] for _ in range(N)]
            self._vops_per_level = [[] for _ in range(N - 1)]
            return []

        exact_sum = sum(self.op_exact.values())
        if exact_sum > total:
            raise ValueError(
                f"Sum of exact operator counts ({exact_sum}) exceeds required total ({total})."
            )

        remaining = total - exact_sum
        if remaining > 0 and len(self.op_unlimited) == 0:
            raise ValueError(
                f"{remaining} operators missing and no unlimited operators to fill them."
            )

        # Build a pool with the desired counts.
        ops_pool: List[str] = []
        for op, cnt in self.op_exact.items():
            if cnt > 0:
                ops_pool.extend([op] * cnt)
        for _ in range(remaining):
            ops_pool.append(random.choice(self.op_unlimited))
        random.shuffle(ops_pool)  # avoid patterned placement

        # Target structure lengths:
        # between-columns per row
        h_lengths = [N - 1] * (N - 1) + [N - 2]   # last row has one fewer
        # between-rows per level (between row r and r+1)
        v_lengths = [N] * (N - 2) + [N - 1]       # last level has one fewer

        # Fill structures from the shuffled pool in deterministic order.
        it = iter(ops_pool)

        self._hops_per_row = []
        for L in h_lengths:
            self._hops_per_row.append([next(it) for _ in range(L)])

        self._vops_per_level = []
        for L in v_lengths:
            self._vops_per_level.append([next(it) for _ in range(L)])

        # Flatten as: [h_row0, v_level0, h_row1, v_level1, ... , h_row_{N-2}, v_level_{N-2}, h_row_{N-1}]
        flat: List[str] = []
        for r in range(N - 1):
            flat.extend(self._hops_per_row[r])
            flat.extend(self._vops_per_level[r])
        flat.extend(self._hops_per_row[N - 1])
        return flat

    # ---------- Expression Evaluation ----------

    @staticmethod
    def _apply_mul_div(a: Fraction, b: Fraction, op: str) -> Optional[Fraction]:
        if op == '*':
            return a * b
        if op == '/':
            if b == 0:
                return None
            return a / b
        raise ValueError(f"Invalid operator in _apply_mul_div: {op}")

    @staticmethod
    def _eval_line_with_precedence(values: List[int], ops: List[str]) -> Optional[Fraction]:
        """
        Evaluate a row/column expression with standard precedence (*, / before +, -).
        """
        assert len(values) >= 1 and len(ops) == len(values) - 1

        # Pass 1: collapse * and / left-to-right.
        tmp_vals: List[Fraction] = [Fraction(values[0])]
        tmp_ops: List[str] = []
        for i, op in enumerate(ops):
            b = Fraction(values[i + 1])
            if op in ('*', '/'):
                a = tmp_vals.pop()
                res = Puzzle._apply_mul_div(a, b, op)
                if res is None:
                    return None
                tmp_vals.append(res)
            else:
                tmp_vals.append(b)
                tmp_ops.append(op)

        # Pass 2: apply + and - on the reduced list.
        acc = tmp_vals[0]
        j = 1
        for op in tmp_ops:
            if op == '+':
                acc += tmp_vals[j]
            elif op == '-':
                acc -= tmp_vals[j]
            else:
                raise ValueError(f"Invalid operator: {op}")
            j += 1
        return acc

    # ---------- Operator accessors (with two absences) ----------

    def _row_ops(self, r: int) -> List[str]:
        """
        Return the between-columns operators for row r.
        The last row has N-2 operators.
        """
        return self._hops_per_row[r][:]

    def _col_ops(self, c: int) -> List[str]:
        """
        Return the between-rows operators for column c (top to bottom), by traversing levels.
        The last level has no operator for the last column. Therefore:
          - if c < N-1 → length N-1
          - if c == N-1 → length N-2
        """
        ops: List[str] = []
        # levels 0..N-3 have N columns
        for level in range(self.N - 2):
            ops.append(self._vops_per_level[level][c])
        # last level (N-2) has columns 0..N-2
        if c < self.N - 1:
            if c <= self.N - 2:
                ops.append(self._vops_per_level[self.N - 2][c])
        return ops

    # ---------- Expected Targets ----------

    def _compute_expected(self) -> List[Fraction]:
        """
        Compute row and column targets with bottom-right blank
        and without the two adjacent operators.
        """
        N = self.N
        b = self.numbers  # length N*N-1

        expected_rows: List[Fraction] = []
        for r in range(N):
            start = r * N
            if r < N - 1:
                vals = b[start:start + N]          # full N values
                ops = self._row_ops(r)             # N-1 operators
            else:
                # last row: only N-1 values (the last cell is blank)
                vals = b[start:start + (N - 1)]
                ops = self._row_ops(r)             # N-2 operators
            if len(vals) == 0:
                raise ValueError("Empty row; N must be >= 2.")
            if len(ops) != len(vals) - 1:
                raise ValueError("Row/ops mismatch while computing expected.")
            res = self._eval_line_with_precedence(vals, ops)
            if res is None:
                raise ValueError("Division by zero while computing expected (row).")
            expected_rows.append(res)

        expected_cols: List[Fraction] = []
        for c in range(N):
            if c < N - 1:
                # full column (N values)
                vals = [b[r * N + c] for r in range(N)]
                ops = self._col_ops(c)             # N-1 operators
            else:
                # last column: only N-1 values (the last cell is blank)
                vals = [b[r * N + c] for r in range(N - 1)]
                ops = self._col_ops(c)             # N-2 operators
            if len(vals) == 0:
                raise ValueError("Empty column; N must be >= 2.")
            if len(ops) != len(vals) - 1:
                raise ValueError("Column/ops mismatch while computing expected.")
            res = self._eval_line_with_precedence(vals, ops)
            if res is None:
                raise ValueError("Division by zero while computing expected (column).")
            expected_cols.append(res)

        return expected_rows + expected_cols

    # ---------- Board Helpers ----------

    @staticmethod
    def _idx_to_rc(idx: int, N: int) -> Tuple[int, int]:
        return divmod(idx, N)

    def _row_values(self, board: List[Optional[int]], r: int) -> List[int]:
        """
        Return NUMERIC values for row r under the new model:
          - rows 0..N-2: N values
          - row N-1: N-1 values (the final corner is blank)
        """
        N = self.N
        start = r * N
        if r < N - 1:
            seg = board[start:start + N]
        else:
            seg = board[start:start + (N - 1)]
        # The board never places the final blank; by design there should be no None here when validating
        return [int(v) for v in seg]

    def _col_values(self, board: List[Optional[int]], c: int) -> List[int]:
        """
        Return NUMERIC values for column c under the new model:
          - columns 0..N-2: N values
          - column N-1: N-1 values (the final corner is blank)
        """
        N = self.N
        if c < N - 1:
            vals = [board[r * N + c] for r in range(N)]
        else:
            vals = [board[r * N + c] for r in range(N - 1)]
        return [int(v) for v in vals]

    def _row_is_valid(self, board: List[Optional[int]], r: int) -> bool:
        vals = self._row_values(board, r)
        ops = self._row_ops(r)
        res = self._eval_line_with_precedence(vals, ops)
        target = self.expected[r]
        return res is not None and res == target

    def _col_is_valid(self, board: List[Optional[int]], c: int) -> bool:
        vals = self._col_values(board, c)
        ops = self._col_ops(c)
        res = self._eval_line_with_precedence(vals, ops)
        target = self.expected[self.N + c]
        return res is not None and res == target

    # ---------- Equality ----------

    def is_equal_to(self, other: "Puzzle") -> bool:
        if not isinstance(other, Puzzle):
            return False
        return (
            self.N == other.N
            and self.operators == other.operators
            and self.expected == other.expected
            and Counter(self.numbers) == Counter(other.numbers)
        )

    # ---------- Solver (Backtracking + MRV-ish) ----------

    def solve_all(self, max_solutions: Optional[int] = None, store: bool = False) -> List[List[int]]:
        """
        Backtracking that places exactly N*N-1 cells (all except (N-1, N-1)).

        Heuristics:
          - MRV-ish: try numbers with the lowest remaining count first.
        """
        N = self.N

        # Indices to fill (omit the bottom-right corner)
        fill_order: List[int] = [i for i in range(N * N) if i != (N * N - 1)]

        board: List[Optional[int]] = [None] * (N * N)
        pool = Counter(self.numbers)
        solutions: List[List[int]] = []

        # Helpers to know when a row/column becomes "complete" under the new rules
        def completes_row(idx: int) -> Optional[int]:
            r, c = self._idx_to_rc(idx, N)
            # rows 0..N-2: complete when c == N-1
            if r < N - 1 and c == N - 1:
                return r
            # last row: complete when c == N-2 (final cell is blank)
            if r == N - 1 and c == N - 2:
                return r
            return None

        def completes_col(idx: int) -> Optional[int]:
            r, c = self._idx_to_rc(idx, N)
            # columns 0..N-2: complete when r == N-1
            if c < N - 1 and r == N - 1:
                return c
            # last column: complete when r == N - 2 (final cell is blank)
            if c == N - 1 and r == N - 2:
                return c
            return None

        def place(k: int) -> None:
            if k == len(fill_order):
                # Extract a flat solution “without blank” (row-wise, omitting the last cell)
                sol = [board[i] for i in fill_order]
                solutions.append([int(v) for v in sol])
                return

            idx = fill_order[k]

            candidates = [v for v, cnt in pool.items() if cnt > 0]
            candidates.sort(key=lambda v: (pool[v], v))

            for val in candidates:
                board[idx] = val
                pool[val] -= 1

                # Boundary validations when a row/col completes
                rr = completes_row(idx)
                if rr is not None and not self._row_is_valid(board, rr):
                    pool[val] += 1
                    board[idx] = None
                    continue

                cc = completes_col(idx)
                if cc is not None and not self._col_is_valid(board, cc):
                    pool[val] += 1
                    board[idx] = None
                    continue

                place(k + 1)

                if max_solutions is not None and len(solutions) >= max_solutions:
                    pool[val] += 1
                    board[idx] = None
                    return

                pool[val] += 1
                board[idx] = None

        place(0)

        if store:
            self.solutions = [sol[:] for sol in solutions]
        return solutions

    def solve_and_cache(self, max_solutions: Optional[int] = None) -> List[List[int]]:
        return self.solve_all(max_solutions=max_solutions, store=True)

    def clear_solutions(self) -> None:
        self.solutions = []

    def num_solutions_cached(self) -> int:
        return len(self.solutions)

    def get_cached_solutions(self) -> List[List[int]]:
        return [s[:] for s in self.solutions]

    def solve_flat(self, max_solutions: Optional[int] = None) -> List[List[int]]:
        return self.solve_all(max_solutions=max_solutions, store=False)


# =========================
# BE-Facing Helpers
# =========================

def _as_board_spec(
    p: Puzzle,
    *,
    include_solutions: bool = False,
    solutions_cap: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Serialize the puzzle to the DB JSONB shape.

    Key changes in this mode:
      - 'numbers' length is N*N-1 (blank not stored).
      - 'operators' length is 2*N*(N-1) - 2.
      - 'expected' already accounts for truncated last row/column.
    """
    spec: Dict[str, Any] = {
        "N": p.N,
        "numbers": p.numbers,
        "operators": p.operators,
        "expected": [_fraction_to_string(x) for x in p.expected],
    }

    if include_solutions:
        sols = p.get_cached_solutions()
        if solutions_cap is not None:
            sols = sols[:solutions_cap]
        spec["solutions"] = sols

    return spec


def _is_duplicate(p: Puzzle, bag: Iterable[Dict[str, Any]]) -> bool:
    """
    Structural duplicate check against already prepared board_specs.
    """
    expected_str = [_fraction_to_string(x) for x in p.expected]
    for spec in bag:
        if (
            spec.get("N") == p.N
            and spec.get("operators") == p.operators
            and spec.get("expected") == expected_str
            and Counter(spec.get("numbers", [])) == Counter(p.numbers)
        ):
            return True
    return False


def find_one_puzzle(
    *,
    N: int,
    operators_spec: List[Tuple[str, Optional[int]]],
    allowed_numbers: Optional[List[int]],
    require_unique: bool,
    max_solutions_check: int = 2,
) -> Optional[Puzzle]:
    """
    Try to generate one puzzle satisfying the constraints (optionally unique).
    """
    p = Puzzle(
        N=N,
        use_daily_seed=False,
        shuffle_after_expected=True,
        operators_spec=operators_spec,
        numbers_choices=allowed_numbers,
    )
    sols = p.solve_all(max_solutions=max_solutions_check, store=True)
    if require_unique:
        return p if len(sols) == 1 else None
    return p if len(sols) >= 1 else None


def generate_and_store_puzzles(
    *,
    count: int = 10,
    N: int = 4,
    difficulty: Optional[int] = None,
    allowed_numbers: Optional[List[int]] = None,
    operators_spec: List[Tuple[str, Optional[int]]],
    require_unique: bool = True,
    max_attempts: int = 500,
    include_solutions: bool = True,
    solutions_cap: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Generate up to 'count' puzzles and persist them into the database.
    """
    saved_specs: List[Dict[str, Any]] = []
    attempts = 0

    while len(saved_specs) < count and attempts < max_attempts:
        attempts += 1

        p = find_one_puzzle(
            N=N,
            operators_spec=operators_spec,
            allowed_numbers=allowed_numbers,
            require_unique=require_unique,
            max_solutions_check=2 if require_unique else None,
        )
        if not p:
            continue

        if include_solutions and not p.solutions:
            p.solve_and_cache()

        spec = _as_board_spec(
            p,
            include_solutions=include_solutions,
            solutions_cap=solutions_cap,
        )

        if _is_duplicate(p, saved_specs):
            continue

        _ = puzzles_repo.insert_puzzle(
            author_id=-1,  # "system"
            title=f"AutoGen {N}x{N}",
            size=N,
            board_spec=spec,
            difficulty=difficulty,
            num_solutions=p.num_solutions_cached() or len(p.solutions) or None,
        )

        saved_specs.append(spec)

    return {
        "requested": count,
        "inserted": len(saved_specs),
        "attempts": attempts,
        "difficulty": difficulty,
        "N": N,
    }


def completes_col(idx):
    return 0


def completes_row(idx):
    return 0


def solve_all(self, max_solutions: Optional[int] = None, store: bool = False) -> List[List[int]]:
    N = self.N
    # Indices of all cells except the bottom-right blank space
    fill_order: List[int] = [i for i in range(N * N) if i != (N * N - 1)]
    # Initialize an empty board and a pool of available numbers
    board: List[Optional[int]] = [None] * (N * N)
    pool = Counter(self.numbers)
    # List to store all valid solutions found
    solutions: List[List[int]] = []

    def place(k: int) -> None:
        """Recursive helper that attempts to fill position 'k'."""
        # Base case: all cells filled -> store the current configuration
        if k == len(fill_order):
            sol = [board[i] for i in fill_order]
            solutions.append([int(v) for v in sol])
            return

        idx = fill_order[k]

        # Sort remaining candidates by how few copies remain (MRV heuristic)
        candidates = [v for v, cnt in pool.items() if cnt > 0]
        candidates.sort(key=lambda v: (pool[v], v))

        for val in candidates:
            board[idx] = val
            pool[val] -= 1

            # Validate the row when it becomes complete
            rr = completes_row(idx)
            if rr is not None and not self._row_is_valid(board, rr):
                pool[val] += 1
                board[idx] = None
                continue

            # Validate the column when it becomes complete
            cc = completes_col(idx)
            if cc is not None and not self._col_is_valid(board, cc):
                pool[val] += 1
                board[idx] = None
                continue

            # Recurse to the next position
            place(k + 1)

            # Stop early if the desired number of solutions is reached
            if max_solutions is not None and len(solutions) >= max_solutions:
                pool[val] += 1
                board[idx] = None
                return

            # Backtrack: undo placement and restore the number count
            pool[val] += 1
            board[idx] = None

    # Start recursive placement
    place(0)

    # Optionally store solutions in the object for later retrieval
    if store:
        self.solutions = [sol[:] for sol in solutions]

    return solutions