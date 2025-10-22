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

    Rationale:
      Storing expected targets as strings avoids floating-point rounding issues
      and preserves exact arithmetic semantics across the stack.
    """
    return str(fr.numerator) if fr.denominator == 1 else f"{fr.numerator}/{fr.denominator}"


def _string_to_fraction(s: str) -> Fraction:
    """
    Parse a canonical fraction string ("a/b" or "a") back into a Fraction.

    Input:
      - "a/b" where a and b are signed integers and b != 0
      - "a"   where a is a signed integer

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
    N×N arithmetic-slide puzzle generator.

    Board encoding:
      - numbers: flat list with N*N integers. The blank is represented by a single '1'
                 (conventional in this project), and the remaining N*N-1 numbers are
                 sampled with replacement from a configured domain (>=2).
      - operators: flat list with 2*N*(N-1) operators laid out in a grid-mesh
                   (each row has N-1 horizontal ops; each column has N-1 vertical ops).
      - expected: list of length 2*N with target results: the first N are row targets,
                  the next N are column targets. Expressions are evaluated with precedence
                  (*/ before +-), not strictly left-to-right.

    Notes:
      - This class only builds a puzzle instance and can solve it via backtracking.
      - Uniqueness (exactly one solution) is decided externally by limiting the solver
        to at most two solutions and checking the count.
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
          use_daily_seed: If True and no seed is given, derive a daily seed so the same
                          parameters reproduce the same random stream that day.
          shuffle_after_expected: If True, shuffle numbers after computing expected targets.
                                  This preserves the math but makes the layout look random.
          operators_spec: Operator specification as a list of tuples:
                            [ ('+', None), ('-', None), ('*', 2), ('/', 2) ]
                          A 1-tuple ('+',) or ('*',) also means unlimited. A 2-tuple with
                          an integer count means an exact amount of that operator.
          numbers_choices: Allowed domain for non-blank numbers (>=2). If None, use [2..9].
        """
        if seed is None and use_daily_seed:
            seed = self._daily_seed(f"{date.today().isoformat()}-{N}")
        self._rng = random.Random(seed)

        self.N = N
        self.op_exact, self.op_unlimited = self._normalize_op_spec(
            operators_spec or self.DEFAULT_OP_SPEC
        )
        self._numbers_choices = self._normalize_number_choices(numbers_choices)

        self.numbers = self._gen_numbers_with_blank_at_end()
        self.operators = self._gen_operators()
        self.expected = self._compute_expected()  # List[Fraction]

        if shuffle_after_expected:
            self._rng.shuffle(self.numbers)

        # Cache for solved boards (each is a flat N*N list). Useful for hints in the FE.
        self.solutions: List[List[int]] = []

    # ---------- Seeds & Normalization ----------

    @staticmethod
    def _daily_seed(key: str) -> int:
        """
        Build a 32-bit deterministic seed from an arbitrary string.

        Used to create daily-stable randomness: same inputs → same puzzle on a given day.
        """
        return int(sha256(key.encode()).hexdigest(), 16) % (2**32)

    @staticmethod
    def _normalize_op_spec(
        spec: List[Tuple[str, Optional[int]]]
    ) -> Tuple[Dict[str, int], List[str]]:
        """
        Validate and split operator specification into:
          - op_exact: dict of operator -> exact count
          - op_unlimited: list of operators that can be used to fill the remaining slots

        Accepted forms in 'spec':
          - ('+',) or ('+', None)  → unlimited
          - ('*', 2)               → exactly 2 times

        Raises:
          ValueError on invalid operators, shapes, negative counts, or conflicts (both
          exact and unlimited for the same operator).
        """
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
        """
        Validate/normalize the allowed number domain for non-blank tiles.

        Behavior:
          - None  → default domain [2..9]
          - list  → must be non-empty, all integers >= 2

        Raises:
          ValueError on invalid inputs.
        """
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

    def _gen_numbers_with_blank_at_end(self) -> List[int]:
        """
        Sample N*N-1 numbers from the domain (with replacement) and append a single '1'
        to represent the blank tile. Returns a flat list of length N*N.
        """
        total = self.N * self.N
        nums = [self._rng.choice(self._numbers_choices) for _ in range(total - 1)]
        nums.append(1)
        return nums

    def _gen_operators(self) -> List[str]:
        """
        Build the operator grid (flattened) with length 2*N*(N-1).

        Process:
          1) Place all exact-count operators.
          2) Fill the remaining slots by sampling from unlimited operators.
          3) Shuffle to avoid patterned placement.

        Raises:
          ValueError if exact counts exceed the total or no unlimited operators exist to fill.
        """
        total = 2 * self.N * (self.N - 1)
        if total == 0:
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

        ops_out: List[str] = []
        for op, cnt in self.op_exact.items():
            if cnt > 0:
                ops_out.extend([op] * cnt)
        for _ in range(remaining):
            ops_out.append(random.choice(self.op_unlimited))
        random.shuffle(ops_out)
        return ops_out

    # ---------- Expression Evaluation ----------

    @staticmethod
    def _apply_mul_div(a: Fraction, b: Fraction, op: str) -> Optional[Fraction]:
        """
        Apply '*' or '/' between two Fractions. Returns None on division by zero.
        """
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
        Evaluate a single row/column expression with standard precedence:
          - Perform all * and / left-to-right first,
          - Then perform + and - left-to-right.

        Returns:
          Fraction result, or None if an invalid op (e.g., division by zero) occurs.

        Assumes:
          len(values) >= 1 and len(ops) == len(values) - 1
        """
        assert len(values) >= 1 and len(ops) == len(values) - 1

        # First pass: collapse */ into the value list.
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

        # Second pass: do + and - on the reduced list.
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

    # ---------- Expected Targets ----------

    def _row_ops(self, r: int) -> List[str]:
        """
        Slice the horizontal operators for row r from the flattened operator list.
        """
        start = r * (2 * self.N - 1)
        return [self.operators[start + j] for j in range(self.N - 1)]

    def _col_ops(self, c: int) -> List[str]:
        """
        Slice the vertical operators for column c from the flattened operator list.
        """
        base = (self.N - 1) + c
        step = 2 * self.N - 1
        return [self.operators[base + k * step] for k in range(self.N - 1)]

    def _compute_expected(self) -> List[Fraction]:
        """
        Compute target values for all rows and columns using operator precedence.

        Returns:
          A list of length 2*N: first N are row targets, next N are column targets.
        """
        N = self.N
        b = self.numbers

        expected_rows: List[Fraction] = []
        for r in range(N):
            vals = b[r * N:(r + 1) * N]
            res = self._eval_line_with_precedence(vals, self._row_ops(r))
            if res is None:
                raise ValueError("Division by zero while computing expected (row).")
            expected_rows.append(res)

        expected_cols: List[Fraction] = []
        for c in range(N):
            vals = [b[r * N + c] for r in range(N)]
            res = self._eval_line_with_precedence(vals, self._col_ops(c))
            if res is None:
                raise ValueError("Division by zero while computing expected (column).")
            expected_cols.append(res)

        return expected_rows + expected_cols

    # ---------- Board Helpers ----------

    @staticmethod
    def _idx_to_rc(idx: int, N: int) -> Tuple[int, int]:
        """
        Convert a flat index to (row, col).
        """
        return divmod(idx, N)

    def _row_values(self, board: List[Optional[int]], r: int) -> List[Optional[int]]:
        """
        Return the r-th row (possibly partially filled) from a flat board.
        """
        i = r * self.N
        return board[i:i + self.N]

    def _col_values(self, board: List[Optional[int]], c: int) -> List[Optional[int]]:
        """
        Return the c-th column (possibly partially filled) from a flat board.
        """
        return [board[r * self.N + c] for r in range(self.N)]

    def _row_is_valid(self, board: List[Optional[int]], r: int) -> bool:
        """
        Check whether row r exactly matches its expected target (when the row is full).
        """
        vals = [int(v) for v in self._row_values(board, r)]
        res = self._eval_line_with_precedence(vals, self._row_ops(r))
        target = self.expected[r]
        return res is not None and res == target

    def _col_is_valid(self, board: List[Optional[int]], c: int) -> bool:
        """
        Check whether column c exactly matches its expected target (when the column is full).
        """
        vals = [int(v) for v in self._col_values(board, c)]
        res = self._eval_line_with_precedence(vals, self._col_ops(c))
        target = self.expected[self.N + c]
        return res is not None and res == target

    # ---------- Equality ----------

    def is_equal_to(self, other: "Puzzle") -> bool:
        """
        Structural equality:
          - same N
          - identical operator sequence
          - identical expected targets
          - same multiset of numbers

        Useful for duplicate detection.
        """
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
        Enumerate solutions via backtracking on a flat N*N board.

        Heuristics:
          - MRV-ish: try numbers with the lowest remaining count first.
          - Prioritize placing '1' earlier (since the blank is abundant).

        Args:
          max_solutions: None to search all, or an integer cutoff to stop early
                         (e.g., 2 to test uniqueness quickly).
          store: If True, cache found solutions in self.solutions (deep copy).

        Returns:
          List of flat solutions (each of length N*N).
        """
        N = self.N
        board: List[Optional[int]] = [None] * (N * N)
        pool = Counter(self.numbers)
        solutions: List[List[int]] = []

        def place(idx: int) -> None:
            if idx == N * N:
                solutions.append([int(v) for v in board])
                return

            r, c = self._idx_to_rc(idx, N)
            candidates = [v for v, cnt in pool.items() if cnt > 0]
            candidates.sort(key=lambda v: (pool[v], 0 if v == 1 else 1, v))

            for val in candidates:
                board[idx] = val
                pool[val] -= 1

                if c == N - 1 and not self._row_is_valid(board, r):
                    pool[val] += 1
                    board[idx] = None
                    continue
                if r == N - 1 and not self._col_is_valid(board, c):
                    pool[val] += 1
                    board[idx] = None
                    continue

                place(idx + 1)

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
        """
        Convenience wrapper: call solve_all(..., store=True).
        """
        return self.solve_all(max_solutions=max_solutions, store=True)

    def clear_solutions(self) -> None:
        """
        Drop any cached solutions.
        """
        self.solutions = []

    def num_solutions_cached(self) -> int:
        """
        Return the number of currently cached solutions.
        """
        return len(self.solutions)

    def get_cached_solutions(self) -> List[List[int]]:
        """
        Return a deep copy of cached solutions to avoid external mutation.
        """
        return [s[:] for s in self.solutions]

    def solve_flat(self, max_solutions: Optional[int] = None) -> List[List[int]]:
        """
        Backward-compat convenience alias (no caching by default).
        """
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
    Serialize a Puzzle into the JSONB shape stored in the database.

    Fields:
      - N: board size
      - numbers: flat list of N*N integers
      - operators: flat list of 2*N*(N-1) operators
      - expected: list of fraction strings ("a/b" or "a") to remain exact
      - solutions (optional): list of flat boards (ints). Included only if
        'include_solutions' is True; capped to 'solutions_cap' if provided.

    NOTE:
      Solutions are cached in the Puzzle instance. If include_solutions=True and no
      solutions are cached yet, ensure the caller invokes solve_and_cache() first.
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
    Check for duplicates against a collection of already prepared board_specs
    (e.g., within a generation batch), using structural equality:

      - same N
      - same operators sequence
      - same expected targets (fraction strings)
      - same multiset of numbers

    Returns True if a duplicate is found.
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
    Try to generate a single puzzle that satisfies the constraints.

    Constraints:
      - If 'require_unique' is True, the puzzle must have exactly one solution.
        We enforce this by solving with 'max_solutions_check' (default 2) and
        accepting only when exactly one solution is found.
      - If 'require_unique' is False, we accept any puzzle with at least one solution.

    Returns:
      A Puzzle instance that meets the criteria, or None if not satisfied.
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

    Behavior:
      - Attempts to generate puzzles until either 'count' are saved or 'max_attempts'
        total tries are exhausted.
      - Uses 'find_one_puzzle' for each attempt to enforce uniqueness (if requested).
      - Avoids duplicates within the same batch (in-memory check). If you need to
        avoid duplicates across the whole DB, add a DB-side uniqueness query here.

    Persistence:
      - Inserts a row into 'puzzles' with:
          author_id = -1  (system/algorithm user)
          title     = "AutoGen {N}x{N}"
          size      = N
          board_spec = JSONB (see _as_board_spec)
          difficulty = optional tag
          num_solutions = number of cached solutions (when available)

    Returns:
      A summary dict:
        {
          "requested": <count>,
          "inserted": <how many saved>,
          "attempts": <tries made>,
          "difficulty": <difficulty>,
          "N": <board size>
        }
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

        # Ensure solutions are cached if the caller wants them saved in board_spec.
        if include_solutions and not p.solutions:
            p.solve_and_cache()  # could be cut down later via solutions_cap

        spec = _as_board_spec(
            p,
            include_solutions=include_solutions,
            solutions_cap=solutions_cap,
        )

        # Avoid duplicates within this generation batch.
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
