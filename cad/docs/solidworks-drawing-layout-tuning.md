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
callout wording, view choice. That is `cad/docs/drawing-simplicity-policy.md`.

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

## What is readable from the API (stop guessing)

| Question | API | Evidence |
| --- | --- | --- |
| A view's sheet box, metres | `IView::GetOutline` -> `[xmin, ymin, xmax, ymax]` | `types/IView/GetOutline.md` |
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
| Where a datum tag REALLY went after `SetPosition2` | `IAnnotation::GetPosition` — the leader/symbol junction, not the symbol centre: reads 0–5 mm from the request on a straight attachment, 17 mm on an OD-attached tag whose attachment re-solved along the edge (bearing swung 4.7°). `IAnnotation::GetLeaderCount` is 0 for every datum tag, and in the authoring session `IDatumTag::GetLineCount/GetLineAtIndex` stay frozen at the INSERTION geometry through a rebuild — useless as a readback. | `drawing:pinion_cam` datums A–D, 2026-09-16, two seats; `_drawing_common.add_datum_feature` |

All of it is **sheet space, metres**, origin at the sheet's lower-left — for
view-owned annotations too (measured: a dimension inside a view 102 mm from the
left edge reports `GetPosition` x = 0.074 m, and its `GetDisplayData` lines agree).
Report and reason in mm; call the API in m. The third coordinate is model depth
and is not always 0; ignore it.

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
  (`_drawing_common._zoomed_on`; `draw_fr_frame_assembly._short_frame_balloon`
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

**b. `IView::SetDisplayMode4` refusing HLR on a native detail view.**
Don't: read `False` as "detail views can't do HLR". Two causes, both documented
in `types/IView/SetDisplayMode4.md`: (1) `UseParent = True` — "If UseParent is
true and a parent view exists, then this method's Mode, Faceted, and Edges
parameters are ignored"; (2) a same-mode set is a no-op that also returns False.
Do: pass `UseParent = False` and assert the RESULT, not the return value:
`GetUseParentDisplayMode()` must read False and `GetDisplayMode2()` must read the
mode you asked for (`types/IView/GetUseParentDisplayMode.md`,
`types/IView/GetDisplayMode2.md`). This is what
`_drawing_common.set_hidden_lines_visible` does: `SetDisplayMode4(False, HLR,
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
`_drawing_common.set_hidden_lines_visible` exists for exactly this and is
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
`_drawing_common.create_section_view(..., partial=True)` passes
`swCreateSectionView_Partial` (0x10) to `CreateSectionViewAt5`, SolidWorks
sections just the span, the cut closes, and `GetPartialSection()` reads True by
design (top-frame B-B/E-E; the recipe's `_assert_section_display(removed=True)`
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
`_drawing_common.model_point_in_view` wraps.

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
(`_drawing_common._assert_attached_to`). `ISldWorks::IsSame` proves an edge or
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

**j. A fresh detail view whose readbacks lag its ink.**
Right after `CreateDetailViewAt4` + rebuild, `IView::GetOutline` is centred
on the request while `ModelToViewTransform` projects the circle centre 99 mm
away and `Position` reads 99 mm from where `SetViewPosition` later has to put
it (cone_swing_platform detail B, leaf 20260928T075849Z-1-882b4704). A loop
that "corrects" the projection moves a correct view off the sheet target and
needs a second move to recover; on three #1105 leaves it never did.
Do: place by the outline centre (`GetOutline` is the ink; `SetViewPosition`
moves it by the delta from the `Position` it reads), then re-read the
projection until it agrees with the outline before hanging anything on the
view.
The same holds for a section after `IDrSection::SetReversedCutDirection`:
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

**l. A datum named by a frame's datum identifier.**
Don't: name a pattern datum with `IGtol::SetDatumIdentifier` and take
`GetDatumIdentifier` as proof. On the knife mount (farm run
20261009T171439353Z) it read "B" back before and after the rebuild and the
sheet printed no B, while the tap and bore frames referenced A|B. The API
help (`types/IGtol/SetDatumIdentifier.md`) says only that it "sets the name
of the datum being defined"; the frame XML schema has no node for it.
Do: insert a real datum tag on the selected frame
(`_drawing_common.add_frame_datum_feature`) and require the tag's attachment
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
(`_gtol_spec.TRANSLATION_GLYPH`). On farm run 20261009T204136744Z both slot
frames printed "<GTOL-POSI> | 0.05 | C | B | <MOD-TRANS2>", the triangle in
the datum's compartment and no vector. Every flag form tried printed a
vector (run 20261009T182549169Z): empty i, j, k printed "[0,0,0]", "false"
values printed "[false,false,false]", and SOLIDWORKS rewrote the flag after
the letter to the empty-vector XML. `add_feature_control_frame` still reads
the printed text items (`IAnnotation::GetDisplayData`) and fails on any
bracket or a missing or misplaced glyph
(`_gtol_spec.translation_print_problem`), logging `gtol.translation_print`.
`GetSymbolXml` reads the symbol code back unescaped,
`<DatumLetter>C<MOD-TRANS2></DatumLetter>`, which is not well-formed XML
(run 20261009T200747541Z); the frame-XML parser escapes `<MOD-…>`/`<GTOL-…>`
codes before parsing.

## The sheet-split rule

When two views' callouts are squeezed together, the fix is a NEW SHEET, not a
smaller scale. Policy rule 8: extra sheets are cheap, cramming is not. The
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
