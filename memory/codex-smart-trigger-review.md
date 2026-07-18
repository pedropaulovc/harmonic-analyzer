---
name: codex-smart-trigger-review
description: Codex PR auto-review now smart-triggers instead of reviewing every push — use @codex mentions when a push doesn't get an automatic review
metadata:
  type: reference
---

Codex's PR auto-review (the GitHub App that reacts 👀→👍/review on pushes,
driven via `watch-pr`) changed from "review every push" to a smart trigger:
Codex itself decides whether a given diff warrants a fresh review, rather
than firing unconditionally on each push.

**Why this matters:** the `watch-pr` skill's happy path assumes a push always
produces a `reaction EYES` → `reaction THUMBS_UP`/`review` event. With smart
triggering, a push can go by with no reaction at all — that is no longer a
sign something is broken, just Codex opting out of re-reviewing a change it
judged low-risk (e.g. a mechanical rebase, a test-only tweak).

**How to apply:** if a push sits with no Codex reaction after a reasonable
wait and you want a review anyway (e.g. before merging, or after a
substantive fix), explicitly request one with an `@codex review` mention via
`reply.sh <pr> --issue --body "@codex review"` (or on an existing thread) —
this is the fallback path `watch-pr`'s table already documents as
`comment-reaction EYES/THUMBS_UP`. Don't wait indefinitely for an automatic
review that smart-triggering may never fire.
