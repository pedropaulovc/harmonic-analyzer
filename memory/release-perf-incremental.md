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

## 2. release re-rendered/re-exported all 81 docs every time (even on a no-change release)

`cut_release.export_neutral` had NO staleness check: it opened all 81 docs, SaveAs3'd
STEP+STL, and rendered 486 PNGs **every** release. v0.9.1 reported "no part changed" yet
still spent ~546 s re-rendering byte-identical PNGs + re-exporting STEP/STL the `export`
task had *just* produced in `cad/out`.

**Fix (two parts, both incremental):**
- **STEP/STL are now COPIED from `cad/out`** (`_stage_neutral_geometry`) instead of
  re-SaveAs3'd. They are byte-equivalent: `_common._STL_INT_PREFS`, `export_models`, and
  `cut_release` ALL export with `PREF_STL_UNITS:0` (= swMM), fine, binary, no-translate,
  STEP AP214. The old "NEVER cad/out/stl, it's metre-unit" comment was **stale/wrong** —
  verified all three share mm prefs. `_require_fresh` fails loud if cad/out is
  stale/missing (export is release's spine predecessor, so fresh in the happy path).
  Eliminates ~81 document opens.
- **PNGs are still rendered on the seat but cached** by resolved-geometry fingerprint
  (`_png_key` → `cad/out/release/png-cache/<key>/`). Part key = sha256(SLDPRT bytes,
  captures geometry+stored appearance). Assembly key = sha256(monolithic resolved-geometry
  STL + SLDASM bytes + colors.json) — a changed *child* part regenerates the mono STL, so
  the assembly re-renders. **Safe-by-construction:** a cache miss only ever re-renders,
  never serves a wrong image. A geometry-unchanged release opens **nothing**. Cache is
  pruned to keys used this run (best-effort, never fatal). Bump `PNG_RENDER_REV` when
  `_export_pngs` rendering params change.

Net on the v0.9.1 (no-change) case: release ~663 s → ~75 s (pack-and-go + copy + diff +
zip). On a typical few-parts-changed release: only the changed parts + the top assembly
re-render.

Dead code removed from cut_release: `_set_export_prefs`, `_restore_export_prefs`,
`_active_config`, the `SW_SAVE_*` + neutral-export `PREF_*/TOGGLE_*/_EXPORT_*` block
(release no longer SaveAs3-exports geometry).

## ⚠️ Validation status

Offline-validated only (this dev box has no SolidWorks; uv even picked py3.14 by
default — pin `--python 3.11`): `py_compile`, `ruff` clean on the diff,
`test_dodo_recipe`/`test_buildgraph`/`test_artifact_cache`/`test_telemetry`/
`test_nameplate_geometry` = 48 passed, verify `--suite math` 9/9 + `config` 13/13,
`doit list`/`doit info verify:subsystems` correct.

**The COM paths (verify on the seat, the release neutral export + PNG cache) MUST be
run once on the SolidWorks seat before the next real release.** Best first run:
`doit verify:subsystems` after `verify:soundness`, then a `doit release -- vX --no-publish`
(dry run — builds the bundle + logs, nothing leaves the machine) to confirm the
copy/cache flow ships the same step/stl/png set.
