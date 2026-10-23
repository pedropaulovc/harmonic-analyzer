# SolidWorks drawing layout tuning

> Dated incidents and calibration examples retain their recorded identifiers and paths. Current identities are listed in [subsystem identities](subsystem-identities.md).

Source of truth for the managed skill `solidworks-drawing-layout-tuning`. Keep
this file and the skill in sync; the skill is minted from this body.

## When to use

Use when you are authoring or repairing a `cad/scripts/draw_*.py` recipe and the
problem is WHERE things sit: a dimension printing on a line, two callouts on top
of each other, a leader across a neighbouring view, text in the title block, or
one section's callouts crowding the next. Also use when a SolidWorks API refuses
a placement operation (`OffsetText` on a diametric dimension, HLR on a detail
view, moving a section view to another sheet).

Do not use for what the drawing SAYS — dimension selection, tolerancing,
callout wording, view choice. That is `cad/docs/drawing-guidelines.md`.

## The loop

Never render to find out where things are. Render to confirm what you already
measured.

1. **Author** the views and annotations as usual.
2. **Audit the live document** before export:

   ```python
   from diagnostics.drawing_layout_audit import audit_document
   from _layout_geometry import format_findings

   findings = audit_document(adapter)
   if findings:
       raise RuntimeError("layout:\n" + format_findings(findings))
   ```

   Ten seconds, on the open document, in sheet millimetres. The 5-13 minute
   PDF/PNG export is not a layout tool.
3. **Fix by coordinates.** Every finding carries the offending boxes in sheet mm
   and a `try SetPosition2(x, y, 0.0)` starting point. Convert mm to metres
   (`/1000`) and set the position; re-audit. Do not nudge by trial.
4. **Export once**, at the end, and eyeball the render for what geometry cannot
   judge (balance, emphasis, readability).

Standalone, on a built drawing, without touching a recipe:

```bash
uv run cad/scripts/diagnostics/drawing_layout_audit.py \
  cad/out/slddrw/<part>.SLDDRW [--json dump.json] [--sheet N] [--quiet]
```

It holds the machine-global COM seat lock (`dodo._com_seat`) for the whole
open-audit-close, so it queues behind a running `doit` build instead of landing
inside it. Never bypass that with a bare attach: an attach-only `OpenDoc6`
changes the seat's active document and a sibling part build mid-sketch dies in a
plain selection call (three `part:top_frame` builds were lost that way on
2026-09-16 to an unlocked probe). Any read-only COM probe you write gets the
same `with dodo._com_seat("<label>"):` wrapper.

Exit 1 means findings. The dump lists, per sheet: size, inner border from
`ISheet::GetZoneMargin`, the title-block keep-out, every view's outline / scale /
display mode, and every annotation's text box, `GetPosition`, and line segments.

## REPORT findings versus per-drawing enforcement

The canonical policy is
[`_layout_audit.py`](../scripts/_layout_audit.py): `severity()` classifies a
finding with `GATING_KINDS`; `enforced(mode, gating, *, stem)` decides whether
it refuses the leaf. These are **different decisions**. `GATE` enforces every
gating finding. `REPORT` still records all findings, but refuses only kinds in
`ENFORCED_KINDS` or `STEM_ENFORCED_KINDS[stem]`.
[`_drawing_layout_audit.run_layout_audit`](../scripts/_drawing_layout_audit.py)
writes the report before refusing those selected findings.
[`finalize_drawing`](../scripts/_drawing_common.py) normally uses `REPORT`;
a successful export is therefore not evidence of zero gating findings.

Use the artifact stem from
[`_drawing_registry.py`](../scripts/_drawing_registry.py), not the recipe's
underscored name, for per-drawing enforcement (`ch-rocker-arm`, not
`ch_rocker_arm`). Add the kinds to the existing immutable mapping's **dict
literal**, only after a native build and printed-sheet inspection demonstrate
zero real findings in those classes. Do not switch the whole fleet to `GATE`,
demote a genuine collision, loosen thresholds, or add a runtime allowance to
get one drawing through.

### Magnifier CHECK block placement (combined 0fb89)

The retained report
`C:/farm-runs/com-perf-combined-mg-inspection-20261021/reports/layout-audit/mg-magnifier-assembly.json`
measures ASSEMBLY STEPS sequence `DetailItem376` at native extent
[17.6178, 95.3983]–[227.9432, 258.4113] mm and CHECK `DetailItem377` at
[17.6178, 61.8495]–[224.9324, 84.6455] mm, insertion (18, 84.4) mm.
The title-block keep-out is [216, 0]–[431.8, 66] mm. Move CHECK's insertion
to (18, 92.6) mm (+8.2 mm up), not the audit's downward hint, and sequence
insertion ultimately from (18, 258) to (18, 260.5) mm (+2.5 mm up).
Original-seat translation predicts CHECK extent [17.6178, 70.0495]–[224.9324,
92.8455] mm: 4.0495 mm above the title block and 5.0528 mm below the
sequence's translated extent [17.6178, 97.8983]–[227.9432, 260.9113] mm.
Sequence top inner-border clearance is 5.7887 mm; predicted printed gap is
5.9353 mm. Actual median printed heights are 3.8733/3.8734 mm, so existing
near-contact/separation thresholds are 1.93665/3.8733 mm, not nominal-font
1.75/3.5 mm.
The finished-view outline starts at x=276.6802 mm, leaving CHECK/sequence
horizontal air of 51.7478/48.7370 mm; its caption and wire balloon are farther
right. CHECK left/bottom inner-border clearances are 4.9178/57.3495 mm.
The subsequent 86bc native drawing at sequence Y259.5/CHECK Y92.6 passed
with zero gating findings, but measured sequence extent [17.6475, 96.8088]–
[227.8142, 259.7953] and CHECK [17.6475, 70.1210]–[224.4782, 92.9963] mm.
Its 3.8125 mm native gap missed our unchanged 4 mm padding acceptance,
despite a 4.9354 mm printed gap clearing the 3.8733 mm advisory threshold.
Evidence: `C:/farm-runs/com-perf-mg-clearance-inspection-20261021/actual-clearance-measurements.json`.
Raising only sequence Y259.5 to Y260.5 predicts 4.8125 mm native gap,
5.9354 mm printed gap and 5.9047 mm top-border clearance on that seat;
title clearance stays 4.1210 mm. The existing fit test retains both measured
seat cases and requires full 4 mm padding for each.
Text, wrapping, font, scales, geometry and native guards stay unchanged.
Fresh exact-head native audit and printed-sheet acceptance remain necessary:
these translations do not certify the Y260.5 output.
### TL-00 instruction-sheet source references

The oblique-jig assembly's `ASSEMBLY STEPS` reference at source `a0ba383f2b70`
measured 45.422 mm high at 1:20 in a 42.250 mm reserved region. A projected
model box is not the native view outline, and native outline padding need not
shrink in proportion to the view scale.

Keep the instruction text, caption reservation and title-block clearance.
Try only the reference's bounded 1:20, 1:25 and 1:30 scale ladder, rebuilding
and measuring both native outline dimensions at every rung. Centre the actual
outline and retain the strict final region/title-block check; exhausting the
ladder still refuses the drawing. The reference caption and finalizer's
per-sheet scale both report the measured-fit scale. The visible collapsed
model view remains the live source of the instruction sheet's properties.

The TL-00 C2A functional section in farm run
`20261021T104559405Z-fe8717a1858740b59ae5521c62b90d19` created all 23 native
lines but printed them at 1/20 size near the sheet origin, outside the border,
while its labels remained in the intended area. `CreateLine` takes coordinates
in the active drawing sketch, not paper metres. Obtain the sheet's own
`IView` from `IDrawingDoc.GetFirstView`, then its `GetSketch()` and live
`ModelToSketchTransform`; map the requested paper endpoints before creation.
Do not hard-code a ×20 correction or change the reference's measured-fit scale
to conceal it. Model-view insertion can also auto-drift the native sheet scale:
pin and read back the fitted reference ratio **before** reading the sketch
transform or creating the lines. This is the same ratio the finalizer re-pins,
including when the reference needs 1:25 or 1:30 rather than 1:20.

The recipe now requires every segment to belong to that sheet sketch and
remain non-construction geometry. Both native endpoints inverse-map to their
individual intended paper points within 0.1 µm, with their full bounds inside
the reserved schematic region. Independently match every authored line,
including feature-label arrows, against the sheet view's native `GetLines4`
display ink, using `GetXform` for its paper origin and scale. Model
`GetPolylines` data excludes these user-drawn segments.
Repeat the proofs after the finalizer re-pins the sheet scales and rebuilds,
also requiring the authored native scale to remain unchanged. The subsequent
`e9aa2521665e` native run proved all 23 lines at placement but correctly refused
finalization when their paper coordinates shrank by exactly four. Its old log
did not record the initial sheet ratio; creation at an auto-drifted 1:5 followed
by finalization at 1:20 is consistent with that factor, not yet a measured
ratio. Creation, placement and settled checks now log the actual sheet
properties, sheet-view transform, sketch transform and first raw endpoint.
A count of successful `CreateLine` returns or a broad region-containment check
alone cannot prove a full-sized, correctly located schematic. Offline
regressions exercise nonidentity scale, rotation and origin; scaled, displaced
and missing display ink; an inserted-view sheet-scale drift; and finalization
at each fitted scale. Fresh native export and all-ten-sheet visual inspection
remain required.

The cf3 assembly review found that C2A's loose caption list did not identify
its ink. Keep separate pointers to the pin, block, feeler, mounting plane and
ground bridge, and put the spec-owned `0.50 MIN` beside the recess bracket
between the pin-tip witness and Z=0. These native sheet-sketch arrows use the
same exact endpoint/display proof as the section. The BOM's explicit native
top-left anchor must leave visible air on both border sides; retain the native
row/column bounds and reference/title-block keep-outs. The exploded lock wire
stays near its drilled screw heads, separately from the withdrawn cotter, with
the existing real-edge balloon ownership and settled-landing guards unchanged.

Keep pointer starts clear of the labels' complete line boxes, not just their
text anchors. The C2A PIN/BLOCK/FEELER checks exposed a 0.025 mm overlap;
moving the PIN/BLOCK labels up and the FEELER pointer start down by 2.5 mm
leaves 2.475 mm vertical air under the conservative text model. Keep the
feature endpoints fixed and retain both the offline overlap checks and native
endpoint/display proofs.

The e12 review required the capture presentation to use the available sheet
width. The 808 review then showed why a second identical exploded cartridge
was not useful: both bearings still hid behind the block, and the clevis had
followed the retainer lift instead of its pin's cross-hole. Keep one coherent
native exploded cartridge on the left. Select upper/lower bearing occurrences
separately so C1 reads pin/upper bearing, upper seat, then lower bearing;
attach item 14 to both actual bearings. Correct only the clevis/cotter's
vertical presentation to follow the pin, retaining their axial withdrawals.
Preserve every-instance translation/rotation readbacks and the proof that
collapse restores the operational assembly; these are presentation changes,
not changes to mating geometry or fit-up criteria.

Replace the unballooned twin with a visible assembled plan locator, a genuine
longitudinal section A-A through the pivot and clevis axes, and a small
bolt-seat section B-B for the underhead point that the centre plane cannot cut.
Reuse native `create_section_view` and the existing assembly `Crop2` pattern,
explicitly isolating the parent and each child. Keep their section/crop,
configuration, visible-occurrence, scale, attachment and paper-field
readbacks through the final rebuild. The exploded view stays first for the
sheet's live property association; the assembled inspection views carry no
additional BOM balloons. Do not run whole-sheet ring relaxation on a view
reserved to the left field. Retain real-edge ownership, ring uncrossing and
settled-landing proofs, with exactly the two intended bearing attachments.
`IDrSection.GetLineInfo` returns parent-sketch/model-space XYZ endpoints, not
paper coordinates. Read the parent's current sketch transform on every replay;
compare full endpoints in either order and their model-space length. Arrow and
text positions remain sheet-space. Author crop circles with protected
`AddToDB=True` and select the closed profile explicitly. Retain that exact native
segment and read its centre, model radius and current `ISketchSegment.GetSketch`
owner after moves/rebuilds: `Crop2` consumes the profile, so enumerating
`IView.GetSketch` is not authoritative. The retained segment must remain
accessible; do not invent a crop-feature getter or fallback if it does not.
Set assembled views' final scales before authoring their crops (locator 1:4,
A-A 1:2, B-B 1:2); do not walk a scale ladder after `Crop2`. Refresh native display
geometry after HLR/scale changes before measuring the outline. `GetOutline` is
a padded view extent, not an exact crop circle box. The locator's 54 x 43 mm
field accommodates its measured 43.884 x 41.516 mm native extent; its caption
moves down with the field's lower edge, without moving neighboring labels.
If a view does not fit, retain its native scale, position, outline, overflow and
selected profile geometry/owner transform in the refusal. Keep strict native
outline, label-clearance and geometry tolerances.

Inspection callouts identify the existing C-step reading points and limits:
chamber excess is chamber height minus flange thickness, not a third gap.
Neither a centre section nor a static nominal pose replaces the prescribed
whole-face, endplay, clocking and motion inspections.
Assembly-section edge listings can be empty while the native sheet pick finds
the drawn edge. Use the existing narrow-zoom pick on that native edge:
require exactly one native EDGE, with any other selection only the same
activated drawing view. A bare plan owner must match the unique visible leaf's
full model path case-exactly, have no native parent, and reference the same
part file as the leaf's component. A section owner must have exactly one native
parent: its file must be the authored source assembly used to create the views,
and the owner name must equal that parent's native name plus the exact leaf
path. Compare nonempty file paths after resolution. Drawing-component names
can carry a synthetic `SectionAssembly` root and are not source-owner identity;
never decide occurrence identity from a basename or suffix. Reselect only the
verified edge and prove native identity before creating its attached note.
Section witnesses retain the existing `1e-8 mm²` part-local closest-point bound,
so a nearby rim, floor or roof cannot substitute for the intended land.
At the two C4 bore mouths, the retainer top corner and loaded clevis meet.
Acquire the natively proved vertical bore edge at midheight, then retain the
original top-corner closest-point, attachment and settled leader-landing
checks. The acquisition point is not a changed inspection station or a retry.
The loaded clevis also coincides with the upper cross-hole boundary. Point its
label to the text-side corner of that same boundary at the unchanged upper-hole
height, acquiring the pin's outer journal wall above the hole and below the
tip chamfer. Require that pin-owned edge to pass through the corner, then keep
the native attachment and settled landing proofs; do not hide components.

The C5B plan note identifies the cotter eye/prong regions and points to the
manual motion/feeler inspection; it is not a static clearance dimension.
The visible prong and obscured eye can share a plan projection at different
depths. Preserve its exact occurrence, attachment and existing 2D leader-landing
proof without inventing a 3D gap witness or changing the inspection criterion.

After the reading-label rebuild, compare freshly enumerated visible occurrence
paths with the exact installed set. On refusal, record all four views' sorted
expected, actual, missing and extra paths plus offending drawing-name/path/
visibility tuples before changing identity or isolation rules. Successful
edge selection does not prove settled component visibility.
Native section-tree `IDrawingComponent.Visible` flags can remain true for all
110 parts while `IView.GetHiddenComponents` correctly retains the same 95
excluded occurrences throughout isolation, orientation, crop and label rebuild.
For sections, derive the visible inventory from that native hidden list, not
the generated tree flags. Match every hidden owner to one exact view leaf using
the existing part-file/source-parent proof; reject unknown, duplicate or
unreadable identities. Ordinary-view visibility and the exact installed-set
comparison remain unchanged. Do not guess root names or reapply hiding.
Bind notes returned by `IView.GetNotes` to `INote` before calling `GetText` or
`IsBomBalloon`; raw dispatch can materialize those zero-argument members as a
string or Boolean. Keep exact caption/uniqueness and balloon-count/native-identity
checks rather than guessing callable forms.

`INote.GetExtent` also encloses an attached leader; it is not a text-only box.
For capture-label ink checks, use native `IDisplayData` text runs with positive
finite widths/heights, positions, angles and all six text-reference anchors,
following the kit's measured-text pattern and shared `display_box`. Missing or
zero native width is a refusal with all run metadata, never a font-width estimate.
Keep whole-note extent containment and the separate leader checks as well.

The pivot-capture native PDF exposed a 2.463 mm C5A/C3A block gap below the
3.234 mm row pitch and a cotter leader crossing the A cut line after the
glyph guards passed. Move the reading text, not its physical criterion anchor.
Replay the original PDF's vector strokes as well as the cached audit JSON,
which retains only their count, before checking neighboring ink. Translated
label previews predict native junction routing; the unchanged native guards
and final PDF audit must still qualify the result.

On refusal at the four final layout guards, report all indexed glyph and
whole-note rectangles, outside-field entries and overlapping pairs, not only the first
conflict. Field gaps are left/bottom/right/top; pair gaps are horizontal/vertical,
in metres, with negative values denoting overlap or field overrun. Include
the existing leader segments/crossings and the three reading-view outlines
(or their read errors), without masking the original refusal. Move labels only
from measured bounds and neighboring clearances; do not relax layout guards.
Earlier reading-field and other-view leader checks retain their fail-fast order.

The C2A schematic and its exact sheet-scale/endpoint/display proof travel with
the bench procedure to sheet 8; feed checks, cap seating and carrier capture
have distinct headings in that print order, without new acceptance criteria.

For the assembly's imported CL-tip reference, curate the native dimension at
a near-tip **dimension-line anchor**, reset inherited `OffsetText`, then use
`offset_dimension_text` for the separate clear text lane. Moving the whole
dimension into that text lane first leaves unnecessarily long witnesses even
if the value's position reads back correctly. Require the native display's
arrow tips to remain at the projected model endpoints on the near-tip line
both immediately and after finalization; retain the native model value,
reference brackets, precision and no-tolerance contract.

Apply that separation to the complete native annotation, not just its leader.
The `b9e4d6b45` carrier cleared the enforced leader crossings while its 45.00
dimension still struck the REAM tolerance stack and callout rows. Retain every
captured text row, arrow edge and neighboring annotation in layout regressions;
an arrow tip alone can miss a clearance violation by the arrow's flank.
These replays budget a proposed placement; the regenerated PDF remains the
evidence of the actual layout.

When a placement guard refuses, report the stage, requested and actual
annotation origins, native arrow tips, `OffsetText`, tolerances and differences.
Keep unavailable probes as explicit read errors and preserve the original
exception. A combined “line moved or text missed” error cannot distinguish a
setter refusal from a clamped position, and does not justify loosening a guard.

For the oblique block's multiline linear captions, after enabling `OffsetText`
and moving the text, the final line landed at the prior annotation origin,
not the false-mode arrow Y. Calibrating that arrow first moved the final line
by 19.447 mm. Set the false-mode annotation origin to the desired line anchor
once, enable offset text, then move the text and check the settled arrows,
witnesses and text origin. Source `f441b8b25` passed the native guards with
this handoff; do not replace it with an iteration or a hard-coded correction.

The second cartridge uses the same capture-part families on the other
support, so its identification does not need duplicate BOM balloons. Explain
that the capture parts are identical at both supports in the existing
reserved exploded-view footer, alongside the BOM/assembly-sequence references.
Do not introduce a free-floating caption beneath the ring: that area is not
reserved text space. The existing footer width, on-sheet/title-block bounds,
ring separation and native layout-audit checks remain in force.
### TL-22 pivot-block callout lanes

The native drawing at `6dd691486` refused three enforced findings. On
**Bearing and carriage**, the carriage-hole callout leader
`(172.2,216.6) -> (158.1,238.8)` mm crossed both the removed-view **C**
pointer's text box `[161.8,228.9]..[165.1,232.5]` mm and its leader
`(165.6,230.9) -> (163.4,222.0)` mm. C is a view-owned viewing pointer,
not a datum-feature symbol. Keep its tip and the callout's selected counterbore
edge; move the callout text anchor from `(188,250)` to `(212,250)` mm.
The projected text-end route is then right of C rather than through it.

On **Register recesses**, the complete native `CapRegister2Dia` block's
horizontal shoulder at Y233.9 mm crossed `CapRegisterUpperY` at X294.5 mm,
whose offending line ended at Y238.0 mm. Raise the diameter text from model
Y27 to Y33 mm: at 2:1 this allocates 12 mm more sheet height and projects the
shoulder to Y245.9 mm, above the unchanged Y24 station. Keep the imported
diameter, its source tolerance, both register locations and native leader style.

The offline tests replay those measured conflicts and the requested text
translations; they are not native after-fix proof. Parent validation must
rebuild and inspect the full text blocks, leaders and border clearance on both
sheets, with the existing layout enforcement unchanged.

The five-sheet `7f008ec06db9` PDF also exposed native text/ownership traps.
The diagonal D-D cut through the staggered receivers really produces an
approximately 6° oblique section; it is not a view-angle error. A square
depth section can cut the first receiver at constant model X, with the
existing `2X` depth applying to both recesses in the same cut feature.
Project its cutting endpoints through the parent view, but pass keeper and
section-owned linked-caption positions directly in **sheet coordinates**.
Reusing the plan's paper anchors leaves the depth text and caption beneath
the plan even when their native owner is the section.

Allocate lanes for complete callouts, not just values: the 9.000 mate block
overprinted the web-hole callout, and the 74.50 wall qualifier printed in
A-A's hatch. On the same export, `CboreFloor`'s audit text already contained
the M4 engagement qualifier above 15.600, but the PDF omitted that multiline
qualifier. `GetText` is therefore not printed-ink proof. Keep the accepted
short-engagement fact attached to the native floor dimension and inspect
its full exported text, witnesses and neighbouring ink.

Retain the D-D depth line, text shelf and projected witnesses for a read-only
check after the final rebuild, along with all three capture-wing offset
line/text placements on sheet 2. Keep the f441 origin handoff and existing
placement guards; the settled checks must refuse drift, not reposition it.
The `cf3fd16025ab` native leaf also exposed a wrong witness-gap origin:
`HoleRow1Y` ends at the carriage row's `BOLT_X`, not the block's +X face.
The accepted gap therefore started the witness 10.5 paper mm short of its
clear lane. Compute it from that actual row endpoint; still require the
rebuilt witness to clear the complete A letter by 2 mm and remain visible.

### TL-30 capture-cap functional sheets

The `d349b99300c6` native cap drawing imported all 32 model dimensions, including
the real `RegisterEndChamfer`, but packed their complete manufacturing callouts
into seven views on one sheet. Its log recorded 108 gating findings. The
enforced pair was `WireWidth`'s shoulder `(217.5,83.7) -> (137,83.7)` mm crossing
`PocketDepth`'s witness `(215,87) -> (215,80.6)` mm. The failed leaf published no
paper/audit artifacts, and the worker's next source preparation had removed
them: the remaining 107 records cannot honestly be classified from that log.

Keep the full source text and 1:1 scale, with these separate ASME B sheets:

| Sheet | Native dimension ownership |
| --- | --- |
| `ACCESS` | Outline, aperture coordinates/size, head and wire access, mouth depths |
| `SECTIONS` | Underside pocket size/corner coordinates, A-A pocket section and cap thickness |
| `BOLT-LOCATIONS` | Through-clearance size and all eight actual pocket-axis bolt coordinates |
| `REGISTERS` | Both bosses' size/coordinates/projection, root-radius maximum and no-undercut requirement |

The formerly explicit circular-rim chamfer imported in `*Top`, not `*Right`;
native transfer to `*Right` refused. Do not preserve its extra XZ view or marked
MAX dimension after the free-end chamfer adopts the general 0.25 mm edge-break
limit. Keep the native 45-degree feature and geometry readback, and charge that
whole general limit to the coupled register-engagement bound. The unmirrored
`*Front`/`*Right` context owns the projection; separate `*Back` views retain
visible native pocket-axis witnesses.
Every sheet takes precision and complete callouts from the same part-spec maps.

Remove the unconditional second `auto_center_marks` pass. The existing template
inserts centre marks; the replacement census requires one for the central bore
and each visible pattern feature (five in `*Front`, seven in `*Back`), refusing
missing or duplicate marks. The 12 duplicate records are consistent with that
second pass, but their individual native records were not recovered. Fresh
native validation must confirm the census and inspect **all four** printed
sheets and the full audit, not only the formerly enforced pair. Requested
coordinates and offline routing tests are not zero-collision native evidence;
all existing audit kinds, fit guards and model-owned tolerance controls remain.

### Stock allowances and local drawing-number fit

When the native model shows a fitted part rather than its supply blank,
attach `SUPPLY n.n MIN THICK` to the real thickness's REF callout (TL-31).
Do not dimension an undrawn blank or retain an annotation-only sketch that
leaves a witness in empty paper. Keep the actual fitted acceptance and its
running-face finish; the stock allowance is not a finished-size band.
For a round washer, the filing-button convention moves the genuine imported
OD from the circular face to `*Right` with `move_model_dimension`.

A purchased drawing whose Number overruns the REV divider opts into
`NumberFit.SHRINK_TO_CELL` in its own recipe (VN-52). This measures and fits
the linked native note locally; do not change the shared template or rename
the part. Inspect the fresh native witnesses, callouts and Number/REV gap:
source positions alone are not after-fix evidence.

### Rocker R19 regression and local placement contract

R19 at `81ac56b26598b63c0c9a11a467208ac4176ce646`, farm run
`20261013T051541021Z-0456b55b4ef7424793cb5fdafaf10c41`, exported successfully
with 18 gating records. At that point the rocker had no per-stem entry, and
none of those records' kinds was globally enforced in `REPORT`. The four
visible collision pairs were **already detected**, not missing audit coverage.
The twelve real records, numbered in R19 gating order, are:

| R19 records | Existing gating kind | Actual native/printed defect |
| --- | --- | --- |
| 1, 2, 3 | `text-clearance` | B against PIN AXIS; E inside #47 DRILL; HubLength value/stack against the drill's lower row |
| 4, 5 | `text-on-line` | B's box line through PIN AXIS; PIN AXIS shoulder through B |
| 8, 9 | `extension-through-own-text` | HubLength witnesses through its own value/stack; angular witness through TO MIRROR PLANE |
| 10 | `dim-line-through-own-text` | The native angular arc through TO MIRROR PLANE |
| 11, 12 | `arrow-near-text` | Taper arrow 1.6205 mm from R816; HubLength outside-arrow tail 1.7251 mm from the drill row (2 mm rule) |
| 17, 18 | `duplicate-annotation` | Identical front-view centre-mark pairs at (178.1134, 169.9608) and (246.2447, 175.4982) mm |

[`test_layout_audit.py`](../scripts/test_layout_audit.py) keeps a compact
`_rocker_r19_dump()` extracted from the actual report's `sheets[0]`: native
display coordinates, circle-label data, duplicate anchors and actual PDF text
spans, in **sheet metres**. It calls the existing `audit_dump` and own-text
finder with their unchanged thresholds. `ROCKER_R19_REAL_RECORDS` identifies
all twelve; `_rocker_r19_real_findings()` is the replay interface for a separate
per-stem refusal test after R20 native acceptance. The unified audit keeps
one finding per `(kind, a, b)`; the own-text finder also stops at the first
striking line per row. Isolating each recorded native HubLength witness proves
both the left witness through 7.056 and the right witness through the stack
without inventing a new drawing or claiming an R20 render.

The six other R19 gating records were classified from native/PDF/PNG evidence,
**not demoted**: 6/7 are padded-outline `text-on-view` phantoms above detail D;
13 is the printed U inside native `<CL-U>` that the text claim key misses;
14–16 are printed 0.18 mm model edges the classifier expects at 0.25 mm.
Their shared collector/claim/edge-classification follow-up is
[#1419](https://github.com/pedropaulovc/harmonic-analyzer/issues/1419#issuecomment-6139402807).
Keep those classes outside this rocker's six-class cutover; do not hide their
reports or weaken a real predicate. `report_sheet()` strips PDF strokes to a
count: a stroke-less replay cannot prove model-edge absence or repair an
outline phantom. Use the actual cached PDF with
[`diagnostics/layout_calibration.py`](../scripts/diagnostics/layout_calibration.py)
`--pdf-dir` for that evidence, not fabricated strokes.

R20 placement changes belong in the rocker recipe, not the shared audit:
move B's complete symbol/box/leader clear of PIN AXIS and its shoulder while
keeping the attachment on its actual broad face; move E's letter clear of both
drill rows; place the **whole** HubLength value/stack to the left, outside both
witnesses and clear of the drill and arrow tail. A rightward move is not a
clearance proof: an above-callout row can reflow the lower tolerance into E's
full circle. R23's numeric angular BASIC box still crossed its witness and
arc. Pedro's superseding R27 ruling removes that angular dimension entirely
(option 4 later moved datum C from the +X tip land to the rod-pin hole: note 1
now says the mirror plane is clocked by C, note 2 makes the tip lands radial
to the arc centre, and the old note 5 is gone). Do not replace the removed dimension
with another offset, seed or route mechanism. Retain R23's R800/R816 positions;
their C1/C2 clarity findings remain open. Remove automatic
centre-mark reinsertion on front/D/E while strictly retaining the native
2/1/1 **printed** centre-mark census, rather than counting every allocated
annotation or merely deleting the observed front pair.
An isolated translated box is only an offline predicate control, never native
after-fix proof. Detail D uses the existing non-feature `NoOutline` convention;
do not alter its circular crop geometry. Its outline-style flags are
conditional on `NoOutline`, while E retains its full-outline display checks.
Preserve all model/spec/nominal/tolerance values, view centres and scales,
physical A/C datum checks, E at Y110, 3 mm fatal caption air and 4 mm target,
the strict 3.5 mm Manufacturing Notes source font, and the shared persisted
profile/crop guards (including signed four-edge F5 deltas and exact zero-slack
crop containment). Only after the current native sheet shows zero does the
parent add the six real classes above to `STEM_ENFORCED_KINDS["ch-rocker-arm"]`.

R21 at `3d771e59d3d2e5afc42763ff6e056693ff06da3e`, run
`20261013T095135303Z-94e3c17bba524633997e55a0bf8a0cef`, passed the corrected
width owner and D's `NoOutline`/persisted-crop checks on SP4, then refused
because detail D had two type-13 annotations rather than one. R19's native
records explain why: D's template `DetailItem352` has eight printed lines,
whereas `DetailItem354` has readable empty display data and an anchor at
(708.6834, 127.0803) mm, outside its crop. E similarly retains printed
`DetailItem358` and off-crop, empty `DetailItem356`. These are native cropped-out
ghosts, not missing holes or ink that should be deleted.

Classify every centre-mark annotation exactly once and log its native id,
position and line count. `PRINTED` requires non-empty display with every
primitive inside the persisted crop, subject only to the display encoding
precision below; only these count toward 2/1/1. `GHOST` requires **both** empty
display and an anchor outside the crop, with no anchor tolerance. Empty inside,
non-empty primitives beyond encoding precision, unreadable data or
malformed/truncated arrays must refuse, not become zero ink. Account for the
entire annotation array with non-centre marks plus printed/ghost buckets, and
preserve the exact printed
counts. Ghosts remain untouched: deleting an invisible object adds native
risk without improving the sheet. The R19 dump rounds coordinates to 0.1 um;
replay fixtures must state that quantization rather than silently adding
runtime crop padding.

R22 at `db94ffe29a8878fe6aab46181b0f66fa483cf393`, run
`20261013T111844759Z-1c357921c6af4a77806cd9dc0d20a5bf`, confirmed the ghost
bucket but refused a printed D arm by 0.8702278898 nm. Its native endpoint
`0.15309999912977218` m is exactly `0.18 - float32(0.0269)`, while the persisted
double-precision crop starts at `0.15310000000000007` m. The display arrays
carry single-precision local offsets: a sub-ULP overrun is encoding, not ink,
and this arm is clipped at the crop circle by construction. Main ruled that
each **display primitive versus persisted crop** coordinate comparison gets
one derived float32 ULP at the magnitude of its larger operand:
`float64(spacing(float32(max(abs(a), abs(b)))))`, or an equivalent IEEE-754
calculation. Log the per-row tolerances and overruns. This is not a fixed
epsilon, rounding of native rows, crop expansion or a global audit allowance.
Two-ULP and 1 um overruns still refuse; ghost, inside-empty and malformed-data
rules are unchanged. The shared exact-zero **crop versus outline** containment
and independent 50 um F5 equation remain unchanged (double versus double).

R24's remaining repairs are local to the rocker recipe. The rod-hole position
frame retains its circular-edge attachment, but uses a short right-sided bent
leader with a filled-dot arrowhead on the south rim where the printed
centre-mark arm passes through it. Read back the leader side/style, disabled
smart-arrow state, dot style in both annotation and display data, complete
leader points, attached-entity identity and unchanged frame XML after redraw.
The actual route must miss the taper; a success status alone is not evidence.
Do not use `SetLeaderAttachmentPointAtIndex` on the frame.

R800 retains R23's native-proven **145/136 mm** text position and its
complete-circle exterior guard. The inside-circle attempt recorded by
`a8dcea067` drew a roughly 355 mm off-sheet centre tail and a 6.3 mm outside
arrow extension onto the strap, despite the expected radial leader flags.
The proposed 130/190 mm position shares that unproven mechanism; a fabricated
tail-free fixture does not establish native behaviour. C1's finite-top-arc
landing clarity therefore remains open, rather than claiming an off-part
leader proof. R816 also retains R23's native-proven **169/128 mm** position and
complete-circle exterior guard; C1/C2 stay open for the current blind review.
The 5.59 land dimension retains both real corner attachments and the unchanged
E crop, with both actual native witnesses visible. A standard extension-line
gap is not a missing attachment: validate the authoritative native gap and
the outward, collinear witness start from each projected corner, its arrow
connection and positive visible portion inside the crop. R24 on SP4 returned
True from `SetWitnessLineGap(index, False, 0.0)` but then read
`(True, True, 0.001)` after rebuild; the requested zero override did not persist.
Zero itself is not the readability requirement. Do not change the document-wide
gap or ignore that readback. R25's actual native geometry at the 1 mm effective
gap passed both witness routes, with upper/lower crop-visible portions
2.016936/7.715339 mm. Readability still needs the rendered-sheet review.
The parent taper witness must miss E's source circle without changing its value
or endpoints. Note 2 states
explicitly that the top basic is **ABOVE A** and the common arc centre is
above A. The B2-1 reference clarification, as revised by option 4, defines
the mirror plane through datum axis A, perpendicular to datum B and clocked by
datum C, the rod-pin hole, whose BASIC pin coordinates fix the angle.
The familiar pin coordinates and arc basics remain unchanged and are thereby
chained to A|B|C. None of these presentation/reference controls changes a
datum feature, geometry, zone or manufacturing tolerance.


## What is readable from the API (stop guessing)

| Question | API | Evidence |
| --- | --- | --- |
| A view's native extent, metres (not a detail's bare circular crop) | `IView::GetOutline` -> `[xmin, ymin, xmax, ymax]` | `types/IView/GetOutline.md` |
| An annotation's sheet origin, and WHICH corner that is | `IAnnotation::GetPosition` | `types/IAnnotation/GetPosition.md` (note = upper-left of text box; display dimension = leader attachment / centre of text box's bottom border; GD&T = upper-left; surface finish = lower-left; table = per `ITableAnnotation::AnchorType`) |
| A note's EXACT box | `INote::GetExtent` -> 6 doubles, lower-left then upper-right, sheet space | `types/INote/GetExtent.md` |
| Real rendered lines (dimension line, witness lines, leader) | `IAnnotation::GetDisplayData` -> `IDisplayData::GetLineCount` / `GetLineAtIndex3` -> `[color, lineType, lineStyle, lineWeight, startPt[3], endPt[3]]` | `types/IAnnotation/GetDisplayData.md`, `types/IDisplayData/GetLineAtIndex3.md` |
| Text items, height (m), anchor corner, angle | `IDisplayData::GetTextCount` / `GetTextAtIndex` / `GetTextHeightAtIndex` / `GetTextPositionAtIndex` / `GetTextRefPositionAtIndex` (`swTextPosition_e`) / `GetTextAngleAtIndex` | `types/IDisplayData/*.md` |
| Whether an annotation renders at all | `IAnnotation::Visible` -> `swAnnotationVisibilityState_e` (1 visible, 2 half-hidden, 3 hidden) | `types/IAnnotation/Visible.md`, `enums/swAnnotationVisibilityState_e.md` |
| Sheet ink vs template ink | `IAnnotation::OwnerType` -> `swAnnotationOwner_e` (0 view, 1 sheet, 2 template) | `types/IAnnotation/OwnerType.md` |
| All dimensions' lines, arcs, arrows, text positions in one array | `IView::GetDimensionDisplayInfo5` (+ `GetDimensionDisplayInfoSize2`) | `types/IView/GetDimensionDisplayInfo5.md` — **current sheet/view only**, and "does not support hole callouts" |
| Sheet size | `ISheet::GetProperties2` -> `[paperSize, templateIn, scale1, scale2, firstAngle, width, height, sameCustomProp]` | `types/ISheet/GetProperties2.md` |
| Inner border keep-out | `ISheet::GetZoneMargin(swZoneMargin_e)` — **takes the side as an argument** (top 0, bottom 1, right 2, left 3) | `types/ISheet/GetZoneMargin.md`, `enums/swZoneMargin_e.md` |
| Every sheet, without activating any | `IDrawingDoc::GetSheetNames` + `IDrawingDoc::Sheet(name)` -> `ISheet`, then `ISheet::GetViews` | `types/IDrawingDoc/GetSheetNames.md`, `types/ISheet/GetViews.md` |
| Dimensions on an INACTIVE sheet | `IView::GetFirstDisplayDimension6` | `types/IView/GetFirstDisplayDimension6.md` ("obsoletes ...5 by supporting inactive sheets") |
| Where a datum tag REALLY went after `SetPosition2` | `IAnnotation::GetPosition` — the leader/symbol junction, not the symbol centre: reads 0–5 mm from the request on a straight attachment, 17 mm on an OD-attached tag whose attachment re-solved along the edge (bearing swung 4.7°). `IAnnotation::GetLeaderCount` is 0 for every datum tag, and in the authoring session `IDatumTag::GetLineCount/GetLineAtIndex` stay frozen at the INSERTION geometry through a rebuild — useless as a readback. | `drawing:pinion_cam` datums A–D, 2026-09-16, two seats; `_drawing_gdt.add_datum_feature` |

All of it is **sheet space, metres**, origin at the sheet's lower-left — for
view-owned annotations too (measured: a dimension inside a view 102 mm from the
left edge reports `GetPosition` x = 0.074 m, and its `GetDisplayData` lines agree).
Report and reason in mm; call the API in m. The third coordinate is model depth
and is not always 0; ignore it.

**BOM-adjacent captions follow the rebuilt table, not a row-count estimate.**
The pen assembly's parent-scoped vendor Numbers wrap in its 30 mm part-number
column. The naming cutover grew its native BOM from the earlier 91.5 mm
measurement to 121.515 mm, putting the old fixed caption through row 12.
`draw_pn_pen_assembly._place_exploded_caption` follows the existing native-table
pattern: read the top-left `IAnnotation::GetPosition`, sum every rebuilt
`ITableAnnotation::GetRowHeight`, then place the caption below that bottom.
Keep the full Numbers and the view's actual scale. Read `INote::GetExtent`
after insertion to prove at least 4 mm of final air, as well as sheet and
title-block containment; a readable source string does not prove a readable PDF.

**FR's set-screw balloon must follow that same rebuilt BOM boundary.**
The full-sheet inspection at `ebb3c20596a66f93c01fa2084eca7b3602ea32dd`
confirmed #1843: the BOM's bottom rule passed through balloon 10's ring and
number. The recipe's measured placement and clearance helpers existed but
were not consumed by `_place_package`. After ordinary reattachment, apply
`_place_frame_set_screw_balloon`: keep its right-hand lane and real screw tip,
placing the complete ring 4 mm below the native table bottom or lower to
retain a short leader. Include its short-leader proof with the other balloon
settlement proofs, not just an insertion-time check.

`_assert_frame_bom_balloon_clearance` must run after placement and again after
the final rebuild. It requires at least 3 mm between the BOM rule and the
ring's outer edge, separation from the neighbouring cap balloon, and clear
leader routes. A rebuilt table growing down or a ring drifting up refuses
export. The regression also brackets that unchanged floor at 3.001/2.999 mm;
these are offline geometry cases, not a claim of native pixel resolution.
Do not rescale the view, alter its explode or move the attachment to create
clearance. All ten item identities and the geometric inset proof stay intact;
the next farm export and full-sheet inspection must establish the final ink.

**The one thing that is NOT readable: rendered text WIDTH.** No API returns it
(`IDisplayData::GetTextInBoxWidthAtIndex` is table cells only and returns 0 when
`GetTextInBoxStyleAtIndex` is `swTextInBoxStyleNone`). `_layout_geometry`
estimates width from the string and cap height, and calibrates the glyph advance
against notes on the same sheet whose exact extent IS available (tube-frame
calibrates to 0.741 of cap height against the default 0.62). So the text box's
POSITION and HEIGHT are measured; only its width is estimated, and it estimates
high. Treat a sub-millimetre text-box finding as advisory; treat millimetres as
real.

## COM traps that make a correct audit read as an empty drawing

Every one of these produced a plausible-looking wrong answer instead of an error.

- **`OpenDoc6` returns a tuple.** `Errors`/`Warnings` are `[out]` parameters, so
  pywin32 hands back `(IModelDoc2, errors, warnings)`. Unpack it. A tuple answers
  every accessor with `AttributeError`, and a tolerant reader reports "the
  drawing has no views".
- **One dispatch, many interfaces, and the project's wrapper is STRICT.**
  `sw_type_info.early_bound_or_flag(obj, iface)` exposes only what `iface`
  declares (the late-binding fallback was deliberately removed). `GetViews` is
  `IDrawingDoc`; `GetAnnotations`/`GetOutline` are `IView`; `GetExtent` is
  `INote`; `GetProperties2` is `ISheet`. Bind the owning interface at each hop.
  The registered [`test_drawing_layout_check.py`](../scripts/test_drawing_layout_check.py)
  contracts use explicit producer owners and closed interface member surfaces,
  never identity-cast fallbacks. Notes, annotations and text formats stay separate;
  a sketch profile may support both segment and arc QI, but each binding exposes
  only its own methods. Wrong-owner returns injected into the actual note factory,
  crop and collector routes must refuse before borrowing a member. Keep native
  properties as values (`IView.Type` is get-only), and math points separate from
  transforms despite their shared `ArrayData` name. These offline contracts do
  not establish native transform frames, rendered geometry or print acceptance.
- **An annotation array still contains opaque dispatches.** Bind the view to
  `IView`, call `GetAnnotationCount()` **before** `GetAnnotations()` as the
  official remarks require, and match the actual nonnegative integer count to
  the returned tuple/list length. Null is legitimate only for count zero,
  including a deliberately undimensioned isometric. Bind every nonnull item to
  `IAnnotation` before passing it to a best-effort dimension-name helper.
  Otherwise a failed `GetSpecificAnnotation` can be
  swallowed into an empty name and a valid drawing appears to have no marked
  dimensions. The rocker R17 native census reported `front=[]` after successful
  import/curation and caption seating; the binding explanation is an inference,
  not a logged native exception. Keep exact per-view ownership, duplicate and
  global-union checks, and log both annotation count and resolved marked names.
  An unnamed actual display dimension is not permission to omit it: read
  `GetType()` as an actual `swAnnotationType_e` integer, then bind its nonnull
  specific object to `IDisplayDimension`. A nonnull `GetDimension2(0)` with an
  unreadable name is fatal. Null underlying model data may be skipped only with
  an actual `IsHoleCallout() == True`; null alone is not a documented hole-callout
  identity. Preserve original native/binding exceptions.
- **Sweep past the last failed native guard before another farm round.**
  Check every remaining collection/count/primitive shape, unit and null policy
  through save, PDF and PNG. A present truncated row is not an empty primitive
  set, and a nonempty view whose text is entirely skipped is not a clearance
  proof. Do not apply a raster-pixel tolerance to exact format metadata, or use
  exact metadata tolerances for a measured quantized extent. Capture late
  audit/finalize refusals while the native seat remains open, with phase and
  original exception; secondary forensic or telemetry failures must never
  replace that refusal. Shared collector/primitive omission paths discovered
  in this sweep are tracked separately in
  [#1419](https://github.com/pedropaulovc/harmonic-analyzer/issues/1419), because
  changing shared behavior needs full-farm sheet-diff/rule-#1362 coverage.
- **Properties are not methods.** `IView::Name`, `Type`, `ScaleRatio`,
  `Position`, `Sheet`, `ModelToViewTransform`; `IAnnotation::OwnerType`,
  `Visible`, `Layer`; `ITableAnnotation::RowCount`/`ColumnCount`;
  `IDisplayDimension::OffsetText`/`LeaderVisibility` are all propget/propput.
  There is no `IView::GetName` — that call raises, and a `getattr`-and-call
  helper will silently fall back to a default. Read them as attributes.
- **`IView::Sheet` is None on the sheet's own view.** `IDrawingDoc::GetViews`
  returns one array per sheet whose first entry is the SHEET's view; that entry's
  `Sheet` property is empty (measured on tube-frame). Get the `ISheet` from
  `IDrawingDoc::Sheet(sheetViewName)`; a real drawing view's `Sheet` does answer.
- **Hidden annotations are still in `GetAnnotations`.** tube-frame carries a
  `swSFSymbol` parked at the sheet origin with `Visible` = 3
  (`swAnnotationHidden`); auditing it invented an 18 mm border breach at (0,0).
  Skip 2 and 3; keep 0 (unknown), because the property cannot see layer or
  suppression state.
- **The sheet FORMAT is in there too.** Frame, zone letters and title-block text
  arrive as `OwnerType` = 2 (`swAnnotationOwner_DrawingTemplate`) on the sheet's
  view — on tube-frame, 41 of the sheet view's 42 annotations. Filter to
  `OwnerType` = 1 for sheet-owned ink, or you audit the template against itself.
- **`GetDisplayData` is the window's rendering, not the sheet's.** A balloon's
  circle and leader start read at fit to the sheet sit where the seat's window
  drew them, a pixel being 0.68 mm on an 820-high window and 0.94 mm on a
  640-high one. The PDF prints from the model. Frame item 2, SetPosition
  (89.32, 250.85) mm: zoomed onto a 24 mm square the ring read (93.61, 249.03)
  and printed at (93.52, 249.06), 0.10 mm apart (items 5 and 9: 0.19, 0.23 mm;
  run 20260928T141421973Z, swmaker000008). Read at fit after the rebuild on
  swmaker000005 (run 20260928T142458776Z), the same SetPosition gave
  (92.85, 249.98), 1.14 mm off. Place and check a ring zoomed
  (`_drawing_scan._zoomed_on`; `draw_fr_frame_assembly._short_frame_balloon`
  re-zooms after its fit rebuild); at fit, check only model values such as
  `GetPosition`. On 1024x640 seats the leader start COM reports is 0.15 to
  0.78 mm from where the PDF starts that leader, on the printed ring; the
  layout audit takes the printed start (`_layout_audit._printed_leader_starts`).
  After a rebuild at fit the reported start stays where the fit render put it
  at any zoom, and `UpdateViewDisplayGeometry` zoomed does not move it: frame
  item 2 re-zoomed read its ring exactly as placed but its leader starting
  4.19 mm from the centre inside a 4.89 mm ring, bit-identical on
  swmaker000008 and swmaker000005 (runs 20260928T144159300Z,
  20260928T145256004Z), while the same SetPosition printed its leader from the
  ring. Check a leader start only on the read right after `SetPosition`.
  Zoomed, the ring centre snaps to the window's pixel rows. An anchor-to-ring
  offset read inside the window misses the placed ring only by the choice of
  the two rows bracketing the target, under a pixel; read with the ring some
  50 mm above a 24 mm zoom, it was up to two rows off, and frame item 5 landed
  1.59 and 1.89 px high (2026-10-01; run 20261010T073339590Z). Bring a ring
  inside the zoomed window (place it at fit first) before reading the
  anchor-to-ring offset zoomed.
- **Generated native caption separators inherit document font sources.**
  The rocker R15 native failure (artifact 3130) retained a standalone space
  between `SCALE` and its ratio at **0.00635 m**, despite the documented
  annotation rich-text reset and a successful local 3.5 mm write. Its existing
  Manufacturing Notes displayed uniformly at **0.0035 m in Century Gothic**;
  `GetTextFormat(0)` agreed, with `GetUseDocTextFormat(0) == True` and
  `IsHeightSpecifiedInPts() == False`. A local caption-format write therefore
  does not prove that generated separators changed.
  [`IAnnotation.GetTextFormat`](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotation~GetTextFormat.html)
  also warns that its format may not represent embedded rich text.

  Source the height and face from **every** uniform, positive native
  [`IDisplayData.GetTextHeightAtIndex`](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDisplayData~GetTextHeightAtIndex.html)
  and `GetTextFontAtIndex` fragment of the existing Manufacturing Notes.
  Only then obtain its actual `ITextFormat`, require matching metre height,
  face, and native height authority, and pass that **unmodified format** to
  the drawing's
  [`IModelDocExtension.SetUserPreferenceTextFormat`](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SetUserPreferenceTextFormat.html).
  Create and seat that same linked source note at its existing coordinates
  after the front/property view exists, and pin the inherited defaults
  **before creating D/E's native detail views and circles**. Existing generated
  runs are not documented to re-read changed defaults; do not rely on a late
  font write to repair them.

  The official **Document Properties > Views** table scopes
  `swDetailingViewTextFormat` **18** to `swDetailingNoOptionSpecified` **0**.
  **Document Properties > Views > Detail** scopes
  `swDetailingDetailTextFormat` **3** and
  `swDetailingDetailView_Name/Label/Scale/DelimiterTextFormat` **42/43/44/45**
  to `swDetailingDetailView` **301**. Pin and read back exactly those six
  `(preference, option)` pairs. Do not substitute option 0 for detail-specific
  slots or use legacy `swDetailingDetailLabelTextFormat` 9, whose document
  scope is not documented. Numeric values come from installed SW2026 Interop
  enum literal metadata (34.4.0.78), not a claim about an exact worker seat.

  Each setter must return actual `True`; immediately obtain a fresh
  [`IModelDocExtension.GetUserPreferenceTextFormat`](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~GetUserPreferenceTextFormat.html)
  and check its height, face, and `IsHeightSpecifiedInPts()` authority.
  Repeat readbacks after rebuild/redraw and after creation/normalization.
  Document formats do not expose annotation `useDoc` authority; do not invent
  that boolean. The audited generated SW2026 bindings make `Extension` a
  read-only dispatch property and Get/Set methods (DISPID 166/167), with
  `(I4, I4)` and `(I4, I4, DISPATCH)` inputs and no out parameters; the setter
  returns BOOL. No application/seat-global preference is changed.

  Require the resulting native caption's actual `GetUseDocTextFormat(0)` to
  be `True`, `HasMultipleFonts` to be `False`, and **every native fragment**
  (including blank spaces) to match the source height and face. Preserve the
  complete linked string, `<VLNAME>/<VLLABEL>/<VLSCALE>/<VLSCALEV>` identities,
  order and counts, resolved native glyphs, caption identity, native view
  ownership, scales, and view/caption positions. `INote.GetText` returning
  spaces is not resolved glyph proof. Source note format/content/position
  must remain unchanged; never replace it with a fixed size or app default.
  Parent-circle letters retain their existing local
  [`IDetailCircle.SetTextFormat`](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDetailCircle~SetTextFormat.html)
  normalization and independent `GetDetailCircleInfo2` height readback after
  both writes, with native label/position/ownership guards. Uniform caption
  inheritance, especially the generated separator, still requires farm
  proof; passing preference readbacks alone is not success. Retain later
  whole-string stability and fatal clearance guards, and capture refusals
  before closing the seat. The rocker keeps E at Y110, the fatal 3 mm air
  requirement, and its 4 mm caption target.

- **Native detail-circle arrays describe allocation, not just used records.**
  The rocker R16 farm run `20261012T230027778Z-c441f84fade64106b64bfe9537883c2b`
  at `556f06825161ed9fde16f434d78da13638ea694f`
  ([native evidence](https://github.com/pedropaulovc/harmonic-analyzer/pull/1354#issuecomment-6134936171))
  verified both complete 3.5 mm Century Gothic captions with
  `HasMultipleFonts == False` and both 3.5 mm source-circle formats. Its only
  refusal was the assumption that the parsed circle records must consume
  the entire `GetDetailCircleInfo2` array: the native array contained **69
  finite doubles**, with count 2, two complete 16-double zero-arrow records,
  both displayed heights 0.0035 m, and **36 unused zero doubles**.

  Read the authoritative
  [`IView.GetDetailCircleCount2`](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~GetDetailCircleCount2.html)
  return/out pair `(count, Size)` and require an actual two-integer tuple:
  count must be exactly 2 and `Size` must equal the complete info-array
  length. The official
  [Get Detail Circle Information VBA example](https://help.solidworks.com/2026/english/api/sldworksapi/Get_Detail_Circle_Information_Example_VB.htm)
  asserts count equals `info[0]` and `Size == UBound(info) + 1`, then walks
  only the declared circles/arrows; it does **not** assert the final record
  index equals the allocated length. Follow that count-driven traversal,
  rejecting every nonnumeric/nonfinite value, incomplete 16-double circle
  header, nonintegral/negative arrow count, and incomplete nine-double arrow
  record, including the last circle's arrows, before using the shared decoder.
  Accept unused declared allocation **only if every value is exactly zero**;
  nonzero data, NaN, garbage, and undeclared appended zeros remain fatal.
  Zero-filled unused allocation is observed R16 evidence, **not a documented
  zero-padding guarantee** or an assumed fixed capacity. Keep the existing
  1e-7 m displayed-height tolerance and original-exception forensic capture.

## Longer parent-scoped identity callouts

Budget the whole printed block, including its shelf, rather than just the
dimension anchor. The fulcrum shaft's `SETS MHA-CH-VN-55` block measured 44.9 mm
wide in the native PDF and overran the inner border by 0.19 mm. Its recipe moves
the anchor 4 mm left; the containment check uses a 45 mm envelope and retains
the 3 mm border clearance and greater-than-5 mm tip clearance.

For a linear dimension whose identity/function text no longer fits between
the witnesses, use `offset_dimension_text` to put the complete block on a
native shelf, as on the cone-tip block's `9.750` engagement dimension. Preserve
the value, precision and attachments; audit the new text box and leader, then
check the native PDF for line strikes. This is not the radial/diametric
`OffsetText` case below.

Full parent-scoped Numbers can also grow a BOM without changing its column
widths or font. On MHA-SM-00 sheet 2, the native table bottom moved from
179.495 to 158.6533 mm after the identity cutover; its fixed caption at
Y176 mm then overprinted rows 8–9. Measure the rebuilt top-left table's
annotation position minus the sum of `ITableAnnotation.GetRowHeight` values,
as the magnifier package does, rather than estimating from the nominal row
pitch. The summing caption follows that measured bottom with a 6 mm anchor
offset. Its `INote.GetExtent` must prove at least 4 mm below the table and
remain clear of the border/title block both on placement and after the final
rebuild. Keep every BOM row, complete Number, caption text and native font;
log the measured table bounds, caption bounds and air for native acceptance.

## Refusal catalogue — do / don't

**a. `IDisplayDimension::OffsetText` on a radial or diametric dimension.**
Don't: set `OffsetText = True` on a radius/diameter dim and expect the text to
leave the dimension line. It reads back False — measured on tube-frame's Ø5.00
cross-hole callout (`{'Diametric': True, 'OffsetText': False, ...}`), which
failed the recipe's own assertion "cross-hole callout text did not leave its
dimension line". `types/IDisplayDimension/OffsetText.md` says why: "Because
radial and diametric dimensions are already attached to the end of a leader,
this property is not available for these types of dimensions."
Do: the text is already leader-attached, so place it with
`IAnnotation::SetPosition2` and shape the LEADER instead of toggling offset.
What actually fixed the 93 mm tail on that callout was
`IDisplayDimension::LeaderVisibility = 3` (`swLeaderLineNone`,
`enums/swLeaderLineVisibility_e.md`): the tail disappeared and the arrowhead
survived — `IDisplayData::GetArrowHeadCount` stayed 1
(`types/IDisplayData/GetArrowHeadCount.md`). `LeaderVisibility = 2`
(`swLeaderLineSecond`) changed nothing, and `SetPosition2` alone re-reported the
same position — the tail was the dimension LINE pair, not a leader. Also on the
dimension: `ArcExtensionLineOrOppositeSide` (radial only,
`types/IDisplayDimension/ArcExtensionLineOrOppositeSide.md`), `DisplayAsLinear`
(render a diameter as a linear dim, then the linear rules apply —
`types/IDisplayDimension/DisplayAsLinear.md`), and `SetBrokenLeader2(UseDoc,
Broken)` (`types/IDisplayDimension/SetBrokenLeader2.md`). Re-read the geometry
from `GetDisplayData` afterwards; the render is not the evidence.

The rocker's abandoned angular-offset attempt is not a reusable placement
contract. R26's false-offset 109-degree seed did not determine its final
connector: offset restored the old stubs and landed at 105.690091123 degrees,
inside its own arrowhead. Its boxed BASIC carrier also overhung the lower
border, unlike the native thumbnut's unboxed carrier. Pedro's R27 ruling
removes the rocker angular dimension and its dedicated offset/seed/route
guards instead of adding another layout mechanism. The source-derived
10.46° BASIC remains in Manufacturing Note 1; no datum, geometry or tolerance
changes accompany that presentation-only removal.

The later #1020 follow-up restores the land's BASIC angle on **Detail E** as
the imported `TipLandAngle@StrapProfile`, not the abandoned front-view offset
dimension. Its native driven angle measures the actual radial land against a
vertical construction ray in the part sketch; the drawing checks the angular
type and magnitude of its native radian readback with the builder's `1e-8`
radian tolerance before adding the BASIC box and `2X` count. The
construction ray changes neither the solid nor the profile zone. Do not
substitute a typed angle or ambiguous radial-land prose for this model-owned
dimension.
Seat E's native linked caption 8 mm left of the crop centre so the angle's
vertical witness does not graze `DETAIL E`; retain the independent 3 mm
crop/title-rule clearance guards and leave D's caption centred.

The common arc-centre location then left the general notes for the feature
it governs (drawing-guidelines rule 7): `TOP_RADIUS_CALLOUT` (`CENTRE ABOVE A`)
is written as one R800 below-text row through the same strict
`SetText(4)`/`GetText(4)` readback `_dress_arc_radii` already used for R816's
`CONCENTRIC WITH R800`, and the notes are two lines (hub wall, built-up
permission). Only presentation moved: the source centre stays (0, 816) and
the pivot (0, 8), both anchored to x = 0 in `build_ch_rocker_arm`; the native
BASIC 8, R800, R816, the 2X angle and the profile-frame control scheme are
unchanged, and no 808 driving dimension or new band exists. R800's text
request moves from 132/156 to **120/160 mm**. The base native audit shows the
left 132.76 BASIC box reaches y = 149.8 mm: a two-row R800 callout at y = 156
would route its shoulder through the box. One row and the 4 mm raise leave
the projected shoulder about 3.6 mm above it. This projection still requires
fresh native proof; request coordinates are not ink bounds. Provenance: the
reviewed main PDF is
`c70f077f3848ef1eb32a2f94129d33c39cadd7f2e3250587e6a0c73147bc3510`, the
prior #1704 SHIP PDF
`8adf355ae1fdb32ed066d041098201f16b142881f288c3664033ebaf3747d2a6`. The
earlier judge accepted the off-sheet centre as a note; the fresh judge holds
rule 7 (state it at the feature). This change claims no native acceptance
and reran no review; Detail D's faceting stays the shared, non-gating #1141.

**b. `IView::SetDisplayMode4` refusing HLR on a native detail view.**
Don't: read `False` as "detail views can't do HLR". Two causes, both documented
in `types/IView/SetDisplayMode4.md`: (1) `UseParent = True` — "If UseParent is
true and a parent view exists, then this method's Mode, Faceted, and Edges
parameters are ignored"; (2) a same-mode set is a no-op that also returns False.
Do: pass `UseParent = False` and assert the RESULT, not the return value:
`GetUseParentDisplayMode()` must read False and `GetDisplayMode2()` must read the
mode you asked for (`types/IView/GetUseParentDisplayMode.md`,
`types/IView/GetDisplayMode2.md`). This is what
`_drawing_view_display.set_hidden_lines_visible` does: `SetDisplayMode4(False, HLR,
...)`, verify, then `SetDisplayMode4(False, HLV, ...)`, verify. There is no
`UseParentSettings` property — not found in the bundle; the flag is the first
argument of `SetDisplayMode4`. Modes are `swViewDisplayMode_e`: 1 wireframe
(= hidden lines visible), 2 hidden lines removed, 3 hidden lines greyed.

**c. Moving a section/detail view to another sheet.**
Don't: assign `IView::Sheet` — it is get-only (`types/IView/Sheet.md`), and no
`IView::SetSheet` / `IDrawingDoc` view-move method exists in the bundle
(`IDrawingDoc` has `PasteSheet` and `ReorderSheets`, which move whole SHEETS;
`IModelDocExtension::MoveOrCopy` moves selected annotations/sketch entities
WITHIN a sheet — `types/IModelDocExtension/MoveOrCopy.md`). **No API to relocate
an existing view across sheets was found in the bundle.**
Do: re-create the view on the destination sheet from its own definition and
delete the original — `IDrawingDoc::CreateSectionViewAt5` /
`CreateDetailViewAt4` on the new sheet, then re-apply its display mode, scale
and annotations. In a recipe this is cheaper than it sounds, because the recipe
already owns the code that created it: parameterise the sheet, do not migrate
the object.

**d. Per-variable callout precision.**
Don't: `IDisplayDimension::SetPrecision3` for a hole callout's primary
precision. `types/IDisplayDimension/SetPrecision3.md`: "This method does not
support setting the Primary and PrimaryTol values for hole callouts."
Do: `ICalloutLengthVariable::Precision` and `::TolerancePrecision` per variable
(`types/ICalloutLengthVariable/Precision.md`), reached through
`IDisplayDimension::GetHoleCalloutVariables`. Dual/dual-tolerance values are
global and still go through `SetPrecision3`, as both pages state.
A REF depth in a hole callout goes the same way: into the DEFINITION, not the
resolved text. A callout's four definitions read back through
`IDisplayDimension::GetText` parts 5..8 (`swDimensionTextParts_e`: prefix,
suffix, callout above, callout below) and are written through parts 1..4
(`SetText(part - 4, ...)`; `draw_fr_harmonic_base._set_cross_tap_callout_text`
writes 3 and reads back 7). The output fixture marks its thumb-screw tap's
thread depth REF by bracketing the VARIABLE, `(<hw-threaddepth>)`, in the one
definition that holds it, then reads all four back and requires exactly that:
one bracketed thread depth, the drill depth's `<hw-tapdrldepth>` once and
bare (it governs), the process prefix intact
(`draw_mg_output_fixture._reference_thread_depth`). The printed `(10.1)` stays
the model's value and follows it; typing the number would not. The thread's
extent is the note's business (`FULL THREAD TO ROD BORE.`), not a band on the
REF value.

**e. The hidden-line regen trap after annotating.**
Don't: trust `GetDisplayMode2` / `GetFacettedHlrDisplay` to mean the EXPORT will
carry the dashed edges. An annotation attached after placement leaves the HLV
edge set unregenerated, and `IView::UpdateViewDisplayGeometry` does not rebuild
it — that method "accesses new view geometry before Microsoft has repainted the
window" (`types/IView/UpdateViewDisplayGeometry.md`), which is a repaint
concern, not a regen. `IModelDoc2::GraphicsRedraw2` is display-only and marked
Obsolete in favour of `IModelView::GraphicsRedraw`
(`types/IModelDoc2/GraphicsRedraw2.md`).
Do: re-assert the display mode AFTER the last annotation on that view, with a
real mode CHANGE (HLR then HLV), then verify with `GetDisplayMode2` —
`_drawing_view_display.set_hidden_lines_visible` exists for exactly this and is
idempotent by design.

**f. A partial section view printing olive with no hatch.**
Don't: chase hatch flags first. `IDrSection::GetAutoHatch` /
`SetAutoHatch` / `ScaleHatchPattern` control the pattern
(`types/IDrSection/GetAutoHatch.md`), but an unhatched olive face is the
signature of a cut that did not close — the section line does not span the
view, so SolidWorks renders an uncut face instead of a section.
Do: read `IView::GetSection` -> `IDrSection`
(`types/IView/GetSection.md`) and check `GetPartialSection()`
(`types/IDrSection/GetPartialSection.md`). If it reads True and you did not ask
for a partial cut, the section line is short: extend it past both silhouette
edges, or call `SetPartialSection(False)`
(`types/IDrSection/SetPartialSection.md`). `GetLineInfo` / `IGetLineSegmentCount`
give the line's actual extent to compare against `IView::GetOutline`.
(`ISectionViewData` is the MODEL-side section-view feature — `FirstPlane`,
`GraphicsOnlySection` — not the drawing section; do not reach for it here.)
When a short line is what you WANT — an ASME removed section through one rail
of a symmetric frame, not that rail and its unannotated twin — ask for it:
`_drawing_sections.create_section_view(..., partial=True)` passes
`swCreateSectionView_Partial` (0x10) to `CreateSectionViewAt5`, SolidWorks
sections just the span, the cut closes, and `GetPartialSection()` reads True by
design (top-frame H-H/E-E; the recipe's `_assert_section_display(removed=True)`
pins it). Centre the line's span on the profile you dimension: a partial section
is centred on the cut span, so `view_xy` places that profile, not the old
full-cut centre.

**f2. Face labels on a pictorial read as leaders crossing the view.**
Don't: insert the label as a sheet note. A note whose leader ENDS on a view
is, to the audit, a sheet-owned leader crossing that view (12 findings for six
labels), and it does not move with the view.
Do: insert it while the view is active — `add_leader_note(..., view=view)`
activates the view first and proves `IAnnotation::OwnerType ==
swAnnotationOwner_DrawingView` (0) — so the view owns it, lists it under
`GetAnnotations`, and the audit exempts the one view a leader is allowed to land
on. `place_pictorial_sheet` does this for every octant face label.

**f3. Face names: the print's or the machine's?** Pictorial face labels are
the PRINT's (FRONT = the face `*Front` shows, +Z; RIGHT = +X) — the ASME
orientation-key reading every fleet caption follows. The MACHINE's front is
model −Z (`dimensions.yaml` "Z = depth (− front)"), and model-owned dimension
names carry that word (`StudFrontZ` → "FRONT HANGER Z"). A blind reviewer reads
the two as conflicting locations; resolve it with one key note on the priming
sheet saying which is which (top-frame `ORIENTATION_KEY_TEXT`), never by
flipping the model names.

Assembly opening views and fitter projections have separate contracts. MG's
standard Front faces machine −Z, matching HA; its named fitter views preserve
the back/left inspection and exploded projections independently of that remap.

Named-camera placement does not establish the source model's active
configuration. `NameView`, `ShowNamedView2` and
`CreateDrawViewFromModelView3` document the view/orientation, while
`IView.ReferencedConfiguration` selects the drawing view's configuration;
`IModelDoc2.ShowConfiguration2` separately activates the source configuration.
MG's native drawing at `d58d05d82` reached the wheel balloons with the view in
`Default Simplified`, zero readable explode steps and the source in `Default`.
That proves the configuration mismatch, not that the named camera itself
reactivated a captured configuration. The former recommendation to activate
the source configuration around the balloon reader is superseded by r7 at
`6bb872b2b` (artifact225): the source was clean at scope entry, 137.8 s, then
dirty at 138.3 s immediately after
`ShowConfiguration2("Default Simplified")`, before any balloon operation.
Restoring the configuration cannot undo that source mutation.

Documented `IConfiguration` explode-step reads are configuration scoped, but
native reads still returned zero steps. `ShowExploded2` applies to the current
configuration; there is no evidenced immutable native-API workaround for this
MG path. Do not activate the model or show/collapse its explode during drawing
generation. The builder instead verifies the native presentation and stores
aggregate world translations in metres for **every** top-level instance,
including zero offsets, separately for `Default` and `Default Simplified`.
These are file-level custom properties, authored before the builder's normal
save and bound to the configuration, named view, explode-step count and a
required `contract_sha256`. This SHA-256 fingerprints canonical JSON of the
ordered current `plan_explode(instances)`: each step's label, raw member
selectors, axis, distance in millimetres and resolved component names.
The assembly remains saved collapsed in `Default`.

The drawing reads those properties through `GetCustomInfoValue("", name)`,
validates their owner/view/step count, exact current instance membership and
fingerprint against the current resolved explode contract, and passes the
referenced drawing configuration's translations to associative edge balloons.
Changes to axes, distances, member selectors or resolved instance membership
therefore reject stale metadata even when the step count is unchanged.
This proves recipe freshness, not detection of external native explode edits
that leave the stored metadata and current recipe unchanged.
Missing or invalid metadata fails with a request to rebuild
`assembly:mg_magnifier`; no nominal-spec or direct-step fallback is allowed.
Simplified drawing views, original camera geometry and final associative
balloon landing proofs remain required. Place/configure views, isolate groups,
set tangent edges and fit before binding the complete BOM to the whole-assembly
reference; drawing-view configurations remain final once the BOM binds.

The narrower native run at PR1764 head `e3d66daf9` (artifact198) first records
`magnifier source went DIRTY after lever ClampStation above callout` at
31.8 s. Earlier checkpoints, including model-item import/curation, are clean.
That checkpoint immediately followed
`_drawing_dimensions.set_dimension_callouts` →
`IDisplayDimension.SetText(3, "CLAMP STATION: SETS MAGNIFICATION")`.
It identifies a source save-flag mutation, not a geometry change. The
[native source-hash controls](pipeline/evidence/vm2-datum-placement/source-hash-cause.md)
already reproduce imported/source dimension identity (`IsSame == 1`), callout
`SetText` dirtying the source, and drawing `SaveAs3` persisting that mutation.

The API ownership matters: `IDisplayDimension.SetText` edits the native
dimension's text, returns void and has no drawing-only ownership argument.
`swDimensionTextParts_e` uses 3/4 for the above/below callout compartments;
neither replaces or hides the native numeric value (unlike `SetText(0, ...)`).
`AddDisplayText` is not a persistent replacement: its documented graphics are
temporary and revert when the dimension changes. The drawing-only
`DimensionLowerText` argument to `IModelDocExtension.EditDimensionProperties`
is a separate lane, not the required above/below callouts. No proven
drawing-only setter preserves these exact callout compartments.

All four MG setting callouts now belong to the assembly model:
`mg_magnifier_assembly_spec.SETTING_CALLOUTS` owns the exact text and native
compartments for PressGauge, Endshake, ClampStation and FixtureDrop.
`build_mg_magnifier_assembly` authors them beside their reference dimensions,
strictly reads each compartment back and marks/blanks the chains before its
normal assembly save, following `build_pd_transgear_arm`'s model-text pattern.
The drawing only imports the associative native dimensions and checks their
inherited text, precision and stack tolerances, initially and once settled.
It must reject a stale assembly lacking the text, not stamp it during drawing
generation. Setting callout wording now re-keys `assembly:mg_magnifier` and
requires rebuilding that source and its drawing; BOM/step/check prose remains
drawing-only and must not enter the assembly builder's import closure.

The temporary per-operation crop/settings checkpoints and synthetic
checkpoint-attribution tests are superseded by this native evidence. Keep
read-only `magnifier.source_save_flag` phase telemetry, the initial clean
source guard, and the final fail-closed refusal before drawing `SaveAs3`.
MG also captures a streaming SHA-256 baseline before opening the source and
always logs expected/actual source SHA-256 plus `GetSaveFlag` in native
`task.log`: before finalization, in settled checks immediately before
`SaveAs3`, and after finalization (including a failed finalization). Either
different bytes or a dirty flag fails closed. The post-finalization proof
also revalidates saved `Default`, collapsed presentation and metadata; if
finalization already failed, a proof failure is warned without replacing the
primary exception. These checks do not save, reset or repair the source.
Never save a dirty released source, clear its flag, replace native dimensions
with free-text notes, or assume identical text setters are harmless. The
immutable metadata contract and offline fakes do not establish byte/source
cleanliness or a native pass. Native acceptance still requires the rebuilt
assembly's callout and metadata readbacks, saved `Default` collapsed state,
simplified views, printed dimension text, associative edge balloon landings,
and unchanged source identity throughout drawing generation.

MS's working pose has the thumbscrew above the stick, both standalone and
parked in HA. Its graduated face remains against the fixed clamp wall and is
therefore underneath; the named underside inspection view shows that scale.
The HA parking height comes from the rotated assembly envelope, not the
thumbscrew head. Native orientation checks must inspect component axes, not
infer physical placement from a camera.

**g. Picking one of four identical bores.**
Don't: `SelectByID2("CylinderFace", "FACE", 0, 0, 0, ...)` and hope. A generated
face name is not stable across rebuilds, and four identical bores make the name
ambiguous.
Do: pick by COORDINATE, decided at build time from geometry.
`IBody2::GetFaces` (`types/IBody2/GetFaces.md`) plus `IFace2::GetBox` ->
`[XCorner1, YCorner1, ZCorner1, XCorner2, YCorner2, ZCorner2]`
(`types/IFace2/GetBox.md`) identifies which bore is which by position — note its
warning that the box is approximate and "may vary after rebuilding", so use it
to DISCRIMINATE between well-separated candidates, never as a dimension. Then
select with `IModelDocExtension::SelectByID2(Name="", Type="FACE", X, Y, Z, ...)`
(`types/IModelDocExtension/SelectByID2.md`) or
`IModelDocExtension::SelectByRay` (`types/IModelDocExtension/SelectByRay.md`),
which "selects the first entity ... intersected by a ray" and, unlike the
obsolete `IModelDoc2::SelectByRay`, re-selects "the original entity ...
regardless of the viewing transform". In a DRAWING, "use model space view to
determine the selection vector" — project through `IView::ModelToViewTransform`
(get-only, `types/IView/ModelToViewTransform.md`), which is what
`_drawing_projection.model_point_in_view` wraps.

**h. A datum tag that will not leave its attachment.**
Don't: attach a datum tag to a bore by selecting the edge OBJECT
(`add_datum_feature(entity=visible_circle_edge(...), shoulder=True)`) and then
loosen the placement guard until the build passes. `SetPosition2` returns True
and the tag stays at its default drop on the far side of the bore — crank_pinion
datum A read 60.3 mm from its request and printed on top of the Ø dimension
leader; the 80 mm `position_tolerance_m` that let it through was added in the
same commit as the `entity=` pick (73a3ceb1). fr_top_frame datum B, attached to
its scanned dowel-hole circle by `edge_entity=`, read 37.6 mm from its request
(farm run 20261009T164113078Z); `test_fr_top_frame_drawing` now refuses any
`add_datum_feature` edge-object attachment to a `circle_at` circle.
Do: pick the edge by SHEET POINT (`edge_xy=bore_top`, as cone_gear and the
transgear recipes do); the same tag then reads 8.0 mm from its request and
prints there. Keep the guard at its 20 mm default and tighten it only where the
leader itself is shorter than 20 mm (a snap-back would pass otherwise:
channel_lever, platen_guide, rocker_arm, cone_tip_block E).

For a datum defining a width's median plane, keep the native attachment to
the width dimension, not either side edge. On `fr-top-frame` sheet 2,
run `20261014T055244900Z` proved D stayed on that dimension but ignored the
requested `(142, 95)` mm placement: its native box was at X122.7–129.7,
Y106.0–113.0 mm and overprinted **CROSSBAR FLANGE**. Move the associative
width text within its existing clear band instead of loosening attachment
checks. Read both annotations' native display data after rebuilding and
require 2 mm between D's ink and **each** width-text row; a combined two-row
box falsely collides because the value lies left of D while the suffix lies
below it. The local recipe check refuses missing display reads or estimated
text widths; the fleet audit's REPORT mode and nominal datum fallback stay
unchanged. A native build and eye pass must still prove the new placement.

**i. Moving a leader after the symbol is inserted.**
Don't: land a surface-finish symbol's or feature-control frame's leader with
`IAnnotation::SetLeaderAttachmentPointAtIndex`. It returns True, moves the
tip, and DETACHES the annotation: `GetAttachedEntityCount3` goes 1 -> 0 and
`GetAttachedEntityTypes` empties, while `ISFSymbol.IsAttached` /
`IGtol.IsAttached` keep reading True, `GetLeaderCount` stays 1 and
`IsDangling` stays False (13 surface finishes on the #1105 sfprobe leaves;
6 frames on farm run 20260928T080412049Z, re-set to the tip they already
had). Those three reads are not attachment evidence.
Do: select the entity, call `ISelectionMgr::SetSelectionPoint2(1, -1, x, y,
0)` with the sheet landing, THEN insert (`InsertSurfaceFinishSymbol3`,
`InsertGtol`); after the rebuild require `GetAttachedEntities3`,
`GetAttachedEntityCount3` and `GetAttachedEntityTypes` to agree on ONE entity
of the selected kind, and require that entity to BE the selected one
(`_drawing_attachment._assert_attached_to`). `ISldWorks::IsSame` proves an edge or
face; it reads 0 for every silhouette, so a silhouette is proved through
`ISilhouetteEdge::GetFace` — the selected and attached silhouettes' faces
passed IsSame on all 16 silhouette finishes and frames of farm run
20260928T085009031Z, and `IModelDocExtension::IsSamePersistentID` on the
drawing agreed. The two flanks of one cylinder share that face; the leader
landing readback (`GetLeaderPointsAtIndex`) tells them apart, and it must be
within 1 mm of the request: 13 of 14 landings on run 20260928T084216466Z were
within 4e-8 m, the pinion-bracket pivot-bore finish re-solved 0.61 mm along
its edge. A pointer note (`add_leader_note`) has no attachment to lose (0 -> 0
on the same run) and keeps the call. Where the pick and the landing differ,
the leader may end on the PICK (pinion_bracket pivot finish, 4.6 mm off), so
pick the edge at the landing point.
The owning-face proof can also refuse a seemingly attached silhouette:
the magnifying lever's capsule OD on retry10 (source `644308e47`, launcher
`20261012T164103041Z`) read one type-46 entity, one leader and not dangling,
but its attached silhouette's face failed `IsSame` against the picked one.
Keep that refusal. Resolve the part-owned finish-control face on the view's
`ReferencedDocument` and attach as a FACE with the pre-insertion selection
point (`draw_dt_pinion_arbor`): `IsSame` proves
the actual cylinder and the 1 mm landing readback still pins its flank.

An entity-attached `InsertNote` can use the same pre-insertion selection-point
pattern. On the oblique hold-down stud, coordinate hit-testing missed the
resolved factory-rim edge. Selecting that exact edge, setting
`SetSelectionPoint2` and then inserting the note succeeded on `f441b8b25`.
Both rim and barrel-outline notes passed exact attachment identity/type and
settled leader-tip checks within 1 mm. This differs from the unattached
`add_leader_note` pointer above; do not move an attached tip after insertion
and assume its ownership survived.

**j. A fresh detail view whose readbacks lag its ink.**
Right after `CreateDetailViewAt4` + rebuild, `IView::GetOutline` is centred
on the request while `ModelToViewTransform` projects the circle centre 99 mm
away and `Position` reads 99 mm from where `SetViewPosition` later has to put
it (cone_swing_platform detail B, leaf 20260928T075849Z-1-882b4704). A loop
that "corrects" the projection moves a correct view off the sheet target and
needs a second move to recover; on three #1105 leaves it never did.
The cone-swing workaround placed by the outline centre, then re-read the
projection before hanging anything on the view. Do not generalize that
centre: the profile fixture's outline was 5 mm off its physical bore centre.
Refresh parent and detail with `UpdateViewDisplayGeometry` before reading
their transforms or the one outline used for containment/classification.
Use `_drawing_detail_projection.settle_detail_projection` for projection
settling; don't settle it with a count of `EditRebuild3` calls. Rebuilds,
re-reads and idle time each catch the transform up only some of the time.
Detail B's first read was stale in 41 of 41 leaves, and it was still stale
after three rebuilds on 4 of them (#1336). With the barrier in front of every
read, the cone-gear-shaft tip detail read current first time in 15 of 15 leaves,
against 3 of 35 without it. On seat-probe leaf 20261013T052718Z-1-4b76316f,
20 throwaway details all read stale first and all 4 behind the barrier then
read current. The same leaf's real detail B, settled the old way, stayed
stale through three rebuilds and failed. The settle span records `reads`,
`rebuilds`, `waited_s` and the unrefreshed control offset. If the barrier ever
fails to refresh the transform, the span shows it as more than one read,
inside a time budget.
The historical swing log also shows a transient 38 x 40 mm outline becoming
68.776 mm square around its 48 mm circle; even containment is unreliable if
the outline is read before the display-geometry barrier.

For shared layout collection, `_drawing_detail_crop.read_circular_detail_crop`
uses the persisted complete sketch circle, its sketch inverse, and the
parent/detail native transforms and scale ratios. `IView.Type == 3`
(`swDrawingDetailView`) selects this path, not the generated view name.
Missing, duplicate, invalid or non-contained crop data raises with the view
name; it never falls back to `GetOutline` or disappears through an attempted
read. The geometric crop box must be contained in the same refreshed native
outline with **exactly zero slack**: equality is allowed, one ULP outside
refuses, and no clipping or guessed padding is applied. Log both boxes.
Only the view's occupied box changes. Keep its original outline for small
note classification, and retain all annotation/table/title-block/leader
objects, scopes and collision policies. Incidental coverage from a padded
view box is not the annotation's contract; the native/PDF audit still reads
those objects. Every other view kind retains its existing outline.
The rocker additionally compares all four shared crop edges, in both
directions, with its independent source-fence formula within the existing
50 micrometres. That check must stay: synthetic math fixtures do not prove
the new cross-view inverse step on a real seat. No new optional ownership,
broken-view, depth-parallelism or outline-style probes are implied here.
A section's projection can also lag after `IDrSection::SetReversedCutDirection`:
the reversal stood thumbnut A-A rim-up, yet `SetViewPosition` on its
creation target left the seat projected one nut length (48.3 mm at 3:1)
above where a centred rim-up section puts it (run 20261001T142942518Z).
`draw_pd_transgear_thumbnut._centre_section_outline` re-centres by the outline.

**k. A datum or dimension picked by sheet coordinate where two lines meet.**
Don't: hang a datum tag or a locating dimension on `SelectByID2("", "EDGE",
x, y)` at a point where a second visible line runs within the hit-test
radius. The pick resolves to whichever line SolidWorks tests first and the
sheet prints a correct-looking symbol on the wrong feature: summing-lever
datum B, aimed at the plate's end face, landed on the end rib's flange 5.08 mm
inboard, and the BASIC start-Z dimension off the same pick read 3.35 for 8.43
(#1105, run 20260928T090231982Z) — no error, only a print that would put the
hole pattern 5 mm from where the casting has it.
Do: name the edge (`scan_view_edges` + an exact model-space filter, or
`ViewEdges.circle_at` for a rim) and pass it as `edge_entity` / `entities`;
`add_datum_feature` then proves the tag sits on THAT edge by `IsSame`
(`_assert_attached_to`, `expected_leaders=0` — a datum tag's triangle is not
a `SetLeader3` leader). A datum that must keep its coordinate landing point
passes the named edge as `expected_entity`: the hit-test's selection must be
that edge before insertion, so the wrong-neighbour case cannot pass by the
selection and the readback agreeing with each other. `assert_dimension_measures`
takes the same two named entities and proves the dimension's attached
entities ARE them (`IAnnotation::GetAttachedEntities3` + `IsSame`, no extra
attachment, not dangling) before checking the value against the spec
constant — the value alone accepts any of a hole row's equal-pitch pairs or
any rim at the row's X. `entities=None` is value-only and the call site says
why. Every datum and dimension of summing-lever's pattern definition (A, B,
76.20, 39.85, 8.43, 7.06) is identity-checked. A coordinate-only datum
(`edge_xy` alone) is proved only to sit on what its hit-test returned; it is
acceptable where no second line runs inside the hit radius of the pick, and
`draw_ch_rocker_arm._require_datum_on_bore` shows the alternative, a recipe-side
`IsSame` readback against the named bore.

For FR-00's nameplate inset in section B-B, model geometry alone was not
attachment evidence. Farm run
`20261022T204612817Z-cd964f67d895402c96f536ac40ba51d8`
(`C:/src/farm-runs/fix1667`) selected `fr-nameplate-1` at machine
x=163/163, y=52.300, z=25 mm and `fr-harmonic-base-1` at x=167/167,
y=50.006, z=25 mm. The initial dimension read 4 mm and not dangling, but
the final rebuild returned dangling with attached types `()`.
Changing the component provider to `IDrawingComponent.Component` did not
fix that loss. Do not suppress the final guard or retry unchanged.

The API distinguishes
[`IComponent2.GetCorrespondingEntity`](https://help.solidworks.com/2026/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IComponent2~GetCorrespondingEntity.html)
(component context) from
[`IView.GetCorrespondingEntity`](https://help.solidworks.com/2026/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks.IView~GetCorrespondingEntity.html)
(drawing-view context). The FR recipe explicitly maps each ray-identified
component edge into B-B, then reverse-maps both entities into the same source
part with `IModelDocExtension.GetCorrespondingEntity2` and requires
`IsSame == 1`. Missing or unknown correspondence refuses; changing the
selection API is not a fallback. Share one drawing-component snapshot for
both targets and retain the batched body rays: walking every engraved edge
took 783 s, versus about 21 s for the ray path.

Before retaining a component edge across these rebuilds, obtain its
`IEntity.GetSafeEntity()` result; ordinary entity pointers are transient.
Check `IEntity.IsSafe` before every section mapping. The documented safe entity
retains model topology through rebuilds within this SolidWorks session, but is
invalid if its source entity is deleted. Keep the ray's explicit `IComponent2`
alongside it to identify the source part and occurrence; do not recover that
ownership through `IEntity.GetComponent`. Missing or unsafe handles refuse
rather than rematching similarly shaped geometry. This session-local proof
does not promise identity across close/reopen.

After creation rebuild and final rebuild, reacquire the section edges from
their model identities and use `assert_dimension_measures` to prove exactly
those two native attachments, not dangling, and the spec-owned 4 mm value.
Require native edge/linear types and membership in B-B's display-dimension
inventory too. Correspondence, selected view/instance and reference failures
stay in `drawing.inset_*` telemetry. Offline lifecycle regressions are not
native proof: require the farm's rebuilt/saved dimension, its ordinary PDF
colour and the complete-sheet comparison, not a nominal note or detached
sketch that merely prints the right number.

The bounded diagnostic at source `c0e403c5b1255e5839a572d839f25514d2447b6b`,
based on production `61a6fb0b53dc962955351559f8820de1f4662f01`, retained
its evidence under the `fr-inset-safe-context-diagnostic` failure namespace
(attempt `20261023T063410Z-1-e8160cfb`, receipt timestamp `20261023T063641Z`).
For both references, the component-mapped input's `GetComponent` was already
null **before** `GetSafeEntity`; the safe handle did not lose an owner.
`IView.GetCorrespondingEntity` supplied the full drawing instance. Both mapped
variants matched the original-main screen control by `IsSame == 1`, including
their source-part reverse correspondences, before and after rebuild.

All three native dimensions retained two exact attachments, measured
`4.000000010000034` mm, belonged to B-B and printed black after rebuild.
Nevertheless, `IAnnotation.GetAttachedEntityTypes` returned `[]` for **all**
three, including the working screen control. That empty legacy summary made
the diagnostic receipt's composite `passes` flags false; it was not evidence
of missing attachments. The production guard therefore reads each actual
`GetAttachedEntities3` object's `IEntity.GetType` and requires two edges.
The summary remains diagnostic telemetry only. Exact attachment identities,
`IsDangling`, native linear type, measured value and section ownership remain
required. No screen-control code or expensive diagnostic probing belongs in
the production recipe; a full production finalization/export still requires
its own farm proof.

**l. A datum named by a frame's datum identifier.**
Don't: name a pattern datum with `IGtol::SetDatumIdentifier` and take
`GetDatumIdentifier` as proof. On the knife mount (farm run
20261009T171439353Z) it read "B" back before and after the rebuild and the
sheet printed no B, while the tap and bore frames referenced A|B. The API
help (`types/IGtol/SetDatumIdentifier.md`) says only that it "sets the name
of the datum being defined"; the frame XML schema has no node for it.
Do: insert a real datum tag on the selected frame
(`_drawing_gdt.add_frame_datum_feature`) and require the tag's attachment
to be that frame by annotation name. Select the frame with
`IAnnotation::Select2(False, 0)`: on farm run 20261009T182549169Z it
attached the knife mount's datum B to DetailItem354 (one entity, type 13),
where `IAnnotation::Select3(False, <view ISelectData>)` had returned False
(run 20261009T174542021Z). A tag on a frame is not placed in sheet
coordinates: on runs 20261009T182549169Z and 20261009T185542819Z,
`SetPosition2(0.1613, 0.2)` read back as (0.0, 0.2) and the letter printed
at (0.160, 0.413), 0.2 m above the frame's bottom edge and held to its
mid-width. Set y as the offset from the frame's bottom edge, then correct by
the printed letter's miss (display-data text position) in the space
`GetPosition` reports, and prove the final print. On runs
20261009T200747541Z and 20261009T204136744Z the first set printed 7.0 mm
low and one correction landed the letter 0.40 mm off; the sheet passed with
B under the ⌖Ø0.13|A frame. Read a composite frame's lower tier for its
datums only (`gtol_frame_datums`): it reads back with an empty
`<ToleranceSymbol>`. Also end the sheet with `assert_frame_datums_defined`,
which fails when any frame names a datum that no `IView::GetDatumTags`
label prints.

**m. A translation modifier proved by its XML alone.**
Don't: take `<Translation>true</Translation>` read back from
`IGtolFrame::GetSymbolXml` as proof that a frame prints "B▷". On the top
frame's slot frames (farm run 20261009T174542021Z) that flag printed
"B", "<MOD-TRANS2>", "[0,0,0]": SOLIDWORKS also prints the Datum dialog's
translation vector (`<TranslationValueI/J/K>`) at its zero default, 13.6 mm
of text that ASME Y14.5-2018 does not write.
Do: write the modifier as its symbol code after the letter,
`<DatumLetter>C&lt;MOD-TRANS2&gt;</DatumLetter>`, with no flag
(`_gtol_frame.TRANSLATION_GLYPH`). On farm run 20261009T204136744Z both slot
frames printed "<GTOL-POSI> | 0.05 | C | B | <MOD-TRANS2>", the triangle in
the datum's compartment and no vector. Every flag form tried printed a
vector (run 20261009T182549169Z): empty i, j, k printed "[0,0,0]", "false"
values printed "[false,false,false]", and SOLIDWORKS rewrote the flag after
the letter to the empty-vector XML. `add_feature_control_frame` still reads
the printed text items (`IAnnotation::GetDisplayData`) and fails on any
bracket or a missing or misplaced glyph
(`_gtol_frame.translation_print_problem`), logging `gtol.translation_print`.
`GetSymbolXml` reads the symbol code back unescaped,
`<DatumLetter>C<MOD-TRANS2></DatumLetter>`, which is not well-formed XML
(run 20261009T200747541Z); the frame-XML parser escapes `<MOD-…>`/`<GTOL-…>`
codes before parsing.

**n. Linear-dimension text requested outside its witness span.**
Don't: treat the requested x coordinate as the centre of a vertical dimension's
text. Outside the witness span, SOLIDWORKS hangs the rows away from the witnesses
under a shoulder. In `mg-magnifying-bracket` retry08 (source `ae7c8f4d6`,
launcher `20261012T111849499Z`), text requested at x 167 mm printed a shoulder
from x 146.6 to 167.0 mm, across the adjacent arm-depth column at x 147 mm.
Do: use the measured printed text boxes and shoulder endpoints, then derive the
column and row positions with clearance for the full hung text and outside-arrow
tails. A value-plus-callout row is wider than its number; do not centre either
by assumption. Recheck the native audit after the repair.
A HORIZONTAL dimension hangs differently: its rows print centred on the
requested x and its dimension line runs on under the lowest row to that row's
far end. The bracket's `10.00 / ARM WIDTH`, requested at x 88 mm beside its
x 129..139 mm span (retry09, source `8d6d2088a`, launcher
`20261012T124257186Z`), printed its rows over x 75..101 mm with the flange
width's witness at x 91 mm through both; the block's far end is the request
minus half the widest row, and every line that side of it must clear by a text
height. A span shorter than its row (the 6.35 mm hole-row offset, witnesses at
y 88.65 and 95 mm) requested AT a witness's coordinate prints centred on its own
column, the witness and dimension line through the text: request it beyond the
span so it hangs like the others.

The crank pin's `3.70` station is another short-span case: in the cached
sheet reviewed on 2026-10-19 (source `290d89a72`, PR #1651), its PDF text is
9.051 mm wide but its witnesses are only 7.4 mm apart at 2:1. Both witnesses
touch a digit when the text is centred between them. Move the native text
beside the span, allowing for its full width, the 6.35 mm outside-arrow tail
and neighbouring leaders; moving the same centred text up does not widen the
span. The part-specific offline placement contract bounds that envelope;
only the regenerated native audit and printed sheet prove the repair.

A genuine diameter hangs the same way and stops READING as one. The output
fixture's groove root Ø7 is a doubled distance (`AddSpecificDimension`
`swDiametricLinearDimension`, `Diametric` proven on the part); requested under
the view on retry09, SOLIDWORKS ran its dimension line 20 mm down out of the
groove into a 30 mm horizontal shoulder beside the bore's station, and the
machinist read the Ø as an axial length. Nest it instead: the root Ø's line
standing across the groove root to root, the spigot's Ø9 a pitch outboard
(20 mm), their texts staggered 5 mm either side of the axis so each breaks only
its own line, and prove the INK, not the glyph: `IDisplayDimension::Type2` is
6 or 15 (`swDiameterDimension`, as retry10's drawing import reports, or
the authoring `swDiametricLinearDimension`), `Diametric` is True, and
`IDimension::SystemValue` equals the root diameter, not its radius or some
other circle's diameter. Type14 is the single-distance radial linear form
and is refused. The measured strokes must put an extension line from each
root (starting 1 mm off it) out to the dimension line at the requested x
(`draw_mg_output_fixture._prove_groove_root_diameter`).

**o. A linear reference dimension formatted as a diameter.**
Don't: pass a linear offset to `set_reference_dimensions`: that helper supplies
the diameter prefix `(<MOD-DIAM>`. It printed the bracket's datum-face offset
as `(Ø3.35)` although the model dimension was a linear point-to-point distance.
Do: use the singular `set_reference_dimension` for a linear REF value; reserve
the diameter-specific helper for actual diameters.

**p. A generic Hole Wizard note census copied from a previous topology.**
Don't: retain a through-tap note count after changing the native feature, or
replace it with a universal “blind taps emit no note” rule. The fixture's old
through-to-bore feature emitted one `Tapped Hole` note; retry08's blind feature
emitted zero on the same worker, while other blind-tap drawings still emit one.
Do: keep the final note sweep and a strict part-specific measured census. Keep
the explicit resolved thread/drill callout and centre-mark proofs separate:
an autogenerated label is not the machining instruction. The template also
centre-marks an extruded annulus bore as the view is placed, not only Hole
Wizard holes: the bracket's collar end view arrived with one mark on the bore
(its extended lines end at the bore radius plus 2.5 mm) and the explicit
`auto_center_marks(holes=True)` printed a second, identical one over it
(DetailItem351/352 at (266.15, 180) mm, retry09; the washer's annulus end view
read 1 → 2 the same way in #913). Add none; prove the one on the axis
(`draw_mg_magnifying_bracket._prove_collar_centre_mark`).

The census is not a manufacturing count when the same recipe emits different
automatic labels. Summing lever already recorded view-dependent labels in
#1591. The PR1709 native leaf (`5c5d3e3b3672`, 2026-10-19) imported four
cosmetic threads into H-H and put all four on `TAP-THREAD-SECTION`, but H-H
emitted no `Tapped Hole` note: the package had seven notes, not the eight
another build had emitted. That is not evidence of a missing tapped hole.
Following top frame's per-view cleanup, summing lever deletes every actual
automatic label and reads back each view to reject survivors. Its final
settled check rejects any late label and requires the three original native
callouts (counter-anchor, spring-hole pattern, blind bracket taps) to remain
in their authored views, non-dangling, with unchanged native definitions.
The shared finalizer's exact-count contract is unchanged for other recipes.

**q. A standard view placed as-is is not necessarily in projection.**
Don't: assume `*Right` beside `*Top` makes a third-angle set, or add a mirrored
`*Back` view to carry a face's hole dimensions. `mg-magnifying-bracket` retry09
(source `8d6d2088a`, launcher `20261012T124257186Z`): `*Top` was the principal
view with model +Z running DOWN it, but `*Right` arrived with +Y up and +Z to
the sheet's LEFT, so the collar's circle stood beside an arm running left and
the blind machinist read a different part (mreview09 blocker 1); the `*Back`
view under it, mirrored about the flange, carried the counterbore callout and
the hole coordinates and read as a duplicate "not a projection of anything
above it". The same sheet located the bore axis twice from two origins — the
arm's 54.30 from its buried start in the top view and the actual seat's
55.19 from the axis in the side view (blocker 3).
Do: turn the view by a MEASURED angle, not an assumed one: project a model
axis before and after `IView::Angle` (`model_point_in_view` on the origin and
a point along +Z, the cradle's `_turn`), require +Z down and +Y left within
1e-6 rad, then pin the view's ORIGIN (not its centre) to the principal view's
measured origin height through `IView::Position` / `SetViewPosition`, read
back within 1e-4 m (the latch hook's `_pin_origin`), all BEFORE any import so
every placed text is in the final frame
(`draw_mg_magnifying_bracket._project_side_view`). Dimension the mounting
face on the ALIGNED view that shows it (`*Front` under `*Top`): the
counterbores open on the face that view cannot see, so the hole callout
attaches to the THROUGH rims on the visible face (`ViewEdge.circle_at` at
`SIDE_PLATE_Z[1]`, radius `CLEARANCE_DIA / 2`) and names the entry side in its
process prefix (`DRILL / COUNTERBORE FROM` / `FACE OPPOSITE MOUNTING FACE`);
whether `AddHoleCallout2` on
the through rim resolves the Hole Wizard feature is native evidence, not an
assumption. Give one axis ONE controlling chain from the actual flange seat,
not an inner step merely labelled "mounting face". Other face-to-axis values
are REF, with sufficient precision that their printed step sums consistently,
and the dimension from the buried start is unmarked. The collar's OD, with no
band of its own, inherits the title block's `.XX` ±0.51. The named OD print
corners in `mg_lever_press_fit_geom` are conservative independently: strength
uses Ø11.49 (330.8 MPa von Mises, below the 333 MPa limit), while maximum
pressure and press force use Ø12.51. The press force is the friction term over the
whole conservative contact envelope, not the nominal 7 mm straight cylinder, plus
the normal reaction on the partial dome. The longest straight cylinder is
10.00 − 2.997 = 7.003 mm; the part of the R3 hemisphere still outside the smallest
(5.986) bore adds sqrt(3.000² − 2.993²) = 0.204819 mm, so the explicit maximum is
7.207819 mm. Friction (μ 0.10–0.15, p 143.66 MPa, d 6.000, L 7.207819 mm) gives
1951.871–2927.806 N, and the projected dome axial-normal reaction bound adds
18.933819 N, so the total press force is 1970.804504–2946.739847 N
(1.970805–2.946740 kN). The two corners are chosen independently on purpose
(the smallest dome sets the longest cylinder, the largest dome the deepest
penetration), so this is an envelope, not one physical part; its coupled tight
corner is 7.204819 mm. The shared note rounds the high total upward to
**3.0 kN MAX**. The 2.9 kN prints from native 16 are source-specific evidence for
the old 7.003 mm, friction-only note; they do not prove this 3.0 kN note.
`test_mg_fixture_installation` checks both corners and the
ceiling independently. A safe low-OD stress corner does not justify using
the nominal OD to cap force, nor an unnecessary second OD band.
For the bracket the actual seat is local Z55.1875877804, not the arm's
Z58.3 end: the flange's 3.175 stock thickness is a different distance.
The controlling chain is 55.19 seat-to-axis plus 3.11 arm-past-seat;
58.30 is the sum, printed as a genuine drawing-native linear REF picked
on the collar rim's arc centre and the arm end. Identify the mounting plane
from the installed joint, rather than guessing it from a step's outline.
The arm's 3.11 extension lies beside the lever across a 5.55 mm X gap.
Label that short extension `ARM PAST MOUNTING FACE`, not merely 3.11.
Across the flange, the lower edge is Y=-6.35, the arm spans -3.00..+4.50
and the far edge is +6.35: 3.35 edge-to-arm plus 7.50 arm width leaves
1.85, not a contradictory 12.70 chain. The existing 3.35 edge-to-arm and
3.00 arm-to-bore controls locate the bore axis 6.35 from the flange edge;
do not duplicate that sum with an optional reference dimension. The required
short overhang remains labelled `ARM PAST MOUNTING FACE`. A SIDE-view rim
combined with a BOTTOM edge made an angle, and a subsequent mapped sketch
centre could not prove its source identity: neither justifies relaxed
dimension-type or identity guards. The optional REF and its exclusive
selection code are removed; the complete mounting-coordinate ink guard stays.

The arm's controlling 3.00 locates its Y=-3 face, not the opposite Y=+4.5
face: label it `NEAR ARM FACE TO BORE AXIS`. Put `VIEW ON MOUNTING FACE`
below the lower view it describes, rather than in the gap above it where
it reads as the upper view's title. Read the rebuilt caption, controls and
manufacturing-note extents to prove the lower placement remains clear.
The added drill/counterbore process had two standalone rows; it was not
an inherited five-row Hole Wizard limitation. Combine those into one
truthful `C'BORE OPP. MOUNTING FACE` row, retaining the native
hole association, size and tolerance stack.

Put the junction's 7.50 width and 3.35 edge location on the bottom view,
where its footprint is visible, without a second controlling copy in the
side view. Short inside-arrow spans can overlap their arrowheads even after
the witness crossings disappear. Instead distribute the controls between
views and stack outside-arrow dimensions by their rebuilt ink: here the
3.35 hangs below at x150, the 12.70 above at x166, and the 7.50 is outermost
at x175. A full diametric chord always passes the bore-axis witness at the
centre; use the genuine near-side single-arrow style
(`set_near_side_diameter`) and prove the rebuilt leaders clear of each
station witness separately. The view-direction caption belongs above the
bottom outline where neither mounting witnesses nor the hole leader crosses
it; centre it on `IView::GetOutline` and prove clearance to the neighbouring
view's printed dimension ink.

The MG-06 hex fixture's principal `*Top` view looks down the rod bore,
which runs through the hex corners along local Y, not normal to a flat.
Its height is AF 11.1125, with one projected corner ridge through the bore
circle. An unturned `*Right` end view instead puts Y up and shows the
across-corners height 12.8316; that is not a third-angle projection of the
principal view. Turn the end view by its measured axis mapping so -Z is up
in both views, then align their projected origins before importing any
dimensions. The end-view bore axis now runs through the left/right corners;
do not change the model to make a mistaken flat-entry reading true.
The bore-to-flat wall is the ligament to the two parallel flats,
not an entry-face wall. Name the through-corners orientation on the sheet,
and hold on flats and centre-drill the 120-degree ridge before drill/ream.
The end-view bore axis is a native centreline attached to the named
`RodBore` cylindrical face. Map its feature with `IView.GetCorresponding`,
then reacquire exactly one centred Ø5.20 Y-axis cylinder from that mapped
feature's faces. Prove it back to the independently identified source face
with `GetCorrespondingEntity2` and `IsSame == 1`. The rotated end view returned
null for direct source-face mapping; that is not permission to accept an
unmapped face or replace the native axis with cosmetic ink.
Retain one tap centre mark but disable its extended arms, so the
rod axis and small tap cross communicate different features, not duplicate
lines. Place the vertical stock AF REF beside the rotated hex and prove
its model identity, value, parentheses and flat-to-flat witness ink.
For the groove R1.20, keep the genuine model radius and turn off
`ArcExtensionLineOrOppositeSide`: an arrow on the circle's extension in
air is not a material-arc attachment. Give only the groove-station's
centre-side witness a 3 mm local gap, not the root-diameter witnesses,
and prove the rebuilt radius arrow lies on the groove arc with at least
2 mm separation from that station witness. A flag readback alone does not
prove where SOLIDWORKS drew the leader.
Check the entire radius shoulder, not only its elbow: the native 29 mm
shoulder at y196 crossed the OverallLength face-side witness at x160.4.
Keep that proven material-arc leader and give only OverallLength's face-side
extension a local gap derived from the y198 face corner, y196 shoulder,
2 mm clearance and 0.4 mm ink readback allowance (4.4 mm here). Its expected
start moves to y193.6, retaining 68.4 mm of witness. After rebuild require
one complete witness at each length endpoint and at least 2 mm measured
separation from every radius stroke to both witnesses; the readback allowance
does not discount that minimum. Do not suppress the final layout audit.

The next accepted native render still printed `R1.20 +/-0.05` through the
spigot-diameter's top extension. Inspect the actual enlarged PNG as well
as the audit boxes: this one crossed the glyphs, not merely their bounds.
Join the model's material circle directly to the full shoulder, without a
sub-millimetre jog or a new shoulder-span heuristic. At y197.6 the radius
circle is x147 + sqrt(4.8^2 - 1.2^2) =151.647580 mm. Using the actual
native keep-to-elbow offsets 15.2764/2.7781 mm derives the
(166.923980,200.3781) mm text keep. The same OverallLength gap solve
gives 2.8 mm and a witness start at y195.2, preserving 2.4 mm leader
clearance. The expected text-to-diameter witness gap is 0.534 mm:
collision-free text, not a 2 mm text-clearance claim. The native run
must prove that the genuine material arrow and direct junction persisted;
do not weaken the existing single-shoulder identity. No extra diameter-
witness gap mechanism is warranted.
The fixture recipe must refuse every remaining `text-on-line` finding
in its existing completed audit report, not only findings naming the
radius. Reuse those collected findings after finalization; do not add a
second geometric parser or change the fleet-wide enforced-kind registry,
which would re-key every other drawing for a one-sheet guard. Missing,
malformed or wrong-stem audit output cannot count as a clean sheet.
The known 0.18 mm model-edge collector false positives remain reports;
they do not justify suppressing actual text crossings.

## The sheet-split rule

When two views' callouts are squeezed together, the fix is a NEW SHEET, not a
smaller scale. drawing-guidelines.md rule 14 (keep text off the part): extra sheets are cheap, cramming is not. The
`view-crowding` finding is the trigger; move whole sections, detail views, or the
hole table with its notes. Do not abbreviate text, shrink the scale, or thread
callouts between lines to make one sheet fit.

Measure crowding between ACTUAL PAIRS of text boxes, never between per-view
union boxes. On tube-frame, `Drawing View1` owns a note at the top of the sheet
and dimensions at the bottom, so its union box covers 320 mm of sheet it does
not occupy and every callout of the neighbouring view falls "inside" it. The
audit demands one text height of clearance between callouts of different views.

## HLV / HLR rule

Hidden lines only where they inform. One hidden-line view per part is typical,
sometimes none, occasionally two for orthogonal cross-hole families; every other
orthographic view is hidden-lines-removed so dimensions sit on clean geometry.
Assembly views are HLR. Never dimension to a hidden line — cut a section.
Re-assert the mode after annotating (see refusal **e**).

## Format-on-write trap

Do NOT use an editor's patch/format-on-write path on an existing
`cad/scripts/*.py`: a formatter pass rewrites unrelated lines and buries the
real change (a 2-line docstring edit came back as a 173-line reformat). Create
NEW files with a plain write; change existing ones with a small explicit
string-replacement script. Run `uv run --frozen ruff check` and never
`ruff format`.

## Crankshaft centre-hole permission: identify the orthographic end

`draw_dt_crankshaft.py` attaches the unchanged centre-hole permission to
FRONT's right-hand Ø9.000 plain end. Resolve the actual model circle at
`SHAFT_LENGTH`, select that exact edge and set its selection point before
inserting the note. Require the rebuilt attachment to remain that same edge;
the isometric's apparent top end is not the identification contract.
Keep the leader landing in its small FRONT-end window after measured text
placement. The note's field is below the pictorial caption and above the
title block, with its leader corridor right of FRONT's station witnesses
and left of the pictorial/caption, away from MATCH DRILL above the shaft.
Native acceptance must inspect the complete exported sheet, the actual
end landing and both leader/text clearances, not only attachment count.
This changes neither centre-hole permission nor the dome's separate punched
witness, shaft geometry, tolerances or the declared RV-02 rim shortfall.

### Crankshaft necks: opposite real silhouettes and native full width

The right-hand imported `NeckDiaDim` no longer carries `2X`; its native
callout-above text is cleared and read back. Its native 9.525 mm value,
original driven state (1 or 2), places, general band and placement remain
unchanged. The left-hand collar-side neck gets its own associative native
**vertical linear full-width measurement**, with only `<MOD-DIAM>` in the
prefix. Neither a numerical text replacement nor native diameter doubling
is involved.

The actual geometry census
`D:/farm-runs/rolling-main-post-v44-20261021/crank1864-81150dc3-complete-native-geometry-census.json`
identifies the two real `ISilhouetteEdge` objects at
`payload.visible_components[0].silhouettes[10:12]`. They span the exact
`COLLAR_REAR .. JOURNAL_START` short land (41.33–42.50 mm), on model
`X=0`, with opposite radial normals along `Z=±SHAFT_DIA/2`. Their actual
separation is the full 9.525 mm. Endpoint order reverses between the two;
the endpoints are `MathPoint` evidence, **not** selectable `IVertex` objects.
Resolve exactly one lower and one upper outline from FRONT's native
kind-4 silhouette inventory. Enumerate `IView.GetVisibleComponents()`, then
call `visible_component_entities(view, component, 4)` for each component:
the helper returns a flat list of bound entities, not component/entity pairs,
and its first argument is the view, never the adapter. A long shank, right
neck, journal flank, duplicate lower flank or screen-space pick is not an
alternative.

Independently resolve exactly one physical short-neck cylinder from all
bodies of FRONT's referenced part. Require native cylindrical-surface
parameters with the spec radius and unit ±Y axis through `X=Z=0`, and
finite six-value face bounds confined to the same spec-owned land.
`IFace2.GetBox` is approximate: the declared `1e-8 m` bound is only a source
face discriminator, not the measured diameter or sole identity proof.
Native silhouette endpoints independently prove both stations and both
opposite radial extrema. Both silhouettes must own the same drawing-context
cylinder, using `ISldWorks.IsSame == 1` in **both** directions.

The census's drawing-context face 49 compares directly unequal to physical
source face 6. Do not invent cross-context face or raw silhouette identity.
Require the source model's documented
`IModelDocExtension.GetCorrespondingEntity2(silhouette.GetFace())` to return
a **non-null** canonical source face which is `IsSame == 1` to the
independently resolved physical cylinder in both directions. Equal geometry
alone does not suffice. A missing reverse map refuses; do not replace it
with a forward roundtrip, a raw source/view identity OR branch or a fallback.
The actual inverse face-map result for this new candidate remains unproven.

Use the existing native projection helper to read FRONT's actual
model-to-sheet transform. Require its endpoint projections to agree with
model Y along sheet X, model Z along sheet Y, and the unchanged 2:1 scale;
an additional projected model-X offset proves the view normal. These
readbacks verify projection, not ghost selection coordinates. Prequalify
each exact native silhouette with the existing entity-selection helper,
strict selected count/type (`swSelSILHOUETTES=46`), non-null readback and
`GetSelectedObjectsDrawingView2` owner equal to FRONT in both identity
directions. Then reuse `add_edge_dimension` with both supplied objects,
`entity_types=("SILHOUETTE", "SILHOUETTE")` and `orientation="vertical"`.
It selects through `ISilhouetteEdge.Select2` with `SelectData.View`, checks
the two-object selection count and calls `AddVerticalDimension2`.
The factory's XYZ locate text only; supplied entities are not coordinate
hit-tests.

Keep the approved true-measurement initialization at the **fresh empty
SIDE boundary**, before the angle setter, existing rebuild and any native
dimension import. Require actual integer `GetDimensionCount4() == 0`
and the strict counted annotation inventory: native nonnegative I4 count,
`None` only for zero count, otherwise a tuple/list of exactly that length,
no null annotations and actual I4 annotation types. There must be no type-4
dimension; automatic non-dimension marks remain. Only then set
`ProjectedDimensions=False` and require strict false readback.
The SDK warns that changing this property deletes existing dimensions:
never set it on a populated or unqualified view. Retain false readback after
the existing angle rebuild and at all four proofs, alongside exact native
`ScaleRatio=(2, 1)` and `ScaleDecimal=2`. No scale compensation is permitted.

The first factory `IDimension.SystemValue` read must already be positive
`0.009525 m`, **before** any driven-state or presentation write. Log native
type/value/mode and refuse an incorrect immediate value; never divide,
double or reformat it into correctness. Require the existing native linear
type roster `(2, 12)` (`swLinearDimension`, `swVertLinearDimension`), not an
unsupported guarantee that `AddVerticalDimension2` always reports type 12.
Types 6, 11 and 15 are not this factory contract. Set only the new native
dimension's `DrivenState=1` and read it back. Add only
`SetText(swDimensionTextPrefix, "<MOD-DIAM>")`, with readback; never
`swDimensionTextAll`, numeric notes/overrides, `Diametric=True`, constructed
geometry or a type-6/type-15 fallback. Retain the visible native value and
unparenthesized presentation, no suffix/callout prose and read-only
`IDimension.Tolerance.Type == swTolNONE`. Its one-place precision comes from
`DRAWING_REFERENCE_PRECISION["OutboardNeckDia"] == NECK_DIA_PLACES`, so the
same title-block general band governs both necks.

Author the new neck only **after all preexisting native annotations**, including
the SIDE cross-hole callout, surface finishes and property notes, immediately
before finalization. Immediately before its native factory, capture the **full**
preexisting SIDE inventory as native `IDimension` reference, `FullName`, finite
numeric `SystemValue`, native I4 `DrivenState` and the actual annotation row.
Zero values and state 0 are valid for other dimensions. After insertion rebuild,
final settling rebuild, actual SLDDRW save and actual PDF save, reacquire the new
display from FRONT by the captured native object's **live** `FullName` and
bidirectional native identity. Require exactly one matching dimension and
exactly every preexisting dimension with unchanged value/state, no extras, using
live names across SaveAs. Do not ignore native callouts, filter unexpected IDs or
relax the count. Settling positions are not pinned. Continue proving the original
right-hand neck's size, state, precision, empty quantity and general band.

Inventory refusals report expected/current native `FullName` rows and actual
annotation `OwnerType`/owner-wrapper IDs. Wrapper IDs are diagnostic only, never
native identity evidence. If a receipt getter fails, retain the original refusal
with an explicit getter-failure note rather than inventing an owner or name.

At each of those four normal proofs require drawing-view `OwnerType=0`
and annotation owner FRONT in both native identity directions, exactly two
non-null kind-46 attachments and no dangling annotation. Re-read both
attached endpoint sets, cylinder geometry, shared face identity and required
inverse canonical source identity. The shared `assert_dimension_measures`
adds its established two-attachment/native-value proof; its silhouette
identity is owning-face identity, so the stricter opposite-endpoint proof
distinguishes the two flanks. `GetLeaderCount` remains diagnostic, not a
note's one-leader requirement.

Keep one existing void `GraphicsRedraw2` per proof before reading native
display data, with no retries, extra save/reopen or rebuild loops.
Require exactly two finite twelve-value `GetArrowHeadAtIndex2` records,
vertical nonzero projected directions and sheet-normal arrow planes.
Both actual tips must lie within the short land's axial extent, one at each
physical opposite flank, on the same vertical dimension line, with only
the declared 0.01 mm sheet-space tip readback tolerance. Merely falling inside
the neck's rectangular window does not prove either physical landing.
Also require positive native width (along the normalized direction) and height
(across it). Construct all three head vertices using the same tip-to-base
direction semantics as `_layout_audit.arrowhead_segments`: the full horizontal
envelope must stay inside the exact physical X trim, **without** extending it
by the tip tolerance. Log both actual head bounds and the minimum physical-X
clearance in millimetres at all four proofs. Inside/outside arrow directions
are both legitimate; no additional inward-Y requirement is imposed.

The bounded ordinary-dimension candidate requests the new native origin at
`((COLLAR_REAR_X + JOURNAL_START_X) / 2, 0.1948) m`, i.e.
`(177.53, 194.8) mm`. Keep both actual dimension tips and their complete
heads inside the physical neck X trim `[176.36, 178.70] mm`; the opposite
physical flank tips are at Y=`170.475` and `189.525 mm`. The rear finish
symbol stays at X=`COLLAR_REAR_X + 0.0069`, Y=`0.1973 m`, with the exact
physical tip `(COLLAR_REAR_X, _sheet_y(COLLAR_DIA / 2))`, unchanged
part-owned control, symbol type and roughness. All other finishes, stations,
values, geometry, centre permission and dome witnesses remain unchanged.
No `OffsetText`, dimension text-position setter or font-baseline calibration
is involved.

Capture `_collar_rear_rim(adapter, side)` once and retain the actual
`ISFSymbol` returned by `add_surface_finish`, whose existing authoring helper
qualifies the controlled face and exact edge attachment. This **one** finish
is the local straight-leader exception: on its live early-bound `IAnnotation`,
call `SetLeader3(1, 0, True, False, False, False)` and require actual integer
status `0`, not a truthy/bool result. Do not change the shared factory's bent
default or manipulate its root. A straight line from the old bent root can
cross the symbol's own rising legs; refuse that crossing, rather than treating
it as an attachment or tolerance waiver.

At all four existing neck checkpoints, early-bind the retained symbol's live
`GetAnnotation()` result and reuse `_assert_attached_to(..., entity_type="EDGE")`
plus `_assert_leader_lands` with its unchanged **1 mm** default, not the stale
5 mm helper-doc wording. Require native `GetSymbol() == 1` and `GetText(8)`
equal to `dt_crankshaft_notes.COLLAR_REAR_FINISH_TEXT`, derived from the actual
part control, without a literal value override. Require actual integer leader
style `1`, exactly one leader and six finite straight-leader coordinates
(physical tip last), with readable native line/text/head primitives. Preserve
positive head dimensions, sheet-normal planes, actual rim identity and the
exact specification through both saves. Log actual native points, identity,
type, roughness, phase, route and full-head distances. The captured interfaces
must survive SLDDRW/PDF SaveAs; no reopen, fallback identity strings, extra
redraw/rebuild/save cycle or source-part write.

The proof has two deliberately distinct stages:

- **All four checkpoints:** require the ordinary three-line dimension route
  and both complete, nonblank, positive-width native text **ADVANCES** on the
  RIGHT of the actual dimension line, above the journal roof and within the
  actual journal-dimension right wall. Native advances include trailing blank
  space. Read raw doubles, not the rounded JSON audit dump; refuse side flips,
  malformed counts/metrics, crossed preexisting routes, finish self-crossing
  and full native head-to-advance gaps below the existing **2 mm** rule.
  `GetTextPositionAtIndex + GetTextHeightAtIndex` is **not** printed glyph ink.
  Skip only well-formed, finite ten-field zero-length display sentinels, as
  the shared decoder does; they cannot replace any required real primitive.
  The vertical interval union must connect both actual physical tips to the
  actual shelf root, including reversed endpoints and the intended overlap.
- **After the existing successful PDF export:** read that one actual PDF with
  `_pdf_ink`. Match the actual `9.5` and roughness glyphs to their native text
  owners, and identify the Ø token as a unique complete closed vector ring
  plus crossing slash in its actual native prefix slot. Missing, open,
  ambiguous, extra or observably bay-clipped components refuse qualification.
  Merge joint crossings within the existing native geometry roundoff
  tolerance before requiring two distinct ring/slash crossings.
  The whole actual diameter glyph, including vector pen radius, must fit the RIGHT
  placement bay whose top is `197.2 mm`; this is a placement boundary, **not**
  a relaxed clearance threshold. Require complete painted heads (including
  triangle interiors and actual pen radii) at least **2 mm** from every actual
  numeric glyph and Ø stroke, not a union-box white corner. Also prove the
  actual straight route, symbol legs and relevant dimension intersections.
  Only solid painted paths can own those native primitives; unrelated
  unpainted clip paths and dashed centre lines are not annotation ink.
  All aligned PDF pieces, including interior fragments, must continuously
  cover each complete native primitive within the existing attribution
  tolerance. Retain their actual offsets and pen radii for collision checks;
  endpoint fragments cannot stand in for a missing middle. Compare the finish
  and neck paint against each other as well as preexisting dimensions.
  Head coverage intervals do not clip head paint: retain complete attributable
  endpoints, allowed displacement and pen radii for every distance/intersection
  proof. Refuse an ambiguous longitudinal head overhang beyond the existing
  attribution band rather than guessing a shortened triangle.
  A shared symbol root exempts only a point junction, never positive-length
  collinear overlap; this applies to native and printed routes alike.
  This is semantic ownership of the reader-observed ring/slash, not forensic
  font identity or arbitrary PDF clip-path detection; final whole-paper
  legibility inspection remains necessary.
  The finalizer's existing after-PDF callback propagates refusal before
  downstream precision qualification, metadata/rendering and publication,
  even if the exported PDF file already exists. No extra export is performed.

**[INFERENCE]**, pending the exact-source export: the ordinary shelf at
Y=`191.9951` clears the journal roof `191.388` by only `0.6071 mm`.
The finish's middle bar at `202.9118` and the collar shelf at `203.6951`
retain the tight `0.7915 mm` endpoint gap. Conservative native finish-text
advance to the JournalDiaDim vertical remains `0.6963 mm`, not the roof-only
`1.0086 mm`. Static inspection of the preceding LEFT-layout PDF found that
the actual Ø slash is taller than the numeric glyphs; numeric-only
`193..196.6 mm` bounds do not enclose the complete token. The straight
route-to-slash paint gap is predicted to be only approximately `0.51 mm`,
not a broad empty strip; the 2 mm ARROW_TEXT rule applies to the complete
head, not every leader segment.
None of these measurements or predictions is a new threshold or a PASS.
Exact-source native/PDF qualification, both heads' final legibility, whole-paper
inspection and machinist review remain mandatory.
The discarded type-6 circle factory produced native 19.05 mm under projected
mode and a type-mismatch under false-mode initialization; its resolver, factory
and circle-only fixtures are not retained. Accept only exact-source native
success and inspection of the whole exported sheet for both physical neck
landings, readable arrows/text and clearance from collar, running-fit and finish
leaders, followed by the required machinist review. Independent code review is
not claimed. Preserve centre permission, dome/witness geometry,
tolerance limits, RV-02 and MATCH DRILL unchanged.


## Synchronous builds and session hygiene

- The COM seat is shared but SELF-SERIALIZING: `_com_seat` (a machine-global
  file lock) queues every doit COM task and the attach-only audit runner. Do
  NOT ask sibling agents whether the seat is free -- submit the build
  synchronously and let it queue; `com.seat.wait` in the log is normal.
- **The lock serializes, it does not isolate — so the lock holder OWNS the
  session.** Every process drives the same SolidWorks, whose open-document
  table is keyed by FILENAME: a read-only probe that opens `fr-top-frame.SLDDRW`
  also loads `fr-top-frame.SLDPRT` read-only, and a later `part:fr_top_frame` build
  binds to that resident copy and fails on its first `Select2` (measured
  2026-09-16, twice). The contract: whoever acquires the seat is right to,
  and must, `ISldWorks::CloseAllDocuments(True)` and start from an empty
  session; any document a previous holder left open unsaved was never
  protected, and it is not the taker's problem. Nobody holds work across a
  lock release — save or discard before releasing.
- Attach, never launch: `HARMONIC_SW_AUTOSTART=0` plus a held
  `HARMONIC_COM_SEAT`. `cad/scripts/diagnostics/_owned_native_session.py` is the
  attach-only runner.
- Open read-only + silent (`swOpenDocOptions_Silent | ..._ReadOnly`). On
  taking the seat, `CloseAllDocuments(True)` first; on release, close what you
  opened by path with `ISldWorks::CloseDoc(path)` and prove the session is
  empty: `ISldWorks::GetDocumentCount()` and `ActiveDoc`.
- Keep each attach short and one-shot. A held session blocks every sibling's
  build; ten seconds of audit does not.
- Never launch a `doit` build to inspect a drawing. Audit the open document.
- One export at the end. If you are exporting to see where something is, stop
  and run the audit instead.
