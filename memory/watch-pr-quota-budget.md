---
name: watch-pr-quota-budget
description: "Multiple concurrent watch-pr monitors exhaust the 5000/h GitHub REST quota in ~40 min (403s poison every gh call fleet-wide); for multi-PR sessions use ONE aggregated GraphQL poller instead"
metadata:
  type: feedback
---

During the 2026-07-21 four-PR drawing-batch fan-out, running THREE `watch-pr`
monitors concurrently burned the entire 5000/h GitHub **REST** quota in ~40
minutes — twice in a row. The symptom was misleading: `watch-pr: comment
formatter failed — will retry next poll` on every poll (looks like a formatter
bug; first diagnosis chased an "empty thread set" red herring). The real check
that settles it in one call: `gh api rate_limit --jq .resources` (that endpoint
is unmetered) — core at 0 = quota, not code.

**Why:** `watch-pr.sh` is designed to babysit ONE PR; each poll issues many REST
calls (checks, reviews, comments, reactions, threads). N instances multiply
that, and the quota is shared with every agent's `gh` call on the seat, so
exhaustion 403-poisons the whole fleet (PR state reads, `gh pr ready`, replies).

**How to apply:**
- For a multi-PR session, do NOT launch one watch-pr per PR. Run ONE aggregated
  poller on the **GraphQL** quota (a separate 5000/h pool): a single query with
  PR-aliased fragments (state/isDraft/mergeable/headRefOid/reviewThreads
  isResolved/last review/comments+reactionGroups) covers any number of PRs for
  ~1 point per poll; diff summaries and emit change lines. Working script:
  session scratchpad `pr-watch-graphql.sh` (2026-07-21); GOTCHA: the reaction
  count field is `ReactionGroup.reactors{totalCount}`, not `.reactions`.
- On a change line, fetch thread bodies on demand via GraphQL — don't stream
  them every poll.
- Subagents sharing the seat should not tight-poll `gh pr view`; the
  coordinator's watcher relays events. GraphQL mutations
  (`markPullRequestReadyForReview`, `addComment`) substitute for `gh pr ready`
  / comment posts while REST is cooling down.
- watch-pr stays the right tool for a SINGLE-PR babysit session.

Related: [[codex-smart-trigger-review]].
