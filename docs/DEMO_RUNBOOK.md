> STATUS: structure retained from v1; the demo script is REWRITTEN AT M11 for StudySetu (see ROADMAP). Fallback philosophy (demo_cache, seeded resets, rehearsed paths) is unchanged and binding.

# DEMO_RUNBOOK.md - The Demo Is a Procedure, Not a Performance
Purpose: click-by-click script, reset procedure, and failure playbooks. Updated after EVERY rehearsal. Nothing untested may appear here; nothing absent from here may be demoed (RULES.md #27).

## Roles
DRIVER (hands only, never talks) | NARRATOR (talks, never touches) | SAFETY (watches Sentry + hotspot, runs resets).

## Step 0 - Reset (before every run, <60s)
1. `uv run scripts/seed_demo.py` (wipes to seeded class: 8 students, 3 personas active)
2. Student phone: SETU installed, logged in as Priya, unit pack downloaded, airplane mode OFF
3. Teacher laptop: dashboard open on class GJ8A via hotspot-capable network
4. Props: notebook page A (primary), page B (backup) at marked page
5. Verify golden cache: demo_mode=true in config; /healthz green

## Script (7 min) - each step lists its FALLBACK
1. (0:00) Narrator: problem framing, one stat. [no tech]
2. (0:30) Diagnostic on phone -> "Builder" reveal. FALLBACK: persona pre-seeded mid-lesson, skip to 3.
3. (1:30) Lesson card -> deliberately choose distractor 2 -> misconception hint appears. FALLBACK: any distractor works; all tagged.
4. (2:30) Photograph notebook page A -> confirmation screen -> root gap "Distributive Property, 2 levels upstream" -> 2 Socratic turns. FALLBACK 1: page B. FALLBACK 2: type the question (path always works, golden-cached).
5. (4:00) AIRPLANE MODE ON -> answer 2 more items -> OfflinePill shows queued. FALLBACK: none needed; fully local.
6. (5:00) Airplane OFF -> cut to teacher laptop: rows update, cluster "sign error x7" alert -> one-click remediation push. FALLBACK: SAFETY triggers seeded sync burst via /demo/seed?burst=1.
7. (6:00) Class graph heat map -> close on architecture one-liner: "The LLM explains; the graph and the probability model decide."

## Failure playbooks
- Venue network dead: hotspot (SAFETY's phone) already configured on teacher laptop; droplet is external so hotspot suffices.
- Droplet down: NARRATOR continues on phone (offline story intact) while SAFETY plays backup video for teacher half.
- LLM chain fully down: demo_mode golden cache serves the scripted doubt; narrate the failover as a feature.
- Projector issues: phone-mirroring app pre-installed; else backup video.

## Rehearsal log
(append: datetime | run # | what broke | fix | script version)
