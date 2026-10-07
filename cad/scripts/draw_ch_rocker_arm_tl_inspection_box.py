r"""Create the rework drawing for the rocker inspection box (MHA-CH-006-TL-08).

The bought box parallel is drawn whole; only the shop's rework is dimensioned:
the clamp windows on the left-side view, the back window on the rear view and
the C stop bar taps on the front view, each from the base and the face it
leaves whole.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    import_cosmetic_threads,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    visible_component_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_rocker_arm_tl_inspection_box_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    TAP_DRILL_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_inspection_box"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 127 mm cube: 1:2 puts the left side, front and rear views in one row.
SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
LEFT_CENTER = (0.075, 0.165)
FRONT_CENTER = (0.170, 0.165)
BACK_CENTER = (0.265, 0.165)
ISO_CENTER = (0.370, 0.175)
ISO_NOTE_XY = (0.335, 0.240)
# Left-side view: the front face is on the view's right, the base at its foot.
LEFT_KEEP = {
    "WinLowFront": (0.100, 0.238),
    "WinLowW": (0.085, 0.224),
    "WinLowH": (0.118, 0.159),
    "WinLowBase": (0.032, 0.150),
    "WinUpBase": (0.020, 0.160),
}
FRONT_KEEP = {
    "TapY": (0.128, 0.152),
    "TapLeftX": (0.150, 0.118),
    "TapRightX": (0.165, 0.106),
}
BACK_KEEP = {
    "BackW": (0.265, 0.212),
    "BackH": (0.306, 0.170),
    "BackY0": (0.320, 0.150),
    "BackX0": (0.275, 0.118),
}
DIMENSION_CALLOUTS = {
    "WinLowW": "2X",
    "WinLowH": "2X",
    "WinLowFront": "2X WINDOWS THRU LEFT WALL",
    "BackW": "WINDOW THRU BACK WALL",
    "TapLeftX": "TAPS IN FRONT FACE",
}
TAP_CALLOUT_XY = (0.148, 0.215)
_THREAD_LABEL_LAYER = "INSPECTION-BOX-THREAD-LABEL-HIDDEN"


def _hide_thread_labels(adapter: Any, view: Any) -> int:
    """Hide the front view's cosmetic-thread label; the hole callout already
    states the thread (draw_dt_cone_tip_block's hidden-layer recipe)."""
    manager = _early_bound(adapter.currentModel.GetLayerManager(), "ILayerMgr")
    if manager.GetLayer(_THREAD_LABEL_LAYER) is None and int(
        manager.AddLayer(_THREAD_LABEL_LAYER, "duplicate thread labels", 0, 0, 0)
    ) != 1:
        raise RuntimeError("failed to add the inspection-box thread-label layer")
    layer = _early_bound(manager.GetLayer(_THREAD_LABEL_LAYER), "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("inspection-box thread-label layer is not hidden")
    hidden = 0
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        kind = int(annotation.GetType())
        # swCosmeticThread, or the thread's own "Tapped Hole" label note.
        if kind != 1 and not (kind == 6 and "Tapped Hole" in str(
            _early_bound(annotation.GetSpecificAnnotation(), "INote").GetText() or ""
        )):
            continue
        annotation.Layer = _THREAD_LABEL_LAYER
        if str(annotation.Layer or "") != _THREAD_LABEL_LAYER:
            raise RuntimeError("front-view cosmetic thread refused the hidden layer")
        hidden += 1
    if not hidden:
        raise RuntimeError("inspection box front view has no cosmetic thread label")
    rebuild_drawing(adapter, label="hide front-view thread labels")
    return hidden


def _tap_edge(adapter: Any, view: Any) -> Any:
    radius_m = TAP_DRILL_DIA / 2000.0
    for component in adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ():
        for raw in visible_component_entities(view, component, 1) or ():
            edge = _early_bound(raw, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve.IsCircle() and abs(float(curve.CircleParams[6]) - radius_m) <= 1e-6:
                return edge
    raise RuntimeError("inspection box front view shows no C stop bar tap")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open inspection box source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Inspection Box Rework Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker inspection box; bought box parallel, reworked; MHA-CH-006-TL-08",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=VIEW_SCALE)
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))
    for view in (left, front, back, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter, left, keep=LEFT_KEEP, view_label="left side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter, front, keep=FRONT_KEEP, view_label="front face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter, back, keep=BACK_KEEP, view_label="rear",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add center marks to the C stop bar taps")
    add_native_hole_callout(
        adapter,
        front,
        callout_xy=TAP_CALLOUT_XY,
        label="C stop bar #8-32 taps",
        edge=_tap_edge(adapter, front),
        process="#29 DRILL, THEN TAP",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.088)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # Precise shaded isometrics need the taps' cosmetic threads imported
    # (draw_pn_pen_hanger); the label would otherwise appear at save.
    import_cosmetic_threads(adapter, iso)
    _hide_thread_labels(adapter, front)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Inspection Box Rework Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
