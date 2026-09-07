# Alignment source-save boundary control

This is diagnostic instrumentation, not an accepted save-policy change. Native
execution requires a reviewed frozen revision and the shared seat grant.

## Retained failure

The ordinary alignment-pinion pilot at `add24145` produced native/PDF/PNG output,
then rejected its owned source copy because the bytes changed. Recipe time was
22.666290000022855 s, including existing diagnostic reads. The receipt is
`cad/out/reports/datum-policy-s3q2gji6/pilot.json` in the primary checkout:

- Receipt SHA-256: `e9190be3f09daf379d7e71bde6b73e08e1aa71f33fc6b35447a3362847cffe62`.
- Original and initial copy: `858dc759943c2f739b3081fd02f313c26ead01eb837e08f9c79d59caac388920`.
- Copy after the recipe: `4bd7337bcdb79e2020e802c784eb8e5e7c6d0bad39aa6d23472ff1d8ca2804f0`.
- Trace: `0xcded02273219e9a9d40d5c2f5ff65034`.

The copy's observed last-write time, `2026-09-07T06:43:48.8946648Z`, falls inside
`drawing.save_native` (`06:43:48.542209Z`–`06:43:49.998375Z`), before the PDF span.
This associates the disk write with the native-save phase; it does not identify
which earlier operation first dirtied the source. The recipe applies the bore's
`THRU - REAM\nPRESS FIT` callout and precision before finalization. Each helper
already performs its own rebuild. The observer does not add a rebuild or setter.

The failure capture retained the same named `ArborBoreDia@ArborBoreProfile`
manufacturing value/tolerance witness (`0.008000000002`, tolerance type 2).
The ordinary `source_after` acceptance bank was not reached. One parameter is
not a full source-equivalence proof. The original part and other protected inputs
kept their hashes. Ownership returned from an empty baseline to empty; cleanup
was null. The final runtime guard also reported the changed copy, as required.

For comparison, the earlier arbor first-dirty control
`probe_source_dirty_recipe.py` (`source-dirty-9cbdz77u`, frozen `99eadbe7`) observed
its first dirty transition around the unchanged callout helper, with only the
bore's below-text changing among its 20 observed dimensions. It did not bisect
that helper's SetText versus rebuild operations and did not save. That result is
not evidence that alignment has the identical first-dirty operation.

## Instrumented replay

`--source-observation alignment_save` opts the existing owned full-recipe pilot
into nine read banks: initial, then before/after callouts, precision, native save,
and PDF export. Only `--target alignment_pinion` is accepted. Default behavior and
all original source/copy/runtime/attachment/layout/cold/export guards remain.

The helper calibrates one source `IDisplayDimension` through the exact named
feature once. It requires a unique observed display and its exact existing
`IDimension`; it never toggles visibility. At each boundary it records:

- GetSaveFlag before and after the getters, plus exact copy-file hash;
- freshly resolved named source configuration/value/tolerance/BASIC and native
  parameter identity, using the existing pilot reader;
- an additional unrounded, finite, single GetSystemValue3 scalar, with exact
  same-session equality, and tolerance limits;
- the cached display's current exact parameter identity, type, precision and raw
  GetText parts 1–8. Hole-callout text is explicitly unsupported here.

The repeated source reader resolves only the manifest's named feature dimension,
not a complete source annotation or BREP inventory. Its existing rounded witness
is retained alongside the new raw scalar. Every bank has its own read duration;
these additional reads are not a speedup. Raw presentation changes are evidence,
not silently classified as harmless. Getter-induced dirtiness, missing/ambiguous
calibration, invalid native shapes, or identity/value/tolerance changes fail.

The save wrapper composes the existing `artifact_context`; it performs no save
itself. Both native-save and PDF observations survive before the unchanged
after-recipe immutable-copy gate rejects disk drift. Primary operation errors
remain primary if a subsequent read or evidence checkpoint also fails.

Example command, only after a current PID and seat grant are supplied:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<reviewed-current-PID>'
$env:PYTHONPATH = 'C:/src/ha-perf-source-save-boundaries/cad/scripts;C:/src/harmonic-analyzer/SolidworksMCP-python/src'
uv run --no-project --python C:/src/harmonic-analyzer/.venv/Scripts/python.exe python cad/scripts/diagnostics/probe_datum_policy_recipes.py --candidate HEAD --factory normal --target alignment_pinion --source-observation alignment_save --source-root C:/src/harmonic-analyzer/cad/out/sldprt --guard-root C:/src/harmonic-analyzer/cad/out/sldprt
```

Run from the frozen isolated checkout. The existing parent runner takes the
machine lock; the worker remains attach-only. It fingerprints actual imported
adapter/helper sources and uses unique owned copies. No native result for this
new opt-in is claimed by its offline tests.

Offline verification: 133 tests passed in 2.64 s across source-boundary,
full-recipe pilot, first-dirty control and factory suites; Ruff passed. Tests
include raw sub-rounding value changes, malformed native arrays, replaced
documents/parameters, getter dirtiness, original-error retention, CLI scope, and
both save banks surviving before the unchanged immutable-copy rejection.

## Save API contract and separate candidate

The bundled current `IModelDocExtension.SaveAs3` explicitly accepts
`swSaveAsOptions_e`. That enum defines `Silent=1` separately from
`SaveReferenced=4`, the latter requesting all referenced assembly/drawing
components. A bounded candidate can therefore omit bit 4:

```python
extension = _early_bound(drawing.Extension, "IModelDocExtension")
advanced = extension.GetAdvancedSaveAsOptions(0)
result = extension.SaveAs3(native_path, 0, 1, None, advanced, 0, 0)
```

This is a candidate call shape, not a guarantee that dirty referenced files stay
unchanged. `GetAdvancedSaveAsOptions(0)` uses the separate
`swSaveWithReferencesOptions_e`: zero means the normal reference list, **not**
"no references." `SaveAllAsCopy=False` likewise is not a no-reference-save
contract. The obsolete `IModelDoc2.SaveAs3(path, 0, 0)` page does not document its
Options parameter enough to transfer the modern contract to that legacy call.

The earlier four-cell `probe_drawing_template_save.py` control
(`template-save-74ytw6wb`, frozen `282bb9e7`) proved the legacy three-argument call
saved/reopened blank SLDDRW and DRWDOT files. The tested modern advanced/silent
shape returned `(True, 0, 0)` but produced neither requested file nor native path.
Those blank documents had no dirty references, so that failure does not answer
the reference-write question. A new control must validate native result, actual
file/path, exact source hashes and cold witnesses. No alternative save is added
by this commit.

Docs read: `IModelDocExtension.SaveAs3`, `GetAdvancedSaveAsOptions`,
`IAdvancedSaveAsOptions.SaveAllAsCopy`, `IModelDoc2.SaveAs3`,
`swSaveAsOptions_e`, `swSaveWithReferencesOptions_e`, and the bundled PDF-save
example. Source getter docs and the dimension-enumeration example were read
before implementing the banks.

Composition seam for a separate save control: install its context **before**
`SourceSaveBoundaries.observe()`. The observer captures the current
`_drawing_common.save_drawing` and forwards its composed `artifact_context`
without duplicating either save. The legacy context must remain an exact no-op.

## Native boundary replay at `3b426b62`

The separate legacy and null-advanced extension runs used adapter `e77bfda4`,
the same existing PID 31860, fresh copies of the pinned alignment part, normal
factory, and disabled remote cache/autostart. The pre-existing pivot drawing and
part were preserved, including native identities and clean/visible state; both
runs cleaned up their owned documents without error. Originals stayed exact.

Legacy receipt: `datum-policy-drg09evu/pilot.json`, SHA-256
`3c965cb022f790d3b84108873a31908797ab7c2debac9572cad602cef75b7d0d`.
All nine source banks completed. The source was clean before the callout helper
and dirty afterward; observed text slots 4 and 8 changed to
`THRU - REAM\nPRESS FIT`. Precision did not change the observed source display.
The exact raw bore value `0.008000000002000001`, tolerances and native parameter
identities stayed unchanged at every bank. This locates the first dirty helper,
not SetText versus its existing rebuild within that helper.

The copy SHA stayed original through `before_native_save`, then changed to
`09c1de0d6b849fa848ebf1f5fe6a1d08664caa45f1f5bf09ff46ac6f4240acde`
at `after_native_save`, where the dirty flag cleared. Both PDF banks retained
that changed hash. The recipe's unchanged copy-hash gate rejected it. Recipe
time including instrumentation was 33.808 s; total pilot time was 89.388 s.
Failure evidence was complete with no capture errors. This is a failed source
acceptance control, not a performance baseline for uninstrumented production.

Modern receipt: `datum-policy-ytl97oo4/pilot.json`, SHA-256
`0046e3ce7abca28a3570c2a4bc78a0ac78d5b9c394ab593e81b4d0576b3c4878`.
The typed null-advanced call returned `(True, 0, 0)`, produced a 203,426-byte
native drawing at the exact requested path, and took 1.105 s. The source
remained dirty in memory and retained its original disk hash after that call;
all seven reached source banks retained exact raw value/tolerance/identity.

The trial nevertheless failed: the diagnostic's post-save inventory check ran
inside the `saving_as` scope, before that scope reconciled the authorized
unsaved-to-saved path/title transition. It therefore rejected the renamed
drawing against its old recorded name. The native save itself passed its
file/path/result checks. Scope exit reconciled ownership and cleanup succeeded.
Failure-only PDF evidence was complete and preserved source bytes; ordinary
recipe PDF, built acceptance and cold reopening were not reached. Runtime final
guards reported no drift. Recipe/pilot times were 31.738/91.643 s.

The next run must correct the diagnostic scope ordering and keep the immediate
post-observer active-document check. This partial result establishes native
persistence for this call shape, not a completed source-safe drawing recipe.

## Reconciled modern save: cold callout loss

At `5db764ad` the corrected native scope completed the recipe and both save
boundaries. Receipt `datum-policy-uiu2rsnq/pilot.json`, SHA-256
`7583b8e718b945884648ceec42bb6bbd25dfa4ab20e3b0d314d624ea09fbdd7a`,
retains all nine source banks. The modern save returned `(True, 0, 0)` and
produced a 203,888-byte drawing in 1.125 s. Original copy hashes remained exact
after the complete recipe, PDF export, closing and final cleanup. All source
value/tolerance/identity banks passed; the built explicit bore-finish witness
also passed. Recipe/pilot times were 36.769/156.874 s, including diagnostics.

Cold reopening failed the unchanged annotation comparator: all 162 rejected
observations belong to `ArborBoreDia`. The two callout lines `THRU - REAM` and
`PRESS FIT` disappeared, and the dimension's text/leader layout changed with
them. The initial and cold failure PNGs visibly confirm that content loss;
the value and tolerance remain printed. Other annotations were unchanged.
The source remained unsaved, so avoiding its disk write alone does not preserve
the current shared callout fields. This is not an accepted production save fix.

Failure PDF evidence completed with no errors. The two pre-existing pivot
documents retained exact identities/states, owned cleanup succeeded, and final
runtime guards reported no drift. The complete offline recipe gate at this
revision passed 4,824 tests in 81.57 s; it does not override this native failure.

The smallest next field-level control is `IDisplayDimension.SetLowerText`, with
explicit `GetLowerText` readback. `IModelDocExtension.EditDimensionProperties`
distinguishes `DimensionLowerText` (valid for drawing display dimensions only)
from `CalloutText1/2`. The bundled chamfer example demonstrates that setter on a
drawing-created dimension. Imported diameter, multiline text and cold persistence
remain untested deltas; no source-authoring or drawing-owned-note refactor is
required before trying that documented field.

## Isolated drawing lower-text field control

The pilot now accepts `--callout-storage lower_text`, only for alignment with
source observation banks and an explicit legacy or modern save arm. Omission
does not change the production helper. The selected control patches both loaded
recipe/common callout aliases before the source observer enters; all aliases
restore on success or failure. It changes `SetText(4, text)` to the documented
void `SetLowerText(text)` on the same exact imported bore dimension, then performs
the existing single rebuild. No source getter uses this drawing-only field.

Both initial operation readback and fresh built/cold snapshots require exact
GetLowerText, native source-dimension/annotation/view identities, unaltered
parameter/attachment witnesses, and both requested lines in the existing native
text runs. Cold snapshots use newly resolved source handles, never old handles
from a closed document. Whole-drawing layout and source-copy hash gates remain
unchanged. This permits native placement of text below the dimension line;
it does not accept hidden string storage as visible manufacturing content.

First test the existing save API, changing only the text field from the retained
legacy arm. Use the same verified PID, attach-only environment and frozen-root
conditions above:

```powershell
uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
  --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --guard-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --target alignment_pinion --factory normal `
  --source-observation alignment_save --drawing-save legacy `
  --callout-storage lower_text
```

The offline helper/pilot/save selection passed 180 tests. Native source cleanliness,
multiline layout and cold persistence are not established by those tests.

## Lower-text legacy replay: lost before built acceptance

At `a39b52d8` with adapter `e77bfda4`, PID 31860 and the command above,
`datum-policy-3hcoww72/pilot.json` failed built acceptance, before cold reopening.
Receipt SHA-256:
`ddd562d723419f7ec142f52ee4d08deda81fb02706cc3f8522992b90080b1da6`.
The setter and its existing rebuild both retained exact
`THRU - REAM\nPRESS FIT`, raw bore value `0.008000000002000001`, source
parameter identity and attachment type `[10]`. The operation took 1.611 s.

All nine source banks stayed clean with the original copy hash, including after
legacy native save and PDF export. Source text/value/tolerance witnesses were
unchanged. However, the fresh built display returned empty GetLowerText and its
native text runs contained neither requested line. The recipe PNG confirms the
missing text. Recipe/pilot times were 34.053/115.002 s including diagnostics.
No cold comparison was reached; this is not a cold-persistence result.

Failure evidence completed without capture errors; originals and the owned copy
kept their exact hashes. The pre-existing clean/visible pivot drawing and part
were preserved; owned cleanup succeeded and final runtime guards were empty.
The first control proves source cleanliness for this call sequence, not usable
printed callouts. It does not locate the later text-clearing operation.

The next replay adds optional fresh drawing-field banks alongside the eight
non-initial source banks. Those reads keep exact source/attachment witnesses,
do not add a setter/rebuild, and remain inside the source getter-dirtiness guard.
They record text loss without accepting it; the built/cold gates still reject
missing storage or printed lines. The initial source-only bank never calls the
drawing reader. The next run separates the precision helper, intervening recipe
work, native save and PDF export as candidate loss boundaries.

At `f26ec691`, the modern-save arm with these fresh drawing banks produced
`datum-policy-7t6zttug/pilot.json`, SHA-256
`c071a53c66aae1436c191ff82d3ec4df4f8a2ca36bc8969d61b7042ed87f92c4`.
The lower text survived fresh inventory after callouts, before precision and
after precision. It was already empty at `before_native_save`, and remained
empty through both export banks and built acceptance. Thus this loss precedes
either save call; a save-API change cannot repair it. Subsequent annotation
operations and sheet finalization remain unseparated by these nine banks.

The modern call itself returned `(True, 0, 0)`, wrote 202,884 bytes and took
1.179 s. Recipe/pilot times including the expanded reads were 56.745/141.028 s.
All source banks stayed clean with exact hashes and raw parameter/tolerance
witnesses. Built acceptance rejected missing lower text; cold reopening was not
reached. Failure evidence retained no capture errors. Originals and the copied
source remained exact, the two baseline pivot documents were preserved, and
cleanup/final guards were clean. No production text/save policy is promoted.

## Remaining recipe boundaries: loss during finalization

At `5e468895`, adapter `e77bfda4`, PID 31860, the same legacy command produced
`datum-policy-q37e1dvb/pilot.json`, SHA-256
`facb0ee216034501391cfac1502ef4a289900b8f650b6d619d8b63cb021c18cf`.
Fresh lower-text reads remained exact after center marks, circle selection,
datum, feature-control frame, surface finish and both property notes. The text
was still present immediately before `finalize_drawing`, but empty immediately
before native save. The clearing operation is therefore inside finalization,
not any preceding annotation helper. This does not yet distinguish SetScale
from the other finalization operations.

The run reached 23 of the 25 selected banks. The after-native bank rejected the
renamed drawing because this pilot still called the raw adapter saver: the
outer drawing-creation scope did not reconcile SaveAs ownership until recipe
exit. The previously repaired shared owned saver was not on this call path.
The fix is to install that owned saver in the actual pilot before its optional
save control, preserving the legacy control's no-op contract; six call-path
tests reproduce the failure and check both native APIs and failure cleanup.

Recipe/pilot times were 96.983/154.319 s, including diagnostic reads. Ordinary
PDF, built and cold acceptance were not reached. Failure capture completed with
no errors; source/copy hashes stayed exact. On exit, creation-scope
reconciliation and owned cleanup succeeded, the two clean/visible baseline
pivot documents remained open, and final runtime guards were empty.
No production text policy is accepted from this failed pilot.
