import json
import pytest
from fractions import Fraction
from app.services.puzzle_generation import Puzzle, _fraction_to_string, _string_to_fraction

def test_operator_spec_mixed_modes():
    """
    Verifies that mixed operator specifications (e.g., '+', '*2') are normalized properly.

    This test:
    - Creates puzzles using a combination of unlimited and fixed-count operator specifications.
    - Confirms that operators are generated in correct quantities according to N and specification.
    - Ensures total operator count follows 2*N*(N-1)-2.
    """
    p1 = Puzzle(N=3, use_daily_seed=False, seed=1, operators_spec=[('+',), ('*', 2)])
    assert p1.N == 3
    assert p1.operators.count("*") == 2
    assert len(p1.operators) == (2 * 3 * (3 - 1) - 2)

    p2 = Puzzle(N=3, use_daily_seed=False, seed=1, operators_spec=[('+',), ('/', 4)])
    assert p2.N == 3
    assert p2.operators.count("/") == 4
    assert len(p2.operators) == (2 * 3 * (3 - 1) - 2)

    p3 = Puzzle(N=3, use_daily_seed=False, seed=1, operators_spec=[('+', 2), ('*',)])
    assert p3.N == 3
    assert p3.operators.count("+") == 2
    assert len(p3.operators) == (2 * 3 * (3 - 1) - 2)


def test_number_choices_out_of_range():
    """
    Ensures that invalid number ranges trigger ValueError exceptions.

    This test:
    - Attempts to create puzzles where `numbers_choices` contains invalid values (<1 or >9).
    - Verifies that a ValueError is raised for each invalid configuration.
    """
    with pytest.raises(ValueError):
        Puzzle(N=3, use_daily_seed=False, seed=2, numbers_choices=[10])

    with pytest.raises(ValueError):
        Puzzle(N=3, use_daily_seed=False, seed=2, numbers_choices=[0])


@pytest.mark.parametrize("N", [3, 4, 5, 6, 7])
def test_row_col_op_lengths_respect_blank_edges(N):
    """
    Validates that operator grids correctly omit operations adjacent to the blank cell.

    This test:
    - Builds puzzles of different sizes (N = 3–7).
    - Ensures that the last row and column have one fewer operator (blank cell area).
    - Confirms that both row and column operation lengths match expected layout rules.
    """
    p = Puzzle(N=N, use_daily_seed=False, seed=123, operators_spec=[('+',), ('-',)])
    for r in range(N):
        row_ops = p._row_ops(r)
        expected_len = (N-1) if r < N-1 else (N-2)
        assert len(row_ops) == expected_len
    for c in range(N):
        col_ops = p._col_ops(c)
        expected_len = (N-1) if c < N-1 else (N-2)
        assert len(col_ops) == expected_len

@pytest.mark.parametrize("N", [3, 4, 5, 6, 7])
def test_total_operator_count_matches_formula(N):
    """
    Confirms that total operator count matches the expected formula: 2*N*(N-1) - 2.
    """
    p = Puzzle(N=N, use_daily_seed=False, seed=7, operators_spec=[('+',), ('-',)])
    assert len(p.operators) == 2*N*(N-1) - 2



def test_fraction_string_roundtrip_covers_integers_and_proper_fractions():
    """
    Ensures Fractions serialize and deserialize correctly using the string conversion helpers.

    This test:
    - Iterates over integer and proper Fraction objects.
    - Converts them to string form using `_fraction_to_string`.
    - Converts back using `_string_to_fraction`.
    - Confirms the roundtrip preserves exact numerical equivalence.
    """
    cases = [Fraction(5,1), Fraction(-3,1), Fraction(7,3), Fraction(-11,4)]
    for fr in cases:
        s = _fraction_to_string(fr)
        assert _string_to_fraction(s) == fr

def test_is_equal_to_same_seed_same_spec():
    """
    Verifies that puzzles with identical seed and operator specs are structurally equal.

    This test:
    - Creates pairs of puzzles with the same parameters.
    - Confirms `is_equal_to()` returns True for each identical pair.
    """
    for i in range(100):
        p1 = Puzzle(N=4, use_daily_seed=False, seed=42, operators_spec=[('+',), ('-',)], shuffle_after_expected=False)
        p2 = Puzzle(N=4, use_daily_seed=False, seed=42, operators_spec=[('+',), ('-',)], shuffle_after_expected=False)

        assert p1.is_equal_to(p2)

def test_is_equal_to_different_operator_spec_is_false():
    """
    Verifies that puzzles with different operator specs are not considered equal.
    """
    for i in range(100):
        p1 = Puzzle(N=4, use_daily_seed=False, seed=42, operators_spec=[('+',), ('-',)])
        p2 = Puzzle(N=4, use_daily_seed=False, seed=42, operators_spec=[('+',), ('*', 2)])
        assert not p1.is_equal_to(p2)

def test_eval_line_with_precedence_basic_cases():
    """
    Validates that arithmetic precedence is respected in isolated expressions.

    This test:
    - Checks precedence of *, / over + and - using simple expressions.
    - Covers mixed operator combinations (add, subtract, multiply, divide).
    - Ensures division by zero returns None instead of raising.
    """
    # 2 + 3*4 = 14  (multiplication before addition)
    assert Puzzle._eval_line_with_precedence([2,3,4], ['+','*']) == Fraction(14,1)

    # (8 / 2) + 2 = 6  (division before addition)
    assert Puzzle._eval_line_with_precedence([8,2,2], ['/','+']) == Fraction(6,1)

    # 10 - 3*2 = 4
    assert Puzzle._eval_line_with_precedence([10,3,2], ['-','*']) == Fraction(4,1)

    # (5*2) - 6/3 = 8  (5*2=10; 6/3=2; 10-2=8)
    assert Puzzle._eval_line_with_precedence([5,2,6,3], ['*','-','/']) == Fraction(8,1)

    # Division by zero returns None
    assert Puzzle._eval_line_with_precedence([5,0], ['/']) is None
