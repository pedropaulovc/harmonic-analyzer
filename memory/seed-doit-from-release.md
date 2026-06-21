---
name: seed-doit-from-release
description: A release bundle can seed doit's incremental build (skip the ~25min COM rebuild) via cad/scripts/seed_from_release.py — with three real caveats
metadata:
  type: project
---

A published release's `solidworks/` Pack-and-Go files use the exact dashed
target names doit expects, so they drop straight into `cad/out/sldprt|sldasm`
and let `doit build` skip the SolidWorks/COM rebuild for unchanged parts.
Tool: `cad/scripts/seed_from_release.py <zip|tag>` (extract → `doit reset-dep`
→ write assembly recipe sidecars + inject `_recipe_digest`). Measured at the
v0.8.0 tag: **76/83 COM tasks skipped (~92%)**, only 7 rebuild.

Three non-obvious caveats (the reasons the tool isn't just "drop files + reset-dep"):

1. **`reset-dep` does NOT recognise assemblies.** It records file_dep/target
   state but never fires the `_RecipeTracker` uptodate callable (no
   `_recipe_digest` saved) nor writes the recipe sidecar `build_or_refresh`
   reads — so every assembly would do a needless ~500 s FULL re-insert. The tool
   injects `_recipe_digest` into the doit DB (bucket key is `_values_:`, WITH the
   trailing colon) and writes the sidecar.

2. **Pack-and-Go omits parts the top assembly doesn't reference.** Orphan/
   standalone parts (`chain_sprocket`, `crank_pin`, `eccentric_cam`, `nameplate`)
   and the base channel springs (superseded by the generated `stretchNN`
   variants that DO ship) aren't in the bundle, so they always rebuild.
   `assembly:channel` also stays stale (it file_dep's the absent base spring).

3. **Correctness trap:** `reset-dep` records the CHECKED-OUT source as the
   built-state. Seed with HEAD != the release commit and doit marks the v0.8.0
   geometry as current-for-HEAD → silently skips genuinely-changed parts. The
   tool asserts `git HEAD` == the bundle's `PROVENANCE.json` commit (`--force`
   overrides). Correct flow: checkout the release tag → seed → checkout target
   branch → build.

The seed's payoff is only as large as the source delta is small: a change to a
universally-imported helper (e.g. `_config.py`, in every part's import closure)
invalidates all 75 parts regardless — that's correct [[incremental-builds-validation]]
behavior, not a seed bug. Do NOT run the seed against the main repo's `cad/out`
when it's already built at HEAD — it would downgrade unchanged parts to the
older release geometry.
