# PRD.md - StudySetu (FINAL, reflects approved FEATURE_EXPLANATION.md)
Product: **StudySetu**. Tagline: **A Personalized Learning Platform for Every Student.**

## Vision and philosophy
Teachers remain the primary source of learning. StudySetu is the intelligent companion that handles what one human cannot do for 60 students at once: continuous diagnosis, personalized revision, adaptive practice, weak-topic detection with prerequisite awareness, and analytics that convert into one-click teacher action. Not a lecture replacement: a learning gymnasium attached to every course.

## Users
Institution admin (provisions accounts, pools, config, aggregate analytics) · Teacher (subjects, chapters/topics, checkpoints, banks review, grading, analytics, doubts) · Student (diagnose -> personalized session -> practice -> assessments -> assignments -> doubts -> Explore; owns their timeline). Self-serve teacher tier: an institution-of-one (approved OQ4).

## Scope: Phase 1 (frozen; detail in FEATURE_EXPLANATION.md S17 F1-F17)
Identity (institution-provisioned, roll+password, activation), pools (snapshot+delta enrollment), Subject->Chapter->Topic with ordered Topic/Assessment blocks, materials (text-PDF grounding), per-topic AI item banks with teacher review, 5-question diagnostics (stratified draw + weak-prereq slot; feedback at end-of-probe), personalized sessions (S16 recipe; shared-segment assembly; prereq revision injection), BKT mastery + confidence decay, checkpoint assessments (gating + feedback modes), manual assignments (rubric, upload, teacher review), typed doubts (root-gap + Socratic/direct), three-altitude analytics + timelines, mentor guidance (deterministic), Explore (quota 3/week, global dedupe library), Generated Content Store + cost ledger, configurable security flags.

## Explicit Phase 2 (architected dark, flags exist)
OCR (photo doubts, scanned materials, AI pre-grading with teacher confirm), offline PWA sync (events.client_id/seq ready), adaptive item selection, syllabus-PDF auto-structuring, video intelligence, email digests.

## Non-goals (v1): payments, parent accounts, cross-institution features, native apps, runtime lesson generation (sessions assemble pre-generated segments), AI-released marks.

## Success criteria
A teacher builds a subject with 2 chapters and publishes in <15 minutes. A student completes diagnostic->session->practice in <15 minutes with zero dead ends. Bank generation: <60s per topic, 100% through review queue. Cache hit rate >80% on session segments after first cohort pass. Teacher Today-view surfaces a true stuck/cluster signal within 30s of the triggering activity. AI marginal cost per active student per week: measured and displayed (admin), target < Rs 5.

## Assessment integrity: all flags configurable (config/security.yaml); webcam OFF by default; framing = friction and visibility, not certainty.

## Scope changes: (append: date | change | reason | approved by)
