---
name: drawing-view-sketch-space
description: Sketch geometry drawn inside an ACTIVATED drawing view (section cut lines, detail circles) is in view space (model units, origin = model origin), not sheet meters; convert via ModelToViewTransform origin + ScaleRatio. Probe recipe for a failing coordinate pick.
metadata:
  type: project
---

2026-09-02: the fleet's first section (`create_section_view`) and detail
(`create_detail_view`) users failed on the seat with "failed to select
<label> edge 0 at sheet (x, y)" / "failed to add the <label> dimension".
Bounding boxes, scales and positions all looked right; the picks found only
the drawing view itself (`swSelDRAWINGVIEWS` = 12).

**Cause.** After `IDrawingDoc.ActivateView`, `ISketchManager.CreateLine` /
`CreateCircle` coordinates are the VIEW's sketch space: model units with the
origin at the model origin's projection, scaled by the view. A cut line asked
for at sheet (0.1125, 0.152..0.248) was drawn at model (112.5, 152..248) mm
-- its "A" arrow sat above the sheet's top edge and the section cut nothing
(hollow outline, no hatch). The official CreateSectionViewAt5 example draws
its line at +/-2 model units for the same reason.

**Fix.** `_drawing_common._sheet_to_view_sketch`: `(sheet - origin) / scale`
with `origin = model_point_in_view(view, (0,0,0))` and
`scale = ScaleRatio[0]/ScaleRatio[1]`; both helpers keep their sheet-meter
API. Rotated views (`IView.Angle` != 0) would also need the axes turned.

**How to apply / debug a pick.** Never reason a coordinate pick from bbox
math alone; run `cad/scripts/diagnostics/probe_drawing_pick.py
<draw_module> "<label substring>"` (seat idle): it wraps `add_edge_dimension`, prints
the view outline/position, sweeps `SelectByID2` on a grid and prints an
ASCII map of edge hits, reports the selection TYPE at the pick points, tries
the dimension, and saves a sheet snapshot (SaveAs3 SLDDRW then PDF, then
pdftoppm) so the geometry can be SEEN. Type 12 at a pick = nothing there.
SaveAs3's return code is unreliable; trust file existence.
