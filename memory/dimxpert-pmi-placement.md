---
name: dimxpert-pmi-placement
description: "Why the pipeline uses PLAIN model annotations for GD&T, not DimXpert (2026-07-29): DimXpert display positions are UI-drag-only (every COM setter reverts at save; FCFs on cylindrical faces only legal in the axis-perpendicular view; imported frames stack). Plain InsertGtol/InsertDatumTag2: SetPosition2 persists exactly on part AND sheet — but seed frame compartments BEFORE ConvertFormat, and import per view requesting only still-missing types (re-requesting duplicates; datum tags need the axis-aligned view)."
metadata:
  type: project
---

The display/placement layer on top of [[dimxpert-authoring-probe]] (authoring
itself). All facts probe-verified on transgear-stub, R2026x SP3.0 Makers seat;
probes in `cad/scripts/diagnostics/probe_pmi_*.py` (worktree branch
`dimxpert-pmi-migration`, PR #450).

**The legality rule (user-discovered, explains every symptom).** An FCF on a
cylindrical face is only legal in the annotation view PERPENDICULAR to the
face's axis — Top for this repo's Y-axis turned parts (UI: right-click
annotation > Select Annotation View > Top). PMI authored into any other view
is CORRUPTED: unselectable/unmovable, positions revert at save, datum glyph
renders rotated on sheets, frames co-locate. Symptom cluster = wrong view.

**Routing at insert time is asymmetric.** `ShowNamedView2` before authoring
routes `InsertDatum` to the view matching the viewport — but `InsertGtol`
IGNORES the viewport and lands front-ish regardless. Fix in
`_part_pmi._consolidate_pmi_annotation_views`: move everything into the ±Y
view (`GetViewRotation()[7]| > 0.999`). `MoveAnnotations` persists ONLY into
DimXpert's own AUTO-created views (a view from `InsertAnnotationView` loses
the moved annotations at save), so the ±Y view must already exist — the datum
insert creates it.

**Persistence matrix (why placement is drag-only).**
- `IGtol.SetPosition` / `IAnnotation.SetPosition2`: take transiently, ALWAYS
  revert at save — part and sheet, legal and corrupt state alike. The bool
  return is False even when the transient move happens.
- UI drag: persists (user-proven part + sheet, survives reopen + rebuild).
- A drag of imported PMI on a DRAWING SHEET writes the position back into the
  referenced PART (the drawing save then re-saves the part — that is also why
  drawing `SaveAs3` returns False-with-warning). So the part owns positions.
- Sheet `ImportAnnotations` PROJECTS part-side positions: a part with
  separated positions imports separated; the default (near-identical)
  positions import stacked at the view centre, overprinting frames.

**Sheet display needs a section view.** In the part viewport the legal-state
PMI is nearly invisible: Top view = annotated faces occluded by the collar
(SW suppresses the display), iso = frames foreshortened to slivers in the Top
plane. Same on sheets — a plain top view shows floating/no annotations; a
Top-aligned SECTION view through the annotated bosses displays all PMI
(datum included) attached and movable. Recipe: horizontal cut in the front
view at the annotated feature's height (`create_section_view` +
`model_point_in_view`), import DimXpert annotations into the section view
only.

**RESOLUTION (2026-07-29): the pipeline uses PLAIN annotations, not
DimXpert.** `IModelDoc2::InsertGtol` / `::InsertDatumTag2` on the same spec
faces have NONE of the pathologies: `SetPosition2` persists EXACTLY (0.00 mm)
through save+reopen on both part and sheet
(`probe_pmi_plain_annotations.py`). Two plain-gtol gotchas: (1) `InsertGtol`
creates an OLD-format gtol with no frame API — seed the simple compartments
(`SetFrameSymbols2`/`SetFrameValues2`) BEFORE `ConvertFormat`; converting an
empty frame first permanently drops the tolerance display. (2)
`IDrawingDoc::InsertModelAnnotations3` re-inserts an already-imported gtol
into every further view it is asked about — import per view requesting only
the annotation types still missing (gtols land in any view; a datum tag only
lands in a view aligned with its attachment face, i.e. the axis/end view for
turned parts). A datum tag's position snaps to its leader-consistent locus
at SET time — constrained but deterministic. Plain annotations print black
natively (no PDF-color toggle needed). The synthesized-drag path for
DimXpert placement was abandoned untested (needs unlocked desktop +
foreground; `GetForegroundWindow()=0` when locked).

**COM gotchas hit on the way:** `IMathUtility.CreatePoint` with a bare Python
list MIS-MARSHALS (elements shift one slot; transforms silently wrong) — pass
`double_array(...)` (`solidworks_mcp.adapters.com_variant`), as
`model_point_in_view` does. Teal PMI on sheets = COLOR PDF export; set app
toggle `swPDFExportInColor` (323) False around the PDF save for B&W sheets.
