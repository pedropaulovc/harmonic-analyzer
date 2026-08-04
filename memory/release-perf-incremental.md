# Release/build perf: kill the COM-spine duplication (2026-06-25)

Profiled the **v0.9.1 release logs** (attached as `harmonic-analyzer-v0.9.1-logs.zip`
on the GitHub release: per-task build/verify logs + the full `*-release.log`, each line
stamped `[ cumulative_s + delta_s ]`). A full cold build+verify+export+release was
**~153 min**, all serial on the one STA COM seat. Where it went:

| stage | wall | note |
|---|---|---|
| parts (73) | 4700 s | real modeling; already incremental + remote-cached (≈0 on a no-change release) |
| **verify** (3) | 2113 s | soundness 1097 + subsystems 977 + kinematics 38 |
| assemblies (8) | 962 s | |
| export | 767 s | |
| release | 663 s | of which **~546 s was PNG rendering** (486 PNGs = 6 views × 81 docs) |

Two structural time-sinks, wasteful **regardless of cache state**. Both fixed this pass.

## 1. verify soundness/subsystems were ~95% the same work (≈980 s/run)

`_verify_static_one` (soundness) and `_verify_isolation_one` (subsystems) both opened
**all 8 (sub)assemblies** fresh and ran an identical battery: DOF-defined,
no-over-constrained, **model-healthy deep** (≈140 s for the top assembly, ≈45 s for
`channel` — run *twice*), interference-free, component-count, gear-ratios. The ONLY gate
subsystems added was `assert_channel_independence` on the single `channel` assembly (it
just reads the component-name list — cheap).

**Fix:** `_verify_isolation_one` now early-returns for every assembly except
`CHANNEL_OWNER` and runs ONLY channel-independence (soundness already owns the shared
battery and runs first on the spine). `dodo.py task_verify`: `verify:subsystems` now
deps on / passes only `channel` (`suite_names`/`suite_deps`). Saves ~16 min/run.
No coverage lost — soundness is a strict superset of the dropped gates.

> **UPDATE (superseded — this §1 describes an intermediate state).** The `subsystems`
> suite was later RETIRED ENTIRELY (commit `ca38b0b8`), not merely limited to `channel`:
> channel-independence was folded into `soundness`, so `verify:subsystems` and its `dodo`
> task no longer exist. Current SW-spine verify suites are `soundness` + `kinematics` (with
> `math`/`config` off-spine). The redundancy finding stands; only the mechanism changed.
> §2 (the PNG render cache) below is unchanged and current.

## 2. release re-rendered/re-exported all 81 docs every time (even on a no-change release)

`cut_release.export_neutral` had NO staleness check: it opened all 81 docs, SaveAs3'd
STEP+STL, and rendered 486 PNGs **every** release. v0.9.1 reported "no part changed" yet
still spent ~546 s re-rendering byte-identical PNGs + re-exporting STEP/STL the `export`
task had *just* produced in `cad/out`.

**Fix — PNG render cache only (STEP/STL still exported here):**
- **STEP/STL stay re-exported per document via SaveAs3** (the proven v0.9.1 path).
  ⚠️ A first cut of this work tried to COPY STEP/STL from `cad/out` to skip the 81
  opens — **WRONG, caught by Codex P1 on PR #91.** `cad/out` is the *render cache*, not
  the per-document neutral set: `cad/comparisons/manifest.json` lists only `harmonic_analyzer`,
  so `export_models` writes per-mesh STLs + the top assembly's STEP/STL ONLY — **no
  per-part STEPs, no subassembly STEP/STL**. Copying would fail on the first missing part
  STEP. The bundle ships 81 STEPs (73 parts + 8 asms); release must generate them itself.
- **PNGs are rendered on the seat but cached** by resolved-geometry fingerprint
  (`_png_key` → `cad/out/release/png-cache/<key>/`). Key = sha256(the just-exported
  stage STL(s) for the doc) + sha256(source SLDPRT/SLDASM) + colors.json digest +
  `PNG_RENDER_REV`. The exported STL is the actual resolved geometry being rendered (for
  an assembly the monolithic STL bakes in every child), so a changed child re-renders the
  assembly; the source-doc hash catches mate/appearance changes; colors.json catches any
  other colour change. **Safe-by-construction:** a miss only ever re-renders, never serves
  a wrong image. `_staged_pngs` copies the cached set on a hit (no SaveBMP) else renders
  the open doc + populates the cache (atomic rename). Cache pruned to keys used this run
  (best-effort). Bump `PNG_RENDER_REV` when `_export_pngs` params change.

Net: a geometry-unchanged release still OPENS every doc (for STEP/STL) but skips all 486
SaveBMP renders — the bulk of release time. (Skipping the opens too would need either a
complete per-document STEP/STL cache or expanding `export_models` to emit the full set;
deferred as a seat-validated follow-up.) STEP/STL export prefs + SaveAs3 options retained.

## ⚠️ Validation status

Offline-validated only (this dev box has no SolidWorks; uv even picked py3.14 by
default — pin `--python 3.11`): `py_compile`, `ruff` clean on the diff,
`test_dodo_recipe`/`test_buildgraph`/`test_artifact_cache`/`test_telemetry`/
`test_nameplate_geometry` = 48 passed, verify `--suite math` 9/9 + `config` 13/13,
`doit list`/`doit info verify:soundness` correct. *(This validation predates the subsystems retirement — `verify:subsystems` no longer exists; use `verify:soundness`/`verify:kinematics`.)*

**The COM paths (verify on the seat, the release neutral export + PNG cache) MUST be
run once on the SolidWorks seat before the next real release.** Best first run:
`doit verify:kinematics` after `verify:soundness` (`verify:subsystems` has since been retired), then a `doit release -- vX --no-publish`
(dry run — builds the bundle + logs, nothing leaves the machine) to confirm the
copy/cache flow ships the same step/stl/png set.
