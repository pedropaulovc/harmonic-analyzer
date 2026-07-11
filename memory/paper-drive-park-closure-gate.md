---
name: paper-drive-park-closure-gate
description: RESOLVED BY REMOVAL 2026-07-09 — the park-closure gate is deleted with the whole park machinery, so its unsatisfiable 0-DOF assert on gear/belt-coupled trains (issue #205) is moot; the SW fact stands — gear/belt-chain couplings never reduce the fully-defined count
metadata:
  type: project
---

> **2026-07-09 — RESOLVED BY REMOVAL.** `assert_park_closure`, the preflight
> park stage and the `HARMONIC_PREFLIGHT_SKIP_PARK` hatch are all deleted with
> the park machinery ([[default-free-dof-park-drivers]]); close issue #205.
> The durable SolidWorks fact this incident pinned: **gear mates, rack-pinion
> mates and Belt/Chain features are MOTION couplings that never reduce the
> fully-defined count** — any future gate asserting 0-DOF over a gear-coupled
> train is unsatisfiable by construction (the exact-set soundness gate instead
> lists coupled families as allowed-under-constrained). History below.

The v0.17.0 release (first since the #196 paper-drive rework — [[paper-drive-real-train]])
failed the release preflight `gate.park_closure`:
`components not fully defined: transgear-feed-pinion-1 (under), rack-pinion-1 (under)`
(`expected_free_dof=1 specs=1 authored=1`). verify:soundness is GREEN — only the
release-time SUFFICIENCY proof fails.

**NOT a geometry bug (owner-confirmed):** the disc is gear-mated 12:120 to the
third gear, the knob cluster (T24+third+knob-shaft) is a locked rigid body
belt/chain-coupled to the crank, and the 12T feed-pinion is locked to the disc —
turning any gear drives the whole train. The failure is that **SolidWorks gear
mates + Belt/Chain features are MOTION couplings that DON'T reduce the
"fully-defined" DOF count**, so the gear-driven disc (`rack-pinion-1`) + feed-pinion
read under-defined even though kinematically driven. `assert_park_closure`
(`_assembly_postbuild.py`) requires EVERY component fully defined after authoring
the 1 recorded crank driver — a gear-coupled train can't satisfy that.

Shipped through #196's merge because **preflight is opt-in, NOT in the merge gate**
(`build` proves DOF necessity only); v0.16.0 predates #196 so this had never seen a
release preflight.

**Interim (v0.17.0):** off-by-default env-var hatch in `preflight_release.py` —
`HARMONIC_PREFLIGHT_SKIP_PARK=paper-drive` skips ONLY that assembly's park-closure
(gear-ratios still runs), loud WARN, model unchanged. Tracked in **issue #205**.

**How to apply:** proper fix (issue #205) = make park-closure gear-aware (exempt
gear/rack-pinion/belt-chain-coupled components, or a Gruebler/mobility count) OR
record the transgear pair as a 2nd deferred park DOF (expected 1→2). Until then a
release needs the env hatch. Relates to [[default-free-dof-park-drivers]],
[[auto-repair-opt-in-decision]] (same opt-in-escape-hatch philosophy).
