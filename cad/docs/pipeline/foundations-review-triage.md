# Foundations Windows review triage

Read-only review retrieval on 2026-09-07 used only the completed Windows CLI
history, not another review request:

```powershell
Set-Location C:/src/ha-cr-cli-foundations
& 'C:/Users/pedro/AppData/Local/Programs/coderabbit/coderabbit.exe' review findings
```

The complete 17 finding JSONs remain in the CLI's native receipt directory:

```text
C:/Users/pedro/AppData/Local/coderabbit/reviews/6c1cc811/4949ebb2/reviews/1788791303159
```

`git.json` pins head `d8ec09f5d4208cc8a06c2cf98f5ede227ab41cbf` and main base
`9e746e1513479290565e6d920e74dadb3c7062a2`; `.session-complete-v2` says
`complete`. The SHA-256 of `git.json` is
`799c99c67d22adccc8292be47e5b7a3e18ce4645a3e53c65aeafc203a62e45f7`;
`incrementalDiff.v2.json` is
`b74656792a26918480e4e09a2a840475f97e70eb43aac038c6cd06026478478b`.
No authentication files were opened. The findings were also checked against
root `bd7e33843eb65d1d22afa4fa8e413b1b78cd59cd`, without editing that checkout.

## All findings

Line numbers below identify the reviewed foundation, not subsequent patches.
Twelve findings warrant diagnostic/test/prose changes, four are false positives,
and one needs the later evidence linked rather than a production feature flag.
None is merely fixed by the inspected top-of-stack changes.

| Finding (receipt ID prefix) | Foundation location | Disposition |
|---|---|---|
| `10c94fda` | `probe_datum_dimension_attachment.py:531` and five sibling probes | Add operation spans. The session already spans attach/disconnect; this is finer-grained coverage, not missing all telemetry. |
| `170ef6e7` | `_recipe_acceptance_targets.py:25` | False positive: `PartDatum.key` already calls `datum_key`, returning `datum:A`. |
| `2101e9c7` | `diagnostics/template_defaults.md:407` | Heading level/spacing correction. |
| `3b0d3b21` | `probe_gtol_leader_override.py:674` | Real: failed owner construction leaves `None`; accessing `.close` masks the primary exception before final receipt/hash capture. |
| `404e9f6c` | `probe_retained_drawing_export.py:421` | Real: final checkpoint may replace the primary exception. Ordinary per-file hash `OSError`s are already recorded by `final_hashes`. |
| `5b11b5b7` | `probe_licensed_startup.py:517` | Timeout message spacing correction. |
| `5e56fe47` | `probe_fresh_lever_column.py:118` | Real: create report root before `mkdtemp` on a clean checkout. Later factory-ABI changes did not fix this. |
| `7e801495` | `test_source_dirty_recipe_drawing.py:246` | Tighten expected exception classes and payloads. Original hash, cleanup and no-save assertions stay intact. |
| `858ccc6a` | `test_cwm_mate_guard.py:324` | False positive: autouse `_patch` owns a fresh module via `monkeypatch.setitem(sys.modules, ...)`; the assigned transform stub cannot leak to the real adapter or next test. |
| `859bb802` | `_annotation_entity_context.py:206` | Real: reject unsupported type before reads and observer mutation, avoiding an unfinished timing row. |
| `99564e61` | `probe_source_basic_dimensions.py:173` | Real: exact target BASIC change must also update expected datum-embedded dimension semantics; actual comparison remains strict. |
| `bda03e20` | `probe_dimension_arrangement.py:601` | Improve malformed PID error. Existing conversion already fails before COM; this is not a launch/ownership bypass. |
| `beba64c9` | `_drawing_native_display_data.py:99` | False positive: called `_native_counts` already rejects nonzero Ellipse, Parabola and Point inventories. |
| `c5cd2d51` | `build_channel_assembly.py:1607` | Stale saved-acceptance premise; later VM2 evidence below. No speculative alternate-path flag. |
| `ce3c41ed` | `diagnostics/baked_template_layout.md:6` | Clarify opening paragraph's pronoun. |
| `f0363864` | `build_cone_pivot_screw.py:93` | False positive: `_common._early_bound(None, ...)` deliberately returns `None`, so the following error guard is reachable. |
| `fc364a86` | `probe_datum_dimension_attachment.py:263` | Array-length integrity improvement. `binding` already rejects mismatches but captures them as failed evidence; later `zip` can still truncate that evidence. Not an established false-acceptance path. |

The exception/span/probe-message/prose fixes are a separate diagnostic slice.
The context/BASIC corrections and precise source-dirty test are foundation-local;
no production annotation policy, model-coverage helper, source pin or manifest
is changed. On the inspected top, the source-dirty test is parameterized over
three targets, so integration must retain all those cases when applying its
small exception-only change.

## Retained-driver evidence scope

The later [VM2 report at `a6b5c900`](https://github.com/pedropaulovc/harmonic-analyzer/blob/a6b5c900def3b8dc45f3475607f9de6aae4b4992/cad/docs/pipeline/assembly-vm2-results.md#candidate-acceptance)
records the actual native candidate at `60178f31`, adapter `e77bfda4`: all eight
assemblies rebuilt, all eight independently reopened saved soundness checks and
kinematics passed, with zero failed native tasks/recoveries. Channel's saved
soundness took 30.156 s. The later identity trial kept all six DOF manifests
byte-identical, and the complete artifact manifest binds all 116 native files
and producer tokens across baseline/candidate/identity-accepted snapshots
(manifest SHA-256 `e49aa7e075bf0a7afbe421cb9fa5c0a7426d8a6b33a27b771012ffb5f8fd330c`).

Both `build_channel_assembly.py` and `_channel_pose.py` are byte-identical between
foundation `d8ec09f5` and tested `60178f31`; `git diff` on those two paths is empty.
Thus independent saved acceptance of the retained-driver implementation is not
missing. This is not a new paired post-save experiment isolating bank release
from per-channel release, an end-to-end speedup claim, a population failure-rate
claim, or a transferred drawing-inclusive full-build gate on a different tree.
The original construction comparison in `performance.md` remains historical.

## Repeatable offline checks

`test_prepared_template_surface_finish_drawing.py` already tests nonzero
Ellipse/Parabola/Point rejection through the actual raw display reader.
`test_flag_only.py::test_non_com_objects_still_pass_through_quietly` already pins
the `None` behavior. The added CWM nested-fixture regression proves module identity
and attributes are restored without touching native COM.

```powershell
$env:PYTHONPATH = "$PWD/cad/scripts;$PWD/cad/comparisons/tools"
uv run --no-sync python -m pytest -q cad/scripts/test_annotation_entity_context_drawing.py cad/scripts/test_source_basic_dimensions_drawing.py cad/scripts/test_source_dirty_recipe_drawing.py cad/scripts/test_cwm_mate_guard.py cad/scripts/test_prepared_template_surface_finish_drawing.py cad/scripts/test_shaft_recipe_acceptance_drawing.py cad/scripts/test_flag_only.py
uv run --no-sync python -c "from diagnostics._recipe_acceptance_targets import TARGETS; from _common import _early_bound; assert _early_bound(None, 'IFeature') is None; [print(key, TARGETS[key].entity_labels) for key in ('fulcrum_shaft', 'pivot_shaft')]"
```

Before the two diagnostic corrections, five new regressions failed and 31 checks
passed (`run-7jhbi94_`). Afterwards the seven-file focused/adjacent suite passed
352 tests in 2.09 s (`run-sh7ltruo`); Ruff F and `git diff --check` passed.
All checks used the isolated worktree's own venv and adapter `e77bfda4`. No COM,
native artifact writes, new native acceptance or remote changes were performed.

## GitHub review: entity and measurement checks

Review `5133229263` added findings not present in the 17-item local report.
The following decisions have executable checks, rather than assuming a suggested
change improves performance or safety:

- `3950733385`: a null `IEdge.GetCurve` now raises a named error. It is not
  silently removed from the topology search. Both circle and line roles reproduce
  the earlier `AttributeError` (`run-n57x9tyh`, two failures before the guard).
- `3950733397`: retain the no-callout early exit. The actual callout/GTol handoff
  regression measures a dimension-only obstacle zero times in the callout stage
  and once in the GTol stage. Entering the before/final callout witness solely to
  fill the handoff would measure it twice, not remove a repeated measurement.
- `3950733451`: source-PMI pairing explicitly uses `strict=False`: the exact
  comparator already records a length mismatch, and a strict zip must not replace
  that failure report. Geometric endpoint pairs use `strict=True`.
- The view-scale test now states what it proves: model-only identity resolution.
  Its unused fake view position/scale did not exercise native layout behavior.
- The unused `_clear` helper was removed. `_candidate_text_cells` stays: both
  production GTol arrangement and the right-column diagnostic call it, and its
  existing tests cover the returned cells.
- Do not memoize content hashes using only path, length and mtime. The new
  prepared-template regression changes equal-length bytes, restores the original
  mtime, and verifies that the exact hash still changes. Such a memo would accept
  altered template bytes under their old identity.

The eight-file focused/adjacent suite passes 292 tests in 3.69 seconds
(`run-boyf6tsi`). These are offline regressions, not new native drawing acceptance.
