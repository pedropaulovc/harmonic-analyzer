---
name: codex-review-diminishing-returns
description: Judge Codex review rounds by finding quality, not round count — keep fixing while it finds real bugs, decline only genuine over-pinning
metadata:
  type: feedback
---

On PR #208 (benchmark design doc) Codex ran 8+ review rounds. Mid-way the
user said "pause if codex is returning diminishing returns feedback" and I
adopted a round-count heuristic (stop auto-fixing after ~2-3 rounds). That
heuristic was wrong twice: rounds 7 and 8 surfaced result-inverting defects
(a sign-convention landmine in the scoring schema, ground-truth leakage via
delta-tagged filenames — a P1, a gameable headline metric). When I proposed
hard-stopping, the user corrected: "if it is finding good bugs thats fine;
keep addressing them".

**Why:** the pause criterion is the *quality* of findings, not their round
number. A reviewer that keeps finding real bugs is paying rent; cutting it
off on a schedule ships the bugs. Diminishing returns means the findings
themselves have degraded to taste/over-pinning — judge each batch on its
content.

**How to apply:** triage every round on substance: fix anything that would
corrupt results, mislead an executor, or contradict another part of the
change; decline (with a reasoned reply) only pure spec-tightening that a
downstream step already covers. Never predict "the next round will be
noise" — assess it when it arrives. Applies to docs and code PRs alike.
