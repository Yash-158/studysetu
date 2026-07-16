-- 0006: uploads, events (timeline ledger), generated_artifacts, ai_invocations, demo_cache
BEGIN;
CREATE TABLE uploads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  purpose upload_purpose NOT NULL,
  ref_id uuid,                                   -- submission/material/doubt id (app-enforced by purpose)
  provider text NOT NULL DEFAULT 'local',
  storage_key text NOT NULL,
  mime text NOT NULL,
  size_bytes int NOT NULL CHECK (size_bytes > 0),
  expires_at timestamptz,                        -- null = permanent (materials/submissions); set = TTL (doubt photos)
  created_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE INDEX ix_uploads_cleanup ON uploads (expires_at) WHERE deleted_at IS NULL AND expires_at IS NOT NULL;
ALTER TABLE materials ADD CONSTRAINT fk_materials_upload FOREIGN KEY (upload_id) REFERENCES uploads(id);

-- THE timeline ledger (S8/S13): append-only; client_id/seq nullable now, become the offline sync key in Phase 2
CREATE TABLE events (
  ingest_id bigint GENERATED ALWAYS AS IDENTITY,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  event_type text NOT NULL,                      -- registry documented in DATABASE.md (diagnostic_completed, session_started, ...)
  subject_id uuid REFERENCES subjects(id),
  topic_id uuid REFERENCES topics(id),
  ref_id uuid,
  payload jsonb NOT NULL DEFAULT '{}',
  client_id uuid,
  seq bigint,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  server_ts timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_events_client_seq ON events (client_id, seq) WHERE client_id IS NOT NULL;
CREATE INDEX ix_events_user_time ON events (user_id, occurred_at DESC);
CREATE INDEX ix_events_topic ON events (topic_id, occurred_at DESC) WHERE topic_id IS NOT NULL;

-- Generated Content Store (S13): every AI output written before shown; lookup before generate
CREATE TABLE generated_artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scope artifact_scope NOT NULL,
  artifact_type artifact_type NOT NULL,
  topic_id uuid REFERENCES topics(id),
  user_id uuid REFERENCES users(id),             -- set for student_unique scope
  cache_key text NOT NULL,                       -- hash(type, topic, level/misconception params, source_hash, prompt_version)
  content jsonb NOT NULL,
  source_hash text,
  prompt_version text NOT NULL DEFAULT 'v1',
  model text,
  tokens int,
  flagged boolean NOT NULL DEFAULT false,        -- teacher QA loop (S14)
  hidden boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_artifacts_cache_key UNIQUE (cache_key)
);
CREATE INDEX ix_artifacts_topic ON generated_artifacts (topic_id, artifact_type) WHERE NOT hidden;
CREATE INDEX ix_artifacts_user ON generated_artifacts (user_id) WHERE user_id IS NOT NULL;

CREATE TABLE ai_invocations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task text NOT NULL,
  provider text NOT NULL,
  model text NOT NULL,
  cache_hit boolean NOT NULL DEFAULT false,
  ref_artifact uuid REFERENCES generated_artifacts(id),
  latency_ms int,
  input_tokens int,
  output_tokens int,
  success boolean NOT NULL,
  error text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_invocations_time ON ai_invocations (created_at DESC);

CREATE TABLE demo_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task text NOT NULL,
  input_hash text NOT NULL,
  response jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_demo_cache UNIQUE (task, input_hash)
);
COMMIT;
