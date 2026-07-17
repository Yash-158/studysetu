# ARCHITECTURE.md - StudySetu System Design (FINAL)
Structural truth. Product truth: FEATURE_EXPLANATION.md. Law: RULES.md. Changes via docs/adr/.

## Thesis
One topic graph per subject (topics + prerequisite edges) with a per-student BKT mastery overlay; an append-only event ledger that IS the timeline; and a Generated Content Store enforcing generate-once-serve-forever. The LLM writes content and dialogue; deterministic math does diagnosis, mastery, and guidance.

## Components
- **apps/web**: React 18 + TS + Vite SPA. Role-shelled routes (student/teacher/admin). Runtime config from /config.json (branding -> CSS vars). State: zustand (UI) + react-query (server). PWA/offline machinery deferred to Phase 2 (flag exists).
- **apps/api**: FastAPI modular monolith. modules/: auth, institutions, pools, curriculum, assessment, learning, mastery, analytics, assignments, doubts, explore, mentor, timeline. core/: config (sole config reader), db, security, logging. ai/: facade -> gateway -> providers (sole SDK importers). storage/: StorageProvider (local now; s3 later by config).
- **Data**: PostgreSQL 16 + pgvector, one instance, schema = docs/DATABASE.md (32 tables, validated). Uploads on local volume via StorageProvider; permanent for materials/submissions, TTL for Phase-2 doubt photos.
- **infra**: Docker Compose (api, postgres, caddy) on one DO droplet behind own domain (ADR-001 unchanged: venue/campus-network resilience).

## Canonical flows
DIAGNOSTIC: open topic -> ensure bank exists (Content Store lookup; generate+review-queue if not) -> draw 5 (stratified + weak-prereq slot) -> answers = attempts(context=diagnostic) -> BKT updates -> end-of-probe review (stored explanations) -> events.
SESSION PLAN: planner reads diagnostic + mastery + prereq ancestors (below threshold -> revision segments injected) -> assembles plan from segment_shared artifacts (generating missing segments once) -> learning_sessions.plan -> student plays cards -> practice attempts (instant reasoning) -> mastery/mastery_history -> events.
ASSESSMENT: block in chapter flow -> gating check -> items served -> feedback per assessment mode -> analytics.
ASSIGNMENT: teacher rubric -> student upload (StorageProvider, permanent) -> review screen -> rubric scores + comments -> returned/completed -> events. (AI pre-grade = Phase 2 into submission_reviews.ai_suggested.)
DOUBT (typed): embed -> topics HNSW top-3 -> prereq walk scored (1-p_known)*proximity -> Socratic/direct streaming (RAG over materials.extracted_text) -> transcript stored -> events.
EXPLORE: query -> embed -> global explore-library match (dedupe) -> hit: reuse bank/segments, fresh draw; miss: create kind=explore topic + generate (quota-checked) -> same machinery as subjects, personal namespace.
MENTOR: nightly + on-activity deterministic rules over mastery graph -> mentor_card artifacts (LLM phrases from cached templates only).

## Engineering principles
Config-driven everything (config/*.yaml per subsystem); events over state; lookup-before-generate; one datastore; boring infra on an owned domain; scale story told not built (read replica, redis cache backend, worker split for generation: each a config/one-module swap).

## Decision log
ADR-001 single droplet + self-hosted PG (unchanged). ADR-002 Postgres adjacency graph (unchanged). ADR-003 BKT + deterministic guidance over LLM-judged anything (reaffirmed). ADR-006 local storage behind StorageProvider (extended: permanent classes added). ADR-007 Topics are polymorphic (kind subject|explore) so Explore reuses all machinery. ADR-008 chapter_blocks ordered-flow model for checkpoints. ADR-009 snapshot+delta pool enrollment. ADR-010 Generated Content Store with content-addressed cache keys is a first-class subsystem.
ADR-011 Shared multi-project edge layer: HTTPS termination and reverse-proxying for this droplet live in a SEPARATE repo (`caffeineclause-edge`), not in this one. Reasoning: the droplet hosts multiple team projects; per-repo Caddy + published 80/443 means only one project could ever bind those ports, and each project reimplementing TLS/cert renewal is pure duplication. This repo's `infra/docker-compose.yml` stops publishing 80/443 and joins an external Docker network named `edge` by container name (`studysetu-api`, and `studysetu-web` at M1); `infra/Caddyfile` here is reference documentation only, copied by hand into the edge repo. Subdomains are flat (`studysetu.caffeineclause.tech`, `studysetu-api.caffeineclause.tech`) because the team's wildcard DNS record is single-label, which also makes frontend/API genuinely cross-origin (CORS + an explicit API base URL, not same-origin proxying, in production). Tradeoff accepted: a routing change now touches two repos instead of one; mitigated by keeping the edge repo's Caddyfile a straight concatenation of each project's documented block.
