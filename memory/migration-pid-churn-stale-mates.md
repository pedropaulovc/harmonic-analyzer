---
name: migration-pid-churn-stale-mates
description: Tree-wide gate.health code-48 "mate entities suppressed" after a recipe-digest migration = stale parent PIDs, not a mate bug; fix by full-rebuilding assemblies against current parts.
metadata:
  type: project
---

A `verify:soundness` / build `gate.health` that explodes with hundreds of errors
(saw 273 on the top assembly, 180 on channel, 16 frame, 1 summing) whose codes
are **48** (`swFeatureErrorMateBroken`, "one or more mate entities were
suppressed"), 43 (`MateDanglingGeometry`), 46 (`MateOverdefined`) is almost never
a real mate-logic bug — it is **stale persistent-reference IDs (PIDs)**.

**Why:** the recipe-digest migration (the one `doit reset-dep` / a one-time
content-key shift triggers) rebuilds parts *from scratch* with an **unchanged
recipe**. SolidWorks reassigns PIDs on every from-empty rebuild, but the recipe
digest is content-stable, so doit does NOT refresh the dependent assemblies
(this is the documented "recipe ≠ PID identity" limitation in AGENTS.md). The
assemblies' saved mates still point at the *old* PID numbering → on reopen those
entities resolve to nothing → code-48 floods. The smoking gun is **file mtimes**:
the parts are newer than the `.SLDASM` that references them (parts rebuilt at
19:06, assemblies last saved 17:05).

**How to apply:** don't chase individual mates. Confirm it is staleness (parts
mtime > assembly mtime; errors are codes 43/46/48), then **full-rebuild every
assembly against the current parts** so mates re-bind to live PIDs — either via
the `doit` spine (a recipe change on any part/assembly cascades a FULL rebuild of
dependents) or by running the `build_*_assembly.py` scripts directly bottom-up.
Set `HARMONIC_CACHE_MODE=off` during the restore so a cache HIT can't re-restore a
foreign-PID assembly. Verify with deep `gate.health` (`errors=0`) + a reopen.
Distinct from a genuine over-definition like [[fix-relations-last-resort]] (a
redundant `ground=True` on top of datum mates, which is a real code-46 bug fixed
in PR #111). Related: [[release-perf-incremental]].
