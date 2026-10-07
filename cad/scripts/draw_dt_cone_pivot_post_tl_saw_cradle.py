r"""Create the drawing for the cone pivot post's saw cradle (MHA-DT-005-TL-02).

Three ASME third-angle views at 1:2 plus the isometric. Every dimension runs
from the origin corner the build anchors each sketch to: the base's kerf-side
end (X), its underside (Y) and its side face (Z).

* Front: the saddle and pad stations above the view, the overall and base
  heights left of it, all from the end face and the underside.
* Top: the base size and the two stud taps, with the native tap callout.
* Right: the saddle width stations and the seat (diameter, axis station,
  bottom height), from the side face and the underside.

Run (SolidWorks already open)::

    uv run python cad\scripts\draw_dt_cone_pivot_post_tl_saw_cradle.py dt-cone-pivot-post-tl-saw-cradle
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
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
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from dt_cone_pivot_post_tl_saw_cradle_spec import (
    BASE_LENGTH,
    BASE_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FOOT_SADDLE_X,
    HEAD_SADDLE_X,
    OVERALL_HT,
    PAD_X0,
    PAD_X1,
    SADDLE_Z,
    SEAT_CENTRE_Y,
    STUD_TAP_DRILL,
    STUD_X,
    STUD_Z,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["dt_cone_pivot_post_tl_saw_cradle"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 95 x 100 x 39 block: 1:2 leaves room for the six stacked stations above
# the front view and keeps the right view clear of the title block.
SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # sheet metres per model mm

FRONT_CENTER = (0.095, 0.090)
TOP_CENTER = (FRONT_CENTER[0], 0.180)
RIGHT_CENTER = (0.185, FRONT_CENTER[1])
ISO_CENTER = (0.320, 0.185)
ISO_NOTE_XY = (0.280, 0.240)
NOTES_XY = (0.020, 0.060)

_ROW = 0.007  # baseline-stack pitch
_GAP = 0.008  # first row's clearance from the view


def _x(model_x: float) -> float:
    """Sheet X of a model X in the front and top views (bbox-centred)."""
    return FRONT_CENTER[0] + (model_x - BASE_LENGTH / 2.0) * _S


def _y(model_y: float) -> float:
    """Sheet Y of a model Y in the front and right views."""
    return FRONT_CENTER[1] + (model_y - OVERALL_HT / 2.0) * _S


def _top_y(model_z: float) -> float:
    """Sheet Y of a model Z in the top view (the side face Z0 is at the top)."""
    return TOP_CENTER[1] - (model_z - BASE_WIDTH / 2.0) * _S


def _right_x(model_z: float) -> float:
    """Sheet X of a model Z in the right view (the side face Z0 is at the right)."""
    return RIGHT_CENTER[0] - (model_z - BASE_WIDTH / 2.0) * _S


_FRONT_TOP = _y(OVERALL_HT)
# Stations above the front view, nearest first, each to a saddle or pad top
# corner; the heights stack left of the end face.
FRONT_KEEP = {
    name: (_x(station / 2.0), _FRONT_TOP + _GAP + index * _ROW)
    for index, (name, station) in enumerate(
        (
            ("HeadSaddleX0", HEAD_SADDLE_X[0]),
            ("HeadSaddleX1", HEAD_SADDLE_X[1]),
            ("PadX0", PAD_X0),
            ("PadX1", PAD_X1),
            ("FootSaddleX0", FOOT_SADDLE_X[0]),
            ("FootSaddleX1", FOOT_SADDLE_X[1]),
        )
    )
} | {
    "BaseHt": (_x(0.0) - _GAP, _y(9.5)),
    "OverallHt": (_x(0.0) - _GAP - 1.2 * _ROW, _y(OVERALL_HT / 2.0)),
}
_TOP_TOP = _top_y(0.0)
TOP_KEEP = {
    "StudX": (_x(STUD_X / 2.0), _TOP_TOP + _GAP),
    "BaseLength": (_x(BASE_LENGTH / 2.0), _TOP_TOP + _GAP + _ROW),
    "StudNearZ": (_x(0.0) - _GAP, _top_y(STUD_Z[0] / 2.0)),
    "StudFarZ": (_x(0.0) - _GAP - 1.2 * _ROW, _top_y(STUD_Z[1] / 2.0)),
    "BaseWidth": (_x(BASE_LENGTH) + _GAP, TOP_CENTER[1]),
}
# The seat axis stands above the saddle tops, so the side-face stations stack
# above it; the seat-bottom height stands right of the side face.
_SEAT_AXIS_TOP = _y(SEAT_CENTRE_Y)
RIGHT_KEEP = {
    "SaddleZ0": (_right_x(SADDLE_Z[0] / 2.0), _SEAT_AXIS_TOP + _GAP),
    "SeatZ": (_right_x(BASE_WIDTH / 4.0), _SEAT_AXIS_TOP + _GAP + _ROW),
    "SaddleZ1": (_right_x(SADDLE_Z[1] / 2.0), _SEAT_AXIS_TOP + _GAP + 2 * _ROW),
    "SeatBottomHt": (_right_x(0.0) + _GAP, _y(14.0)),
    "SeatDia": (_right_x(BASE_WIDTH) - 0.010, _SEAT_AXIS_TOP + _GAP),
}
# The tap callout leads from the near stud's drill rim to the clear sheet
# right of the top view's station stack.
NEAR_STUD_RIM = (_x(STUD_X + STUD_TAP_DRILL / 2.0), _top_y(STUD_Z[0]))
TAP_CALLOUT_XY = (_x(BASE_LENGTH) + 0.012, _TOP_TOP + 0.004)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open saw-cradle source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Post Saw Cradle Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "cone pivot post saw cradle; milled 1018 block; MHA-DT-005-TL-02",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # The taps are fully stated by their callout and the seats show in the
    # right view, so no view needs hidden lines. The iso takes HLR first too,
    # as on the pen hanger: on the bare iso finalize_drawing's shaded-with-
    # edges readback kept its high-quality cosmetic-thread flag False.
    for view in (front, top, right, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = []
    for view, keep, label in (
        (front, FRONT_KEEP, "front"),
        (top, TOP_KEEP, "top"),
        (right, RIGHT_KEEP, "right"),
    ):
        annotations += curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=label,
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the stud taps")

    add_native_hole_callout(
        adapter,
        top,
        edge_xy=NEAR_STUD_RIM,
        callout_xy=TAP_CALLOUT_XY,
        label="cap-bridge stud taps",
        process="TAP",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # Materialize the iso's cosmetic threads before the strict final note
    # cleanup; otherwise their label first appears during the native save.
    import_cosmetic_threads(adapter, iso)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Post Saw Cradle Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "... Tapped Hole" note once a tap carries a
        # hole callout; the callout already states the thread and drill.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
