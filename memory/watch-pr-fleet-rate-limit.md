---
name: watch-pr-fleet-rate-limit
description: Running many parallel watch-pr Monitors against one repo exhausts the shared 5000/hr GitHub GraphQL quota and self-perpetuates
metadata:
  type: feedback
---

Do not launch one `watch-pr` Monitor per PR when babysitting a large stack (e.g.
12+ PRs from a parallel-agent fan-out). Each Monitor polls GraphQL independently
on its own short interval; N of them running concurrently against the same repo
collectively exhaust the 5,000/hr GraphQL quota (shared across the whole
account/session, not per-Monitor). Once exhausted, every Monitor's poll starts
failing (`watch-pr: comment formatter failed`, spurious `unresolved-threads: 1`
flips that are just fetch failures, not real new Codex findings) and keeps
firing on its normal cadence — burning the user's turns with repeated noise for
the ~duration of the rate-limit window, and re-exhausting the quota the instant
it resets since all N Monitors retry in lockstep.

**Why:** discovered while babysitting 12 stacked PRs (issues #48–#65 in
`pedropaulovc/meshprobe`) fixed by 14 parallel background agents — 12
simultaneous `watch-pr.sh` Monitors blew the GraphQL budget within about an
hour, and the failure symptom (`unresolved-threads: 1` + formatter failure)
looks exactly like a genuine new Codex finding, so it costs real triage time to
notice it's just rate-limit noise (confirm via `gh api rate_limit --jq
.resources.graphql` showing `remaining: 0`).

**How to apply:** for a large PR fleet, prefer ONE consolidated poll loop that
batches all PRs into a single GraphQL query per interval (or a longer per-PR
poll interval) over N independent `watch-pr` Monitors. If already in the noisy
state, `TaskStop` every watch-pr Monitor (task IDs from the notification
`<task-id>` field) to stop the pile-on, wait out the reset window
(`gh api rate_limit --jq .resources.graphql.reset`), then re-launch monitoring
— staggered or consolidated — rather than restarting all N at once.
