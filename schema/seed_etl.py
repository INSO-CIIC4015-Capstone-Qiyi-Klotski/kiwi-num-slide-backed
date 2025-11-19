#!/usr/bin/env python3
"""
Deterministic ETL/seed script for the Kiwi Num Slide backend.

This script connects to PostgreSQL, wipes the main tables (optionally),
and inserts synthetic but consistent data for local development.

It is meant ONLY for local/dev databases. Do not run this against production.

Environment
-----------
The script expects a `.env.local` file at the project root with at least:

  DB_USER=...
  DB_PASSWORD=...
  DB_HOST=...
  DB_PORT=5432
  DB_NAME=kiwi_num_slide_dev

Basic usage
-----------
1) First-time setup on an empty local DB (recommended):

    python schema/seed_etl.py --allow-delete

This will:
  - Truncate users, puzzles, follows, likes, solves, and daily_puzzles.
  - Reset all IDs.
  - Insert a default amount of users, puzzles, follows, likes, solves, and daily puzzles.

2) Reset the database back to the initial seed state:

    python schema/seed_etl.py --allow-delete --seed 2025

Run this whenever you have manually modified or broken the data and want to
restore the initial test dataset.

3) Customizing parameters
-------------------------
You can change any of the generation parameters from the CLI:

    python schema/seed_etl.py \
      --allow-delete \
      --seed 1337 \
      --users 80 \
      --puzzles 160 \
      --min-follows 1 --max-follows 12 \
      --min-likes 1 --max-likes 25 \
      --min-solves 0 --max-solves 8 \
      --daily-start 2025-08-01 \
      --daily-end 2025-12-31

Notes
-----
- If you run the script WITHOUT --allow-delete on a DB that already has data,
  inserts may fail due to existing constraints or IDs. The intended workflow is:
  empty or disposable dev DB + --allow-delete.
- Using the same seed and the same parameters will always produce the same dataset.
"""

import argparse
import os
from datetime import date, timedelta
import random
import string
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Json


# Resolve project root (one level above schema/)
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env.local"

load_dotenv(ENV_PATH)


# -------------------------
# Deterministic randomness
# -------------------------
def make_rng(seed: int) -> random.Random:
    """Return a Random instance seeded with the given integer."""
    rng = random.Random()
    rng.seed(seed)
    return rng


# -------------------------
# Board spec generator
# -------------------------
OPS = ["+", "-", "*", "/"]  # division is included for future engine support


def gen_board_spec(N: int, rng: random.Random, ops) -> dict:
    """Build a random board specification for an N x N puzzle."""
    # numbers: N*N - 1
    numbers = [rng.randint(1, 9) for _ in range(N * N - 1)]

    # operators: 2*N*(N-1) - 2
    op_len = 2 * N * (N - 1) - 2
    operators = [rng.choice(ops) for _ in range(op_len)]

    # expected: 2*N target values (rows + columns)
    expected = [rng.randint(-20, 40) for _ in range(2 * N)]

    return {"N": N, "numbers": numbers, "expected": expected, "operators": operators}



def gen_solution_from_board(board_spec: dict) -> dict:
    """Generate a simple 'solution' payload based on the board specification."""
    # For now, we treat the solution as the final ordered list of numbers.
    # This keeps it compatible with the shape N*N-1.
    return {"solution": list(board_spec["numbers"])}


# -------------------------
# Synthetic data helpers
# -------------------------
FIRST_NAMES = [
    "Alex", "Sam", "Chris", "Taylor", "Jordan", "Riley", "Casey", "Jamie", "Avery", "Morgan",
    "Dana", "Reese", "Rowan", "Quinn", "Skyler", "Eli", "Noa", "Luca", "Kai", "Milan",
]
LAST_NAMES = [
    "Rivera", "Santos", "Martínez", "García", "Núñez", "Ramírez", "Torres", "Díaz", "Vega",
    "Pérez", "López", "Rodríguez", "Castro", "Ramos", "Gómez", "Mendoza", "Suárez", "Figueroa",
]
ANIMAL_AVATARS = ["giraffe", "hippo", "leon", "monkey", "zebra"]


def slugify(s: str) -> str:
    """Convert a name string into a simple lower-case slug."""
    allowed = string.ascii_lowercase + string.digits
    s = s.lower().replace(" ", ".")
    return "".join(ch for ch in s if ch in allowed or ch == ".")


def gen_users(rng: random.Random, count: int):
    """Generate a list of synthetic users with unique emails.

    The very first user is the system user 'Kiwi' (id=1 after TRUNCATE RESTART IDENTITY).
    The rest are random synthetic users.
    """
    users = []

    if count <= 0:
        return users

    # 1) System user: Kiwi (will get id=1 after truncate + restart identity)
    system_pwd_hash = "$2b$12$sMquzFY7EemeV3HqfUYw7eknl4x8tuhv7US.nl8Zzi/SwIhfhdQBW"
    users.append((
        "Kiwi",                              # name
        "kiwi+system@example.com",           # email placeholder
        system_pwd_hash,                     # password_hash placeholder
        True,                                # is_verified
        "avatars/kiwi.png",                  # avatar_key
    ))

    # 2) Rest of synthetic users
    for i in range(count - 1):
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        base = slugify(name)
        email = f"{base}{i}@example.com"
        pwd_hash = system_pwd_hash  # reuse same hashed pass for simplicity
        is_verified = rng.random() < 0.85

        animal = rng.choice(ANIMAL_AVATARS)
        avatar_key = f"avatars/{animal}.png"

        users.append((name, email, pwd_hash, is_verified, avatar_key))

    return users


def gen_puzzles(rng: random.Random, count: int, user_ids, system_author_id: int | None = None):
    """Generate puzzles with random size, board specs, and authors.

    - Most puzzles are assigned to random human users.
    - A subset are considered 'algorithm-generated' and use the system author (Kiwi).
    """
    puzzles = []

    # Si no nos pasan el system_author_id, asumimos que es el primer usuario
    if system_author_id is None and user_ids:
        system_author_id = user_ids[0]

    for _ in range(count):
        title = f"Puzzle #{rng.randint(1000, 9999)}"
        N = rng.choice([3, 4, 5])

        # Decide si este puzzle es "algoritmo" o "usuario"
        # (antes usabas author_id = None para algoritmo;
        #  ahora usamos siempre system_author_id en su lugar).
        is_algorithm = rng.random() < 0.1  # ~10% algoritmo, 90% usuario (ajusta si quieres)

        if is_algorithm and system_author_id is not None:
            # Puzzles "del algoritmo" → autor fijo Kiwi
            author_id = system_author_id

            # Operadores más restringidos, igual que antes
            choice = rng.random()
            if choice < 0.3:
                allowed_ops = ["+"]
            elif choice < 0.6:
                allowed_ops = ["+", "-"]
            else:
                allowed_ops = ["*", "/"]
        else:
            # Puzzles con autor "humano" → cualquier user_id
            author_id = rng.choice(user_ids)
            allowed_ops = OPS

        board_spec = gen_board_spec(N, rng, allowed_ops)

        diff = rng.randint(1, 5)          # dificultad 1–5 siempre
        num_solutions = rng.randint(1, 6) # al menos 1 solución

        puzzles.append((author_id, title, N, board_spec, num_solutions, diff))

    return puzzles


# -------------------------
# Postgres helpers
# -------------------------
TRUNCATE_ORDER = [
    "daily_puzzles",
    "puzzle_solves",
    "puzzle_likes",
    "follows",
    "puzzles",
    "users",
]


def truncate_all(conn):
    """Truncate all main tables and reset identities."""
    with conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                public.daily_puzzles,
                public.puzzle_solves,
                public.puzzle_likes,
                public.follows,
                public.puzzles,
                public.users
            RESTART IDENTITY;
            """
        )


def insert_users(conn, users):
    """Insert users and return the list of generated IDs."""
    sql = """
        INSERT INTO users (name, email, password_hash, is_verified, avatar_key)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """
    ids = []
    with conn.cursor() as cur:
        for params in users:
            cur.execute(sql, params)
            ids.append(cur.fetchone()[0])
    return ids


def insert_puzzles(conn, puzzles):
    """Insert puzzles and return their IDs and stored board specs."""
    sql = """
        INSERT INTO puzzles (author_id, title, size, board_spec, num_solutions, difficulty)
        VALUES (%s, %s, %s, %s::jsonb, %s, %s)
        RETURNING id, board_spec;
    """
    ids, specs = [], []
    with conn.cursor() as cur:
        for (author_id, title, size, board_spec, num_solutions, difficulty) in puzzles:
            cur.execute(
                sql,
                (author_id, title, size, Json(board_spec), num_solutions, difficulty),
            )
            rid, spec = cur.fetchone()
            ids.append(rid)
            specs.append(spec)
    return ids, specs


def insert_follows(conn, edges):
    """Insert follow relationships, ignoring duplicates."""
    sql = """
        INSERT INTO follows (follower_id, followee_id)
        VALUES (%s, %s)
        ON CONFLICT (follower_id, followee_id) DO NOTHING;
    """
    with conn.cursor() as cur:
        cur.executemany(sql, edges)


def insert_likes(conn, likes):
    """Insert puzzle likes, ignoring duplicates."""
    sql = """
        INSERT INTO puzzle_likes (user_id, puzzle_id)
        VALUES (%s, %s)
        ON CONFLICT (user_id, puzzle_id) DO NOTHING;
    """
    with conn.cursor() as cur:
        cur.executemany(sql, likes)


def insert_solves(conn, solves):
    """Insert puzzle solve records with movements and duration."""
    sql = """
        INSERT INTO puzzle_solves (user_id, puzzle_id, movements, duration_ms, solution)
        VALUES (%s, %s, %s, %s, %s::jsonb);
    """
    with conn.cursor() as cur:
        for (user_id, puzzle_id, movements, duration_ms, solution_dict) in solves:
            cur.execute(sql, (user_id, puzzle_id, movements, duration_ms, Json(solution_dict)))


def insert_daily(conn, rows):
    """Insert daily puzzle assignments by date."""
    sql = """
        INSERT INTO daily_puzzles (puzzle_id, date)
        VALUES (%s, %s)
        ON CONFLICT (date) DO NOTHING;
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)


# -------------------------
# Relationship generators
# -------------------------
def gen_follow_edges(rng: random.Random, user_ids, min_follows: int, max_follows: int):
    """
    Generate a set of follow edges ensuring each user has at least
    one follower and one followee.
    """
    n = len(user_ids)
    edges = set()

    for u in user_ids:
        k = rng.randint(min_follows, max(min(max_follows, n - 1), min_follows))
        choices = [v for v in user_ids if v != u]
        rng.shuffle(choices)
        for v in choices[:k]:
            edges.add((u, v))

    # Ensure: each user has in-degree >= 1
    indeg = {u: 0 for u in user_ids}
    for _, v in edges:
        indeg[v] += 1
    for u in user_ids:
        if indeg[u] == 0:
            v = rng.choice([x for x in user_ids if x != u])
            edges.add((v, u))

    # Ensure: each user has out-degree >= 1
    outdeg = {u: 0 for u in user_ids}
    for u, _ in edges:
        outdeg[u] += 1
    for u in user_ids:
        if outdeg[u] == 0:
            v = rng.choice([x for x in user_ids if x != u])
            edges.add((u, v))

    return list(edges)


def gen_likes(rng: random.Random, user_ids, puzzle_ids, min_likes: int, max_likes: int):
    """
    Generate a set of (user_id, puzzle_id) likes, ensuring every puzzle
    receives at least one like.
    """
    likes = set()

    # Per user likes
    for u in user_ids:
        k = rng.randint(min_likes, max(min(max_likes, len(puzzle_ids)), min_likes))
        choices = puzzle_ids[:]
        rng.shuffle(choices)
        for p in choices[:k]:
            likes.add((u, p))

    # Guarantee: each puzzle has at least one like
    liked_by = {p: 0 for p in puzzle_ids}
    for _, p in likes:
        liked_by[p] += 1
    for p in puzzle_ids:
        if liked_by[p] == 0:
            u = rng.choice(user_ids)
            likes.add((u, p))

    return list(likes)


def gen_solves(
    rng: random.Random,
    user_ids,
    puzzle_ids,
    specs,
    min_solves: int,
    max_solves: int,
):
    """
    Generate puzzle solve records per user, with random movements and duration.
    """
    spec_by_id = {pid: specs[i] for i, pid in enumerate(puzzle_ids)}
    solves = []
    for u in user_ids:
        k = rng.randint(min_solves, max_solves)
        if k == 0:
            continue
        choices = puzzle_ids[:]
        rng.shuffle(choices)
        for p in choices[:k]:
            board = spec_by_id[p]
            N = board["N"]
            sol = gen_solution_from_board(board)
            movements = rng.randint(max(0, N * N - 8), N * N + 20)
            duration_ms = rng.randint(20_000, 240_000)
            solves.append((u, p, movements, duration_ms, sol))
    return solves


def daterange(d0: date, d1: date):
    """Yield all dates from d0 to d1 inclusive."""
    cur = d0
    while cur <= d1:
        yield cur
        cur = cur + timedelta(days=1)


def gen_daily_rows(rng: random.Random, puzzle_ids, start_d: date, end_d: date):
    """Assign a random puzzle to each date in the given range."""
    rows = []
    for d in daterange(start_d, end_d):
        p = rng.choice(puzzle_ids)
        rows.append((p, d))
    return rows


# -------------------------
# Main CLI and entrypoint
# -------------------------
def parse_args():
    """Parse command-line arguments for the seeding script."""
    this_year = date.today().year
    parser = argparse.ArgumentParser(
        description="Deterministic ETL/seed script for the Kiwi Num Slide backend."
    )
    parser.add_argument("--seed", type=int, default=2025, help="RNG seed for reproducible data.")
    parser.add_argument("--users", type=int, default=60, help="Number of users to generate.")
    parser.add_argument("--puzzles", type=int, default=120, help="Number of puzzles to generate.")
    parser.add_argument("--min-follows", type=int, default=1, help="Minimum follows per user.")
    parser.add_argument("--max-follows", type=int, default=10, help="Maximum follows per user.")
    parser.add_argument("--min-likes", type=int, default=1, help="Minimum likes per user.")
    parser.add_argument("--max-likes", type=int, default=20, help="Maximum likes per user.")
    parser.add_argument("--min-solves", type=int, default=0, help="Minimum solves per user.")
    parser.add_argument("--max-solves", type=int, default=6, help="Maximum solves per user.")
    parser.add_argument(
        "--daily-start",
        type=str,
        default=f"{this_year}-08-01",
        help="First date (YYYY-MM-DD) to assign daily puzzles.",
    )
    parser.add_argument(
        "--daily-end",
        type=str,
        default=f"{this_year}-12-31",
        help="Last date (YYYY-MM-DD) to assign daily puzzles.",
    )
    parser.add_argument(
        "--allow-delete",
        action="store_true",
        default=False,
        help=(
            "If set, truncates all main tables and resets IDs before inserting. "
            "Without this flag, no DELETE/TRUNCATE is performed."
        ),
    )
    return parser.parse_args()


def main():
    """Main entrypoint for running the ETL/seed process."""
    args = parse_args()
    rng = make_rng(args.seed)

    # Connection config from environment
    cfg = dict(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        dbname=os.getenv("DB_NAME"),
    )

    start_d = date.fromisoformat(args.daily_start)
    end_d = date.fromisoformat(args.daily_end)

    with psycopg.connect(**cfg) as conn:
        conn.execute("BEGIN;")

        # Optional full wipe of dev data
        if args.allow_delete:
            print("Deleting all seed tables and resetting IDs...")
            truncate_all(conn)
        else:
            print("Safe mode: no tables were truncated (use --allow-delete to wipe data).")

        # 1) Users
        user_rows = gen_users(rng, args.users)
        user_ids = insert_users(conn, user_rows)

        # El primer user insertado es Kiwi → system_author_id
        system_author_id = user_ids[0] if user_ids else None

        # 2) Puzzles
        puzzle_rows = gen_puzzles(
            rng,
            args.puzzles,
            user_ids,
            system_author_id=system_author_id,
        )
        puzzle_ids, specs = insert_puzzles(conn, puzzle_rows)

        # 3) Follows (ensure in/out-degree >= 1)
        follow_edges = gen_follow_edges(rng, user_ids, args.min_follows, args.max_follows)
        insert_follows(conn, follow_edges)

        # 4) Likes (ensure at least one like per puzzle)
        likes = gen_likes(rng, user_ids, puzzle_ids, args.min_likes, args.max_likes)
        insert_likes(conn, likes)

        # 5) Solves (optional per user)
        solves = gen_solves(
            rng,
            user_ids,
            puzzle_ids,
            specs,
            args.min_solves,
            args.max_solves,
        )
        if solves:
            insert_solves(conn, solves)

        # 6) Daily puzzles
        daily_rows = gen_daily_rows(rng, puzzle_ids, start_d, end_d)
        insert_daily(conn, daily_rows)

        conn.execute("COMMIT;")

    print(f"[OK] Seed completed with seed={args.seed}")
    print(
        f"Users: {len(user_ids)} | "
        f"Puzzles: {len(puzzle_ids)} | "
        f"Follows: {len(follow_edges)} | "
        f"Likes: {len(likes)} | "
        f"Solves: {len(solves)} | "
        f"Daily: {len(daily_rows)}"
    )


if __name__ == "__main__":
    main()
