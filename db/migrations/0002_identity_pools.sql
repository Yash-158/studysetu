-- 0002: institutions, users, pools, pool_members
BEGIN;
CREATE TABLE institutions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  slug text NOT NULL UNIQUE,
  is_personal boolean NOT NULL DEFAULT false,          -- self-serve teacher tier (F2/OQ4)
  settings jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE TRIGGER trg_institutions_u BEFORE UPDATE ON institutions FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id uuid NOT NULL REFERENCES institutions(id),
  role user_role NOT NULL,
  display_name text NOT NULL,
  roll_number text,                                    -- primary student identifier within institution
  email citext,
  password_hash text,                                  -- null until activation completes
  status account_status NOT NULL DEFAULT 'invited',
  activation_code_hash text,                           -- one-time activation / teacher-issued reset
  locale text NOT NULL DEFAULT 'en',
  prefs jsonb NOT NULL DEFAULT '{}',
  last_login_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  CONSTRAINT uq_users_email UNIQUE (email),
  CONSTRAINT uq_users_inst_roll UNIQUE (institution_id, roll_number),
  CONSTRAINT ck_users_identifier CHECK (roll_number IS NOT NULL OR email IS NOT NULL)
);
CREATE INDEX ix_users_institution ON users (institution_id) WHERE deleted_at IS NULL;
CREATE TRIGGER trg_users_u BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE pools (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id uuid NOT NULL REFERENCES institutions(id),
  name text NOT NULL,
  meta jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  CONSTRAINT uq_pools_inst_name UNIQUE (institution_id, name)
);
CREATE TRIGGER trg_pools_u BEFORE UPDATE ON pools FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE pool_members (
  pool_id uuid NOT NULL REFERENCES pools(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id),
  added_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (pool_id, user_id)
);
CREATE INDEX ix_pool_members_user ON pool_members (user_id);
COMMIT;
