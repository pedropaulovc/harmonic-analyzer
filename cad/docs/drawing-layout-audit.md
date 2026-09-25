# Drawing layout audit

> Design and contract for the unified layout audit that every manufacturing
> drawing runs from `finalize_drawing`. It enforces the machine-checkable part
> of [drawing-simplicity-policy.md](drawing-simplicity-policy.md) rule 8. Code:
> `cad/scripts/_layout_audit.py` (SolidWorks-free),
> `cad/scripts/_drawing_layout_audit.py` (live collection),
> `cad/scripts/_pdf_ink.py` (the exported PDF's text and strokes) and
> `cad/scripts/diagnostics/layout_calibration.py` (calibration).

## Why

Until 2026-09-25 no layout audit ran on most sheets, and the three partial
audits that existed missed real collisions:

| audit | ran on | blind to |
|---|---|---|
| `_drawing_layout_check` (element boxes) | 6 drawings that called it explicitly | any dimension text (a ±4 mm nominal square, never overlap-tested); text vs geometry |
| `_layout_geometry` + `diagnostics/drawing_layout_audit` | 3 drawings | touching text (0.3 mm penetration test); widths counted `<MOD-DIAM>` as ten glyphs; text vs geometry |
| `draw_harmonic_base` locals | harmonic base sheet 2 | everything off that sheet |

The element audit's 8 mm `NONE`-scope square for every dimension and hole
callout is gone: `collect_layout_elements` now gives dimensions no box, only
their leaders, and this audit boxes their text from display data.

`check_drawing_layout` left `finalize_drawing` in ab28f4e49 (2026-07-24); a
post-build gate (46e2f8550) was reverted the same day it landed (8cc8040e6).
The eye pass then found, on MHA-092: "20.8"/"8.42" printed as "20.88.42";
"Ø3.26 ⊽ 6.9" over "6.0"; the ADJUSTER ENTRY callout crossed by the right
view's edge. On MHA-035 sheet 2 it found the datum-origin X axis through the
MHA-114 callout, and the MHA-004 leader through "TOP VIEW SCALE 1:4".

## Where it runs

`finalize_drawing` calls `run_layout_audit` after the PDF and PNG exports, with
the finished document still open, so the audit sees exactly what printed (the
redundant-note cleanup has already run). It walks every sheet through
`IDrawingDoc::GetViews` without activating any. Each sheet is dumped to plain
JSON, together with its page of the exported PDF, and audited by
`_layout_audit.audit_dump`. The offline tests and the
calibration tool replay the same dumps through the same function.

Every sheet dump (its page's text objects, and only a count of its strokes:
the PDF is itself a cached drawing output, and a replay re-reads it), every
finding and the per-class counts are written to the drawing's report, `cad/out/reports/layout-audit/<artifact-stem>.json`. The
report is a declared target of the `drawing:<stem>` task and one of the
outputs the remote cache stores and restores, so a leaf restored from cache
carries the same report as the seat that built it, and the fleet report
covers hits as well as misses. It is not a release output.

Telemetry: one `layout.audit <stem>` span per drawing, with `sheets`,
`gating`, `collect_s`, `read_errors` and one `findings.<kind>` count per
class as attributes (each dump also names the COM accessor behind every
refused read); each finding is a debug log line. A collector or audit fault
fails the drawing in every mode, because a silently skipped sheet would
under-count the fleet report: the dumped sheets must be exactly
`GetSheetNames`, one PDF page each.

## What it checks

**The PDF says where; COM says what.** Each `IDisplayData` text item is
matched to the PDF text object that printed it: same string (symbol tokens
and blanks stripped), its reference point (`GetTextRefPositionAtIndex`:
lower-left, centre, ...) within 3 mm plus one text height of the same point
of the printed box, closest pairs first, one object per item
(`match_ink_indices`). A run with a symbol inside it matches the text objects
either side of the symbol's path. A row's box is the union of its items'
glyph boxes. A symbol token (`<MOD-DIAM>`, `<HOLE-DEPTH>`) prints as a path,
not text, so it is boxed from its COM position and shifted by the offset its
printed neighbours show. Section and detail-circle labels are matched the
same way. The match runs both ways, and both gate: a COM string with no
printed match is `text-unmatched`, and printed text no COM item claims
(outside the title block, the border band and tables) is
`pdf-text-unclaimed`, which is what a refused COM read looks like on paper.

The page must hold the sheet, or the audit stops rather than fall back to
COM boxes: the page size must equal `GetProperties2`'s (0.5 mm), COM text on
a page with no PDF text fails, and so does a sheet where fewer than half of
at least five COM strings find their printed text (origin, scale or page
mapping wrong). A path inside a PDF form XObject fails too (its matrix is
not composed; SolidWorks writes none). A refused COM read is counted per
sheet and per accessor (an overload that answers after another refused is
not a refusal) and is a gating `com-read-errors` finding.

Model edges are the page's 0.25 mm solid black strokes (curves tessellated,
not their Bezier control polygons), each assigned to the smallest view
outline holding it. Annotation lines, arrows and leaders come
from COM display data. `GetArrowHeadAtIndex2`'s direction points from the tip
back toward the arrowhead's base (125 of 125 unambiguous arrowheads on the
calibration PDFs). `GetArcAtIndex2`'s `rotationDir` is CCW when non-zero
(the docs' true) and CW at 0; no open arc appeared in the calibration dumps,
so this rests on the docs. A section's cutting line is drawn between its two
arrow tails: `IDrSection::GetLineInfo` answers in the view's model space.
A dimension's straight lines split into `dim-line` (parallel to an arrow and
through its tip, including the run out to parked text) and `ext-line`
(every other line). `IDisplayDimension::GetDisplayData` is not read: it
equalled `IAnnotation::GetDisplayData` for all 72 dimensions on the
calibration leaves.

`find_text_on_line` buckets every segment in a 5 mm grid, so each text box
is tested against nearby ink only. On a synthetic assembly sheet (67 k
strokes, 350 text runs) the whole audit takes 0.42 s, down from 8.6 s; the
largest calibration sheet (pen-assembly, 8.4 k strokes) takes 45 ms. The
drawing's `layout.audit` span has three children: `layout.read_pdf`,
`layout.collect_com` and `layout.findings` (`findings_s` and the per-kind
counts).

A balloon keeps its rendered circle. The COM row model (exact item widths,
per-sheet glyph advance, supports' shoulder-centred callout rows) remains
only for a dump with no PDF text, i.e. the offline fixtures.

| finding | severity | what |
|---|---|---|
| `text-clearance` | gating | text of two distinct annotations closer than 0.5 × text height, or overlapping |
| `text-on-line` | gating | a foreign line runs through text; covers annotation lines, printed model edges, datum-origin, section-line and detail-circle ink |
| `text-on-view` | gating | text printed inside a view its annotation does not belong to: within the extent of that view's printed edges (`GetOutline` pads the part by a few mm, so it is used, inset, only when no edges printed; pictorial views skipped); from swing's MHA-092 gap diff |
| `leader-through-text` / `leader-through-own-text` | gating | a leader runs through foreign text, or through its own rows (0.2 mm inset, shoulder excluded) |
| `leader-crosses-line` / `shoulder-crosses-line` | gating | a leader, or a callout's shoulder under its text, crosses another annotation's dimension or extension line (Main's ruling a) or frame line transversally (MHA-092's heel-height line through the ADJUSTER shoulder). Not a detail circle (a leader to a feature inside it must cross it), and not on the stretch a leader runs past its arrow tip into the hole, where the hole's own centre and extension lines pass |
| `leader-converges-at-landing` | advisory | a leader crossing within 5 mm of both its own landing and the crossed line's end: two leaders closing on one corner (Main's ruling on cone-gear-shaft's Ra 1.6) |
| `leader-crosses-section-line` | gating | a leader crossing a section cutting line (Main's ruling: the MHA-025 finish leader was moved off its A-A line for this) |
| `line-on-dimension-line` | gating | a leader, or a section line's arrow, lying along another annotation's dimension line within 0.1 mm: the two print as one stroke. Shared extension lines are normal drafting and exempt |
| `dim-line-crosses-extension-at-text` / `dim-line-crosses-extension` | gating / advisory | a dimension line crossing another dimension's extension line. ASME allows it when unavoidable, so it gates only within 0.5 × text height of either dimension's text (Main's ruling b) |
| `leader-crosses-view` / `leader-crosses-leader` | gating | as in `_drawing_layout_check` |
| `outside-border` / `keep-out` | gating | past the zone frame, or inside the title block |
| `merged-blocks` | gating | two callouts (hole callouts or leadered notes) stacked in one column, x spans overlapping, less than a row pitch (1.59 h, 5.556 mm at 3.5 mm text) apart; supports' `find_merged_blocks` |
| `tall-block` | gating | a callout (hole callout or leadered note) over four rows (Main's hb-render-4 ruling); supports' `find_tall_callouts`. A free general note is a text block by design |
| `text-unmatched` | gating | a COM text item with no printed PDF text object: the audit cannot place it |
| `pdf-text-unclaimed` | gating | printed text in the drawable region no COM item claims (not the title block or a table) |
| `view-edges-missing` / `-pictorial` | gating / advisory | a view with an outline but no printed model edge (a shaded or draft view, another edge weight): text over it is unchecked |
| `com-read-errors` | gating | the collector was refused a COM read on the sheet; the counts per accessor are in the finding |
| `text-separation` | advisory | distinct annotation blocks clear of each other but closer than one text height; they read as one callout |

Each kind is reported once per annotation pair: a two-row callout crossed by
one line is one defect.

### Thresholds and where they come from

* **Clearance 0.5 h.** Measured on MHA-092's own PDF with pdfium's tight
  glyph boxes at 3.5 mm text. The word space in "SLOT DEPTH" is 1.77 mm
  (0.51 h). "20.8" and "8.42", which print as one string, are 0.64 mm apart.
* **Separation 1.0 h, advisory.** On hb-render-4 the cross-tap callout sits
  1.75 mm under the spring callout's underline, tighter than the 2.06 mm row
  gap inside a single callout. The fleet report's distribution sets the final
  value.
* **Row pitch 1.59 h and four rows**, both from Main's hb-render-4 eye pass:
  the spring block 1.7 mm over the cross-tap block read as its fourth row,
  and the cross-tap ran six rows. Ported from supports' drawing-local rules
  at 375bf2aad. Text height is the display items' height, never an exact
  multi-row extent or a balloon circle.
* **Line through text 0.15 mm** and **own-row inset 0.2 mm** are inherited
  from `_layout_geometry` and supports' calibration.

All of these are provisional until the calibration run below confirms them.

## Calibration

The exported PDF is the truth: SolidWorks writes each text item as its own
PDF text object with exact glyph boxes, and each line as a stroked path.
Model edges are 0.25 mm black, annotation ink 0.18 mm black (hidden and
centre lines dashed), section lines 0.35 mm, and the template grey.

The calibration run (d09c2b9eb, 6 drawings on integ 06b840e49) decided the
design:

* 208 of 208 COM text items (dimensions, notes, surface finish, GD&T,
  datum) matched a PDF text object 1:1. COM's row boxes did not: a
  dimension's right edge ran a median 2.5 mm and a 95th percentile 21 mm
  past its ink, and every COM baseline sits about 0.9 mm below the glyphs.
  So the audit measures text on the PDF.
* `GetPolylines7` left 8 of 26 views unplaceable. Where
  `ModelToViewTransform` placed a view, its edges covered 0 to 59 % of the
  printed model strokes, and the model-vertex round trip missed by 86 to
  460 mm. Every 0.25 mm stroke fell inside exactly one view outline. So the
  audit takes model edges from the PDF, and neither API is read.

`diagnostics/layout_calibration.py --pdf-dir` replays layout reports and prints, per
annotation kind, the match rate and the COM-vs-ink offsets, per view the
model edges it owns, and the findings per kind.

Positive controls: the MHA-092 and MHA-035 collisions above must fail. The
hb-render-2/-4 replays are in `test_layout_audit.py`. MHA-092 and the
datum-origin case replay from the calibration run's dumps.

## Rollout

1. **REPORT** (`LAYOUT_AUDIT_MODE`): writes the report and never fails a leaf
   on a finding (a fault still fails it).
   One fleet farm run produces each drawing's finding list for its owner.
2. **GATE**: one commit, landed before the release cut. It flips the mode and
   removes the superseded audits: the 6 explicit `check_drawing_layout`
   calls, the 3 `audit_sheet` calls, `diagnostics/drawing_layout_audit`'s own
   collector, and `draw_harmonic_base`'s local checks. An allow-list entry
   needs a cited ruling.

Not checked:

* text inside a part silhouette without crossing a line (rule 8's
  default-exterior preference). An advisory class needs the view's OUTER
  silhouette loop. Ray-crossing parity against every visible edge is the
  cheap test, but it is wrong wherever a view draws interior step or tangent
  edges, which most HLR views do. Outer-loop extraction from the printed
  edges has not been tried, so this class is untested;
* crosshatch: it prints 0.18 mm like annotation ink and no COM record
  claims it, so text over hatching is not seen;
* lines lying on each other other than a leader or section arrow along a
  dimension line (for example an extension line on a section cutting line).
  Shared extension lines are normal drafting, so a general rule would flood.
