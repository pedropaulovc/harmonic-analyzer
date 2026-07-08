---
name: auto-repair-opt-in-decision
description: Decision to NOT silently auto-heal cache-restored dangling mates — offer an opt-in --auto-repair retry instead (tracked in issue #204)
metadata:
  type: project
---

When a remote-cache **partial-mix dangle** fails `verify:soundness`
(`[48]` dangling mates on a foreign cached `.SLDASM`), the remedy today is the
slow `HARMONIC_CACHE_MODE=off` FULL rebuild (~500 s/assembly) — see
[[cache-partial-mix-dangle-remedy]]. The `AutoMateRepair` primitive that would
heal it in ~5 s already exists (`repair_dangling_mates` @ `_assembly.py:2103`,
called only from `refresh_assembly` @ 2261) but never fires on a cache HIT
(never marked stale — the `dodo.py:940-959` KNOWN LIMITATION).

**Decision (Pedro, 2026-07-08, cutting v0.17.0):** do NOT wire a silent
auto-heal. Keep the loud failure as default; add an **opt-in `--auto-repair`**
flag the operator passes on retry, so they consciously weigh AutoMateRepair's
risk (it can re-bind a mate to the WRONG topology → subtly-wrong shipped
geometry) against the ~500 s→~5 s perf gain, case by case. **Not implemented yet**
— tracked in **issue #204** (flag placement, whether a heal re-publishes to
cache, and how it composes with the `dodo.py:955` orchestration-signal "proper
fix" are open there).

**How to apply:** if asked to make cache dangles heal faster, implement #204's
opt-in flag — don't add an unconditional heal to verify or the refresh path.
