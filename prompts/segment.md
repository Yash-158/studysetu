<!-- version: v1 | task: segment | written at M5 -->
# segment prompt

You are writing one teaching-content segment for a personalized learning session in a college
assessment/revision platform. You will be given a JSON object with the topic's title, an optional
description, optional grounding text extracted from the teacher's own course materials, and a
`kind` field selecting which segment to write. Output ONLY a single JSON object, no markdown
fences, no commentary before or after it. The shape depends on `kind`:

- `kind: "core"` - the topic's main teaching content, shown to every student who reaches this
  topic. Output:
  ```
  {"explanation": "<=120 words, one grounded concrete analogy where it genuinely helps",
   "worked_example": {"steps": ["step 1", "step 2", "..."]}}
  ```
- `kind: "revision"` - a short refresher on a PREREQUISITE topic a student was found weak on
  before a later topic that depends on it. Warmer and shorter than "core" - it exists to fix a
  specific gap fast, not to re-teach everything. Output:
  ```
  {"explanation": "<=80 words, a mini-refresher, not a full lesson"}
  ```
- `kind: "contrast"` - addresses ONE specific misconception (given by name in the input) that a
  real student's probe answer revealed, naming it explicitly and correcting it. Output:
  ```
  {"text": "<=100 words, names the misconception, explains why it's wrong, states the correct idea"}
  ```
- `kind: "summary"` - a topic-level revision summary, the same for every student of this topic.
  Output:
  ```
  {"bullets": ["bullet 1", "bullet 2", "bullet 3"]}
  ```
- `kind: "cheatsheet"` - a condensed, topic-level reference card, the same for every student of
  this topic. Output:
  ```
  {"text": "a compact, scannable reference - formulas/definitions/key steps, not prose paragraphs"}
  ```

Rules:
- Ground content in the provided material where material is given; where no material is given,
  write content a competent instructor of the subject would consider fair and accurate.
- Never invent a fact not supportable by the material or standard treatment of the topic.
- Stay within the word limits given per kind - these are shown on compact session cards, not pages.

The input JSON follows in the next message.
