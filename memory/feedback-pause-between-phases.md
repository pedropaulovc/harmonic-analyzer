---
name: feedback-pause-between-phases
description: "On multi-phase plans, stop for user review after each phase instead of chaining them"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1f309627-0ce3-4562-b4bc-935d4f44247a
---

On approved multi-phase plans, complete ONE phase, report what was done + results, and
STOP for the user's sign-off before starting the next phase. Do not chain phases.

**Why:** The user (2026-06-16, summing-lever revert work) explicitly asked to "pause in
between phases for me to review" after approving the plan — they want a checkpoint to
inspect each phase's output before more changes land.

**How to apply:** When a plan has Phase 1..N, bake a "pause for review after every phase"
note into the plan file and honour it. Especially relevant for the live SolidWorks
build/verify/parity work in this repo, where one wrong phase compounds. See
[[harmonic-analyzer-project]].
