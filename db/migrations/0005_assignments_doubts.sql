-- 0005: assignments, rubrics, submissions, reviews, doubts
BEGIN;
CREATE TABLE assignments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_id uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  created_by uuid NOT NULL REFERENCES users(id),
  title text NOT NULL,
  instructions text NOT NULL DEFAULT '',
  rubric jsonb NOT NULL DEFAULT '[]',            -- [{criterion, levels:[{label,desc,marks}]}] validated at app layer
  max_marks numeric(6,2),
  grading grading_mode NOT NULL DEFAULT 'manual_only',   -- ai modes activate Phase 2
  due_at timestamptz,
  status publish_status NOT NULL DEFAULT 'draft',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE TRIGGER trg_assignments_u BEFORE UPDATE ON assignments FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assignment_id uuid NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id),
  status submission_status NOT NULL DEFAULT 'assigned',
  submitted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_submission UNIQUE (assignment_id, user_id)
);
CREATE TRIGGER trg_submissions_u BEFORE UPDATE ON submissions FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE submission_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id uuid NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  reviewer_id uuid NOT NULL REFERENCES users(id),
  rubric_scores jsonb NOT NULL DEFAULT '{}',
  marks numeric(6,2),
  comments text NOT NULL DEFAULT '',
  ai_suggested jsonb,                            -- Phase 2 pre-grade payload; teacher overrides tracked by diff
  returned_for_revision boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_reviews_submission ON submission_reviews (submission_id);

CREATE TABLE doubts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  subject_id uuid REFERENCES subjects(id),
  matched_topic_id uuid REFERENCES topics(id),
  root_topic_id uuid REFERENCES topics(id),
  raw_text text NOT NULL,                        -- typed in Phase 1; OCR-filled in Phase 2
  mode explain_mode NOT NULL DEFAULT 'socratic',
  status doubt_status NOT NULL DEFAULT 'open',
  transcript jsonb NOT NULL DEFAULT '[]',
  resolved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_doubts_user ON doubts (user_id, created_at DESC);
CREATE TRIGGER trg_doubts_u BEFORE UPDATE ON doubts FOR EACH ROW EXECUTE FUNCTION set_updated_at();
COMMIT;
