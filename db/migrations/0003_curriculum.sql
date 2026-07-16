-- 0003: subjects, enrollment (snapshot+delta), staff, chapters, topics, blocks, edges, materials
BEGIN;
CREATE TABLE subjects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id uuid NOT NULL REFERENCES institutions(id),
  created_by uuid NOT NULL REFERENCES users(id),
  name text NOT NULL,
  code text,
  term text,
  status publish_status NOT NULL DEFAULT 'draft',
  settings jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE INDEX ix_subjects_inst ON subjects (institution_id) WHERE deleted_at IS NULL;
CREATE TRIGGER trg_subjects_u BEFORE UPDATE ON subjects FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE subject_staff (
  subject_id uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id),
  PRIMARY KEY (subject_id, user_id)
);

-- snapshot+delta enrollment (FEATURE_EXPLANATION S10): pool edits never auto-propagate
CREATE TABLE subject_enrollments (
  subject_id uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id),
  source_pool_id uuid REFERENCES pools(id),
  status enrollment_status NOT NULL DEFAULT 'active',
  enrolled_at timestamptz NOT NULL DEFAULT now(),
  archived_at timestamptz,
  PRIMARY KEY (subject_id, user_id)
);
CREATE INDEX ix_enrollments_user ON subject_enrollments (user_id);

CREATE TABLE chapters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_id uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  title text NOT NULL,
  position int NOT NULL,
  status publish_status NOT NULL DEFAULT 'draft',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  CONSTRAINT uq_chapters_pos UNIQUE (subject_id, position) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER trg_chapters_u BEFORE UPDATE ON chapters FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- topics: the atomic learning unit. kind='explore' rows form the global Explore library
CREATE TABLE topics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind topic_kind NOT NULL DEFAULT 'subject',
  subject_id uuid REFERENCES subjects(id) ON DELETE CASCADE,
  title text NOT NULL,
  description text NOT NULL DEFAULT '',
  normalized_query text,                       -- explore dedupe key (kind='explore')
  embedding vector(768),
  meta jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  CONSTRAINT ck_topics_scope CHECK (
    (kind = 'subject' AND subject_id IS NOT NULL) OR
    (kind = 'explore' AND subject_id IS NULL)
  )
);
CREATE INDEX ix_topics_subject ON topics (subject_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_topics_embedding ON topics USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ix_topics_title_trgm ON topics USING gin (title gin_trgm_ops);
CREATE TRIGGER trg_topics_u BEFORE UPDATE ON topics FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ordered chapter flow of topic/assessment blocks (S2)
CREATE TABLE chapter_blocks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chapter_id uuid NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  position int NOT NULL,
  block_type block_type NOT NULL,
  topic_id uuid REFERENCES topics(id),
  assessment_id uuid,                          -- FK added in 0004 after assessments exists
  CONSTRAINT uq_blocks_pos UNIQUE (chapter_id, position) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT ck_blocks_one_ref CHECK (
    (block_type = 'topic' AND topic_id IS NOT NULL AND assessment_id IS NULL) OR
    (block_type = 'assessment' AND assessment_id IS NOT NULL AND topic_id IS NULL)
  )
);
CREATE INDEX ix_blocks_chapter ON chapter_blocks (chapter_id);

CREATE TABLE topic_edges (
  src_topic_id uuid NOT NULL REFERENCES topics(id) ON DELETE CASCADE,   -- prerequisite
  dst_topic_id uuid NOT NULL REFERENCES topics(id) ON DELETE CASCADE,   -- dependent
  origin edge_origin NOT NULL DEFAULT 'teacher',
  weight real NOT NULL DEFAULT 1.0,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (src_topic_id, dst_topic_id),
  CONSTRAINT ck_edges_no_self CHECK (src_topic_id <> dst_topic_id)
);
CREATE INDEX ix_topic_edges_dst ON topic_edges (dst_topic_id);

CREATE TABLE materials (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_type material_owner NOT NULL,
  owner_id uuid NOT NULL,                      -- app-enforced polymorphic ref (documented in DATABASE.md)
  kind material_kind NOT NULL,
  title text NOT NULL,
  url text,                                    -- external links
  upload_id uuid,                              -- FK added in 0006 after uploads exists
  extracted_text text,
  readability readability NOT NULL DEFAULT 'stored_only',
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE INDEX ix_materials_owner ON materials (owner_type, owner_id) WHERE deleted_at IS NULL;
CREATE TRIGGER trg_materials_u BEFORE UPDATE ON materials FOR EACH ROW EXECUTE FUNCTION set_updated_at();
COMMIT;
