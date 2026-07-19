# DEVELOPMENT_GUIDE.md - One Line of Code to Production
## The loop, end to end
1. **Session start**: `bash scripts/verify_local.sh` -> open repo (`code .` inside WSL) -> read docs/MEMORY.md + current ROADMAP milestone.
2. **Stack up**: `docker compose -f infra/docker-compose.dev.yml up -d` (Postgres) -> `bash scripts/migrate.sh` (idempotent) -> `uv run scripts/seed_demo.py` if fresh -> terminal A: `cd apps/api && APP_CONFIG_DIR=../../config APP_PROMPTS_DIR=../../prompts uv run uvicorn app.main:app --reload` -> terminal B: `cd apps/web && pnpm dev`. Open http://localhost:5173 (proxies /api + /config.json to :8000).
3. **Write code** on branch `feat/mN-<thing>` (one ROADMAP checkbox). Config knobs go in config/*.yaml the moment they exist; prompts go in /prompts.
4. **Test**: `uv run pytest` (api), `pnpm test` + `pnpm typecheck` (web), Playwright milestone spec against the seeded stack. New behavior ships WITH its test.
5. **Commit/push**: conventional message -> PR -> CI (api, web, migrations jobs) -> review with PROMPTS.md P-REVIEW -> squash-merge.
6. **CD**: watch Actions -> image to GHCR -> droplet deploy.sh -> verify https://api.<domain>/healthz and the feature live -> Sentry quiet for 10 min.
7. **Session end (mandatory)**: update docs/MEMORY.md snapshot + tick ROADMAP -> push.

## Database day-to-day
Reset: `docker compose -f infra/docker-compose.dev.yml down -v && up -d && migrate && seed`. Inspect: `docker compose -f infra/docker-compose.dev.yml exec postgres psql -U app appdb`. New table/column: edit docs/DATABASE.md -> write db/migrations/000N_*.sql -> migrate locally -> CI migration job proves it -> CD applies to prod. Never edit an applied migration; never point local tools at the prod DATABASE_URL.

## Debugging order
Reproduce locally with seeded data -> failing test first -> ranked hypotheses (PROMPTS.md P-DEBUG) -> fix -> regression test -> MEMORY.md known-issues update. Prod-only issues: Sentry event -> logs (`docker compose logs api --tail 200` on droplet) -> reproduce locally from the event's inputs.
