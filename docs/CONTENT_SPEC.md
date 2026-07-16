> STATUS: v1 authoring spec retained as reference. The BINDING content specs for StudySetu are FEATURE_EXPLANATION.md S16 (session recipe: bridge/revision/explanation/worked example/practice/contrast/summary/cheat-sheet, <=120 words per card) and S3 (item banks: 12-15 per topic, difficulty -1/0/1, misconception-tagged options, stored explanations). Card and item JSON schemas are formalized at M4/M5 alongside their generators.

# CONTENT_SPEC.md - Curriculum Content Schemas
Purpose: makes content mass-producible by any teammate or by Claude Code (content-author skill). All files in content/ MUST validate against these schemas (schema_version: 1). Actual content never lives in this doc.

## taxonomy.json
{ schema_version, subject: "maths-g8", nodes: [{ id: "alg.distributive", unit: "algebra",
  title, description(<=40 words, embedding-bearing), examples: [3 canonical questions],
  level_tags: ["foundational"|"grade"|"advanced"], i18n: {hi: {...}} }],
  edges: [{src, dst, type: "prereq"}] }
Rules: DAG only (validator rejects cycles); every node reachable; ids namespaced unit.slug; 40-50 nodes total.

## items/<node>.json
{ schema_version, node_id, items: [{ id, stem(markdown+LaTeX), options: [4],
  correct: index, difficulty_b: -1|0|1, misconception_tags: {"1": "sign-transposition", "2": "distribute-first-only", "3": "guess"} }] }
Rules: exactly one correct; EVERY distractor tagged from the misconception registry below; >=1 item per (node x difficulty) used by the probe; stems self-contained (no "refer to above").

## Misconception registry (extend here, never inline)
sign-transposition | distribute-first-only | like-terms-mixing | exponent-add-on-multiply | fraction-cross-add | formula-recall-swap | unit-confusion | guess

## lessons/<node>.<level>.json
{ schema_version, node_id, level, duration_min: 10, cards: [
  {type: "concept", md}, {type: "worked", md}, {type: "practice", item_ref},
  ... exactly 3 practice refs interleaved ], summary_md }

## ncert_chunks/
Plain-text chunks 200-400 words, front-matter: {chapter, page, node_ids: []}. Embedded by scripts/embed_taxonomy.py into pgvector with metadata for citations ("NCERT 8, Ch 9, p. 143").

## Authoring checklist (per node)
[ ] description embeds well (contains the words students actually use)
[ ] 3 examples span phrasings (symbolic, word-problem, visual-verbal)
[ ] distractors are REAL mistakes (source: teacher intuition/NCERT errata), not random
[ ] Hindi i18n at least for title
[ ] validator passes: `uv run scripts/validate_content.py`
