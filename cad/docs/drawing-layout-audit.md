# Drawing layout audit

> Design and contract for the unified layout audit that every manufacturing
> drawing runs from `finalize_drawing`. It enforces the machine-checkable part
> of [drawing-simplicity-policy.md](drawing-simplicity-policy.md) rule 8. Code:
> `cad/scripts/_layout_audit.py` (SolidWorks-free),
> `cad/scripts/_drawing_layout_audit.py` (live collection),
> `cad/scripts/_pdf_ink.py` and `cad/scripts/diagnostics/layout_calibration.py`
> (calibration against the exported PDF).

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
JSON and audited by `_layout_audit.audit_dump`. The offline tests and the
calibration tool replay the same dumps through the same function.

Every sheet dump, every finding and the per-class counts are written to the
drawing's report, `cad/out/reports/layout-audit/<artifact-stem>.json`. The
report is a declared target of the `drawing:<stem>` task and one of the
outputs the remote cache stores and restores, so a leaf restored from cache
carries the same report as the seat that built it, and the fleet report
covers hits as well as misses. It is not a release output.

Telemetry: one `layout.audit <stem>` span per drawing, with `sheets`,
`gating`, `collect_s` and one `findings.<kind>` count per class as
attributes; each finding is a debug log line. A collector or audit fault
fails the drawing in every mode, because a silently skipped sheet would
under-count the fleet report.

## What it checks

Text boxes are built from `IDisplayData` text items. A position is the run's
LOWER-LEFT corner in sheet space. Inside a row, the gap between two
consecutive items is the first item's exact width. The last item on a row
uses a per-sheet glyph advance measured from those exact widths. A callout
with a horizontal shoulder uses supports' rule: rows are centred on the
shoulder, which spans the widest row. A free note keeps `INote::GetExtent`,
and a balloon keeps its rendered circle.

| finding | severity | what |
|---|---|---|
| `text-clearance` | gating | text of two distinct annotations closer than 0.5 × text height, or overlapping |
| `text-on-line` | gating | a foreign line runs through text; covers annotation lines and visible model edges (`IView::GetPolylines7`), datum-origin, section-line and detail-circle ink |
| `text-on-view` | gating | text printed inside a view its annotation does not belong to, between that view's edges (the view's `GetOutline`, inset as for leaders; pictorial views skipped); from swing's MHA-092 gap diff |
| `leader-through-text` / `leader-through-own-text` | gating | a leader runs through foreign text, or through its own rows (0.2 mm inset, shoulder excluded) |
| `leader-crosses-line` / `shoulder-crosses-line` | gating | a leader, or a callout's shoulder under its text, crosses another annotation's dimension, witness or frame line transversally (MHA-092's heel-height line through the ADJUSTER shoulder) |
| `leader-crosses-view` / `leader-crosses-leader` | gating | as in `_drawing_layout_check` |
| `outside-border` / `keep-out` | gating | past the zone frame, or inside the title block |
| `merged-blocks` | gating | two callouts (hole callouts or leadered notes) stacked in one column, x spans overlapping, less than a row pitch (1.59 h, 5.556 mm at 3.5 mm text) apart; supports' `find_merged_blocks` |
| `tall-block` | gating | a note or hole callout over four rows (Main's hb-render-4 ruling); supports' `find_tall_callouts` |
| `view-geometry-unresolved` | gating | a view's model edges could not be placed on the sheet, so its text-vs-geometry check would be blind |
| `text-separation` | advisory | distinct annotation blocks clear of each other but closer than one text height; they read as one callout |

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
On MHA-092 the model edges are 0.25 mm black, annotation ink is 0.18 mm black,
section lines are 0.35 mm, and the template is grey.
`diagnostics/layout_calibration.py` replays each leaf's dump against its
PDF and reports:

1. the 1:1 match rate between COM text items and PDF text objects, per
   annotation kind, and the edge errors between COM boxes and ink;
2. per view, the coordinate space of `GetPolylines7`, the model-vertex round
   trip through `ModelToViewTransform`, and how much of the COM geometry lies
   on a model-weight PDF stroke;
3. the findings per kind.

If COM boxes match the PDF closely, they remain the audit's boxes. If not,
the audit switches to PDF glyph boxes with COM attribution, running next to
the export it already follows. The data decides.

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

Not checked: text inside a part silhouette without crossing a line (rule 8's
default-exterior preference). An advisory class needs the view's OUTER
silhouette loop. Ray-crossing parity against every visible edge is the cheap
test, but it is wrong wherever a view draws interior step or tangent edges,
which most HLR views do. Extracting outer loops from `GetPolylines7` has not
been tried, so this class is untested.
