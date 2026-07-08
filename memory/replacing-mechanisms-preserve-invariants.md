---
name: replacing-mechanisms-preserve-invariants
description: When you rewrite a staleness/cache/validation mechanism, catalog the OLD one's incidental guarantees first — the regressions come from dropping them, not from the larger scope
metadata:
  type: feedback
---

Taking the LARGER, more-correct fix is the right call, not scope creep — don't
retreat to the minimal "reported-bug-sized" patch to dodge review comments.
(PR #199: rewrote export staleness from mtime to churn-immune recipe digests,
matching what doit / the remote cache / verify's freshness guard already do.
A mtime-only fix would've left export the lone holdout and kept the
cross-machine cache-restore re-export bug unfixed.)

**Why:** Pedro's feedback — "I'd rather look at root causes; you did the right
thing going for the larger fix; the only problem were the regressions." Shrinking
scope trades real correctness for fewer Codex comments. Bad trade.

**How to apply:** The real, avoidable failure when replacing a mechanism is
REGRESSION — the old code's guarantees leave with it SILENTLY, especially the
*incidental/emergent* ones that were never written as intent:
- old mtime code did `src.stat()` → **raised loud** on a missing `.SLDPRT`; the
  digest rewrite returned "fresh" instead (a declared target's digest resolves
  without the file existing).
- old "STEP always stale" **forced all configs of a part to re-export together**,
  so `assert_configs_distinct` always ran; the rewrite enabled single-config
  refresh and bypassed the guard.
Both were side effects, not contracts. So before ripping a mechanism out:
characterize its behavior EMPIRICALLY — what does it do on a missing file? on
partial staleness? on failure? — and check each survives; don't only verify the
new mechanism is internally correct. Then run an adversarial self-review
(`/code-review`, or a subagent with the lens "what input isn't in the key? what
on failure? what if the file's missing? is the fallback complete?") BEFORE marking
the PR ready — that front-loads the completeness/lifecycle findings into one pass
instead of many reactive Codex rounds. Relates to [[no-untested-failure-assumptions]].
