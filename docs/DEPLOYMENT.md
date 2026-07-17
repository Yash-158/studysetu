# DEPLOYMENT.md - How StudySetu Ships
## Environments
LOCAL (WSL): postgres in Docker (compose.dev), api native (uvicorn --reload), web native (vite), uploads to ./.local-uploads. PRODUCTION (DO droplet, multi-project, IP 64.227.177.181): compose.yml (api image from GHCR, postgres) at /home/deploy/studysetu; volumes pg_data/uploads_data/backups_data. This stack does NOT publish 80/443 and does NOT run Caddy - see Edge layer below.

## Edge layer (shared, out-of-repo)
TLS termination and reverse-proxying for `studysetu.caffeineclause.tech` (frontend, added M1) and `studysetu-api.caffeineclause.tech` (backend) are owned by a SEPARATE repo, `caffeineclause-edge`, one Caddy instance shared across every team project on this droplet (docs/ARCHITECTURE.md ADR-011). That repo runs its own compose stack: Caddy on the external `edge` Docker network, ports 80/443 published, TLS auto-provisioned. This repo's `infra/docker-compose.yml` joins `edge` (created once via `infra/droplet-bootstrap.sh`) so Caddy can reach `studysetu-api` by container name; `infra/Caddyfile` here is REFERENCE ONLY - the block to copy into `caffeineclause-edge`'s Caddyfile.
Subdomains are FLAT (one label under `caffeineclause.tech`), not nested: the team's wildcard DNS record matches one label deep only, so `api.studysetu.caffeineclause.tech` would not resolve. Frontend and API are therefore cross-origin; `config/deployment.yaml`'s `cors_origins` + `api_base_url` and `apps/web/.env.production`'s `VITE_API_BASE_URL` are the two sides of that wire.

## Pipeline (every merge to main)
CI (PR): ruff+pytest (api), typecheck+vitest (web), **migration job applies db/migrations against a throwaway pgvector service**: schema breakage cannot merge. CD (main): build api image -> push ghcr.io/<owner>/studysetu-api:<sha> -> SSH -> infra/deploy.sh: compose pull/up, migrate.sh inside container, healthcheck via `docker compose exec` (no public port owned by this stack), auto-rollback to previous tag on failure (.current_tag file). Frontend build+rsync + its own small static-file container on the `edge` network: added in M1.

## Secrets
GitHub Actions: DROPLET_HOST/USER/SSH_KEY (+ GITHUB_TOKEN for GHCR). Droplet: /home/deploy/studysetu/.env (chmod 600). Local: repo .env. Rotation = edit one place + restart.
**Local and production .env are NOT the same file with the same values - this is intentional, not a bug.** They diverge on: DATABASE_URL host (local: `localhost` - Postgres runs via docker-compose.dev.yml with a published port; production: the Docker Compose service name `postgres` - api and postgres share the stack's internal `default` network, no published port, see infra/docker-compose.yml) and every secret value (POSTGRES_PASSWORD, JWT_SECRET, SMTP_PASSWORD, provider API keys - local uses throwaway/dev values, production uses real generated secrets). Both environments read the SAME config/*.yaml (shipped in the image); only .env and APP__ overrides differ, per docs/CONFIG.md. **Known gotcha (M0):** the production .env was first placed on the droplet from a template still containing a literal `<PASTE_POSTGRES_PASSWORD>` placeholder string - Postgres then rejected the real value docker-compose.yml substituted in, and the container never became healthy. There is no automated check for this; when placing a fresh production .env, grep it for `<PASTE_` / `CHANGE-ME` before the first `docker compose up`.

## Database lifecycle
Migrations: forward-only, expand-then-contract, ledgered (schema_migrations). Deploys never touch pg_data. Rollback = previous image tag; DB never rolls back. Backups: scripts/backup_db.sh nightly cron (dumps, keep 7; weekly uploads tar) -> weekly scp pull to a laptop -> weekly restore drill into Neon -> DO snapshots. Full recovery runbook: new droplet -> restore latest dump -> repoint DNS (TTL 5 min) -> redeploy tag.

## Release discipline
main always deployable; demo/launch freeze = tag + stop merging; hotfix = branch from tag, cherry-pick back.
