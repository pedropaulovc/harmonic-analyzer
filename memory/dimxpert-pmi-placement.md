---
name: dimxpert-pmi-placement
description: "DimXpert PMI display/placement rules (2026-07-29, user-discovered + probe-verified): FCFs on cylindrical faces are only LEGAL in the axis-perpendicular (Top) annotation view; InsertGtol ignores viewport routing (datums honor it) so consolidation must move gtols into the ±Y auto view; COM SetPosition reverts at save in EVERY state, UI drag is the only durable move and a SHEET drag writes back into the part; sheet import projects part-side positions."
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

**Open half (blocked on unlocked desktop when last tried):** whether a
SYNTHESIZED drag on the sheet persists + writes back like the manual one —
`probe_pmi_sheet_drag2.py`. If yes, the pipeline places PMI at part-build
time via a throwaway section drawing. Synthesized input needs an UNLOCKED
interactive desktop + foreground (locked desktop ⇒ `GetForegroundWindow()=0`,
every foreground trick fails) — that fragility is inherent; fail loud.

**COM gotchas hit on the way:** `IMathUtility.CreatePoint` with a bare Python
list MIS-MARSHALS (elements shift one slot; transforms silently wrong) — pass
`double_array(...)` (`solidworks_mcp.adapters.com_variant`), as
`model_point_in_view` does. Teal PMI on sheets = COLOR PDF export; set app
toggle `swPDFExportInColor` (323) False around the PDF save for B&W sheets.
