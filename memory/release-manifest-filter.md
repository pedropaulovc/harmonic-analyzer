---
name: release-manifest-filter
description: cut_release neutral export is manifest-restricted (part_stems + ASSEMBLY_ORDER); cad/out accumulates STALE parts that a blind glob would ship
metadata:
  type: project
---

`cad/out/sldprt` + `cad/out/sldasm` are a **persistent cache** — doit never
prunes docs the live build stopped producing. So renamed/retired parts and
scratch assemblies linger there indefinitely:
- `rocker-arm-portal` (retired by PR #82), `rocker-arm-support-manual` (renamed
  by PR #82) — stale SLDPRT.
- `overlay-diag.SLDASM` — a scratch assembly the untracked `render_overlay.py`
  diagnostic saved into `cad/out/sldasm`.

`cut_release.export_neutral` used to `glob` `*.SLDPRT`/`*.SLDASM` blindly, so
all of these silently shipped in the release bundle (**v0.10.0 carried the 2
stale parts**; the v0.10.0 cut nearly shipped overlay-diag before a hand-clean).

Fix (PR #93, on main `ccd05d0`): `_models(folder, ext, manifest)` keeps only the
canonical **build manifest** — `part_stems()` for parts, `ASSEMBLY_ORDER` for
assemblies, both `_`→`-` to match dashed filenames (`_buildgraph.artefact_for`
confirms that mapping). It **logs every stray dropped** (no silent truncation)
and **fails loud if a manifest doc is missing** from cad/out (a partial/stale
build refuses to ship a hole). The build kept 73 parts + 8 assemblies at the time of this note; the current count is ~94 parts (2026-07-04) + 8 assemblies — the filter mechanism is unchanged.

Implication: the didiff vs prior-release in render_diff is now also clean of
strays. If a NEW part's filename ever diverges from `<dashed build-script stem>`
(e.g. PART_NAME set independent of the stem), the manifest filter would drop it —
the fail-loud `missing` guard catches that as a hard error, not a silent omit.
Related: [[mm-normalization-render-bundle]],
[[release-perf-incremental]].
