# PROMPTS.md - The Coding Bible
Use the PREAMBLE at the start of EVERY session, then the milestone prompt for the current ROADMAP checkbox. Utility prompts at the end.

---
## THE PREAMBLE (paste first, always)
You are the implementing engineer on **StudySetu** (A Personalized Learning Platform for Every Student): a senior full-stack engineer who values boring, correct, config-driven code.

**Before writing anything, read in this order:** docs/MEMORY.md (current state: trust it), docs/RULES.md (the constitution: every rule is blocking), docs/ROADMAP.md (find the current milestone), docs/FEATURE_EXPLANATION.md sections relevant to this milestone (functional truth), docs/ARCHITECTURE.md (structure + flows), docs/DATABASE.md (schema: migrations are canonical), docs/CONFIG.md (where every knob lives), README.md (repo map). For UI work also read docs/DESIGN.md; for deployment-touching work docs/DEPLOYMENT.md.

**Discipline:** (Folder) code goes exactly where ARCHITECTURE.md says; provider SDKs only in app/ai/providers; config reads only in the two config modules; prompts only in /prompts. (Config) any new tunable value goes into its config/*.yaml the moment it exists: hardcoding is a review-blocking defect. (Events) every user-visible action emits a timeline event. (AI) lookup generated_artifacts before generating; store before showing. (Testing) new behavior ships with its test in the same PR; the milestone's GATE gets an e2e spec. (Git) branch feat/mN-<slug>, conventional commits, small diffs, squash merge. (Docs) the SAME session updates MEMORY.md (snapshot format) and ticks ROADMAP.md.

**Completion checklist before you declare done:** [ ] GATE criteria demonstrably pass [ ] all new knobs in config [ ] events emitted [ ] tests green locally + CI [ ] no RULES violation (self-review against the list) [ ] MEMORY.md + ROADMAP.md updated [ ] deployed and verified on the domain if CD is live.

**Always:** propose a short plan (files, approach, tests, risks) and wait for approval before multi-file changes. If reality contradicts the docs, STOP and surface it: do not silently improvise.

---
## Milestone prompts

### M0 - Foundation online
Objective: everything in the skeleton actually runs: local stack, migrations, health, config.json, CI green, CD deploying to the droplet.
Modify: apps/api (make main/config/logging real: pydantic validation, loguru+Sentry), scripts/verify_*.sh gaps, .github/workflows (unblock real steps), infra/deploy.sh paths, apps/web boot.
Avoid: all modules/* business logic, db schema, prompts/.
Acceptance: verify_local passes fully; CI 3 jobs green; https://api.<domain>/healthz + /config.json live via CD; local `pnpm dev` renders the StudySetu shell reading /config.json.
Verify: kill a config key -> API refuses to boot with a clear error; merge a comment change -> live in <5 min.
Output: running foundation, zero features.

### M1 - Identity, roles, shells
Objective: FEATURE_EXPLANATION F1: activation flow (roll/email + one-time code -> set password), login, JWT access+refresh, role guards; role-routed shells (student/teacher/admin) + landing page; frontend added to CD (build -> droplet ./site).
Modify: modules/auth.py, core/security.py, core/db.py (models for institutions/users only), web features/auth + role shells, seed_demo (institution+3 users), e2e/auth_roles.spec.ts.
Avoid: pools, curriculum, AI, storage.
Acceptance: seeded admin/teacher/student activate, log in, land on distinct shells, on the real domain; wrong-role route access = 403; refresh works across restart.
Verify: token expiry path; anomaly flag (auth.yaml) emits warn event on concurrent login.
Output: living authentication and the app's skeleton UX.

### M2 - Institution, pools, people
Objective: F2/F3 admin domain: teacher/student CRUD + CSV import, activation issuance (codes printable), pools + members, self-serve teacher tier (personal institution on teacher signup path).
Modify: modules/institutions.py, modules/pools.py, admin feature UI, seed_demo (pool CSE-3A + 8 students), e2e.
Avoid: subjects/curriculum, AI.
Acceptance: CSV of 10 students -> accounts invited -> pool -> activation codes issued -> all can log in; personal institution created via self-serve path.
Verify: institution-scoping (RULES #10): admin A cannot read institution B (test).
Output: the people layer, complete.

### M3 - Curriculum builder
Objective: F4/F5: subjects, chapters, topics, ordered chapter_blocks with reorder, topic_edges UI (teacher links), materials upload via StorageProvider + text-PDF extraction (readability flag), publish flow, pool attach = snapshot+delta enrollment + "new pool members" banner.
Modify: modules/curriculum.py, storage/local.py (real), teacher feature UI (builder screens), seed_demo (DIP subject full), e2e/curriculum_crud.spec.ts.
Avoid: items/banks, diagnostics, AI generation.
Acceptance: GATE: Anvi builds Digital Image Processing (2 chapters, 5 topics, 1 edge Transforms->Frequency Filtering, 1 assessment placeholder block, 1 PDF material) and publishes; enrolled Yash sees published structure only (drafts hidden).
Verify: reorder persists atomically (deferrable constraint); scanned PDF gets stored_only badge; pool edit does NOT change enrollment until banner action.
Output: teachers can author their course.

### M4 - AI gateway, banks, diagnostics
Objective: F6/F7 + the AI substrate: gateway (chains, timeouts, failover, ai_invocations, demo_mode) + providers (claude/gemini/groq) + Generated Content Store (lookup-before-generate); per-topic bank generation (12-15, difficulty+misconception-tagged, explanations) into teacher review queue + review UI; diagnostic engine (stratified draw + weak-prereq slot), probe UI (neutral acks), end-of-probe review screen; attempts + BKT (config params) + mastery/mastery_history.
Modify: ai/* (all), modules/assessment.py (banks+review), modules/learning.py (diagnostic), modules/mastery.py, prompts/item_bank.md + explanations, student probe UI, e2e/diagnostic_flow.spec.ts.
Avoid: session planner, analytics, doubts.
Acceptance: GATE: fresh topic -> generate -> review queue -> approve-all -> Yash's probe (5 items, 1 from weak prereq when history exists) -> review screen shows stored reasoning -> mastery rows updated; second bank request = cache hit (ai_invocations.cache_hit=true).
Verify: kill primary provider key -> chain fails over, invocation logged; draft items NEVER served (test RULES #5).
Output: the assessment brain.

### M5 - Personalized learning
Objective: F8/F9: session planner (diagnostic + mastery + prereq walk -> revision injection below threshold), segment generation into segment_shared cache, session player per S16 recipe (bridge/revision/explanation/worked/practice-with-instant-reasoning/contrast/summary/cheatsheet), timeline events end-to-end + student timeline screen (F13).
Modify: modules/learning.py (planner+sessions), modules/timeline.py, prompts/segment.md, student learning UI + timeline UI, e2e/learning_session.spec.ts.
Avoid: teacher analytics, doubts, mentor.
Acceptance: GATE: Yash (weak Transforms) opens Frequency Filtering -> plan shows injected Transforms revision first -> completes session -> mastery moves -> timeline shows the full causal chain; a SECOND weak student's session hits segment cache (verify ai_invocations).
Verify: plan is stable (stored jsonb) across reloads; abandoned session resumable.
Output: the product's core promise, working.

### M6 - Teacher analytics
Objective: F12: Today view (stuck, misconception clusters, ungraded: each with an action), Explorer drill-down (subject->chapter->topic->student), heat views, per-student detail incl. their timeline + AI artifacts (F14 visibility + flag button), misconception clustering (GROUP BY).
Modify: modules/analytics.py, teacher UI suite, e2e/teacher_analytics.spec.ts.
Avoid: assignments, doubts.
Acceptance: GATE: seeded cohort activity produces a true "distributes-first-term-only x5" cluster on Today; teacher drills cluster -> student -> the exact wrong attempts; flags one AI artifact.
Verify: analytics respect enrollment archive status; empty states designed (DESIGN.md).
Output: the teacher's command center.

### M7 - Assessments & assignments
Objective: F-assessment + F10: assessment blocks live (gating modes enforced, feedback instant/end/after_deadline, taking UI, results to analytics); assignments (rubric builder, upload submission, teacher review screen with rubric scoring + comments + return-for-revision, statuses on timelines).
Modify: modules/assessment.py (taking), modules/assignments.py, storage (submission purpose, permanent), teacher+student UI, e2e.
Avoid: AI grading (Phase 2), doubts.
Acceptance: GATE: mid-chapter checkpoint blocks correctly under 'locked', advises under 'recommended'; full assignment round-trip assigned->submitted->reviewed->returned->resubmitted->completed, visible on both timelines.
Verify: after_deadline feedback hides answers until due_at (test); security flags (security.yaml) emit events during assessment when enabled.
Output: formal evaluation, both automatic and human.

### M8 - Doubts & Explore
Objective: F11 + F16: typed doubt -> embed -> topic match -> root-gap (prereq walk x mastery) -> Socratic/direct streaming grounded in materials.extracted_text -> transcript stored + teacher-visible; Explore: query -> global library dedupe -> reuse or quota-checked creation (kind=explore topic) -> same diagnostic->session machinery, personal namespace.
Modify: modules/doubts.py, modules/explore.py, prompts/socratic.md + direct.md + explore, student UI, e2e.
Avoid: OCR paths (flag stays false).
Acceptance: GATE: doubt about Frequency Filtering identifies Transforms as root and teaches it first; "What are vectors?" from two students = ONE generation (second is library hit); 4th Explore topic in a week politely quota-blocked.
Verify: Socratic contract (no final answer before 2 attempts) enforced by prompt + validated output; student sees the teacher-visibility notice.
Output: curiosity, served affordably.

### M9 - Mentor & guidance
Objective: F15 + decay: deterministic next-best-action (impact x weakness x recency), revision queue (confidence decay job from database.yaml halflife), weekly deltas, mentor cards (LLM phrasing from cached templates only), student home = mentor panel.
Modify: modules/mentor.py, decay job wiring, student home UI, e2e.
Acceptance: GATE: mastery shift changes the recommended action correctly; 6-simulated-weeks decay resurfaces Transforms in the revision queue.
Verify: mentor NEVER calls generation for decisions (code-level assertion/test).
Output: analytics that talk like a mentor.

### M10 - Admin & cost
Objective: F14/F-admin: flagged-artifact review queue, effective-config viewer (secrets masked), AI cost dashboard (ai_invocations rollups: per task/provider/institution, cache-hit rate, Rs-per-student), security flag surfacing on teacher views.
Modify: modules for admin surface, admin UI, e2e.
Acceptance: GATE: teacher-flagged artifact appears in admin queue with hide/regenerate; cost dashboard shows real numbers from M4-M9 activity.
Output: trust, governance, and the cost story.

### M11 - Hardening & demo
Objective: full e2e suite, seed_demo complete + <10s, DEMO_RUNBOOK.md rewritten for StudySetu (script + fallbacks + reset), backups cron live + ONE restore drill executed, 60-concurrent-student sanity, DESIGN.md polish pass (states, a11y, motion).
Acceptance: GATE: two consecutive flawless runbook executions by the demo driver; restore drill documented in MEMORY.md.
Output: a product you can show anyone.

### M12 - Phase 2 kickoff (post-launch)
OCR intake -> AI pre-grade (teacher-confirms) -> offline sync (events client_id/seq) -> syllabus import: one flag at a time, each with its own mini-gate. Plan refreshed at M11 retro.

---
## Utility prompts
**P-DEBUG**: "Bug: {symptom}. Output: {paste}. Read the owning module + MEMORY known-issues. Give a RANKED root-cause hypothesis list with evidence BEFORE any fix. After I pick: fix, add regression test, update MEMORY."
**P-REVIEW**: "Review PR {n} against docs/RULES.md rule-by-rule. Check specifically: config reads outside core/config, SDK leakage outside ai/providers, missing events, un-stored AI output, missing institution scoping, hardcoded values, draft items served. Output: blocking / nits / verdict."
**P-REFACTOR**: "Refactor {target} for {goal}. Zero behavior change (tests prove), no new deps, no schema change. Structure before/after first; wait."
**P-DOCS**: "Feature merged: {summary}. Update MEMORY.md snapshot, tick ROADMAP, update DEMO_RUNBOOK if demo paths changed. Show doc diffs only."
