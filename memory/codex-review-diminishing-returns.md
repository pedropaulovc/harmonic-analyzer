---
name: codex-review-diminishing-returns
description: Stop the Codex fix-reply-push loop when its findings taper into micro-polish; triage instead of auto-fixing every round
metadata:
  type: feedback
---

On PR #208 (benchmark design doc) Codex produced 3 review rounds: round 1-2
were substantive (wrong cost math, gallery-pollution risk, ambiguous
coordinate definitions), round 3 was fine-grained polish (pixel caps,
randomization parity, phase budget wording). The user paused the loop:
"pause if codex is returning diminishing returns feedback".

**Why:** each round costs a commit + push + re-review cycle, and Codex will
keep finding ever-finer pinnable details indefinitely on a spec/design doc
that hasn't run yet. Past the substance, the churn outweighs the gain.

**How to apply:** after ~2 fix rounds, triage instead of auto-fixing: fix
only findings that would actively mislead an executor (wrong numbers,
contradictions); for pure spec-tightening nits, reply "deliberately left to
the executor's judgment" without an edit round, and surface the tradeoff to
the user for the merge call. Applies mainly to docs/design PRs; code PRs
with correctness findings still get fixed. See [[never-say-final]].
