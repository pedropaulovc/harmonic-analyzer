# Copied project-template title layout

This is a blank-only diagnostic, not a production template replacement. It
authors a fresh owned DRWDOT from the unmodified project template using bare
`new_drawing`; it does not normalize units, notes, styles, sheet scale or view
quality. No model document is opened. The following are intentional template
design changes, not compensating offsets or inferred geometry identities:

| Note | Allowed change |
| --- | --- |
| TITLE `$PRPSHEET:"SW-Title(Title)"` | Left justification; cell-left plus half its existing native font height; original Y/font retained. |
| Static REV label | Left justification; revision-cell-left plus half its native font height; original Y/font retained. |
| DWG value `$PRPSHEET:"Number"` | Left justification at the unchanged static DWG label's X, original Y, explicit 3.5 mm font height. |
| REV value `$PRP:"Revision"$PRPSHEET:"Revision"` | Left justification under the relocated REV label, original Y, explicit 3.5 mm font height. |

Cells come from native sheet-format line endpoints. The revision cell is
identified using the original **revision value** anchor, not its misplaced
static label. All links, text, vertical justification, lock state, other font
fields, other notes, raw SF data, dimension-style preferences and sheet
properties remain exact. The transition allowlist permits only these planned
anchors/justifications/heights and their resulting glyph origins/extents.
Neither source dimensions nor part geometry enter this authoring operation.

The **blank** authoring-fit gate covers the changed static REV label and the
unchanged neighboring DWG label in their actual measured cells. Their native
extents and PDF glyph boxes must retain at least **1 mm** pairwise clearance,
an explicit diagnostic layout criterion, not a numeric tolerance. The generic
populated `validation_plan` and `require_field_fit` guards remain strict and
unchanged; the blank phase now has a separate, explicit static-label plan.

All model-linked values, the copyright footer, and material/finish crowding
remain **unaccepted**, not silently passed. The blank has no source model and
actually displays nonempty `$PRPSHEET:{...}` formula tokens. Their full native
ink, extents, text, links and font definitions remain exact persistence
witnesses; their widths do not establish the eventual widths of resolved
values. The receipt lists every linked field with raw text/counts/extents and
`fit_status: deferred`. Missing static labels or unexpected dynamic content in
those label roles still fail. All other notes are preserved by raw snapshot
and full-page print comparison. Only independently proven zero-ink notes have
observational empty extents, following the separately reproduced template-save
behavior. Nonempty formula extents are never put in that exclusion.

The copied template is saved through the already-positive native
`IModelDoc2.SaveAs3(path,0,0)` shape, with raw integer return retained, fresh
nonempty file and exact native path/handle readback. After closing the exact
owned document, its bytes/file identity become a frozen input. A second bare
drawing must inherit the saved layout **without any setters**. Raw snapshots
are compared without rounding, and full-page PDF glyph positions plus all
300-DPI PNG pixels must agree with the authored blank. Each PDF export is also
surrounded by an exact native snapshot check. This is printed-output evidence,
not raw vector-command equality; non-line sketch entities are inventoried but
are not interpreted as rectangular cell rules.

PDFium reports bottom-left glyph boxes. Its search represents the native
`DWG.  NO.` two-space label as `DWG. NO.` in the retained positive PDF; only
ASCII-space repetition is normalized when checking the search result text.
Both raw strings are retained. Native note text and cross-export PDF glyph
inventories still compare exactly. Characters, case and link syntax are never
rewritten.

## Native evidence motivating the experiment

The successful TITLE-only control at root `920d4fc6` is retained in
`cad/out/reports/fresh-title-8nzblgc3/title-update.json`, SHA-256
`e7aa1b8324439f10c98f762c2637c57abc3e6274d491364a9cab6d319de06840`.
It had zero cold native leaf changes, unchanged PDF glyph boxes and zero
changed PNG pixels. The original part/template and owned-session guards passed.

That result does **not** establish that centered TITLE notes must fail. The
full rocker prepared-factory pilot at `b67a12c6`,
`cad/out/reports/datum-policy-8idxoxuz/pilot.json` (SHA-256
`962f8b832d55f6a8e245961f7a941ab8bdb143fe2d092855ddcab2a99473c99b`),
passed its cold-native title gate with no title setters and centered TITLE.
That pilot did not compare cold PDF/PNG output. A saved prepared blank is a
second observed route to native stability; the proposed layout also addresses
title-block readability.

Native line evidence from the TITLE-positive receipt places the DWG/REV divider
at X=378.0279631492408 mm. The REV label anchor was at 376.20152928405176 mm,
outside its intended cell. The revision value's PDF glyph left edge was
372.5946990966797 mm, crossing that divider by 5.4332640525611 mm. On the rocker
PDF the DWG/REV glyph unions remained 1.60067749 mm apart, while their native
note extents overlapped 0.33370960 mm. On the retained lever PDF
`dimension-arrange-ua1q54y6/after.pdf`, the glyph-union gap was only
0.34227024 mm. These are crowding/cell-containment defects, not claims of
literal overlapping ink. The earlier visual impression that DWG and REV shared
one cell was disproved by the measured divider and is not used by the code.

## Invocation and remaining gates

Only after the main agent reviews the frozen commit and grants the machine
seat, using the already-running authorized PID:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '31860'
uv run --no-sync python cad/scripts/diagnostics/probe_baked_template_layout.py
```

The parent runner acquires the global COM lock; the worker attaches only to the
specified PID. Initial visible documents, including dirty unsaved drawings,
remain protected. Only the two exact newly created drawings are closed without
saving any user document. Original-template, helper and imported-adapter hashes,
native observations, outputs and combined primary/cleanup errors are retained
under a fresh `baked-template-*` report directory. Failure never publishes over
the original template, retries, resets or relaxes a comparison.

The first native run at `36476676` stopped before PDF/save after the four
intended mutations passed their exact transition check. Receipt
`baked-template-pw1wlxw9/template-layout.json`, SHA-256
`557b00d6b0f0dce1d0663c11f7ad1cdbe9a702b9fc15cf6de13fb6148e0b494d`,
proves why the original blank-fit premise was too strong:

- Copyright note `DetailItem320` occupies an open footer strip. Its candidate
  left divider stops at Y=13.396414 mm above the Y=12.7 mm bottom border,
  leaving a 0.696414 mm opening; there is no closed rectangular cell.
- TITLE/Number/Revision visibly print unresolved formula tokens. Their native
  extents overflow intended cells by 2.858 mm downward, 9.438 mm right and
  26.804 mm right respectively. These are real captured blank ink, not empty
  notes or a claim about populated manufacturing values.
- The unchanged MATERIAL label straddles a divider. Existing Material/label
  and Finish/label native gaps are only 0.704 mm and 0.352 mm. Neither is fixed
  or accepted by narrowing the blank phase to its two static audited labels.

The original template SHA remained
`cbad80d25315dddc9bb5fefd690915c6f18fa7d181ac8c30d2f1408a980b55cc`;
baseline/final native inventories were empty with no cleanup error. No DRWDOT
or printed artifact was saved by that failed run. The retained native-token
fixture is a Python diagnostic source, so the existing `diagnostics/*.py`
source-scan enrollment invalidates the recipe gate on its edits. A regression
asserts its presence in the actual gate inputs; no `dodo.py` edit was needed.
It proves the original generic
guards still reject those shapes and the blank plan selects only the two
actual static labels, while retaining nonzero formula ink in its phase report.

The corrected blank phase **passed** on frozen root `4b58d536` using adapter
`e77bfda4`, existing SW PID 31860, session 20008. Receipt
`baked-template-rotski52/template-layout.json` has SHA-256
`16592ba587355eaf431656e44b7cc99c78b79bc26530d56aaa0541c22f042d49`.
The 96.601 s probe timer included authoring, native snapshots, save, PDF/PNG
and its inner owned-document cleanup. It excludes parent seat-lock wait,
attach and the outer `run_copy_diagnostic` cleanup; it is not a per-drawing
setup latency measurement. Raw
saved/re-instantiated snapshots and PDF glyphs agreed, with zero changed pixels
and zero maximum channel delta in the 5100×3300 full-page images. The original
template hash stayed exact, ownership was empty→empty/preserved, and both
primary/cleanup error lists were empty.

The new owned `baked-template-rotski52.DRWDOT` is retained beside that receipt,
SHA-256 `1ad599b58fa54bef11a3dc1f5a70758c755bef271c05775f841221eaad0b976d`.
It has not replaced the project template. This blank success cannot prove the
widths of unresolved TITLE/DWG/REV/material values.
Next gates are setter-free normal-setup populated rocker and lever controls,
full recipes with cold native/PDF/PNG comparison, and long-title/field fleet
fit. The open footer and material/finish defects must get explicit semantic
region/layout policies and remain part of that acceptance, not bypasses.
Only after those and review may the copied DRWDOT replace the project
template. Its changed source bytes naturally invalidate prepared-template and
drawing recipe keys; no per-recipe segment scan or layout setter is proposed.
