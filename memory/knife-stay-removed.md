---
name: knife-stay-removed
description: knife-stay part deleted entirely (never existed in the real device); full removal re-keyed all 8 assemblies, COM rebuild deferred
metadata:
  type: project
---

The `knife-stay` part (Ø3 anchor rod + 8×2 strap, formerly placed in
`summing.SLDASM` at machine (0, 1086, 0) as a FIXED, non-mated structural
component) was REMOVED completely on 2026-06-25 — the user confirmed it never
existed in the real device. It was geometrically inert in the mate graph: the
summing lever rocks on `knife-mount` (Axis3↔Axis1), nothing mated to the stay,
so deleting it cannot dangle a mate or add interference; summing drops 9→**8**
top-level components.

**What was deleted/edited (all source-of-truth, no backward-compat):**
- `cad/scripts/build_knife_stay.py` + `cad/config/parts/knife-stay.yaml`
  (must go together — the check:nameplate audit requires declared PART_NAME ==
  parts/*.yaml registry, or it FAILs orphan/unregistered).
- `build_summing_assembly.py`: dropped the `place_component("knife-stay", …)`
  call + docstring; `_transforms.py`: dropped the `"knife-stay": "z"`
  MIRROR_PLANE entry; `build_harmonic_analyzer_assembly.py` docstring; verify.py
  summing `_COMPONENT_BAND` (8,10)→**(7,9)** measured 8; narrative
  `dimensions.yaml` "Knife stay" row; `docs/tolerance-gdt-assessment.md` T1 row.
- Offline gates all green after: pytest test_buildgraph/test_dodo_recipe (23),
  doit check:graph/config/nameplate/recipe.

**Deferred COM rebuild — IMPORTANT.** The user chose *full removal but defer the
rebuild*. Because EVERY assembly imports `_transforms.py`, dropping the
MIRROR_PLANE entry re-keyed all 8 assembly recipes — so the next `doit` (or
`assembly:*`) will do a FULL from-scratch rebuild of the whole machine
(~40–60 min on the COM seat), producing BYTE-IDENTICAL geometry everywhere
EXCEPT summing (which legitimately loses the component). That big rebuild is
EXPECTED, not a bug — it is pure cache-key churn from the `_transforms` edit
(the documented tradeoff: editing `_transforms` re-keys assemblies, not parts).
Until then the `cad/out/*.SLDASM` artifacts are stale (summing still shows the
old component); `cad/out/sldprt/knife-stay.SLDPRT` is an orphaned artifact
(gitignored, was file-locked by an open SolidWorks at removal time).

Related: [[output-layout-m64]], [[solidworks-modeling-pitfalls]].
