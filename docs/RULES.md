# RULES.md - The StudySetu Constitution (FINAL)
Absolute, enforceable in review. Only grows; removals need a MEMORY.md entry.

## Architecture
1. Provider SDKs imported ONLY in apps/api/app/ai/providers/. Feature code uses the ai.* facade.
2. Config/env read ONLY in apps/api/app/core/config.py and apps/web/src/lib/config.ts. Every subsystem's knobs live in its config/*.yaml. No hardcoded behavior, names, colors, models, thresholds, or URLs.
3. Every user-visible action emits an events row (the timeline ledger). Events are append-only; state (mastery, statuses) is derived or explicitly transitioned, never back-edited.
4. Every AI output is written to generated_artifacts BEFORE being shown; every generation is preceded by a cache_key lookup. No un-stored AI content ever reaches a user.
5. Only items with review_status='approved' are ever served to students.
6. All file I/O via StorageProvider. LLM prompts are files in /prompts, versioned (prompt_version in cache keys).
7. Modular monolith: no new services/containers without an ADR. content-affecting schema changes: DATABASE.md first, then a forward-only migration (expand-then-contract), never edit an applied file.
## Code
8. TypeScript strict; ruff on Python; CI (lint+test+migration-check) must be green to merge. Conventional commits, squash merges, branch per ROADMAP checkbox.
9. Deterministic logic (BKT, drawing, guidance rules, clustering) never calls an LLM. LLMs never assign marks, levels, or mastery.
## Security & privacy
10. Secrets in .env only; never in YAML, code, logs, or client bundles. Role guard on every non-student route, institution-scoping on every query (no cross-institution reads, ever).
11. Students are told when transcripts/artifacts are teacher-visible. Doubt photos (Phase 2) TTL-deleted; submissions/materials permanent and backed up. Minimal PII: name, roll, optional email.
12. Assessment-integrity features are config flags; code branches on config values only; webcam stays off absent explicit consent UX.
## Errors & ops
13. AI gateway: per-provider timeout, one parse retry, chain failover, typed error to a friendly retry card; raw provider errors never reach users. All API errors: {code, message, hint}.
14. Empty catch blocks forbidden. Structured logs only (no print). /healthz never behind auth.
## Process
15. Every session ends with the MEMORY.md snapshot update (docs/MEMORY.md format) and ROADMAP checkbox updates: by the same session that did the work.
16. Nothing demos that is not in DEMO_RUNBOOK.md with a rehearsed fallback. No new dependency without a MEMORY.md line.
