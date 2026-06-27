---
name: no-untested-failure-assumptions
description: Don't design defensive fallbacks around unverified assumptions about SolidWorks/tool failure modes
metadata:
  type: feedback
---

When designing, do NOT bake in defensive workarounds or fallbacks predicated on an
**unverified** assumption that a tool (e.g. SolidWorks) will misbehave — e.g. "SW may drift
under-defined components on rebuild, so run checks in a locked pose / force lock for exports."
Assume things work fine; enforce the real checks on whatever is actually being built.

**Why:** speculative hedging adds complexity and special-casing for a failure that may never
occur, and obscures the clean design. The user rejected a plan that ran soundness gates in a
"locked pose" and forced-locked exports to avoid hypothetical free-pose flakiness.

**How to apply:** enforce all gates on the as-built artifact in its actual mode. If a failure
mode is real, *reproduce it empirically first*, then fix it with evidence — don't pre-engineer
around it. See [[fix-relations-are-a-last-resort]] (same spirit: don't reach for heavy
mitigations before they're justified).
