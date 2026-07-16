# CLAUDE.md - StudySetu
You are working on **StudySetu** (A Personalized Learning Platform for Every Student): an AI revision and assessment companion for teachers and students.

**Read before ANY work, in order:** docs/MEMORY.md (current state) -> docs/RULES.md (constitution, blocking) -> docs/ROADMAP.md (current milestone) -> docs/PROMPTS.md (use the PREAMBLE + the milestone prompt) -> then FEATURE_EXPLANATION.md / ARCHITECTURE.md / DATABASE.md / CONFIG.md sections relevant to the task. UI work: also docs/DESIGN.md.

**Hard rules (full list docs/RULES.md):** config only via app/core/config.py + web/src/lib/config.ts (every knob in config/*.yaml); provider SDKs only in app/ai/providers/; file I/O only via StorageProvider; every user-visible action emits an events row; AI output stored (generated_artifacts) before shown, lookup-before-generate; only approved items reach students; forward-only migrations; tests ship with behavior; the SAME session updates docs/MEMORY.md and ticks docs/ROADMAP.md.

**Environment:** WSL2 Ubuntu; repo at ~/dev/studysetu (never /mnt/c); local stack per docs/DEVELOPMENT_GUIDE.md; `bash scripts/verify_local.sh` must pass at session start.
