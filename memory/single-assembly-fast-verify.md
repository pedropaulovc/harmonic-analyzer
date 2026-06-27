---
name: single-assembly-fast-verify
description: Fast inner loop to build+verify ONE assembly without the full doit cascade a _common.py edit triggers
metadata:
  type: reference
---

Editing `cad/scripts/_common.py` flips the recipe digest of EVERY part that imports
it (the digest folds whole-module content, not a per-function call graph — see
`_buildgraph.module_deps_of`), so `doit assembly:<x>` / `doit verify:soundness`
cascade into rebuilding the whole repo on the single STA seat. To iterate on ONE
assembly fast, bypass doit:

1. Rebuild only the parts you changed, standalone: `uv run python cad/scripts/build_<part>.py`
   (writes the `.SLDPRT` to `cad/out/`, used directly by the assembly insert).
2. Build the assembly standalone: `uv run python cad/scripts/build_<asm>.py`
   (the `__main__` → `run_build(build)` path; reopens the on-disk parts, runs the
   build's own `assert_components_fully_defined` + `check_no_interference`).
3. Run the full soundness battery on JUST that assembly:
   `HARMONIC_VERIFY_ALLOW_STALE=1 uv run python cad/scripts/verify.py <stem> --suite soundness`
   (`verify.py [name ...]` targets one assembly; default = all built).

The `HARMONIC_VERIFY_ALLOW_STALE=1` is REQUIRED here: standalone builds don't update
`.doit.db`, so the freshness guard (the [[fix freshness]] feature, PR #101/#103) sees
the stored digest ≠ current recipe and refuses to verify — a false positive when you
KNOW you just rebuilt with current scripts. Drop the flag (and run through doit) for the
real, DB-recorded build before merge/CI. Related: [[semantic-datum-names]].
