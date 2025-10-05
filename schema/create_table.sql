-- =====================================================================
-- Schema: Qiyi Klotski / Puzzles
-- PostgreSQL DDL
-- =====================================================================

BEGIN;

-- =========================================================
-- Table: users  (avoid reserved word "user")
-- =========================================================
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    avatar_key      TEXT,                    -- partial key or fragment for S3 image
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure case-insensitive unique emails
CREATE UNIQUE INDEX ux_users_email_ci ON users (LOWER(email));

-- =========================================================
-- Table: puzzles
-- (puzzles created by users or automatically by the system)
-- =========================================================
CREATE TABLE puzzles (
    id              BIGSERIAL PRIMARY KEY,
    author_id       BIGINT REFERENCES users(id) ON DELETE SET NULL,
    title           TEXT NOT NULL,
    size            SMALLINT NOT NULL,       -- e.g. 3, 4, 5 (board width/height)
    board_spec      JSONB NOT NULL,          -- board specification
    num_solutions   INTEGER,                 -- can be NULL if unknown
    difficulty      SMALLINT,                -- range 1–5 (optional)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_puzzles_size_pos     CHECK (size > 0),
    CONSTRAINT ck_puzzles_diff_range   CHECK (difficulty IS NULL OR difficulty BETWEEN 1 AND 5),
    CONSTRAINT ck_puzzles_num_solutions CHECK (num_solutions IS NULL OR num_solutions >= 0)
);

-- Optimize for common listings by author and date
CREATE INDEX ix_puzzles_author_created ON puzzles (author_id, created_at DESC);

-- =========================================================
-- Table: follows (user social connections)
-- =========================================================
CREATE TABLE follows (
    id           BIGSERIAL PRIMARY KEY,
    follower_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followee_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_follows_pair UNIQUE (follower_id, followee_id),
    CONSTRAINT ck_follows_no_self CHECK (follower_id <> followee_id)
);

CREATE INDEX ix_follows_follower ON follows (follower_id);
CREATE INDEX ix_follows_followee ON follows (followee_id);

-- =========================================================
-- Table: puzzle_likes (likes from users to puzzles)
-- =========================================================
CREATE TABLE puzzle_likes (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    puzzle_id  BIGINT NOT NULL REFERENCES puzzles(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_puzzle_likes_pair UNIQUE (user_id, puzzle_id)
);

CREATE INDEX ix_puzzle_likes_puzzle ON puzzle_likes (puzzle_id);
CREATE INDEX ix_puzzle_likes_user   ON puzzle_likes (user_id);

-- =========================================================
-- Table: puzzle_solves (user attempts or solutions)
-- =========================================================
CREATE TABLE puzzle_solves (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    puzzle_id    BIGINT NOT NULL REFERENCES puzzles(id) ON DELETE CASCADE,
    movements    INTEGER NOT NULL,          -- number of moves
    duration_ms  INTEGER NOT NULL,          -- duration in milliseconds
    solution     JSONB,                     -- final state or path
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_solves_movements_pos  CHECK (movements >= 0),
    CONSTRAINT ck_solves_duration_pos   CHECK (duration_ms >= 0)
);

-- Indexes for query optimization
CREATE INDEX ix_solves_user_created   ON puzzle_solves (user_id, created_at DESC);
CREATE INDEX ix_solves_puzzle_created ON puzzle_solves (puzzle_id, created_at DESC);
CREATE INDEX ix_solves_user_puzzle    ON puzzle_solves (user_id, puzzle_id);

-- =========================================================
-- Table: daily_puzzles (puzzle of the day)
-- =========================================================
CREATE TABLE daily_puzzles (
    id         BIGSERIAL PRIMARY KEY,
    puzzle_id  BIGINT NOT NULL REFERENCES puzzles(id) ON DELETE RESTRICT,
    date       DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Usually one puzzle per date:
    CONSTRAINT uq_daily_puzzles_date UNIQUE (date)
);

CREATE INDEX ix_daily_puzzles_puzzle ON daily_puzzles (puzzle_id);

COMMIT;

