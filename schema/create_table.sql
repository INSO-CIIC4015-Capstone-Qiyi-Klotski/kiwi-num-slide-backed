-- Extensions (optional but useful)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Simple table for smoke test
CREATE TABLE IF NOT EXISTS app_health (
  id         uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  note       text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Minimum seed
INSERT INTO app_health (note) VALUES ('hello from local') ON CONFLICT DO NOTHING;