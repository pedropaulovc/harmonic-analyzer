---
name: semantic-merge-conflict-reds-main
description: "Merging a green PR can silently red main via a SEMANTIC conflict — a test added on PR-A asserts a constant that PR-B changed on an untouched line, git auto-merges clean, main's check:recipe goes red; verify main's SW-free gates after every batch merge"
metadata:
  type: feedback
---

During the 2026-07-21/22 drawing-batch merge campaign, merging **#359** (green
on its own head, `gh pr merge --merge`) left **origin/main RED** on
`check:recipe`. Root cause was a **semantic merge conflict**, invisible to git:

- #357/#358's gear batch had set `_drawing_common._METRIC_EDGE_BREAK_NOTE` to
  the `"…R0.25 MAX OR 0.25 MAX X 45 DEG"` wording.
- #359 **added** `test_pinion_bracket_drawing.py::test_shared_template_edge_break_is_metric_and_not_duplicated`
  asserting the constant equals the `"…R0.25 OR CHAMFER 0.25 MAX"` wording.
- The test file and the constant line live in **different files / different
  lines**, so git found **no textual conflict** and auto-merged cleanly. The
  merged tree combined main's old constant with #359's new test → red.

`gh pr merge` does not run the merged-result CI before completing, so a
"MERGEABLE + green PR head" merged straight into a broken main.

**Why it matters:** the whole fleet builds against main; a red `check:*` gate
blocks every branch and any release preflight. And it's a trap for the
coordinator: I first "verified" main was fine against my **stale local main**
(pre-#359 `HEAD`, where the test didn't exist yet) and wrongly doubted the fork
that reported it. Empirical skepticism cuts both ways — check against the REAL
`origin/main`, not a stale checkout.

**How to apply:**
- **After every merge in a batch, verify main's SolidWorks-free gates** before
  merging the next PR: `git fetch origin main && git merge --ff-only origin/main`
  then run the recipe/metadata/contract + graph/partiso pytest set (≈90 tests,
  ~1 min, no seat). A batch where PRs add tests that pin shared constants
  another PR touches is exactly the setup for this.
- When a subagent reports "main is red," reproduce against fetched
  `origin/main`, not local `HEAD` — fast-forward first.
- Fix a red main with a **roll-forward hotfix committed directly to main** (this
  is the "see something, do something — fix the bad merge" case), not by waiting
  for a downstream PR to carry the repair. The value is dictated by the failing
  test + the code comment (here: the metric note must mirror the inch note
  `R.01 OR CHAMFER .01 MAX`, so the **constant** was wrong, not the test).
- This is the concrete instance of AGENTS.md's "a green build can still conflict
  or drift" — the drift can be a semantic (not textual) merge conflict.

Related: [[stacked-pr-merge-order]], [[codex-drawing-image-review]].
