#!/usr/bin/env bash
# Applies db/migrations/*.sql in order, once each, recording them in schema_migrations.
# Usage: DATABASE_URL=postgres://... scripts/migrate.sh   (defaults to the dev docker compose postgres)
set -euo pipefail
run_psql() {
  if [ -n "${DATABASE_URL:-}" ]; then psql "$DATABASE_URL" "$@";
  else docker compose -f infra/docker-compose.dev.yml exec -T postgres psql -U app -d appdb "$@"; fi
}
run_psql -v ON_ERROR_STOP=1 -c "CREATE TABLE IF NOT EXISTS schema_migrations (filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());"
for f in db/migrations/*.sql; do
  name=$(basename "$f")
  if run_psql -tAc "SELECT 1 FROM schema_migrations WHERE filename='$name'" | grep -q 1; then
    echo "skip   $name"; continue
  fi
  echo "apply  $name"
  run_psql -v ON_ERROR_STOP=1 < "$f"
  run_psql -v ON_ERROR_STOP=1 -c "INSERT INTO schema_migrations (filename) VALUES ('$name');"
done
echo "migrations complete"
