---
name: stack-pinned-off-main-rots
description: "A PR stack deliberately based off a 'known-good' commit instead of main rots into unmergeability — 8 of 10 PRs (#382-#391, #407) had to be abandoned"
metadata:
  node_type: memory
  type: feedback
---

On 2026-07-23 a stack (#382 → #383 → #384 → #385 → #386 → #387 → #388 → #389)
was cut from commit `7d3c6172` with every PR body stating the same rationale:
*"intentionally not rebased onto the newer broken `main`"*. #391 and #407 were
cut the same way. By 2026-07-27 `main` had moved **742 commits** and 8 of the 10
were closed unmerged.

How they died — each failure mode is a distinct warning:

- **Already fixed upstream.** #383 (magnifier `HUB_DIA` import) and #386 (batch
  OTLP export) were independently fixed on `main`. Pure waste.
- **Binary regressions.** #382 and #407 both carried an ~81 KB
  `harmonic-analyzer.DRWDOT` while `main` had moved to 89505 B via `b7e22a23`
  (projection revert) + `3ecd70fd` (regeneration). Merging either would have
  silently rolled both back. A stale binary in a long-lived branch is invisible
  in review.
- **Formatter churn.** #388's real content was ~30 lines; the PR was 91 files /
  4683 changed lines because the branch ran a formatter this repo does not use.
  Unrebasable against anything.
- **Quality drift under time pressure.** #391 relaxed `add_datum_feature`
  `position_tolerance_m` from `1e-6` to `1e-3` (1000×) and added a redraw retry
  to coordinate picks — `main` had meanwhile fixed the same symptom properly in
  #431 with `expected_position_xy`.
- **Overtaken by the goal.** #407 rewrote 8 assembly drawings to three-view
  sheets; `main` had independently done 7 of the 8 (`b3638c4a`, `3e7348d2`,
  #420).

**Why:** "`main` is broken, pin to known-good" optimizes for today's green build
and borrows against every future rebase. The interest compounds silently — a
branch does not announce that its template binary or its formatting has drifted.
Meanwhile whatever made `main` "broken" gets fixed by someone else within a day
or two, so the debt buys almost nothing.

**How to apply:** if `main` is broken, **fix `main`** (or wait for the fix) —
do not fork a long stack off a green ancestor. If a stack must exist, rebase
the whole chain onto `main` daily, not on demand; a stack more than ~1 day
behind is already cheaper to re-derive than to rebase. When re-deriving, extract
the *idea* (usually tens of lines) and re-implement on current `main` rather
than fighting the branch — that is what #435 and #436 did for #387 and #384.

See [[stacked-pr-merge-order]] for the separate hazard of merging a stack's base.
