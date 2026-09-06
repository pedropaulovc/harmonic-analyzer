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
directory. This captures the existing metric edge-break note, MMGS/mm precision,
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

## Evidence and timing boundaries

`measurements.json` is checkpointed before each preparation/trial and after each
outcome/cleanup. Each trial retains source and recipe hashes, artifacts, fresh
saved/reopened witnesses and status/errors. `ownership.json` independently
retains initial/final native inventories, source hashes and cleanup failures.
Source/template hashes are pinned once for the entire block and checked between
trials and in the final failure path. Runtime fingerprints cover the helpers,
configuration, adapter, template resources and every diagnostic Python module.

Timing fields are intentionally separate:

- `template_preparations[].seconds`: one-time setup, DRWDOT save, inherited-default
  verification and its scoped cleanup. Do not exclude this cost when estimating
  first-use performance.
- `trials[].setup_seconds`: the inner setup helper only. Ownership inventory
  guards sit outside this timer.
- `trials[].recipe_seconds`: complete recipe body, including its ownership guards,
  current final validation, native save and PDF/PNG export.
- `trials[].validation_seconds`: additional diagnostic saved/reopened comparison,
  outside the recipe timer. Per-trial final cleanup is also outside that timer.

Saved/reopened comparisons preserve each drawing's native annotation inventory,
attachment geometry, dimension values/tolerances, layout and measured content.
Cross-arm comparisons use a multiplicity-preserving semantic inventory rather
than regenerated DetailItem labels. Datum-to-dimension label removal requires an
independent exact target-dimension witness. Raw observations remain in the
report. Sheet note text/link text/extents/format and every view's display-quality
readbacks are included, even for views with no annotations. Unsupported geometry
exclusions stay explicit; the diagnostic does not claim to prove excluded
attachments. Native extents are not assumed to translate rigidly or be harmless
quantization: a differing final witness fails for investigation.

One ABBA block supports only its observed paired timing differences. It does not
establish a fleet speedup, a conflict probability below 5%, or visual equivalence
of every export. The retained PDFs/PNGs still need a human eye pass.

## Native API provenance and untested boundary

The bundled SolidWorks 2026 reference documents `IModelDocExtension.SaveAs3` as a
Boolean result plus error/warning output masks, and requires advanced options
from `GetAdvancedSaveAsOptions` before the call. The prepared-template save uses
current version 0, silent 1, normal-reference options 0, null export data, and
clears selection first. It requires `True`, zero errors and a fresh nonempty file;
warnings remain recorded. A failed save with a partial file is rejected. The
older `IModelDoc2.SaveAs3` integer result has no defined meaning in the bundled
method page, so this diagnostic does not invent one.

Relevant bundled references are `types/IModelDocExtension/SaveAs3.md`,
`GetAdvancedSaveAsOptions.md`, `types/ISheet/GetProperties2.md`,
`types/INote/GetText.md`, `PropertyLinkedText.md`, `GetExtent.md`, and
`examples/Get_All_Notes_in_Drawing_Template_Example_VB.md`. The checked-in 2026
pywin32 wrapper specifies the exact seven-argument SaveAs3 call and three-value
return. Offline tests prove that shape's acceptance/rejection logic, not native
DRWDOT persistence or cross-arm equivalence. Those remain the first live control's
explicit acceptance gates; no production path is changed before that evidence.

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
Its native run needs its own source review and exclusive seat grant. Do not
weaken the benchmark's unit assertion based only on the first observation.
