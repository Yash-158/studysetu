# MEMORY.md - Living Project State (read FIRST every session; update LAST every session)
Format: replace the SNAPSHOT in place; append one line to the LOG. This is a state document, not a diary.

## SNAPSHOT (current truth)
**Project status:** Foundation complete and frozen. Zero business logic implemented. Awaiting M0.
**Product:** StudySetu - A Personalized Learning Platform for Every Student (name FINAL; see docs/BRANDING.md).
**Completed milestones:** none (foundation precedes M0).
**Current milestone:** M0 Foundation online (docs/ROADMAP.md).
**Next session objective:** Execute PROMPTS.md M0: make the skeleton run (local stack, CI green, CD to droplet, verify scripts pass).

**Architecture in one paragraph:** FastAPI modular monolith + React SPA on one DO droplet (Docker Compose: api/postgres/caddy) behind an owned domain. Topic graph + BKT mastery + append-only events ledger (= the timeline) + Generated Content Store (lookup-before-generate) are the four load-bearing ideas. All behavior config-driven via config/*.yaml per subsystem. Full detail: ARCHITECTURE.md.

**Folder summary:** apps/api (backend; modules are docstring stubs), apps/web (frontend shell; boots from /config.json), db/migrations (0001-0006, VALIDATED: 32 tables), config/ (13 subsystem YAMLs), infra/ (compose dev+prod, Caddyfile, deploy.sh), prompts/ (5 stubs), scripts/ (migrate/seed-stub/backup/verify x2), e2e/ (spec plan), .github/workflows (ci with migration-check job, deploy with rollback).
**Important files:** docs/FEATURE_EXPLANATION.md (functional truth, APPROVED), docs/RULES.md, docs/DATABASE.md, docs/ROADMAP.md, docs/PROMPTS.md, docs/CONFIG.md, apps/api/app/core/config.py (sole config reader), apps/api/app/ai/__init__.py (facade contract).

**Key decisions (ADR-001..010 in ARCHITECTURE.md):** self-hosted PG on droplet; polymorphic topics (subject|explore); chapter_blocks ordered flow; snapshot+delta pools; Content Store first-class; deterministic guidance; teacher-in-loop grading; item-bank diagnostics with end-of-probe feedback.
**Known issues:** none. **Deviations from docs:** none.
**Current configuration notes:** domain placeholders CHANGE-ME in config/deployment.yaml + infra/Caddyfile (set after domain claim); GITHUB_OWNER placeholder in infra/docker-compose.yml; ai.embedding_dim=768 must match the chosen embedding model before M4.

## LOG (append one line per session: date | milestone | one-line outcome)
2026-07-15 | foundation | StudySetu foundation v2 finalized: schema validated (32 tables), skeleton, config system, docs, prompts, verify scripts; ZIP = repo (single source of truth).
