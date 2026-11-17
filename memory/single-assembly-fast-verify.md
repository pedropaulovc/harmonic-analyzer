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
   (writes the `.SLDPRT` to `cad/out/sldprt/`, used directly by the assembly insert).
2. Build the assembly standalone: `uv run python cad/scripts/build_<asm>.py`
   (the `__main__` → `run_build(build)` path; reopens the on-disk parts, runs the
   build's own `assert_components_fully_defined` + `check_no_interference`).
3. Run the full soundness battery on JUST that assembly:
   `uv run python cad/scripts/verify.py <stem> --suite soundness`
   (`verify.py [name ...]` targets one assembly; default = all built).

A bare `verify.py` scores whatever `.SLDASM`/`.SLDPRT` is on disk: it no longer
checks `.doit.db` freshness (the guard and `HARMONIC_VERIFY_ALLOW_STALE` were
removed in #2903). After a `git pull` or branch switch, rebuild first or run the
gate through doit (`verify_soundness:<stem>`), which re-runs on any changed input.
