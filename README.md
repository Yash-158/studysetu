# StudySetu
**A Personalized Learning Platform for Every Student.**

The teacher teaches. StudySetu makes sure it stuck: for every single student. An AI-powered revision and assessment companion: adaptive diagnostics from teacher-reviewed question banks, personalized learning sessions with prerequisite-aware revision, mastery tracking, timelines, and teacher analytics that turn into one-click action.

## Repository map
| Path | What lives here |
|---|---|
| docs/ | The Bible: FEATURE_EXPLANATION (functional truth), ARCHITECTURE, DATABASE, RULES, ROADMAP, CONFIG, DEPLOYMENT, DEVELOPMENT_GUIDE, PROMPTS, MEMORY (living state) |
| apps/web | React 18 + TS + Vite frontend |
| apps/api | FastAPI modular monolith |
| packages/shared | OpenAPI-generated types + BKT test vectors |
| db/migrations | Canonical SQL schema (validated) + scripts/migrate.sh |
| config/ | Per-subsystem YAML configuration (nothing hardcoded) |
| infra/ | docker-compose (dev+prod), Caddyfile (reference only - live reverse-proxy is the separate caffeineclause-edge repo, ADR-011), deploy.sh, droplet-bootstrap.sh |
| prompts/ | Versioned LLM prompt files |
| scripts/ | migrate, seed, backup, verify_local, verify_server |
| .github/workflows | CI (lint/test/migration-check) + CD (build->GHCR->droplet) |

## Start here
1. New human or coding agent: read docs/MEMORY.md, then docs/RULES.md, then docs/ROADMAP.md current milestone.
2. Environment: docs/DEVELOPMENT_GUIDE.md (local loop) and docs/INFRA_SETUP_GUIDE.md (cloud, once).
3. Verify: `bash scripts/verify_local.sh` must print its success line before any development session.
4. Implement: use the milestone prompts in docs/PROMPTS.md, in order.

## Non-negotiables (full list: docs/RULES.md)
Config only via the two config modules. Provider SDKs only under apps/api/app/ai/providers/. All file I/O via StorageProvider. Every user-visible action emits a timeline event. Every AI output is stored before it is shown (lookup-before-generate). No business logic merges without its milestone's tests.
