-- 0007: users.issued_at (activation-code issue time, independent of created_at)
-- Fixes the M1-known gap: TTL was measured from created_at, which breaks once M2 lets an
-- admin reissue a fresh code to an already-existing account (docs/MEMORY.md M1 log).
BEGIN;
ALTER TABLE users ADD COLUMN issued_at timestamptz;
UPDATE users SET issued_at = created_at WHERE issued_at IS NULL;
ALTER TABLE users ALTER COLUMN issued_at SET NOT NULL;
ALTER TABLE users ALTER COLUMN issued_at SET DEFAULT now();
COMMIT;
