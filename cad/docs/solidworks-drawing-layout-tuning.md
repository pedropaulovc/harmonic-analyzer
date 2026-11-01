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

### Measured native supplier-reference text shelves

`_supplier_reference_text.shelve_reference_text` extracts the proven shared
clamp's positive-axis shelf sequence. The caller supplies a strict fresh native
dimension inventory and horizontal/vertical axes; the core has no source-feature
name convention. It measures every native text fragment, rejects unavailable or
non-finite geometry, seeds `OffsetText` from the actual arrow station, rebuilds
and reads back the anchor, enables native offset mode, then moves the entire text
block beyond the measured physical arrow tail. The existing 2 mm clearance,
0.2 mm placement settle and native station tolerance remain unchanged.

Use the returned read-only proof in final settled checks. It reacquires the
inventory and proves physical arrow/witness stations, native offset mode,
complete text-to-tail separation and the original transverse text position.
`force` explicitly shelves an authored multi-row reference even when it fits its
own span; otherwise the native complete-text extent decides. Shelves move only
in the positive dimension-axis direction. The initial measurement rebuild and
three batched transition rebuilds are part of the sequence; the proof never
rebuilds or moves anything.

These native rectangles are not tight printed glyph ink. Retain fraction bars,
underlines and connectors in every captured record: a legitimate fraction bar
can intersect the union of native font rectangles. Do not add a fraction
allowlist or test all strokes against that union. The caller still owns source,
attachment, value and format checks, complete cell/caption containment, its
settled layout checks and post-export inspection/audit using actual PDF ink.
Native shelf separation alone does not prove body or foreign-line clearance.

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
title clearance stays 4.1210 mm. These are historical upstream measurements
for that package's unchanged text/wrapping/font, not fit-test or native proof
for the longer threaded-joint sequence and 72-column CHECK block. No
recipe-specific whole-CHECK native gate is established by these observations;
the shared REPORT limits are unchanged. Inspect the fresh combined drawing's
entire native CHECK extent, printed ink, title-block clearance and sequence/
border/neighbor gaps. Historical translations do not certify its output.

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
A-A 1:1, B-B 1:1); do not walk a scale ladder after `Crop2`. Refresh native display
geometry after HLR/scale changes before measuring the outline. `GetOutline` is
a padded view extent, not an exact crop circle box. The locator's 54 x 43 mm
field accommodates its measured 43.884 x 41.516 mm native extent; its caption
moves down with the field's lower edge, without moving neighboring labels.
At 1:2 the 4.16 mm retainer printed smaller than one arrowhead, so neither
section's landings could be told apart (machinist review). A-A is 1:1 with a
30 mm crop re-centred on its readings' span (C2 lower rim to C5A pin end);
B-B's 1:2 fragment read as an unlabelled speck: it is 1:1
in a 64 x 47 mm top-right field that holds its measured 42.076 x 44.776 mm
native extent, with its caption directly beneath, its C3A labels landing on
the bolt's near side, and a longer cutting line so its arrows stand outside
A-A's on the plan (a shorter one put its letter in the C5B cotter leader).
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

Text dragged outside the witnesses without `OffsetText` hangs off the extended
dimension line: the shelf starts at that line and the widest row's first glyph
sits on it. The cone gear's vertical tooth-thickness line ran 0.19 mm from the
C of CIRCULAR on all 20 sheets of 2056e3344. No `SetPosition2` move separates
them, because the line follows the text. `draw_dt_cone_gear` keeps the line's
pre-offset anchor, offsets the text onto a measured shelf and checks the
exported PDF. Every line except the callout's own shelf must keep 2 mm of
printed air from its glyphs (`assert_tooth_thickness_text_air`, at
`after_pdf_save`). The offset leader starts at the line's midpoint and ends at
the shelf's near end, so it closes on the block's lower-left corner; budget
the first glyph of the widest row against it.

Once offset, a model dimension imported on one sheet per configuration printed
the last sheet's callout text on every sheet. With per-sheet `SetText`
applied before each sheet's offset, T006 printed T120's `ON PITCH CIRCLE
Ø63.500` under its own T006 value and tolerance (cone gear farm runs of
746809f62 and 5000ea76b). Without `OffsetText` the same per-sheet text had
printed correctly. The mechanism is not established. Keep the callout text
of such a dimension identical on every configuration's sheet, and put the
per-configuration sizes in the per-configuration property block (GEAR DATA).
The PDF check requires each row as one text run and names the runs that
start alike when it refuses.

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

The summing lever's R3 Detail D proves why a successful angular text readback
is not route acceptance. At request (51, 81) mm, the native connector from
(58.3221, 166.7272) to (69.6861, 75.4438) mm strikes the final `T` in
`MHA-SM-02 SEAT` below `4X 122.4° ±0.5°`. The native/PDF evidence is
`D:/farm-runs/summing-plate-taps-20261022/r3-sm-visual-evidence/`
(`sm-native-layout-audit.json`, `sm-flank-angle-small-defect.png` and
`sm-detail-d-complete.png`). Seed the exterior arc at its original 18.57 mm radius
and use the same native angular shelf at **(51, 211) mm**, a text-only
**130 mm upward** move. Its entire lower row starts at native Y205.4437 mm,
4.1036 mm above the height's upper witness; its right edge X69.6861 mm is
4.9138 mm left of the ridge witness. A smaller left/upper nudge is not a
whole-neighbor repair: the height's X34.2 mm dimension run crosses that pocket.
The new shelf is above every point on the retained native arc, so any straight
connector from that arc ends below both complete printed rows, leaving at least
0.9338 mm ink air. Do not freeze or rigidly translate the old connector's arc
attachment. The regression replays both native/PDF rows, the complete neighboring
blocks and witnesses, the retained arc/arrows, and the entire possible connector
envelope. The connector crosses the upper height witness rather than the lower
one, a line/line crossing, not text. These are placement projections: fresh
native/PDF inspection must prove the actual re-solved route and full-sheet ink.
The model-owned angle, one-place precision, symmetric band, attachments, all six
views, and the separate `3X 5.00` / `2.59` placements remain unchanged.

That shelf alone still failed machinist review on 41bbeec. With the seed at
153.6° about the shoulder, (58, 184) mm, the offset connector landed on the arc
by the lower arrow at (58.3221, 166.7272) mm. That position did not depend on
the text's position: R3's shelf below and the later shelf above both used it.
From the shelf above, the leader crossed the angle's own arc. In both seeds
tried here, the native landing was the arc end nearest the false-offset seed. Moving the seed to 120°,
(65.3, 191.8) mm, at the same radius made the connector land at the upper
arrow, (73.42, 194.25) mm, outside the arc. Run
`20261028T232328323Z-b403fbd514844805a4b0c59c40b49f8f` read the leader back from
(69.69, 205.44) mm to that point, and machinist review returned SHIP. To change
the end an offset angular leader lands on, seed the arc nearer that end and
keep the measured wedge.

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

**f3. Face names: the print's or the machine's?** The fleet's pictorial face
labels default to the PRINT's (FRONT = the face `*Front` shows, +Z; RIGHT =
+X) — the ASME orientation-key reading. The MACHINE's front is model −Z
(`dimensions.yaml` "Z = depth (− front)"), and model-owned dimension names
carry that word (`StudFrontZ` → "FRONT HANGER Z"). When a package prints both,
a blind reviewer reads them as conflicting locations, and a key note that
translates between them is itself a clarity finding (top-frame machinist
review at 2056e3344). Use one convention per package: where the dimension
names are the machine's, name the pictorial faces the machine's way too
(top-frame: the +Z face is REAR), never by flipping the model names.

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

All five MG setting callouts belong to the assembly model:
`mg_magnifier_assembly_spec.SETTING_CALLOUTS` owns the exact text and native
compartments for PressGauge, Endshake, ClampStation, FixtureDrop and
ThreadProjection.
`build_mg_magnifier_assembly` authors them beside their reference dimensions,
strictly reads each compartment back and marks/blanks the chains before its
normal assembly save, following `build_pd_transgear_arm`'s model-text pattern.
The drawing only imports the associative native dimensions and checks their
inherited text, precision and stack tolerances, initially and once settled.
It must reject a stale assembly lacking the text, not stamp it during drawing
generation. Setting callout wording now re-keys `assembly:mg_magnifier` and
requires rebuilding that source and its drawing; BOM/step/check prose remains
drawing-only and must not enter the assembly builder's import closure.

The threaded-joint setting uses its own `LeverThreadSetting` feature and the
native below-callout compartment for all three rows of `FLAT LEVER TIP /
PROUD OF FAR / BRACKET FACE`. Author/read it beside the existing 1.25 mm
reference before blanking that chain; drawing-time text writes would violate
the same source-clean contract as the original four settings. Keep the sole
native dimension, far-bracket-face datum, precision and general band unchanged.
This authority migration requires a new assembly recipe, not new geometry.

Preserve the physical tip camera across standard-view remapping, not an old
`*Back` string. `_assembly.remap_front_to_machine_front` first shows old
Back/id2, then makes that orientation Front/id1 with `UpdateStandardViews`.
Thus the former unobstructed machine−Z tip view is current `*Front`; saved
`MG BACK` is the old +Z Front, and axle crops still use saved `MG LEFT`.
Keep per-detail orientation and caption consumers consistent. The source
camera mapping alone is not native visible-edge, cropped-ink or final-layout
proof; the same instance/configuration, ownership, physical-boundary and
whole-ink guards must still pass on the rebuilt source.

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

The summing lever's face-height chain also needs a location from the knife
ridge to the coefficient top; `19.05`, `5.08` and `6.99` alone do not locate
that chain from the suspension axis. VIEW F now uses the existing native
`KnifeEnvelopeReference` **height.end** sketch point at model Y5.134 mm,
the same endpoint used by Detail D's `RidgeFromLeft` and `RidgeFromRight`.
Datum A itself stays attached to the physical ridge round; its crest and arc
centre are not interchangeable with this theoretical sharp. Resolve the unique
construction height line, verify its native sketch-to-model transform, then
map that actual endpoint through `IView.GetCorresponding`. Select it with
`ISketchPoint.Select4` and the visible −Z coefficient-top edge with
`IEntity.Select4`; `IModelDoc2.AddVerticalDimension2` supplies the measured
2.594 mm location, displayed as ordinary **2.59** under the existing title block.
No new model point, profile, tolerance, section or view is added. Missing or
ambiguous source geometry, null correspondence and failed selection refuse;
there is no coordinate-only, rounded-crest or cylinder-centre fallback.
The initial and settled checks prove both exact attachments, native value,
VIEW F ownership/visibility, projected rise and ordinary two-place precision.
Its (403.5, 128) mm text request uses the open right/below lane: R2 projection
predicts X403.5–415.1375, Y125.2219–128.7219 mm text, 3.9625 mm inside the
right border and right of the tap callout. This is a placement projection;
fresh native/PDF inspection must prove the complete witnesses, outside arrows,
shoulder and text remain clear. Shared audit guards remain unchanged.

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

The summing lever's sheet-1 `3X 5.00` made the same vertical-dimension mistake
in R2 (`20261022T190921801Z-dbfece22b19a4d68ac2dd248e5168731`): native text/
shoulder X191.1396–209.5 mm and printed ink X192.5961–208.0575 mm crossed
the boss-X `76.20` witness at X197.2187 mm. Its existing `TOP_KEEP` curation
request moves from **(209.5, 103.5) to (193.5, 103.5) mm**: the complete
native text/shoulder/arrow column moves 16 mm left without a new `OffsetText`
mode or a detached note. Translation of the recorded native span predicts
X175.1396–193.5 mm, 3.7187 mm air to the witness and 7.6201 mm to the full
`MID RIB CENTRE` row. The Ø25.40 block remains above/right, not squeezed by
an upward nudge; the lower finish symbol and dimension rows stay untouched.
The existing drawing regression replays both recorded text boxes and the
moving shoulder/outside-arrow runs against complete neighboring text.
This is an offline placement projection, not native after-fix acceptance.
Regenerated native/PDF inspection must prove the complete route and neighbor
air while retaining the model-owned value, tolerance, attachments, `3X`
prefix and all six views; geometry and shared audit guards are unchanged.

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
Do not assume `*Right` beside `*Top` makes a third-angle set, or add a mirrored
`*Back` view merely to carry hole dimensions. Turn by a **measured** angle:
project the model origin and a point along +Z before and after `IView::Angle`,
require +Z down and +Y left, then pin the view's origin (not its bounding-box
centre) to the principal view's measured origin height with `SetViewPosition`.
Read the result back before importing dimensions
(`draw_mg_magnifying_bracket._project_side_view`).

The current MHA-MG-01 is the 2026-10-20 approved simple L bracket: its true
semicircular nose and parallel sides replace the old collar and tapered arm.
Use current-main axis-to-seat **100.3975878**, not the superseded 55.1876
sketch; preserve the 3.175 stock mounting grip with explicit native ±0.13.
The foot's right face merges flush with the centred nominal12.50 neck, printed
12.5 at ordinary `.X` ±0.8; the fitted installation retains full1.5D engagement.
Native mounting dimensions stay attached to their witness sketch, imported
on the visible mounting face; the *Front HLR Hole Wizard callout attaches to
the real +Z exit rim, not the hidden drill-entry rim. Named native part-feature
lookups bind `IPartDoc`: `IModelDoc2` does not declare `FeatureByName`.

The three native mounting-location dimensions `MountingX0`, `MountingX1`
and `MountingY0` share the source-owned below-text flag `[1]`. The same flag
prefixes the existing `MATES MHA-SM-03 TAPPED HOLES` row on the associative
mounting-hole callout. Include all three imported mounting dimensions in the
source-callout readback guard; naming the mate only at the drill callout does
not attach it to the tight locations. The flag changes neither their ±0.05
bands nor the matched receiver row, and adds no match-drilling instruction.

For a point-only Wizard placement, retain the traversed early-bound `ISketch`
and read `GetConstrainedStatus()` directly: only native status 3 proves fully
defined. The named SDK status path returned `source=unavailable`, `raw_status=None`
on the r2 bracket; that is an unavailable channel, not evidence for either
underconstraint or permission to proceed. Existing closed-sketch native status
readbacks are the positive control; do not fabricate a successful fallback.

The through tap's ordinary locations are 5.50 ±0.05 from the physical nose tip
and neck side. These are not zero datum dimensions and not a GD&T frame.
The R5.50 nose and location bands do not establish a maximum finished thread
root. ASME B1.1-2003 §§5.5 and8.3.2 explicitly leave the internal maximum
major diameter unspecified. The user chose a normal standard through tap, so
remove the former custom Ø6.45 inspection sketch, callout and false guaranteed
wall calculation rather than pretending 2B supplies the missing upper bound.
Nominal standard-major wall is2.325 and nominal mouth wall2.125; those are not
manufactured worst-case certificates. Actual finished walls remain subject to
drawing-policy rule17 (2.0 target/1.5 floor). The retained modeled0.20 chamfers
use hidden native primary-distance limits0..0.25, not an unsupported0.15 minimum.
The one ceiling comes from structured
`title_block.edge_break.chamfer_max_mm`; the existing bilateral setter owns
the deviations, and each builder checks the nominal plus its native lower and
upper deviations against 0 and 0.25. The bracket prints no angle-only mouth
note; its title-block edge maximum governs the unchanged native chamfer.
Do not claim both manufactured legs are capped at0.25. The model's45° feature
uses `angular_band_deg()` (±1°), giving the conservative projected leg
envelope `q = 0.25 tan46° = 0.258882578`. `_part_save` already invokes
`apply_block_tolerances`, which verifies the template-owned native angular
preference 126 against the configured value and fails on drift.
The removed1.658 MIN/RV-01 declaration depended on a custom root acceptance
the user explicitly rejected. It is not a standard-thread guarantee and must
not survive hidden in metadata, tests or review context. Do not replace it
with another unasked thread-major limit or local inspection note.

The lever no longer imports or prints its local numeric `TipChamfer` size,
band or `LIMIT RETAINS FULL ENGAGEMENT` text. One native thread-feature
callout is printed in the enlarged detail: designation, `MATES MHA-MG-01`,
then `BRACKET` on its own third row. The modeled0.20 tip chamfer is the
title-block edge break, so the callout no longer names an unsized
`45° ENTRY CHAMFER` (machinist FIX, 1e2b7b5). Its native
attachment and source text are retained; there is no detached manual copy.
Hide drawing-local duplicates
in the front and isometric without changing the source model's callout.
The hidden native primary-distance cap remains in the part, while the title
block supplies the edge maximum. Every crop is created with inference off,
explicitly selected and checked against its persisted native circular fence.
Final exported-PNG inspection still decides real ink clearance and visibility.

MHA-MG-03 now has one free hemisphere and a flat threaded end. Import the
small thread/lead dimensions before circularly cropping its enlarged
independent Front model view, then prove every kept native dimension survives
the crop (the MHA-MG-04 pattern). The assembly's native ThreadProjection
specifies installation depth: the flat tip reaches through the far face,
with no shoulder or added relief groove. Full engaged overlap excludes `q`
at each female mouth, incomplete male thread at both ends, and an ADDITIVE
`q` male tip loss: the print does not explicitly define a chamfer/die-lead
union. The single fitted-projection interval gives **10.017234843** full
overlap, above1.5D = 9.525 with the ordinary12.5±0.8 receiver. Root-runout
clearance is0.525 and minimum tip projection0.740. Rod length variation moves
the fitted free tip; it does not define a second fixed-position joint proof.
There is no press-fit force/finish/elastic-yield contract or added lock.

After comparing the head-options PNG, the owner explicitly selected
**“A — Keep geometry; approve exception”** in this session. This later explicit
reply, not the earlier timed-out selector or annotation-only direction,
authorizes package-owned **RV-03 — Retained head wall controls**, `kind: accept`,
in `config/parts/mg-magnifying-bracket.yaml`. Its rules4/17 scope is exactly
**NoseR R5.50±0.05** and **TapFromTip/TapFromSide5.50±0.05**, retaining the
existing head geometry, these three bands and their native `RETAINS TAP WALL`
below-text. The exception is review context, not a new note on the sheet.
There is no outside-profile fit mate or new finished-thread-major limit.
The finished head minimum wall remains **unknown**: the6.35 BASIC major is
not a manufactured maximum, and the nominal2.325 head /2.125 mouth walls
certify neither the2.0 target nor the1.5 floor. RV-03 accepts only this retained
head/control decision; it does not waive foot grip, mounting mate flags,
drawing line clearance, other walls or installed engagement. The separate
RV-02 retention acceptance is unchanged. The mate-flagged native PDF still
requires native redraw and Codex machinist review; approval is not print proof.

The foot prints explicit **3.175±0.13** with
`MHA-MG-VN-53` / `SCREW GRIP` below it: full engagement3.305 exceeds3.2766,
with0.0075 minimum tip clearance. Rounding it to3.18 at`.XX`±0.51 loses that
joint. Foot length/width retain their own one-place printed-size intervals;
the later owner-approved width cut below changes only nominal Y width and must
not loosen the grip, receiver, rib or depth bands.
The blued material is generic low-carbon steel, matching the existing native
Plain Carbon Steel assignment. The generic-steel qualification below owns
the fitted-band load-demand screen and its unverified material assumptions.

Keep the assembly's complete thread-projection qualifier attached to that native
dimension when wrapping or repositioning it. R16 exported successfully while
the sheet1 qualifier still extended outside the left border: native export
success is not visual acceptance. Read every native display-text fragment,
including the below-value qualifier, and require the full wording to survive.
Fit the union of the existing callout ink and native-position/height/reference/
angle-backed text boxes inside the current drawable sheet region, then check
again after rebuild. The repository's text-width estimator is not an exact
native glyph outline; inspect the final PNG as well. Preserve the native1.25,
its tolerance and real dimension/source attachments.

Create the independent thread-witness segments with `add_line_chain` so
`SketchManager.AddToDB` suppresses inference during creation and restores its
previous state afterward. A bare inferred line in r2 produced a 167.30 native
tip witness for a requested 167.50, beside the 0.20 chamfer. The final native
equation failure said its dependent variable was driven/reference; it did not
name the offending equation, so the edge-snap mechanism remains an inference,
not an observed relation ID. Before applying equations, verify that all thread
witness dimensions are driving and have the requested native values. Do not
apply the pre-equation DrivenState check after equations take ownership.

The dependent MHA-MG-02 clamp uses **1/2 in hex** brass, keeps its bore at
**19.95** from the bottom seat and its overall height at **29.50**. The hook
stays at **919.7**; neither `.XX` ±0.51 band tightens. The native TOP
**HEX 12.70**, at **two places and not REF**, uses the ordinary
title-block `.XX` ±0.51 size12.19–13.21 on all three opposed-flat pairs over
the full height. The ordinary drawn angles use the default±1°; do not exempt
the shape as unconstrained “flats as supplied”. The model-owned `HEX ` prefix
imports with the actual AF dimension; no separate stock-definition leader is
needed. The source uses tolerance TypeNONE=0; inactive min/max getters are
observations, not accepted limits. Read value, both precisions, non-reference
property, prefix/suffix, actual source endpoints and requested-view ownership
again after the final rebuild.

There is no bespoke2 MIN wall/floor or15 MAX stock-envelope inspection note.
The ordinary HEX/profile bands give a conservative full-height body bound:

`D <= (AFmax + 2 Hmax tan(a)) / (cos(30°+a) - sin(a))`

with AFmax13.21, Hmax30.01 and a1° gives16.979159, rounded OUT to17.00
for calculations only. Adjacent normals, opposite-face angular mismatch and
full-height drift are spent; exact60° faces or a centred tap are not assumed.
This is not a supplier certificate or a bound for unconstrained stock.
The opposite-flat/bore/location/relative-angle corner leaves1.644216 mm:
below the2 mm target but above Rule17's1.5 mm hard floor. The drill-point
floor remains2.081671 mm. Neither number becomes a redundant drawing note,
and no ASME internal-maximum-root certificate is claimed.
Retain `MHA-MG-04 SHOULDER SEAT: NO CHAMFER OR SPOTFACE AT TAP`; `AT TAP`
does not constrain unrelated edges. Retain29.50 and .XX±0.51 without a height
qualifier, and identify MHA-SH-VN-55 at its actual top-tap callout.

Spend17.00tan(0.3°) bore run-off even at central tap/floor targets, rather than
an unowned nominal half-depth. Intersect actual male/female full-profile
intervals, excluding the stock screw's **0.47625** tip chamfer and mouth break.
The finite flat-tip contact includes independent relative-entry error and the
existing conservative1.3° contact envelope. Plug reach, stop window, the real
finite118° drill cone, collar clearance and FULL≥1.5D=4.2675 must all pass.
The rod's 8.55/12.75 depths and FULL4.605 are unchanged, conditional on its
actual shoulder seating. This is not an alloy/temper strength certificate.

The approved R22 datum change retains five ordinary native measurements,
with no new FCF or tighter band. `LeverBoreFromZFlat`, `ThumbTapFromZFlat` and
`RodTapFromZFlat`, all in `LeverBoreLocationProfile`, each measure **6.35**
from the **same actual full-height +Z stock flat** with the title block's
.XX ±0.51. The two tap-to-diagonal-flat measurements remain separate 6.35
controls with the same ordinary band. Do not imply that all five dimensions
share a datum. The common datum is the converted full-height edge at
`(corner_radius/2, Y, +AF/2)` owned by the resolved +Z stock face, not a
computed midplane or independently picked top/bottom boundaries.

This is an explicitly approved **change of manufacturing acceptance**, not an
equivalent rewording. With `s = bore_radius - 3.25`, the old feasible set was
`B in [5.84,6.86]`, `T_i - B in [s-1.02,s+1.02]` and
`D_i in [5.84,6.86]`. The new set independently bounds
`B, T_thumb, T_rod, D_thumb, D_rod in [5.84,6.86]`. Each tap's absolute
common-flat interval narrows from the old union [4.82,7.93] to [5.84,6.86].
For positive `s` the new joint set is not even a strict subset:
`B=6.86,T=5.84,r=3.30` satisfies the new limits but gives old rim distance
4.32, above 4.27; conversely `B=6.35,T=7.37,r=3.25` satisfies the old rim
control but fails the new direct tap interval. The conservative maximum
tap/bore centre offset falls from **1.07 to 1.02**; do not add a diameter
half-band to that centre-to-centre location. The tap/tap entry offset maximum
is also 1.02, rather than the former 2.04.

The native witnesses still select the real Wizard points and externally
convert the actual stock edge and cut-producing bore circle. Retain the
four-constraint construction projection: VERTPOINTS26 aligns its start with
the actual tap; HORIZONTAL4 makes the line horizontal; HORIZPOINTS25 aligns
its end with the actual bore centre; COINCIDENT9 places that end on the actual
circle. This geometry remains an association/projection device, **not a
printed rim acceptance**. Measure the projected local start to the same
converted flat segment through the existing point-to-flat constructor; the
bore uses its converted circle centre and that identical flat. Remove the
obsolete rim dimension names, tolerance metadata and point-pair acceptance
contracts rather than retaining them as secondary controls.

Provisional seeds choose the positive projection branch, not measurement
authority. Create endpoints away from the actual bore centre and previous
witness endpoints: `AddToDB` suppresses inference, not exact-coordinate
database merging. Preserve fully defined status, actual relation definition
entities, source identity, ordered point/segment IDs, self/owner controls,
endpoint distinctness and rebuild checks. The new dimension's attachment
proof is the actual projected point plus the actual converted flat segment,
not both line endpoints. The source measurements retain ordinary unboxed,
nonreference authority through equations/rebuild and hidden-sketch import.

A grouped front-view `3X 6.35` identifies `BORE AND BOTH TAP ENTRY AXES`.
The spec's explicit group-to-members contract must cover all three source
measurements. Read back each native value and its appropriate point plus the
same flat identity before suppressing duplicate displayed values. Three
printed instances are unnecessary, but a 3X prefix backed only by the bore
measurement is invalid. The retained projection and point-to-flat primitives
were exercised separately before this change; their new combination and
grouped imported attachments still require Main-owned native validation.

All functional bounds use the independent1.02 entry-offset envelope and the
derived17.00 full-height body bound, with no custom receiving notes.
Thumb FULL overlap is4.392416640≥4.2675, collar clearance3.334893727 and the
blind rod-drill floor2.081671434. Plug reach, stop window and finite drill-cone
clearances remain explicit derived checks in the spec; they are not replaced
by printed machining instructions. These are arithmetic bounds, not native
measurements or executed test results. The ordinary worst bore-flat wall is
1.644216, an admitted miss of the2 mm target, not a breach of the1.5 mm floor.

Keep the three actual witness feature names in the builder's literal
`REFERENCE_SKETCHES` tuple. `_location_sources` uses that declaration to name
the actual source map, and `_location_profiles` creates and blanks every
returned source. The repository hidden-sketch routing scan must resolve those
computed blanking names and verify drawing curation through
`_drawing_hidden_sketches`; an unresolved name is an error, not a reason to
skip the drawing.

The former direct point-to-circle constructor is removed, not retained as a
fallback. R9 proved exact circle identity and accepted/read-back rim selection,
then the same native horizontal constructor returnedNone. Its original failure
reason remains unknown; the prior zero-span hypothesis is not established.
Do not spend another round on pick variants or present successful selection as
successful dimension creation.

Relation creation and readback are separate native contracts. Record every
returned relation kind and its actual definition entities before filtering for
the requested kind; a non-null AddRelation result is not sufficient identity or
semantic proof. R12 restored HORIZONTAL4 and exposed returned kind32/USEEDGE
after a VERTPOINTS26 request, with definitions not two confirmed points.
USEEDGE is not vertical alignment or a valid enum alias. A mismatched returned
handle alone also does not prove the mutation had no effect: compare the actual
owning line/endpoint relation inventory before and after the single mutation.
Require the exact intended kind, actual source entities and native alignment,
not a relaxed returned-kind check. Classify actual definition entities before
identity comparisons; the separate GetEntities/GetEntitiesType inventory is
not the definition-entity inventory.
R13 observed only the same suppressed DISTANCE1 on the retrieved start before
and after requesting26; the required relation was absent there. The old start
seed exactly matched the already-converted bore centre, contrary to that
creation contract. Reuse of that particular centre is consistent with the
inventory but was not directly identity-tested in R13. This is not evidence
that all cross-sketch point relations are unsupported; the same run successfully
used26 with an external origin. Correct the creation collision without changing
the four intended constraints, sources, dimensional bands or final geometry.
R14 proved independent provisional endpoints and actual creation of26 with
two point definitions, unsuppressed and correctly aligned. Raw definition-point
dispatches nevertheless compared as `(0,0)` against the retained start. Its
expected-start ID was not recorded, so equality of the documented native point
keys still requires direct readback rather than a pointer-normalization claim.
R11 regressed the already-passed HORIZONTAL4 check because mandatory runtime
type information returned `Invalid index`; that optional metadata is not an
interface-capability contract. Classify each actual definition with native
[`QueryInterface`](https://learn.microsoft.com/en-us/windows/win32/api/unknwn/nf-unknwn-iunknown-queryinterface(refiid_void))
and the pinned SDK interface IID. Only `E_NOINTERFACE` means that interface is
unsupported; other failures remain unavailable. Reject ambiguous or unsupported
classification. A generated `_early_bound` wrapper's fallback is not capability
proof, and capability does not replace the native sketch-entity identity keys.
Native point IDs/typed keys and definition/interface/self/owner checks are
mandatory. Keep optional internal inventories and diagnostic coordinate reads
separate; their unavailability must not add a constraint-acceptance requirement.
Required alignment/geometry readbacks remain mandatory.

The r5 attempt failed earlier, at the combined selected-count/circle-identity
guard, before setting or reading a native pick. The r6 positive control then
stopped on the previously working point/flat path: count2, native types
`(11,10)`, selected-versus-expected `IsSame=(1,0)`, self controls `(1,1)`.
Both objects were present; that direct segment comparison cannot distinguish
a different sketch entity from an interface/dispatch identity difference.
Do not attribute either failure to the zero-span hypothesis.

The r7 guard exposed an unsupported sketch-to-feature binding: `IFeature.Name`
read a16-double transform instead of a string. Native owner/type/ID comparison
and rim selection were never reached. A generated wrapper's declared members
do not establish that the returned dispatch supports that interface.

For this part recipe's sketch segments, use the native identity documented by
`ISketchSegment.GetID`: **owning sketch name + segment type + ordered ID pair**.
`GetSketch` supplies an `ISketch`, not a proven `IFeature` dispatch. Resolve its
owner through the actual part feature inventory, including child sketches:
`IFeatureManager.GetFeatures(False)`, profile-feature `GetSpecificFeature2`,
and native sketch identity with positive self controls. Require exactly one
matching owner, and read `Name` only from that actual tree `IFeature`.
Reject unavailable or ambiguous ownership; do not cache across rebuilds.
IDs alone are not unique across owners or segment types. Require valid native
identity fields and exact equality wherever actual segments are compared.
For points, [`ISketchPoint.GetID`](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchPoint~GetID.html)
explicitly defines **point type + owning sketch name + ordered ID pair**:
the pair is unique only within that sketch and can overlap other element types.
Use this as the primary native point association and independence contract for
selection, relation definitions and annotation attachments—not a fallback
selected only when raw pointer comparison fails. Require unambiguous point
capability, valid native fields and the same strict self/owner controls.
Read the keys afresh in each validation phase: these are not persistent IDs
and must not be carried across rename or rebuild as cached identities.
For the local construction line, verify its owner/type/IDs and distinct endpoint
identities; dimension attachment identity must match those endpoints, while
constraint definition entities must match the real Wizard point and converted
circle/centre. Keep exact native types/counts, non-null attachments, not-dangling,
measured value, driven ownership and acceptance-band checks after final rebuild.
These identity guards log native keys, not removed cross-proxy equality codes.
Self/owner `IsSame` controls remain mandatory. Log operation stage, count, types,
availability and actual/expected keys; unavailable native keys never pass.
Do not substitute coordinate equality or a fixed number for actual constrained geometry.

The actual Wizard entry point is external to the active bore witness sketch:
native selection reports `swSelEXTSKETCHPOINTS=25`, still an `ISketchPoint`.
Accept only the documented internal/external point kinds, retaining exact
Wizard-point identity and the circle's owner/type/ID guard. Annotation
attachment types use the same `swSelectType_e` enum; do not assume every actual
sketch-point attachment is type11. Type25 alone does not prove the right point.

Imported drawing sketch points and segments belong to the requested drawing
view, not the referenced part's sketch inventory. First prove the actual source
point and flat against a fresh part-feature inventory and the source dimension.
Map those typed source entities with `IView.GetCorresponding`; independently
read the imported annotation's actual attachments. Require exclusive native
point/segment capability, exact part/requested-view annotation ownership,
matching native dimensions and their full names, and matching source features.

Map the actual dimension's `IFeature` through the requested view, then obtain
its supported `ISketch` using `IFeature.GetSpecificFeature2`. That sketch must
match both actual and forward-mapped drawing attachment owners. Compare native
ordered IDs and segment type only within this proven drawing sketch; model IDs
need not equal drawing IDs. The dimension feature's sketch is not a substitute
for the part-inventory source-point owner. Do not cast an arbitrary mapped
object to `ISketch` or infer identity from coordinates or feature names.

This forward route does not require inverse `GetCorresponding2` success on a
drawing sketch point. `GetCorrespondingEntity2` remains the separate supported
face/edge/vertex route. Null, ambiguous or wrong-view results, unknown native
self/owner identity and malformed keys remain refusals. Reacquire all source
and drawing proof after rebuilds; never cache correspondence across them.

The native TOP `HEX 12.70` dimension owns ordinary .XX size on the complete
hex profile. Its prefix is model-owned and source/import/final readbacks keep
the real dimension and owner; no below-text stock qualifier, property-linked
envelope note or special section-edge acceptance flag survives.
Clear height's obsolete below-text explicitly while retaining its numeric
source/precision. Remove only the native hole-callout thread-class variable
where the title block already owns 2B. Keep live thread/drill/depth variables
and reject resolved text that still repeats 2B.

Inspect the actual whole PNG and unchanged native ink audit after simplifying
the sheet. Removing dead notes is not permission to loosen attachment,
location, source-identity, precision or layout guards on remaining features.

R21 export completed with the upper 6.35 extension line touching
the left stroke of the upper A cutting-plane label. Clearance above an arrow
does not prove clearance from its label: inspect the actual glyph ink against
the dimension's complete extension segments as well.

R27 proved all three common-flat imports and their final rebuilt owners, but
its complete three-row qualifier collided with the section label and height
extension. Keep the cleared vertical witness station; move the common-flat
text station from `(50, 175.5)` to `(150, 175.5)` mm instead of lifting it back
through the A stroke. R28 proved this station and the seat note at
`(260, 116)` mm with no gating native layout errors. The current ordinary
HEX drawing has one native `12.70 A/F` size, at two places with the default
band, applying to all three opposed-flat pairs over the full height. It has
no supplied-stock qualifier, separate receiving-envelope callout or finished
wall/floor inspection note: those belonged to the superseded acceptance
scheme. Preserve all five actual native flat-location controls, their values
and bands. Native final text/leader boxes and whole-sheet inspection, not
these historical station coordinates, prove the current layout.

Hole-callout variable arrays return concrete variable dispatches. Follow the
existing precision helper's dynamic metadata read for `VariableName`/`Type`,
then bind the matching concrete string interface for `String`. Merely wrapping
a returned variable as the declared base `ICalloutVariable` can invoke an
incompatible DISPID. Preserve the native2B value before and after print-only
class removal; the drawing's title block does not change the model fit.

For a drawing-only cosmetic-thread `INote`, preserve the portable source text
but send a native CRLF payload and compare its literal readback. The observed
native setter retains CRLF even when sent LF; this is a line-ending boundary,
not permission to collapse spaces, blank lines or changed thread/mate text.
Read every independent post-state field before refusal, with per-reader errors
and precise indexed identity-call labels. Keep owner/attachment/dangling checks.

The 2026-10-22 R2 lever run imported one cosmetic-thread seed and instance,
but `ICThread.ThreadCallout` was still null. Import counts do not prove a
native drawing note exists. As in the clamping-kit hardware drawing, select
that thread's actual annotation in its view, require one `swSelCTHREADS` (39)
selection and `ISldWorks.IsSame` annotation identity, then invoke the void
`IDrawingDoc.InsertThreadCallout`. Rebuild and require the same single thread
annotation before reading its own `ThreadCallout` again. Only that native
`INote` receives the four-row print text and the existing owner, attachment,
literal CRLF, placement and readback checks. A null result, changed thread or
wrong selected identity remains fatal; never author a detached note.

The user clarified that this bracket is a straightforward tapped through hole.
Keep the ordinary end view and real native1/4-20 UNC THRU ALL callout; no A-A,
cutting arrows, orphan section marks or section-thread display/ink machinery
belongs in the production recipe. Its nominal12.50 neck now prints12.5; the
native3.175 foot carries explicit±0.13 and the real screw-grip reference. The
prior no-qualifier direction was superseded by the owner choice above.
Inside corners follow the actual title-blockR1.0 MAX default, not a bespoke
R0.25 inside restriction. The later explicit owner ruling on PR1856
(comment6367964749) narrows the foot's **Y width12.70→11.00**, centred at zero
to match the unchanged neckY±5.50. It does not widen the neck, alter its head
controls or merely hide the former0.85 dimension. Delete that physical
lateral-offset dimension and its inventory/precision/attachment machinery.
The vanished side ledges have no axial root edges: remove theirR0.60 bridge
fillets. Keep the applicableR0.25 inside X root and free-foot outer rounds,
but round only the **two free-end corners at localX−48**. The former+6.25
corner picks now lie on full-length upright edges; rounding them would
unauthorisedly change the head. The final part gate checks actual flushY planes
through the root, retained sharp upright corners, the unchanged nativeR5.50
nose axis/radius/extent, and the actualR0.25 inside-root and both outside-foot
cylinders with trimmed closest-point readback. These are nominal CAD identity
checks, not additional manufacturing tolerances.
Native success still requires enlarged visual inspection of the new root.

R10 (source14975bf5b91a, worker`swmaker00000f@15`,
attempt`20261023T153059Z-1-35ed5a70`) created the11mm foot and `InsideRoot`,
then failed native creation of `FootTopEdges` at the two free-foot front/side
edges. It did **not** reach `FootCorners`, holes, finishPMI or final topology
checks. The worker log explicitly reports no forensic artefacts; no failed
Brep was captured. Interacting termination at the newly coplanar side/root
junction is a source-grounded **inference**, not a measured kernel diagnosis.
The correction selects all **three raw incident edges**—insideXroot plus
both free-foot front/side edges—in one constantR0.25 native feature,
`RootAndFootRounds`, with `propagate=False`. It replaces the two sequential
features; there is no radius reduction, omitted outside round or fallback.
This follows the existing multi-edge constant-radius construction pattern in
`build_dt_cone_gear_shaft` (round and flat step-root edges selected together),
not a claim that its corner topology is identical. The final guard separately
reads each resulting cylindrical radius, axis and transverse centre, then a
trimmed diagonal point; successful construction and its actual corner patches
still require the next native run and enlarged inspection.

The previous5mm free-end extension remains: machineX−8..46.25,
localX−48..+6.25, length54.25 and setbacks9.00/22.70. The matched receiver,
bracket-clearance and screw axes remain localY−0.71 / machineY978.99 and
machineX1/14.7, with unchanged seat/threaded-lever pose. The receiver row is
still3.25±0.05 below the coefficient top; the narrowed foot's native lower-edge
ordinate is now **4.79±0.05**, not5.64. Foot11.0 retains ordinary`.X`±0.8:
the conservative head-clearance-circle ligaments are **2.79 /3.41** lower/upper,
and actual printedØ2.69MAX clearance-hole walls are **3.395 /4.015**.
The minimum foot-edge prying arm becomes **4.74**, charged to the same actual
width/location intervals. Do not substitute the receiver's unrelated±0.51.
The fixed-top7.00±0.51 plate backs the receiver pilot beyond the uniform
5.00±0.51 ribs; retain one native `3X 5.00` rib dimension. No receiver, grip or
engagement band changes with the foot cut.

The SM-facing **+Z foot back**, the physical origin of100.40, is a static
locating seat under rule6. Its part-owned `foot_seat` control is **Ra3.2µm**
(`SEAT_UM`), qualified by the real plane at `SIDE_PLATE_Z[1]`; it is not a
general all-faces grade, screw-head-bearing-front finish or new exception.
`mg_magnifying_bracket_finish_spec` keeps this derived face contract outside
the joint's dimensional-spec import cycle. Author it natively in the part,
then attach the drawing symbol to a visible edge adjacent to that exact face,
with controlled-face validation and native attachment/landing readback.
The title block's `CAST/MACHINED` row and `blued` finish specify no roughness
grade and do not replace the symbol. RV-02/RV-03 cover neither this seat nor
the mounting flags or line clearance.

R11c at source70b14d82f0ae natively passed the jointR0.25 construction,
four cylinder-geometry guards and19trimmed-point probes
(maximum serialized gap7.800000024e−8mm), plus controlled-seat PMI/drawing
attachment readback. Cylinder parameter arrays and attached-face identities
were **not** serialized; distinguish guard execution from a raw binding dump.
This qualified the local foot/root/head geometry, not installed assembly
soundness or sheet readability. The actual PDF and all three Codex runs
confirmed one gating finish defect: `Ra3.2`'s diagonal leader and filled arrow
strike the `a`. Its native segment ran from(75.475,104.0512) to
(79.125,112.0512)mm through the actual text; process success and a clear
annotation-envelope box did not make that readable.

Keep the exact controlled edge and projected landing. Create the symbol
**10mm to the right** and8mm below that landing, instead of10mm left:
the right-reading native grade is then away from the diagonal's route.
Do not drag the attached tip or relax its face/identity/landing guards.
Before accepting the placement, capture actual native display data and
refuse any own stroke or decoded arrow through an individual native text
run. Reuse the linear-callout guard's0.15mm run inset and1e−7m overlap limit;
these are ink-identity allowances, not new manufacturing or neighbour bands.
Retain the existing2mm neighbour clearance checks. FrozenR11c primitives
must fail the guard, while a clear simulated placement is only an offline
control: the next native sheet and actual PDF must still qualify the new ink.

For the12.5 thickness, jog its text beyond the outermost actual
native vertical witness plus4mm and above the front outline. R33 reported an
own-line crossing at the former qualified text's Xstation; the exact crossing
segment was not captured. Keep the native line/arrow/neighbor checks strict.
For `TapFromSide`, use the existing `MountingY0` two-axis jog pattern: text
left4mm beyond the last vertical witness and bottom2.2mm above the measured
pre-placement leader extent. R35 rejected an X-only jog. Requested positions
do not prove the new native jog; retain the actual own-ink and neighbor guards.

The 2026-10-22 R2 bracket run also rejected `MountingY0` after changing
`OffsetText` and rebuilding during its move. Its target came from the old
pre-offset segments; the failing final box/primitive was not captured, so its
exact crossing is unknown. Set and rebuild the native `CenterText`/`OffsetText`
modes first, then derive the existing two-axis jog from the settled native
text/line geometry. Preserve all own-line, neighbour, silhouette and sheet
guards. Capture native text runs, raw lines/arrows and decoded boxes/segments
before modes, after their rebuild and for every final annotation before any
layout guard can fail. The current4.79 row and historical5.64 row retain the
same measured-placement algorithm without changing their model authorities.
Offline historical-witness and simulated mode-transition controls cover both,
including a stale-target crossing and strict rejection. They are not a
replay of the uncaptured R2 primitive or proof that a new native sheet clears;
the combined native drawing run and whole-sheet audit remain required.

The retained structural text is authored with native below-value compartments
on the part, then asserted verbatim after model-item import; the drawing never
rewrites it. All three head bands enter the existing native ink guards. For
the now three-row foot callout, settle `OffsetText` first, keep its full width
4mm left of the overall-reference witness and its bottom4mm above its own
settled leader extent. Guard own-line crossings against each native text run:
the blank space between value and below-text is not glyph ink. Keep the full
union for neighbour, silhouette and sheet containment. This remains the same
single sheet and four views; native redraw and machinist review decide fit.

The 2026-10-23 R7 bracket attempt `20261023T062821Z-1-881fad50`
(source `6e9e4a5e5884`) captured all final native ink before refusing
`NoseR: neighbouring native line crowds its text`. Its radius text union was
X245.683–286.317/Y223.4437–232.500mm. The through-tap leader from
(230.5142,212.8907) to (314.4281,227.6389)mm crossed that union's 2mm
clearance envelope for 9.2782mm. The same capture also showed the
`TapFromTip` outward-arrow flank crossing its `RETAINS TAP WALL` row.
No forensic PDF/image was captured, so these are native envelope measurements,
not exported glyph proof.

Retain the associative through-tap annotation as the radius lane authority.
Keep the radius union's X station and put its bottom4mm above that leader's
measured top (R7 coordinates imply Y231.6389mm, +8.1952mm). Set and rebuild
`TapFromTip` offset mode before measuring: place its complete union4mm left
of its own vertical witnesses and4mm above its settled native line/arrow
extent. The captured X206mm witness and40.634mm text width imply
X161.366mm instead of165.366mm; the new Y depends on the actual offset-mode
rebuild, not the old arrow position. Preserve the 2mm neighbour guard,
individual-run own-ink guards, all functional rows/bands and all four views.
The regression retains R7's head rows, tap leader and arrow flanks; new
offset-mode geometry/moves remain simulations until the next native redraw.

The overall seat-to-nose span is a native drawing reference, not a second
manufacturing tolerance: select the actual mounting-seat edge and nose arc,
set/read back the maximum arc endpoint, and parenthesize the measured result.
Its places come from the part spec's `DRAWING_REFERENCE_PRECISION`. Retain its
constructor annotation just like the lateral dimension. The foot-thickness
text and witness lane stay left of both the measured overall-reference and
seat-to-axis vertical stations, so the new reference does not cross that text.
Do not blank `MountingCoordinates` to remove construction-carrier fragments:
that known operation also hides the delivered native locating dimensions.

The earlier+10 option intersected the existing hex knife stub and was rejected.
The knife mount's pre-existing0.6835 nominal axial air gap is not a2mm wall
policy violation or permission to claim a full articulation clearance proof.
Validate the isometric caption against actual nativeIView.ScaleRatio and
inspect the final whole PDF/PNG, including the enlarged root, for clarity.

The LEVER TIP DETAIL retains its model-owned1.25 projection, attached native
dimension import, actual lever/bracket component and source-configuration
checks, source immutability, 4:1 view, and persisted native crop readback.
Use native projected source stations only to place the dimension and crop;
they do not prove the solids are visible. Inspect the actual exported PNG/PDF
to confirm both the flat lever tip and far bracket face are clearly visible,
then require formal machinist review. The user explicitly removed the added
G7 parser/count-priming/canonical-edge diagnostic subsystem: no substitute
polyline acceptance contract, retry, copied outline or suppressed warning.

Suppress inference while creating the native crop boundary, restore AddToDB,
and check IView.GetDetailCircleInfo2 against the requested centre/radius.
Keep captions outside the complete actual IView.GetOutline and retain ordinary
whole-dimension text, witness/arrow and sheet/title-block clearance checks.
Native export success alone is not physical-visibility or layout acceptance.

The lever's single native Detail A thread callout prints four rows: thread,
entry chamfer, mate ID, then `BRACKET`. Keep the last word wrapped so the mate
row does not cross the thread-length tip witness; do not restore a detached
manual copy. The R10 glyph/witness replay is only an offline collision control.
The current native note's actual font, leader, complete ink and neighbouring
dimension clearance remain required native export/audit checks.

The MHA-MG-00 sheet 4 final wire CHECK also crossed into the tolerance panel.
R22 wrapping of only that CHECK cleared the actual glyphs but left a gating
keep-out for the aggregate note rectangle, whose width came from a preceding
row. Keep the entire measured CHECK block outside the panel: reflow the widest
row as well, preserving every word, native font, total row count and insertion
point. Check both the complete note extent and individual text-run ink against
the panel, border, preceding steps and finished view in the rebuilt whole
sheet. A character-count limit alone is not a physical clearance proof; do
not weaken the audit or exempt this note.

For a long native mounting-hole callout, the existing process-prefix trailing
newline puts the associative quantity/diameter/extent on its own row; do not
replace native variables with literal copied text. Check the complete native
text and line/arrow envelopes against the selected shared template's current
title-block keep-out, including a shoulder that outlasts the text after reflow.

Keep nominal model travel separate from published operating capacity.
`operating_clamp_radius_band` uses the fitted tip-projection frame. With
knife-to-bracket-centre $C=55$, neck $N=12.5\pm0.8$, projection
$P=1.25\pm0.51$, rod $L=167.5\pm0.8$ and thread $T=18.00\pm0.51$,
the free tip is $K=C-N/2-P+L$. The ordinary HEX and actual tap-entry locations
keep the station inside the body; its derived full-height17 bound therefore
covers either bore end without inventing symmetric±8.5. The minimum radius
is $\max(C-N_{\min}/2-P_{\min}+T_{\max},C+N_{\max}/2)+17=83.920$.
Rod length cancels at runout. The maximum is
$K_{\min}-D_{\max}/2-17=193.115$, with short rod, thick neck and greatest
projection acting together. Built165 and nominal part geometry do not move.
These are not new printed stock limits or all-machine clearance claims.

As-made fit-up can inspect and admit more travel, but published capacity does
not credit it. These fitted component bounds, rather than a fixed free-tip frame, are
not a positive stop or an all-machine articulation certificate. Keep the entire
bore clear of the as-made runout/thread and hemisphere. The existing minimum-
pose/kinematics native gate remains open.

The unseated lever thread is not a static clamp: it has no shoulder or preload,
and its rotation sets installed projection. Its operational retention audit
uses the existing adjuster classification and joint-specific
`U-MHA-MG-03-no-lock` ruling, also declared as RV-02 in the assembly and mating
part packages. The user's exact2026-10-20 direction was “no further thread
locking needed because mg-magnifying-lever does not experience rotational
forces”. The approved implementation has no added lock; that is not native
test proof of immunity to vibration, projection drift or backout. The former
custom-root wall declaration is removed; normal standard tapping does not
establish an upper root limit or an all-standard-variation wall guarantee.

The retention and wall checks are not a brass strength certification. Wire
force below the lever produces bending even though there is no torque about
its thread axis. The conservative 10.7 N wire / 1.22 N hanging-weight audit
puts nominal stress near the basic 1/4-20 root above 120 MPa,
before any thread-notch factor. The specified generic brass has no guaranteed
alloy/temper yield minimum; do not claim a yield margin from its CAD material
or transfer the steel bracket's allowable stress to it. For context, even
[Wieland C36000 under 1/2 in](https://wieland-chase.com/36000-standard-alloys/)
has a 25 ksi minimum yield, not the frequently quoted 45 ksi typical value.
No alloy or temper substitution is authorized by this geometry change.

The user explicitly retained generic low-carbon steel with the blued finish,
not a named certified grade. `mg_magnifying_bracket_arm_check.py` supplies the
load-demand screen consumed by `error_budget.py` in JSON and human-readable
reports. Its factor-three simultaneous bending/torsion demand uses the fitted
maximum gravity arm of 161.710 mm, derived from the same length/neck/projection
bands above, not the nominal 160 mm arm. Joint moments use the actual relocated
screw-row centroid projected to the seat plane. Assumed E200 GPa/G79 GPa serve
compliance calculations only; verified yield and verified yield safety factor
remain unavailable. This is a calculated procurement demand, not a material-data
acceptance gate, native proof or demonstrated safety factor.
The section uses minimum accepted11.7×10.9, with maximum accepted axial
reach101.01 to the seat and arm span97.965 after minimum3.045 grip. The
prying screen charges the mounting-location band and the foot's own width
interval. X/Y load stations remain the nominal A1 pose; none of this certifies
every manufactured geometry or the receiver's actual contact footprint.

Keep a mounting-face caption beside the view it describes, clear of its
native hole leader and coordinate witnesses. Distribute short controls
between views rather than forcing overlapping inside arrowheads. For each
new source state, the final native layout audit and rendered sheet—not old
sheet coordinates or source-only tests—decide whether that placement ships.

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

Dashes in an HLR view are not always hidden lines. A part-hidden reference
sketch that `_drawing_hidden_sketches.curate_view_dimensions` shows in a view
prints its construction segments as dashes; a converted edge then reads as a
dashed hidden line on the outline (mg_magnifying_clamp, machinist review of
2056e3344). Changing the display mode does nothing. Measured on that drawing:
setting `ISketchSegment.Layer` on a segment's view instance
(`IView.GetCorresponding`) to a hidden layer does not read back (farm run
20261024T122828167Z, Arc2). A per-view `BlankSketch` after the import and
grouping, followed by setting each imported dimension's `IAnnotation.Visible`
back (the blank alone reads them 3, r21), hides the ink and keeps the
dimensions. Their attachments re-prove (forward identity, `IsDangling` False)
after the blank and after the final rebuild (run 20261024T124533556Z). See
`draw_mg_magnifying_clamp._blank_front_reference_sketch`.

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

### A bare land with no feature dimension of its own: a model witness circle

A turned land cut from a longer core (a neck between a collar and a journal)
has no feature dimension of its own, and the core's dimension carries
another land's fit band. Give it a **construction witness circle** in a
model sketch on a plane at the land's end, driven by the core's global and
toleranced in the build, then drag its diameter onto the land in the
drawing (`build_dt_crankshaft`: `NeckDiaDim` on the seat step's profile,
`OutboardNeckDia` on the journal's). Its extension lines then lie on the
land's own silhouettes. The drawing never authors a tolerance: a
drawing-created dimension cannot carry a model band, and
`test_drawing_specification_purity` refuses tolerance writes in a draw
script. Two SDK traps from the drawing-only measurement this replaced:
setting `IView.ProjectedDimensions` deletes the view's existing dimensions,
and a drawing-created circle diameter reads doubled (19.05 for a 9.525 core)
in projected mode.

A surface-finish symbol attached to a FACE with a smart arrowhead prints a
dot (farm run 20261023T182235406Z). Where such a symbol needs a straight
leader with a filled arrow (the crankshaft collar's rear face), call
`SetLeader3(1, 0, False, False, False, False)` then
`SetArrowHeadStyleAtIndex(0, 1)` on its live `IAnnotation`, each requiring an
integer status of `0`.


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
