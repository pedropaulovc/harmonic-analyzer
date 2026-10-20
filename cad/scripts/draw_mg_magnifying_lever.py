r"""Native quarter-inch lever sheet with an enlarged flat-thread-end detail.

The independent model detail imports its dimensions before its circular crop,
as on MHA-MG-04. Native diameters/lengths/limits remain associative; the part's
cosmetic thread and the sheet share one UNC-2A callout. Only the free end domes.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, dimension_name, place_view

from _check import check
from _com import _early_bound
from _drawing_common import DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties, rebuild_drawing, stamp_drawing_summary, view_name
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from mg_lever_thread_joint import ROD_DIA
from mg_magnifying_lever_spec import DRAWING_DIMENSIONS, DRAWING_PRECISION, FREE_END_CALLOUT, LEAD_CALLOUT, ROD_DIA_CALLOUT, SCREW_SEAT_CALLOUT, SURFACE_FINISHES, THREAD_CALLOUT, TIP_CALLOUT

SPEC = DRAWINGS_BY_NAME["mg_magnifying_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (1, 1)
FRONT_CENTER = (0.115, 0.120)
ISO_CENTER = (0.350, 0.105)
ISO_SCALE = (1, 2)
DETAIL_CENTER = (0.310, 0.190)
DETAIL_SCALE = (3, 1)
DETAIL_FOCUS = (0.156, 0.0, 0.0)
DETAIL_RADIUS_MM = 12.5
DETAIL_KEEP = {"ThreadLength": (0.323, 0.220), "TipChamfer": (0.377, 0.198), "IncompleteLength": (0.368, 0.165)}
FRONT_KEEP = {"OverallLength": (0.115, 0.088), "RodDia": (0.118, 0.150)}
CALLOUTS = {"RodDia": ROD_DIA_CALLOUT, "TipChamfer": TIP_CALLOUT, "IncompleteLength": LEAD_CALLOUT}


def _activate(adapter: Any, view: Any) -> None:
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("could not activate lever drawing view")
    adapter.currentModel.ClearSelection2(True)


def _note(adapter: Any, view: Any, text: str, xy: tuple[float, float]) -> None:
    _activate(adapter, view)
    if add_note(adapter, text, *xy) is None:
        raise RuntimeError(f"could not add lever note {text!r}")
    texts = [" ".join(str(_early_bound(found, "INote").GetText() or "").split()) for found in (_early_bound(view, "IView").GetNotes() or ())]
    if texts.count(" ".join(text.split())) != 1:
        raise RuntimeError(f"lever note is not owned by its view: {text!r}")


def _circle(adapter: Any, view: Any, center: tuple[float, float], radius: float, *, mark: bool = False) -> None:
    _activate(adapter, view)
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = mark
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError("could not create lever detail circle")
    if mark:
        segment = _early_bound(circle, "ISketchSegment")
        segment.Color = 0
        if int(segment.Color) != 0:
            raise RuntimeError("lever detail mark is not black")
        adapter.currentModel.ClearSelection2(True)


def _detail(adapter: Any) -> tuple[Any, list[Any]]:
    view = _early_bound(place_view(adapter, str(SOURCE), "*Front", *DETAIL_CENTER, scale=DETAIL_SCALE), "IView")
    if tuple(float(value) for value in view.ScaleRatio) != DETAIL_SCALE:
        raise RuntimeError("lever thread detail lost its native scale")
    focus = model_point_in_view(adapter, view, DETAIL_FOCUS, label="lever thread focus")
    position = tuple(float(value) for value in view.Position)
    if not view.SetViewPosition(double_array([position[i] + DETAIL_CENTER[i] - focus[i] for i in range(2)]), False):
        raise RuntimeError("could not position lever thread detail")
    rebuild_drawing(adapter, label="position lever thread detail")
    if math.dist(model_point_in_view(adapter, view, DETAIL_FOCUS, label="positioned lever focus"), DETAIL_CENTER) > 0.00005:
        raise RuntimeError("lever thread detail focus shifted")
    set_hidden_lines_removed(adapter, view)
    annotations = curate_hidden_dimensions(adapter, view, keep=DETAIL_KEEP, view_label="lever thread-end detail", dimensions_by_feature=DRAWING_DIMENSIONS)
    _circle(adapter, view, DETAIL_CENTER, DETAIL_RADIUS_MM * DETAIL_SCALE[0] / 1000.0)
    status = int(view.Crop2(False, False, 1))
    adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label="crop lever thread detail")
    view.UpdateViewDisplayGeometry()
    if status != 1 or not bool(view.IsCropped()) or bool(view.CropViewJaggedOutline) or bool(view.CropViewNoOutline):
        raise RuntimeError(f"lever thread detail crop failed: {status}")
    names = {dimension_name(adapter, _early_bound(annotation, "IAnnotation")) for annotation in (view.GetAnnotations() or ())}
    if not set(DETAIL_KEEP) <= names:
        raise RuntimeError(f"lever thread detail crop lost dimensions: {set(DETAIL_KEEP) - names}")
    return view, annotations


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    check("open quarter-inch lever source", await adapter.open_model(str(SOURCE)))
    read_required_properties(adapter.currentModel, ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity", "Iso View Note"), required=("Number", "Material Specification", "Finish", "Quantity", "Iso View Note"))
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout)
    stamp_drawing_summary(adapter, drawing, {0: "Magnifying Lever Rod Manufacturing Drawing", 1: "Harmonic Analyzer hobby-machinist book drawing", 2: "Harmonic Analyzer Project", 3: "quarter-inch brass lever; flat UNC-2A end; external die runout", 4: "Generated from the project-owned ASME B drawing standard"})
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    # Import the small details first: the same RodProfile owns the full view.
    detail, detailed = _detail(adapter)
    full = curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="lever full length", dimensions_by_feature=DRAWING_DIMENSIONS)
    annotations = [*detailed, *full]
    assert_imported_precision(adapter, annotations, {name: places for names in DRAWING_PRECISION.values() for name, places in names.items()})
    set_dimension_callouts(adapter, annotations, CALLOUTS)
    thread_pick = model_point_in_view(adapter, detail, (0.158, ROD_DIA / 2000.0, 0.0), label="lever thread callout landing")
    add_attached_note(adapter, detail, text=THREAD_CALLOUT, entity_xy=thread_pick, note_xy=(0.350, 0.244), label="native quarter-inch external thread", entity_type="SILHOUETTE")
    free_tip = model_point_in_view(adapter, front, (0.0, 0.0, 0.0), label="free hemispherical tip")
    add_attached_note(adapter, front, text=FREE_END_CALLOUT, entity_xy=free_tip, note_xy=(0.030, 0.185), label="free end hemisphere", entity_type="EDGE")
    seat_pick = model_point_in_view(adapter, front, (0.040, ROD_DIA / 4000.0, 0.0), label="whole-body screw seat finish")
    symbol = (seat_pick[0] - 0.010, FRONT_CENTER[1] + 0.020)
    add_surface_finish(adapter, front, edge_xy=seat_pick, entity_type="FACE", symbol_xy=symbol, leader_attach_xy=seat_pick, control=surface_finish_by_key(SURFACE_FINISHES, "clamp_screw_seat"), label="lever clamp screw seat finish", char_height=0.0025)
    _note(adapter, front, SCREW_SEAT_CALLOUT, (symbol[0] - 0.0025, symbol[1] + 0.013))
    focus = model_point_in_view(adapter, front, DETAIL_FOCUS, label="parent thread-detail mark")
    _circle(adapter, front, focus, DETAIL_RADIUS_MM / 1000.0, mark=True)
    _note(adapter, front, "A", (focus[0] + 0.016, focus[1] + 0.016))
    _note(adapter, detail, "DETAIL A  SCALE 3:1", (0.277, 0.142))
    add_property_linked_note(adapter, "Iso View Note", 0.320, 0.071)
    seeds, instances = import_cosmetic_threads(adapter, iso)
    if (seeds, instances) != (1, 1):
        raise RuntimeError(f"lever isometric external thread missing: {(seeds, instances)}")
    return await finalize_drawing(adapter, OUTPUTS, pdf_title="Magnifying Lever Rod Manufacturing Drawing", scale=SHEET_SCALE, layout=SPEC.layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
