# Prepared drawing-template control

`benchmark_template_defaults.py` compares the same pinned recipe in ABBA order:
current setup, inherited-template setup, inherited-template setup, current setup.
It is a diagnostic, not a production template change. No native result or speedup
is established by its offline tests.

The first native block is **arbor_pedestal only**. Review its retained native
drawing, PDF and PNG before authorizing a separate pen_marker block. Both recipes
at the initial source revision `4147d8d8` use sheet scale 2:1 and two decimal
places. The prepared-template key includes the exact scale tuple and precision;
the control rejects unsupported setup arguments instead of silently sharing a
different default. Two- and three-decimal variants are tested offline.

## What changes

Preparation creates a drawing from the immutable project DRWDOT, calls the
existing `new_project_drawing` once, and saves a new DRWDOT under a unique report
directory. This captures the existing metric edge-break note, custom-mm precision,
all ten dimension text/leader style scopes and sheet scale. A new blank drawing
instantiated from that DRWDOT must reproduce the measured defaults before the
first recipe runs.

Candidate setup uses that exact prepared file and retains EditSheet, the ASME-B
sheet assertion and zoom-to-fit. It omits the repeated normalization, units,
dimension-style and scale setters, plus both blank-sheet rebuild calls. All
subsequent recipe view-quality choices, layout repair, dimensions, datums,
surface finish, manufacturing validation and native/PDF/PNG finalization remain
the same. No global preferences, original template or source geometry are edited.
Surface-finish inheritance, automatic updates and display-quality experiments
are deliberately outside this comparison.

## Preconditions and one bounded run

Commit/freeze the benchmark, helper stack and recipes first. Obtain the exclusive
machine-global SolidWorks seat and review this source before native execution.
SolidWorks must already be healthy and licensed; the diagnostic only attaches.
It never launches, recovers or changes settings. The shared ownership helper
rejects unsafe baseline inventories, including hidden baseline documents, and
preserves visible pre-existing documents rather than closing them.

From the isolated worktree, with `HARMONIC_SW_AUTOSTART=0` in the child environment:

```powershell
uv run python cad/scripts/diagnostics/benchmark_template_defaults.py arbor_pedestal --recipe-revision <frozen-commit> --source-root C:/src/harmonic-analyzer/cad/out/sldprt
```

The parent invocation uses `dodo._run(..., com=True)` and the attach-only diagnostic
runner. Do not run the hidden worker directly. Output basenames and directories
are unique; recipe output declarations and aliases are rewritten before recipe
evaluation. This is a bounded adapter for the two trusted direct recipes, not a
sandbox for arbitrary Python recipes.

Each arm now starts from a fresh exact byte-copy of the original part in its own
registered source directory. All four copies share one block-unique basename,
but have different absolute paths. The reviewed shared loader redirects `SOURCE`
before aliases and function defaults bind. The original and project template
retain protected SOURCE ownership; each copy is ordinary COPY ownership, never
registered as SOURCE. A recipe's saved part is retained as that arm's output,
never overwritten or reset for another arm. Its output hash is pinned after the
recipe and must stay unchanged through read-only validation and cleanup.

The owned-copy first-dirty control at `99eadbe7` localized the initial dirty flag
to the `set_dimension_callouts` operation group: observed source BoreDia display
text slots 4/8 changed from empty to THRU, while all 20 observed dimension native
IDs/values/tolerances stayed unchanged. This does not distinguish its inner setter
from rebuild, characterize later writes, or establish full source equivalence.
Accordingly, benchmark source path/kind/configuration/native identity and dirty
state are recorded at recipe-open, before/after save and after persisted checks.
Every model view must reference the exact copied source and configuration.
The small `_source_dimension_snapshot.py` reader is extracted from that proven
control. Initial, pre-save, post-recipe and cold-reopened observations retain all
observed feature/display dimensions, not just the five required arbor dimensions.
Configuration, feature/name inventory, native values, tolerance type/limits and
BASIC designation stay exact. Native dimension handles must remain identical
within the same open part; closed wrappers are never compared. Display inventory,
type and marking remain exact; text and precision deltas are retained explicitly.
The initial snapshot itself must not dirty the fresh source. This is an observed
dimension/attachment witness, not a claim of full BREP/source equivalence.

Persisted validation closes **both** drawing and owned source without saving,
checks the saved copy's disk SHA, discards the old COM handles, and reopens the drawing
with a fresh native source instance. It then repeats the unchanged values,
tolerances, text, attachments, defaults and layout comparisons. A lost THRU callout,
BASIC designation or precision after cold reopen fails; keeping a dirty source
open is not a persistence witness. Both owned documents close after every trial.
The previous immutable-copy failure is recorded below; do not repeat that blocked
shape or change its retained copy to satisfy the hash check. The fresh-per-arm
replacement is offline-tested only until a separately reviewed native run.

## Evidence and timing boundaries

`measurements.json` is checkpointed before each preparation/trial and after each
outcome/cleanup. Each trial retains source and recipe hashes, artifacts, fresh
saved/reopened witnesses and status/errors. `ownership.json` independently
retains initial/final native inventories, source hashes and cleanup failures.
Source/template hashes are pinned once for the entire block and checked between
trials and in the final failure path. Runtime fingerprints cover the helpers,
configuration, adapter, template resources and every diagnostic Python module.

Timing fields are intentionally separate:

- `owned_sources[trial-directory].seconds`: per-arm byte copying and initial hash checks.
- `template_preparations[].seconds`: one-time setup, DRWDOT save, inherited-default
  verification and its scoped cleanup. Do not exclude this cost when estimating
  first-use performance.
- `trials[].setup_seconds`: the inner setup helper only. Ownership inventory
  guards sit outside this timer.
- `trials[].recipe_elapsed_seconds`: complete recipe wall time, including inserted
  initial and pre-save source snapshots. `recipe_seconds` subtracts only those
  explicitly measured snapshots (`recipe_excluded_source_snapshot_seconds`);
  ownership, path/configuration/hash guards, recipe validation and native/PDF/PNG
  finalization remain included. The recipe telemetry span retains inclusive time.
- `trials[].source_snapshot_seconds`: raw per-phase source-witness durations.
  The post-recipe source snapshot is outside recipe wall time; cold-reopened
  source capture is part of the separate validation timer.
- `trials[].validation_seconds`: additional diagnostic cold-source saved/reopened comparison,
  outside the recipe timer. Per-trial final cleanup is also outside that timer.

Saved/reopened comparisons preserve each drawing's native annotation inventory,
attachment geometry, dimension values/tolerances, layout and measured content.
Cross-arm comparisons use a multiplicity-preserving semantic inventory rather
than regenerated DetailItem labels. Datum-to-dimension label removal requires an
independent exact target-dimension witness. Raw observations remain in the
report. Only an exact witnessed arm source path and model-dimension owner suffix
map to `original-sha256:<pinned-input-hash>` across arms. A different owner fails;
other names/text/geometry are not stripped. Initial and cold-reopened source
snapshots are also compared across arms, including their presentation output.
Sheet note text/link text/extents/format and every view's display-quality
readbacks are included, even for views with no annotations. Unsupported geometry
exclusions stay explicit; the diagnostic does not claim to prove excluded
attachments. Native extents are not assumed to translate rigidly or be harmless
quantization: a differing final witness fails for investigation.

One ABBA block supports only its observed paired timing differences. It does not
establish a fleet speedup, a conflict probability below 5%, or visual equivalence
of every export. The retained PDFs/PNGs still need a human eye pass.

## Historical immutable-copy native result

The reviewed arbor-only run at `ab264db8` (parent session 84016, existing PID
37136, AUTOSTART=0, remote cache off) stopped on its first baseline. Retained
bundle: `cad/out/reports/template-defaults/template-abba-ykoh1l_z/`.
Preparation passed in 36.3289 s; source copying took 0.1180 s. Baseline setup was
5.56874 s and its recipe reached finalization in 104.64125 s. Native drawing,
PDF and PNG files were produced, but the copied-source hash gate failed before
cold persisted checks. No candidate ran; there is no accepted ABBA timing delta.

The exact copied part remained the same native handle/configuration, but changed
dirty-to-clean across finalization. Its disk SHA changed from
`dbb991437aea105ca5352b8b76468874077aeed0a74906413a1cc56fb7ca769e` to
`04eabd7157a43ee5f956191e7137f37f3cca1570997ff9c6830098cd20afe303`.
The source hash brackets the complete finalizer, not the individual native/PDF
save calls. Split telemetry records native save 1.50548 s and PDF export
0.696532 s; those timings do not independently identify which call wrote the
part. The changed copy and all outputs remain untouched as evidence.

Original arbor, original project template and derived-template disk hashes all
remained unchanged. Scoped cleanup succeeded without saving: the exact original
visible clean lever and dirty unsaved Draw2 were preserved, with no diagnostic
documents left open. `measurements.json` and `ownership.json` retain the failed
phase, before/after source state, hashes and cleanup evidence.

The falsified assumption was that an owned recipe source could remain byte-wise
immutable throughout the current mutating pipeline. Original-input immutability
remains required. The narrowest next proposal is one fresh byte-copy **per arm**,
with the same unique basename in separate owned arm directories, each starting
from the same original digest. Treat the resulting part as that arm's retained
output; never reset it. Compare observed source native dimension identities,
values/tolerances/BASIC before/after in the same open document, preserve explicit
presentation deltas, and require cold source-plus-drawing semantic readback.
Across arms, map only the independently verified source path/owner to its pinned
original digest. That fresh-per-arm replacement is now implemented as described
above; it has not yet passed a native block. The failed immutable-copy run and
its outputs remain unchanged.

Pre-authoring THRU/precision once on a copied part is a different starting recipe
condition. It also needs a positive control showing that repeated setters do not
dirty/save the source again; it is not a demonstrated shortcut to matched inputs.
Drawing-local callout authoring could avoid shared source presentation writes,
but would change the recipe and requires its own attachment/value/format and
cold-reopen proof. Neither change belongs in the first template-only comparison.

Local official `IModelDoc2/SaveAs3.md` documents only the obsolete integer-return
signature; its option parameters have no described semantics. Do not interpret
legacy `Options=0` using newer enum documentation. `IModelDocExtension/SaveAs.md`
and `SaveAs3.md` explicitly use `swSaveAsOptions_e`, whose `SaveReferenced=4`
includes drawing references and `Silent=1` is independent. A separate minimal
owned-copy control could contrast documented extension-save options 1 and 5,
retaining exact file/path/return/error/source hashes and cold readbacks; omission
of flag 4 is not yet proof that unsaved source presentation persists correctly.
The earlier advanced `SaveAs3` True/no-file result remains specific to that tested
call shape. No save API, option, shared preference or production recipe changed.

## Native API provenance and untested boundary

The prepared-template save now uses the proven production native call
`IModelDoc2.SaveAs3(path,0,0)` after clearing selection. It requires a fresh
nonempty file, an exact owned native path, and full new-from-template defaults
readback; its raw integer is recorded without inventing an undocumented status
meaning. The four-cell native positive control below supports that choice.

The bundled SolidWorks 2026 reference documents the alternative
`IModelDocExtension.SaveAs3` as a Boolean plus error/warning masks, with advanced
options from `GetAdvancedSaveAsOptions`. Its attempted current-version0,
silent1, normal-reference0, null-export-data shape is retained in the diagnostic
control, as are the original strict Boolean/error/partial-file regression tests.
Those checks were not removed to make preparation pass; the benchmark uses a
separately proven native path.

Relevant bundled references are `types/IModelDocExtension/SaveAs3.md`,
`GetAdvancedSaveAsOptions.md`, `types/ISheet/GetProperties2.md`,
`types/INote/GetText.md`, `PropertyLinkedText.md`, `GetExtent.md`, and
`examples/Get_All_Notes_in_Drawing_Template_Example_VB.md`. The checked-in 2026
pywin32 wrapper specifies both the three-argument model call and the seven-argument
extension call. Full styled-template inheritance and cross-arm equivalence remain
the benchmark's acceptance gates; the separate blank-template control only
establishes native save and sheet-property persistence for its tested shape.

## First native preparation observation

At benchmark revision `63b71c14`, the first arbor-pedestal invocation stopped
before DRWDOT save and before any recipe trial: the current setup's native unit
readback was `{system: 4, linear: 0, decimals: 2}`, not the benchmark's asserted
MMGS system 5. The bundled enum defines 4 as Custom and 5 as MMGS; this observation
alone does not identify which operation changed the system. The 5.396-second
failed preparation is not a successful preparation timing or an ABBA result.

The retained `template-abba-7aedax4n/measurements.json` and `ownership.json` prove
both source hashes unchanged and the initial visible channel-lever part plus
dirty unsaved Draw2 preserved; only the newly created blank drawing was closed.
`probe_drawing_unit_defaults.py` is the bounded follow-up: two fresh owned blank
drawings, tracing each of the existing three setter returns/readbacks and comparing
the unchanged adapter helper's result. It performs no save, rebuild or export.

The reviewed follow-up ran at `6b73314c` on the same SolidWorks PID37136. Its
`unit-defaults-61qf0gvd/units.json` records this exact sequence (all setters returned
True):

| Phase | Unit system | Linear unit | Decimals |
| --- | ---: | ---: | ---: |
| Fresh project-template drawing | IPS 3 | Inches 3 | 4 |
| Set unit system 263 to MMGS 5 | MMGS 5 | Millimetres 0 | 4 |
| Set linear units 47 to millimetres 0 | Custom 4 | Millimetres 0 | 4 |
| Set linear decimals 49 to 2 | Custom 4 | Millimetres 0 | 2 |
| Unchanged adapter helper on a second fresh drawing | Custom 4 | Millimetres 0 | 2 |

Thus the individual linear-unit setter caused the observed system transition,
including when length units were already millimetres. The benchmark now requires
the exact terminal Custom4/mm0/requested-precision state and still compares the
system value after template inheritance, reopen and across arms. It does not
accept arbitrary equivalent presets or change the production helper. The live
mechanism control used precision2; precision3 remains an offline-tested variant.
Both owned blank drawings closed, the original template SHA stayed unchanged,
and `ownership.json` again proves the visible part and dirty Draw2 were preserved.

## Modern SaveAs first observation

At revision `59fc13fb`, preparation passed the corrected unit, ten style-scope and
sheet-note checks, then stopped at the owned SaveAs path guard. Extension SaveAs3
returned `(True, 0, 0)`, but the drawing stayed unnamed and the requested DRWDOT
did not exist. The failed preparation cost 16.439 seconds; no trial ran and this
is not successful template timing. Evidence is retained in
`template-abba-qyq6fi4_/measurements.json`; original hashes and visible baseline
documents were preserved with no cleanup error.

`probe_drawing_template_save.py` compares the exact existing production
`IModelDoc2.SaveAs3(path,0,0)` call shape against this advanced silent SaveAs3
shape on fresh blank drawings, each targeting SLDDRW and DRWDOT. Production
SLDDRW is attempted first; if that positive call shape does not persist here,
the remaining cells are not attempted. The control records raw returns, exact
document/path/file witnesses, scoped ownership and save/reopen (or new document
from DRWDOT) sheet properties. It compares complete call shapes, including their
different option values, and therefore cannot isolate a method-only cause.
The legacy integer result is retained without inventing an undocumented meaning;
file plus exact native persistence must independently prove a successful cell.
No unsupported-template or incorrect-guard conclusion follows from the first
modern result.

The reviewed four-cell run at `282bb9e7` completed on PID37136. In
`template-save-74ytw6wb/save.json`, production ModelDoc2.SaveAs3 persisted a normal
drawing (88,700 bytes, 1.149 seconds) and DRWDOT (88,701 bytes, 0.643 seconds), with
exact updated native paths and unchanged sheet properties after reopen or
new-from-template instantiation. Both advanced-silent cells returned True/0/0
but produced no file and retained blank native paths (0.249/0.174 seconds); they
remain rejected, not successful fast saves. The result rules out a template-only
restriction under these tested shapes. Untried: modern options0 or other advanced
option configuration. It does not establish that the modern API never works.

All owned documents closed, the original template hash stayed unchanged, and
the visible baseline part plus dirty Draw2 were preserved with no cleanup error.
Using the proven legacy call changes only one-time preparation; both timed recipe
arms retain the production save/export implementation unchanged.

## Empty linked-note extent observation

At `396792e5`, the styled DRWDOT saved successfully, then preparation stopped
before any recipe at the full new-from-template comparison. Exactly ten notes
with empty resolved text and retained property-link expressions changed native
extents; some widths collapsed from tens of millimetres to zero. All units,
dimension style scopes, sheet properties/mode and nonempty measured notes matched.
This falsifies the blanket assumption that every empty linked-note extent is
stable across template instantiation. It is not a rounding/tolerance finding.
The failed 31.425-second preparation and full before/after data are in
`template-abba-vnh3intp/measurements.json`; original hashes and baseline documents
remained preserved.

The benchmark now has an explicit narrow classification, evaluated from fresh
native data rather than inferred from empty `INote.GetText`: an empty linked note
must expose zero counts in all ten IDisplayData primitive inventories, zero
ordinary and multi-jog leaders, one non-rich native font definition and a finite
native XYZ anchor. Otherwise the diagnostic refuses the classification. Native
line/frame/text/leader content cannot disappear behind this extent exclusion.
No note names, expected count of ten, geometric coordinates or tolerances select
the classification.

For notes satisfying that proof, raw extents and native names remain under
`blank_linked_extent_observations`; the semantic multiset retains exact link
expression, visibility, multiplicity, native counts, leaders, anchor, font and
document-format inheritance. Only that raw observation field is excluded from
defaults comparison. Empty unlinked notes and every nonempty/resolved note keep
their existing exact extent/content comparison. The next controlled native run
must prove or reject the new classification; the preceding observation did not
capture native primitive inventories and is not itself no-ink evidence.
# Exact interrupted-trial recovery

The `bc63e4d7` arbor trial (`template-abba-bn33bcg_`) passed template preparation
but the original part became dirty in memory during the unchanged recipe. The
ownership guard stopped before drawing save and refused its generic cleanup.
Both original disk hashes and the two pre-existing visible documents were
preserved. This is not an accepted performance result or a harmless dirty flag.

`recover_template_abba_scene.py` is the separately reviewed, one-off recovery for
that receipt and PID 37136. It captures the five named source parameters, native
tolerance/BASIC values, current configuration, cached properties and Draw16's
raw dimension/attachment observations, with individual read failures explicit.
It requires the exact four visible documents, native identities and source SHA
before closing only diagnostic-created Draw16 and diagnostic-opened arbor without
saving. It rechecks the disk SHA and original two-document baseline afterwards.
It never changes the shared ownership policy. It cannot be reused for another
scene. The reviewed native run at `aaf2d01b` exited zero: receipt
`scene-recovery-jzbwv6ny/recovery.json` records both no-save closes, the exact
original two-document baseline, and all three arbor SHA witnesses equal to
`dbb991437aea105ca5352b8b76468874077aeed0a74906413a1cc56fb7ca769e`.
Read-only capture returned all five named source dimensions, four source BASIC
designations, cached properties/current Default configuration, and 25 drawing
annotations including nine dimensions. No captured annotation was dangling;
unsupported sketch-entity attachments remain explicitly excluded, not proved.
These five parameters are a bounded forensic snapshot, not proof of complete
in-memory/disk equivalence or of which recipe operation dirtied the source.
Do not run the recovery again: its required four-document scene no longer exists.

The unchanged recipe's imported-dimension `SetText` and `SetPrecision3`, and
drawing-created dimension `SetArcEndCondition`/`SetToleranceType`, are concrete
mutating call sites to investigate. Imported BASIC validation itself is read-only.
The current before/after guard does not localize which operation dirtied the part;
no causal verdict or automatic benchmark retry follows from this observation.
