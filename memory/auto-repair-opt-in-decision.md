---
name: auto-repair-opt-in-decision
description: Decision to NOT silently auto-heal cache-restored dangling mates — offer an opt-in --auto-repair retry instead (tracked in issue #204)
metadata:
  type: project
---

When a remote-cache **partial-mix dangle** fails `verify:soundness`
(`[48]` dangling mates on a foreign cached `.SLDASM`), the remedy today is the
slow `HARMONIC_REMOTE_CACHE_MODE=off` FULL rebuild (~500 s/assembly) — see
[[cache-partial-mix-dangle-remedy]]. The `AutoMateRepair` primitive that would
heal it in ~5 s already exists (`repair_dangling_mates` @ `_assembly.py:2103`,
called only from `refresh_assembly` @ 2261) but never fires on a cache HIT
(never marked stale — the `dodo.py:940-959` KNOWN LIMITATION).

**Decision (Pedro, 2026-07-08, cutting v0.17.0):** do NOT wire a silent
auto-heal. Keep the loud failure as default; expose an **opt-in `--auto-repair`**
flag on `verify.py --suite soundness`, so the operator consciously weighs
AutoMateRepair's risk (it can re-bind a mate to the WRONG topology →
subtly-wrong shipped geometry) against the ~500 s→~5 s gain, case by case.

**Implemented in the drawings-refactor branch (issue #204):** only non-warning
What's Wrong code 48 is eligible. The repair is rebuilt and re-read, then the
normal DOF / over-constraint / deep-health / interference / channel-independence
battery runs. The `.SLDASM` is saved locally only if every gate passes; it is not
republished under the foreign remote-cache key. Default soundness still fails
loud and includes the exact opt-in retry command.

**How to apply:** retry one affected assembly with, for example,
`uv run python cad/scripts/verify.py channel --suite soundness --auto-repair`.
Never turn this into an unconditional verify/cache heal.
