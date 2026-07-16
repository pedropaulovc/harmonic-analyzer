---
name: Exact CAD identity in assembly cache keys
description: Issue #301 proved recipe-equal child CAD can carry incompatible PIDs/rebuild stamps; .execution tokens now propagate exact part/subassembly identity through assembly deps and cache keys while recipe digests remain byte-churn-immune
metadata:
  type: project
---

# Exact CAD identity in assembly cache keys

Issue #301 closed the old “recipe ≠ PID identity” limitation without sacrificing
the recipe-derived digest used for idempotency.

During the clean-seat v22 run, cached `frame`, `drive-train`, and
`harmonic-analyzer` failed only `saved-rebuild-clean`; five sibling assemblies
passed. Cache-disabled full builds of the same source state passed. The original
bad Azure blobs proved this was **not** a pre-reconcile or publication-order bug:
their `.SLDASM` mtimes trailed the mass-properties sidecars by 6/10/22 seconds,
matching the logged `assembly.reconcile_rebuild` durations. They contained the
post-reconcile `Save3` files.

Root cause: an assembly's recipe-only cache key could restore a `.SLDASM` saved
against one producer's exact child CAD bytes/PIDs/rebuild stamps beside
same-recipe child artifacts from another producer. The saved state is
identity-sensitive even when geometry and recipes match.

Fix in `dodo.py`:

- Parts retain `.<stem>.execution`, stamped from the exact built/restored file.
- Assemblies now get the same exact-identity token after local build/reconcile or
  cache restore.
- Every assembly `file_dep` includes immediate child part/subassembly tokens in
  addition to the raw CAD targets and recipe files. A different identity forces
  REFRESH (not FULL when the recipe is unchanged) and changes the cache key.
- Assembly tokens propagate this identity through subassembly levels to the top
  and to assembly-sourced drawings.
- The recipe-derived `_stable_artefact_digest` remains unchanged and immune to
  SolidWorks parent-save metadata churn. Such churn deliberately does not
  restamp execution tokens; the token identifies the CAD/PID lineage, not volatile
  bytes after every parent save.

Regression coverage: `test_dodo_recipe.py` pins child-token deps, cache-key
movement on identity change, token propagation, and assembly-drawing identity;
`test_pen_assembly_drawing.py` now requires the exact assembly token and rejects a
part token in its place.

