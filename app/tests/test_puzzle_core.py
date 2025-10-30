import json
import pytest
from fractions import Fraction
from app.services.puzzle_generation import Puzzle, _fraction_to_string, _string_to_fraction

def test_operator_spec_mixed_modes():
    """Validates that operator specifications mixing unlimited and exact counts (e.g., '+', '*2') are normalized correctly."""
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
    """Ensures ValueError is raised when 'numbers_choices' includes values below 1 or above 9."""
    with pytest.raises(ValueError):
        Puzzle(N=3, use_daily_seed=False, seed=2, numbers_choices=[10])

    with pytest.raises(ValueError):
        Puzzle(N=3, use_daily_seed=False, seed=2, numbers_choices=[0])


@pytest.mark.parametrize("N", [3, 4, 5, 6, 7])
def test_row_col_op_lengths_respect_blank_edges(N):
    """🧩 Checks that operator grids omit operations adjacent to the blank cell at bottom-right corner."""
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
    """🧮 Confirms total operator count follows formula 2*N*(N-1)-2."""
    p = Puzzle(N=N, use_daily_seed=False, seed=7, operators_spec=[('+',), ('-',)])
    assert len(p.operators) == 2*N*(N-1) - 2



def test_fraction_string_roundtrip_covers_integers_and_proper_fractions():
    """🔁 Ensures that Fraction objects serialize and deserialize correctly to string format."""
    cases = [Fraction(5,1), Fraction(-3,1), Fraction(7,3), Fraction(-11,4)]
    for fr in cases:
        s = _fraction_to_string(fr)
        assert _string_to_fraction(s) == fr

def test_is_equal_to_same_seed_same_spec():
    """Confirms that identical puzzles (same seed/spec) are structurally equal."""
    for i in range(100):
        p1 = Puzzle(N=4, use_daily_seed=False, seed=42, operators_spec=[('+',), ('-',)], shuffle_after_expected=False)
        p2 = Puzzle(N=4, use_daily_seed=False, seed=42, operators_spec=[('+',), ('-',)], shuffle_after_expected=False)

        assert p1.is_equal_to(p2)

def test_is_equal_to_different_operator_spec_is_false():
    """Confirms that puzzles with different operator specs are not considered equal."""
    for i in range(100):
        p1 = Puzzle(N=4, use_daily_seed=False, seed=42, operators_spec=[('+',), ('-',)])
        p2 = Puzzle(N=4, use_daily_seed=False, seed=42, operators_spec=[('+',), ('*', 2)])
        assert not p1.is_equal_to(p2)

def test_eval_line_with_precedence_basic_cases():
    """
    Validates the atomic precedence evaluator on hand-crafted inputs,
    without involving any board/layout logic.
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
