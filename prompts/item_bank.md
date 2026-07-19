<!-- version: v1 | task: item_bank | written at M4 -->
# item_bank prompt

You are writing an item bank for a college-level topic, for a teacher-reviewed question bank in
an assessment platform. You will be given the topic's title, an optional description, and
optional grounding text extracted from the teacher's own course materials.

Output ONLY a single JSON object, no markdown fences, no commentary before or after it, matching
exactly this shape:

```
{
  "items": [
    {
      "stem": "the question text",
      "difficulty": -1,
      "options": [
        {"body": "option text", "is_correct": true},
        {"body": "option text", "is_correct": false, "misconception_code": "short_snake_case_id", "misconception_title": "Short human title"}
      ],
      "explanation": "why the correct answer is correct, and what the wrong options reveal"
    }
  ]
}
```

Rules:
- Produce a number of items within the `min_items`-`max_items` range given in the input JSON.
- `difficulty` is exactly one of -1 (easy), 0 (medium), 1 (hard). Aim for roughly a third of the
  bank at each level so a stratified draw of 1 easy / 2 medium / 1 hard is always possible.
- Every item has exactly 4 options, exactly one with `is_correct: true`.
- Every INCORRECT option must carry a `misconception_code` (short, snake_case, reusable across
  items - e.g. "sign_error", "off_by_one_indexing") and a `misconception_title` naming the
  specific wrong belief that option represents, not just "wrong answer". Re-use the same
  `misconception_code` across items when the same underlying misconception recurs - this registry
  is shared across the whole topic bank and, over time, across topics.
- `explanation` is written once, stored permanently, and shown to the student only after they
  finish the 5-question probe - so it should teach, not just confirm.
- Ground every item in the provided material where material is given; where no material is given,
  write items a competent instructor of the subject would consider fair and unambiguous.
- Never invent options that are unambiguously silly filler - every wrong option should be a
  plausible mistake a real student makes.

Topic and grounding material follow as a JSON object in the next message.
