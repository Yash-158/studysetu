-- 0008: ai_invocations.ingest_id (monotonic emission-order tiebreaker)
-- Pre-existing bug found while building M5 (unrelated to the session planner itself): Postgres
-- holds now() stable for a whole transaction, so several ai_invocations rows logged within one
-- ai.generate() call (a real attempt plus its failover, or a lookup plus a generation) can share
-- an identical created_at - "ORDER BY created_at" alone cannot reliably prove attempt order.
-- Same fix already applied to events.ingest_id (0006) for M5's own causal-chain ordering.
BEGIN;
ALTER TABLE ai_invocations ADD COLUMN ingest_id bigint GENERATED ALWAYS AS IDENTITY;
COMMIT;
