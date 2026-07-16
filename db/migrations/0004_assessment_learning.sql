-- 0004: misconceptions, items, options, assessments, diagnostics, sessions, attempts, mastery
BEGIN;
CREATE TABLE misconceptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text NOT NULL UNIQUE,
  title text NOT NULL,
  description text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id uuid NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
  origin item_origin NOT NULL DEFAULT 'ai',
  status review_status NOT NULL DEFAULT 'draft',      -- teacher review gate (S3)
  stem text NOT NULL,
  difficulty smallint NOT NULL CHECK (difficulty IN (-1,0,1)),
  explanation text NOT NULL DEFAULT '',               -- stored reasoning, generated once (S13)
  meta jsonb NOT NULL DEFAULT '{}',
  version int NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE INDEX ix_items_topic ON items (topic_id) WHERE deleted_at IS NULL AND status = 'approved';
CREATE TRIGGER trg_items_u BEFORE UPDATE ON items FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE item_options (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id uuid NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  position smallint NOT NULL,
  body text NOT NULL,
  is_correct boolean NOT NULL DEFAULT false,
  misconception_id uuid REFERENCES misconceptions(id),
  CONSTRAINT uq_options_pos UNIQUE (item_id, position)
);
CREATE UNIQUE INDEX uq_options_one_correct ON item_options (item_id) WHERE is_correct;

CREATE TABLE assessments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_id uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  created_by uuid NOT NULL REFERENCES users(id),
  title text NOT NULL,
  gating gating_mode NOT NULL DEFAULT 'recommended',
  feedback feedback_mode NOT NULL DEFAULT 'end',
  status publish_status NOT NULL DEFAULT 'draft',
  due_at timestamptz,
  settings jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE TRIGGER trg_assessments_u BEFORE UPDATE ON assessments FOR EACH ROW EXECUTE FUNCTION set_updated_at();
ALTER TABLE chapter_blocks ADD CONSTRAINT fk_blocks_assessment FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE;

CREATE TABLE assessment_topics (
  assessment_id uuid NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  topic_id uuid NOT NULL REFERENCES topics(id),
  PRIMARY KEY (assessment_id, topic_id)
);
CREATE TABLE assessment_items (
  assessment_id uuid NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  item_id uuid NOT NULL REFERENCES items(id),
  position int NOT NULL,
  PRIMARY KEY (assessment_id, item_id),
  CONSTRAINT uq_assessment_item_pos UNIQUE (assessment_id, position)
);

CREATE TABLE diagnostic_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  topic_id uuid NOT NULL REFERENCES topics(id),
  item_ids uuid[] NOT NULL,
  score smallint,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_diag_user_topic ON diagnostic_sessions (user_id, topic_id);

CREATE TABLE learning_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  topic_id uuid NOT NULL REFERENCES topics(id),
  diagnostic_id uuid REFERENCES diagnostic_sessions(id),
  plan jsonb NOT NULL,                                -- ordered segment refs into generated_artifacts (S13 tier-2)
  status session_status NOT NULL DEFAULT 'planned',
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_sessions_user ON learning_sessions (user_id, created_at DESC);
CREATE TRIGGER trg_sessions_u BEFORE UPDATE ON learning_sessions FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE attempts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  item_id uuid NOT NULL REFERENCES items(id),
  option_id uuid REFERENCES item_options(id),
  is_correct boolean NOT NULL,
  context attempt_context NOT NULL,
  container_id uuid,                                  -- diagnostic/session/assessment id (app-enforced by context)
  occurred_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_attempts_user_time ON attempts (user_id, occurred_at DESC);
CREATE INDEX ix_attempts_item ON attempts (item_id);

CREATE TABLE mastery (
  user_id uuid NOT NULL REFERENCES users(id),
  topic_id uuid NOT NULL REFERENCES topics(id),
  p_known real NOT NULL DEFAULT 0.3 CHECK (p_known BETWEEN 0 AND 1),
  confidence real NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),   -- decays with inactivity (S4)
  attempts_count int NOT NULL DEFAULT 0,
  last_activity_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, topic_id)
);
CREATE INDEX ix_mastery_topic ON mastery (topic_id);

CREATE TABLE mastery_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  topic_id uuid NOT NULL REFERENCES topics(id),
  p_known real NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_mastery_hist ON mastery_history (user_id, topic_id, recorded_at);
COMMIT;
