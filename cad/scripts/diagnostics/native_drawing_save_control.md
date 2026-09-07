# Native drawing-save control

This is an offline-tested diagnostic, not a production save change. It tests
whether a different native drawing save call avoids the source-copy writes
observed in the alignment recipe. It does not assume that clearing
`SaveReferenced` prevents every possible native reference write.

## One changed call

`DrawingSave.LEGACY` leaves `_drawing_common.save_drawing` untouched, including
its function identity. `EXTENSION_SILENT` replaces that alias only inside an
explicit context; no adapter source, COM object or global preference is patched.

The selected drawing call is early-bound `IModelDocExtension.SaveAs3`:

```python
extension.SaveAs3(str(path), 0, 1, null_dispatch(), null_dispatch(), 0, 0)
```

The arguments mean current native version, Silent only, null ExportData, null
AdvancedSaveAsOptions, and two makepy out-parameter placeholders. The generated
2026 binding declares both nulls as `VT_DISPATCH` and the last two slots as
`[in,out] LONG`; values return in `(success, errors, warnings)`, not writable
Python VARIANT objects. A test checks that exact generated ABI. Success requires
a true native result, zero errors, a nonempty fresh file, and exact requested
native drawing path. Warning bits are retained, not silently dropped. See
[SaveAs3](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SaveAs3.html)
and [save options](https://help.solidworks.com/2026/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swSaveAsOptions_e.html).

The official PDF example demonstrates the extension's older `SaveAs` API with
Silent and export data, not this exact `SaveAs3` form. Earlier owned template
controls used an actual `GetAdvancedSaveAsOptions(0)` object and did not establish
positive persistence for the modern method. The later null-advanced form saved
the requested native drawing, but its recipe failed; see the
[native replay evidence](../../docs/pipeline/alignment-source-save-boundaries.md#native-boundary-replay-at-3b426b62).
A rejection stops the trial; there is no
fallback, added rebuild, ClearSelection, source save, or automatic retry.

PDF and optional PNG still use exactly `draw.SaveAs3(path, 0, 0)`. Each artifact
keeps the adapter's drawing/PDF/PNG order, caller-provided `artifact_context`,
directory creation, stale-target removal and file-existence gate. Native output
alone adds the modern result/nonempty/path validation. Failed/partial files are
retained as evidence, not accepted. Output extensions and sibling-directory
containment are checked before any stale file is removed; the native output is
validated by the existing owned `saving_as` scope.

## Composition

The existing owned pilot supplies the exact PID, seat lock, registered output
directory, immutable originals, source-copy snapshots and cold-reopen checks.
Install the save context **before** the source-boundary observer so the latter
captures the selected save function:

```python
from diagnostics._native_drawing_save_control import (
    DrawingSave, native_drawing_save_control,
)

trial["native_save_calls"] = []
with native_drawing_save_control(
    adapter, DrawingSave.EXTENSION_SILENT,
    records=trial["native_save_calls"],
):
    with source_observer.observe():
        artifacts = await module.build(adapter, drawing_factory=drawing_factory)
```

The source observer's combined artifact context still surrounds native save and
PDF export. The control preserves both the primary save failure and any owned
scope exit failure; exiting restores the original alias in either case.
`seconds` covers the selected save wrapper, ownership checks and artifact
contexts. `native_call_seconds` covers extension binding and the modern native
call, excluding subsequent file/path reads. Neither is end-to-end build time.

This module is a composition seam, not another native launcher. The pilot's CLI
accepts `--drawing-save legacy|extension_silent` only with
`--target alignment_pinion --source-observation alignment_save`. Both parent and
worker validate that scope before any document/file operation. Omission retains
the original unpatched path; an explicit legacy arm also leaves its exact save
function untouched. The save context encloses the source observer so both arms
retain every boundary bank. Native
acceptance needs a reviewed, frozen, single-target `alignment_pinion` legacy /
modern pair through that attach-only runner, using fresh matched source copies,
the same immutable input bytes and source value/tolerance/presentation banks.
All drawing and source persistence gates remain mandatory. Separate legacy and
modern arms ran at `3b426b62`, but neither completed drawing acceptance. The
legacy arm (`datum-policy-drg09evu`) failed on source-copy hash drift. The modern
arm (`datum-policy-ytl97oo4`) used both typed nulls, returned `(True, 0, 0)` and
saved a 203,426-byte drawing at the exact requested path while preserving source
bytes. Its post-save ownership check ran before `saving_as` reconciled the new
path/title, so ordinary recipe PDF, built acceptance and cold reopening were
not reached. The [boundary replay record](../../docs/pipeline/alignment-source-save-boundaries.md#native-boundary-replay-at-3b426b62)
contains both receipt hashes and the cleanup evidence.

The corrected modern run at `5db764ad` (`datum-policy-uiu2rsnq`) completed the
recipe and PDF save with source-copy hashes unchanged, then
[failed cold acceptance when the two fit-callout lines disappeared](../../docs/pipeline/alignment-source-save-boundaries.md#reconciled-modern-save-cold-callout-loss).
These runs establish no accepted production save change or performance benefit.

Run each arm separately on the same frozen checkout and matched source bytes:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<verified existing PID>'
uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
  --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --guard-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --target alignment_pinion --factory normal `
  --source-observation alignment_save --drawing-save legacy
```

After inspecting the legacy receipt and cleanup, repeat with
`--drawing-save extension_silent`. Legacy source-copy drift is an expected failed
control, not permission to alter the source acceptance condition. The modern
arm must still pass that condition and every built/cold drawing witness.

## Offline verification

```powershell
uv run --no-sync python -m pytest cad/scripts/test_native_save_control_drawing.py cad/scripts/test_template_save_drawing.py cad/scripts/test_owned_native_documents_drawing.py -q
```

The 24 new tests cover the default identity, exact generated ABI and arguments,
one native save, unchanged PDF/PNG routing, artifact-context composition, stale
and empty files, wrong path/type/adapter, typed errors/warnings, partial output,
owned-scope rejection, and exception restoration/aggregation. The combined
selection passed 68 tests without constructing an adapter or calling COM.
