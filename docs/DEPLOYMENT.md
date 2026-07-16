# DEPLOYMENT.md - How StudySetu Ships
## Environments
LOCAL (WSL): postgres in Docker (compose.dev), api native (uvicorn --reload), web native (vite), uploads to ./.local-uploads. PRODUCTION (DO droplet prod-1): compose.yml (api image from GHCR, postgres, caddy) at /home/deploy/app; own domain, Caddy TLS; volumes pg_data/uploads_data/backups_data/caddy_data.

## Pipeline (every merge to main)
CI (PR): ruff+pytest (api), typecheck+vitest (web), **migration job applies db/migrations against a throwaway pgvector service**: schema breakage cannot merge. CD (main): build api image -> push ghcr.io/<owner>/studysetu-api:<sha> -> SSH -> infra/deploy.sh: compose pull/up, migrate.sh inside container, healthcheck, auto-rollback to previous tag on failure (.current_tag file). Frontend build+rsync to ./site added in M1.

## Secrets
GitHub Actions: DROPLET_HOST/USER/SSH_KEY (+ GITHUB_TOKEN for GHCR). Droplet: /home/deploy/app/.env (chmod 600). Local: repo .env. Rotation = edit one place + restart.

## Database lifecycle
Migrations: forward-only, expand-then-contract, ledgered (schema_migrations). Deploys never touch pg_data. Rollback = previous image tag; DB never rolls back. Backups: scripts/backup_db.sh nightly cron (dumps, keep 7; weekly uploads tar) -> weekly scp pull to a laptop -> weekly restore drill into Neon -> DO snapshots. Full recovery runbook: new droplet -> restore latest dump -> repoint DNS (TTL 5 min) -> redeploy tag.

## Release discipline
main always deployable; demo/launch freeze = tag + stop merging; hotfix = branch from tag, cherry-pick back.
