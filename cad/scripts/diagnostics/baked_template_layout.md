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

## Minimal populated control

`probe_populated_template.py` consumes an explicit DRWDOT path and exact hash.
It reuses the existing `probe_fresh_title_update.one_trial` lifecycle for one
Front view each of an owned rocker and lever bytecopy. Existing update variants
and their baseline reproduction gates remain unchanged. The populated control
uses the no-treatment variant and independently requires exact cold native,
linked-field PDF glyph and whole-page PNG equality; it does not claim a full
manufacturing recipe.

Normal `new_project_drawing` executes its existing note normalization, units,
dimension styles, scale and rebuild operations. One scoped adapter-factory
argument redirect selects the supplied DRWDOT and is restored on success or
exception; only one matching `NewDocument` call is permitted. There are **no
new title/layout setters**. This tests baked title formatting, not prepared
default setup performance. Setup time and its separate default witness time
are reported independently of the full diagnostic trial duration.

The read-only observer verifies TITLE against the copied part's saved Summary
Title, Number against its file-level Number property, and the preserved
two-term Revision expression against drawing-level plus part-level Revision.
Source configuration, native identity, selected source dimensions/tolerances,
original/copy hashes and true drawing-plus-part cold reopening remain guarded
by the existing trial. The first control targets the two exact recorded source
manifests; configuration-specific property overrides are not being generalized.

All linked fields and PART/DWG/REV/MATERIAL/FINISH labels are audited. Boxed
values use their measured physical cells. Labels have explicit semantic
associations with their value cells, so a MATERIAL label whose anchor is above
its divider cannot be silently assigned to FINISH. Copyright is explicitly a
footer strip between the measured outer sheet bottom and the DWG cell's lower
rule, across the measured outer frame; it is not called a closed cell or used
as a fallback for unknown notes. Its native and printed boxes must fit that
strip without intersecting native template line segments. This does not claim
a collision solver for arbitrary sketch curves or template SF glyphs; those
remain raw/native and full-page print witnesses, and broader fleet acceptance
remains subsequent work.

Every native/PDF containment failure, unresolved visible formula, unsupported
PDF text form, missing region and <1 mm pairwise field gap is retained as an
acceptance failure. Material/finish crowding is not waived. These fit issues
are collected across both targets to expose the full picture; ownership,
source or native-safety failures still stop immediately. Strict cold raw
font/link/layout/default and linked-field PDF-glyph changes also reject the
result. Failed output is retained, never reset or substituted.

After main-agent review and an explicit native seat grant:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '31860'
uv run --no-sync python cad/scripts/diagnostics/probe_populated_template.py `
  --template C:/src/harmonic-analyzer/cad/out/reports/baked-template-rotski52/baked-template-rotski52.DRWDOT `
  --template-sha256 1ad599b58fa54bef11a3dc1f5a70758c755bef271c05775f841221eaad0b976d `
  --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --symbol-library 'C:/ProgramData/SOLIDWORKS/SOLIDWORKS 2026/lang/english/gtol.sym'
```

The first run at root `65f21f18`, adapter `e77bfda4`, PID 31860, session 91024
finished with **failed fit acceptance**, not a persistence failure. Receipt
`populated-template-3kmuxyu1/populated-template.json` has SHA-256
`9c549d6e62a1078fec1772b5de808e338adcda97c8e5bd0e05dcd2d72d1d49c1`.
Rocker and lever trial timers were 106.7342 s and 104.0771 s; both had zero
cold native changes and zero changed full-page PNG pixels. Original parts,
owned source bytes, original/derived templates and helper/adapter guards passed.
These are diagnostic durations, not full recipe build or cleanup-inclusive
timings. The two targets each retained 16 issues (eight repeated built/cold):

- MATERIAL label extends 0.350423 mm above its physical cell; its native gap
  from the material value is 0.667419 mm.
- PART/TITLE native boxes overlap by 0.667419 mm. Printed glyphs have a
  positive 0.270499 mm gap, still below the required 1 mm (not literal ink overlap).
- FINISH/value gaps are 0.333710 mm native and 0.935761 mm printed.
- The angular tolerance is native `<GGTOL-ANGULAR>\r\n±1°`. Its symbol is PDF
  vector ink, so the literal text-only reader cannot validate it. This remains
  an explicit unsupported representation, not missing or zero ink.
- The defaults comparator incorrectly expected the blank property-source mode
  to survive finalization. `_drawing_common.finalize_drawing` explicitly calls
  `ISheet.SetProperties2(..., False)` then sets and validates `CustomPropertyView`.
  `GetProperties2[7]` documents that exact mode, and the retained title stages
  show `Default` changing to `Drawing View1` at the property-link boundary.

The corrected phase contract requires **exactly** inherited mode 1 before
population and explicit mode 0 after, with every other default unchanged.
It also checks the sheet's selected view name against the single actual model
view, exact referenced source identity and configuration. The raw arrays and
named transition stay in the receipt and built/cold equality remains exact.
Bundled references: `ISheet/GetProperties2.md`, `SetProperties2.md`,
`CustomPropertyView.md`, `IView/GetName2.md`, `ReferencedDocument.md`,
`ReferencedConfiguration.md`, and `Set_Drawing_Sheet_Properties_Example_CSharp.md`.
No production setter changed and none of the real fit defects is waived.

### Angular symbol decoding (COM-free positive replay)

The literal-reader failure is now handled by an explicit, single-token vector
witness, not Unicode substitution. The bundled **Gtol Frame XML Schema** guide
defines `<Library-Symbol>` notation and directs readers to the installed
`gtol.sym`. Its `GGTOL/ANGULAR` entry defines only `(0,0)→(1.6,1)` and
`(0,0)→(1.6,0)` lines. The explicit library file is hashed as a guarded input;
the observed installed SHA is
`e179ba2744a1f1725db179bbdea3a5d0fe97196eaed59d56e990068cfbbb8e40`.

Both retained PDFs contain exactly that two-line topology, represented by four
move/line commands, plus the separate literal `±1°` glyphs. The raw content
stream serializes endpoints `887.20001 154.70001`, `897.40002 161.10001`,
`887.20001 154.70001`, `897.40002 154.70001`. Their 0.1 pt grid plus
0.00005 pt decimal/float32 allowance explains the measured 0.039978 pt
aspect residual from ideal 1.6; this is a bounded **symbol-shape** contract,
not a general claim about SOLIDWORKS export precision. Unknown token, curve,
transform, missing/extra line, wrong topology, unsupported grid or stroke
style remains an error. Whole-frame path bounds are resolved into their
actual segments, so the sheet border is not mistaken for local symbol ink.

The actual PDF ink box includes the stroked path and literal glyph union;
the 1 mm clearance/cell-fit checks use those raw values. Cold path endpoints,
stroke/color and glyphs still compare exactly. This COM-free replay passed
for rocker and lever, built versus cold, without changing any native file:

```powershell
# Run in cad/scripts using the worktree's uv project/venv.
uv run --no-sync --project ../.. python -m diagnostics._populated_template_symbols `
  --receipt C:/src/harmonic-analyzer/cad/out/reports/populated-template-3kmuxyu1/populated-template.json `
  --sha256 9c549d6e62a1078fec1772b5de808e338adcda97c8e5bd0e05dcd2d72d1d49c1 `
  --symbol-library 'C:/ProgramData/SOLIDWORKS/SOLIDWORKS 2026/lang/english/gtol.sym'
```

Reader contracts are from installed pypdfium2 and the primary
[PDFium public path/object API](https://github.com/chromium/pdfium/blob/main/public/fpdf_edit.h):
`FPDFPath_CountSegments/GetPathSegment`, `FPDFPathSegment_GetPoint/GetType/GetClose`,
`FPDFPageObj_GetMatrix/GetBounds/GetStrokeWidth/GetStrokeColor`, and
`FPDFPath_GetDrawMode`. This does not make the failed populated layout pass;
MATERIAL, FINISH and PART/TITLE still require measured template corrections.

## Explicit blank variant: populated-gap layout

The original `--layout four-notes` control and its four-note allowlist tests
remain unchanged. `--layout populated-gaps` additionally consumes the exact
failed two-target receipt above. It verifies its SHA, original template hash,
complete rocker/lever inventory, unchanged protected/source-copy bytes and
exact cold raw/image witnesses before creating a drawing. The recipe still
authors a bare, model-free copy of the original DRWDOT. No measurement or
layout setter is added to production finalization.

This variant changes seven notes total: the original TITLE/DWG/REV value and
REV label set, plus MATERIAL label/value and FINISH value. It retains every
font size other than the already approved 3.5 mm DWG/REV values. PART and FINISH
labels remain unchanged. The additional moves come from matching semantic
links, exact font/anchor/style witnesses and actual measured rules/content:

- TITLE moves down 2.167419 mm from the prior left-title target, giving 1.5 mm
  predicted native clearance below PART. Its font stays 5.291667 mm.
- FINISH moves down 1.166290 mm below its existing label. The lever's two-line
  value uses 72.415 mm of a 75.586 mm cell, so a side-by-side treatment would
  fail. The predicted bottom margin is 0.852681 mm; cell containment remains
  strict and the label gap is 1.5 mm.
- MATERIAL uses the cell width: left-align its static label at a half-label-
  height inset, center label and value extents vertically, and place the value
  1.5 mm to the label's right. The shallow cell is 6.498703 mm high; a vertical
  stack with the required 1 mm gap would leave only 0.159350 mm total vertical
  margin. The lever's 49.055311 mm value fits the horizontal plan without
  shrinking its 2.38125 mm font or the label's 1.524 mm font.

These numbers are output observations, not hardcoded placement offsets. The
plan recomputes them from the pinned receipt and current native blank cell
geometry. Its 0.5 mm planning headroom never relaxes the final 1 mm native/PDF
clearance requirement. Both sources' predicted extents must fit their cells
before any setter. A changed template, label/link/style, native anchor, cell
rule or nonfitting source footprint rejects the plan.

Blank acceptance now includes the five actual static labels REV, DWG, PART,
MATERIAL and FINISH in their semantic cells, plus exact approved-transition,
native save/re-instantiation, PDF glyph and full-page PNG persistence. Visible
unresolved formulas are still retained, not treated as resolved field widths
or zero ink. The report explicitly requires fresh populated confirmation;
the copyright footer and all linked-field collisions remain in that phase's
acceptance. Predicted fit is not native or printed proof.

After source review and an explicit native seat grant, the bounded next
blank-only invocation is:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '31860'
uv run --no-sync python cad/scripts/diagnostics/probe_baked_template_layout.py `
  --layout populated-gaps `
  --populated-receipt C:/src/harmonic-analyzer/cad/out/reports/populated-template-3kmuxyu1/populated-template.json `
  --populated-sha256 9c549d6e62a1078fec1772b5de808e338adcda97c8e5bd0e05dcd2d72d1d49c1
```

The new DRWDOT remains an owned diagnostic output. Only a subsequent explicit
populated rocker/lever control can validate inherited values/native/PDF fit
and cold stability; full recipes and fleet fit still follow before rollout.

This seven-note blank variant **passed** at frozen root `5e486cfe`, adapter
`e77bfda4`, existing SW PID 31860. Receipt
`baked-template-d54wy3lp/template-layout.json` has SHA-256
`806cfe2fe54ea76db62aee24962cc0d9f419e3e97723ed9f378c3daf2cf74741`.
The 136.383 s diagnostic timer excludes parent seat-lock wait, attach and the
outer ownership cleanup. Exact authored/saved/re-instantiated native state and
PDF glyphs agreed; the 5100×3300 PNG comparison had zero changed pixels.
The original template and pinned populated-input receipt hashes stayed exact;
the retained error list is empty.

Its fresh derived DRWDOT has SHA-256
`2b1bbe3dfff265e8bb35ea79f0f9690f808049f5cef764cab8959c1eaee5e849`.
It remains a diagnostic output, not the project template. This receipt proves
blank inheritance and print persistence only; resolved-field fit, full recipes
and fleet acceptance are separate controls.
