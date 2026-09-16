# SolidWorks drawing layout tuning

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
HARMONIC_SW_AUTOSTART=0 HARMONIC_COM_SEAT=audit:layout \
  uv run cad/scripts/diagnostics/drawing_layout_audit.py \
  cad/out/slddrw/<part>.SLDDRW [--json dump.json] [--sheet N] [--quiet]
```

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
- **The lock serializes, it does not isolate.** Every process drives the SAME
  SolidWorks session, whose open-document table is keyed by FILENAME. A
  read-only probe that opens `top-frame.SLDDRW` also loads `top-frame.SLDPRT`
  read-only, and that part can stay resident after the drawing is closed; a
  sibling's `part:top_frame` build in another worktree then binds to the
  resident read-only copy and fails on the first `Select2` (measured
  2026-09-16: two deterministic Hole Wizard "face Select failed" runs). Diff
  `ISldWorks::GetDocuments` before/after a probe and `CloseDoc` every document
  the probe pulled in, or do not probe a drawing whose part a sibling may be
  building.
- Attach, never launch: `HARMONIC_SW_AUTOSTART=0` plus a held
  `HARMONIC_COM_SEAT`. `cad/scripts/diagnostics/_owned_native_session.py` is the
  attach-only runner.
- Open read-only + silent (`swOpenDocOptions_Silent | ..._ReadOnly`) and close
  by explicit path with `ISldWorks::CloseDoc(path)`. **Never
  `CloseAllDocuments`** — it destroys whatever a sibling agent has open. Prove
  you left nothing behind: `ISldWorks::GetDocumentCount()` and `ActiveDoc`.
- Keep each attach short and one-shot. A held session blocks every sibling's
  build; ten seconds of audit does not.
- Never launch a `doit` build to inspect a drawing. Audit the open document.
- One export at the end. If you are exporting to see where something is, stop
  and run the audit instead.
