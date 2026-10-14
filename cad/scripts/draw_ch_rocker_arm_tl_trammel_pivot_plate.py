r"""Create the drawing for the rocker template trammel's pivot plate (MHA-CH-006-TL-19)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_trammel_pivot_plate_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_trammel_pivot_plate_spec import (
    CALLOUTS_ABOVE,
    CALLOUTS_BELOW,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HOLE_Y,
    PLATE_HEIGHT,
    PLATE_LENGTH,
    PLATE_WIDTH,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_trammel_pivot_plate"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 50 x 38.1 x 19.05 plate: 2:1 keeps the Ø1.98 pilot and the seat cone
# legible. The top view carries the plan sizes and every station; section A-A
# along the hole centre line shows the seat cone, the pilot depth and the
# countersinks; the shaded isometric sits above the title block.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 1)
TOP_CENTER = (0.115, 0.195)
SECTION_CENTER = (0.305, 0.200)
ISO_CENTER = (0.335, 0.112)
ISO_NOTE_XY = (0.290, 0.152)
CAPTION_XY = (0.305, 0.163)
NOTES_XY = (0.020, 0.090)
# The cutting line runs the plate's length on the hole centre line, past
# both ends (model mm).
CUT_X = (-4.0, PLATE_LENGTH + 4.0)

# Every dimension's text position is a MODEL point (mm) off the part, mapped
# onto its view at run time, so the layout does not hang on which way a view
# lays the model's axes.
_H = PLATE_HEIGHT
_W = PLATE_WIDTH
TOP_KEEP: dict[str, tuple[float, float, float]] = {
    "PlateLength": (25.0, _H, -_W - 7.0),
    "PlateWidth": (-14.0, _H, -_W / 2.0),
    "HoleY": (-6.0, _H, -9.5),
    # The stations baseline from the left end, shortest nearest the part.
    "HoleLeftX": (5.0, _H, 5.0),
    "PilotX": (12.5, _H, 10.0),
    "HoleRightX": (20.0, _H, 15.0),
    # Between the left countersink and the seat, clear of both.
    "PilotY": (18.5, _H, -9.5),
    "HoleDia": (2.0, _H, -_W - 3.0),
    "PilotDia": (33.0, _H, -_W - 3.0),
}
SECTION_KEEP: dict[str, tuple[float, float, float]] = {
    "PlateHeight": (-8.0, _H / 2.0, -HOLE_Y),
    "PilotDepth": (57.0, _H - 3.0, -HOLE_Y),
    "SeatDia": (25.0, _H + 5.0, -HOLE_Y),
    "SeatFlankAngle": (32.0, _H + 9.0, -HOLE_Y),
    "CskDia": (10.0, _H + 5.0, -HOLE_Y),
    "CskFlankAngle": (2.0, _H + 9.0, -HOLE_Y),
}

_UP = [0.0, 1.0, 0.0]
_PIVOT_POINT = ("ch_rocker_arm_tl_trammel_pivot_point_spec", "TIP_ANGLE")


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

requirement(
    "seat_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), part_spec.PLATE_HEIGHT),),
    requirements=("height", "length", "width"),
    fields={
        "normal": (_UP, ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "y", "value": part_spec.PLATE_HEIGHT},
            ("PLATE_HEIGHT",),
        ),
        "height": (limits(part_spec.PLATE_HEIGHT, 2), ("PLATE_HEIGHT",)),
        "height_nominal": (part_spec.PLATE_HEIGHT, ("PLATE_HEIGHT",)),
        "length": (limits(part_spec.PLATE_LENGTH, 1), ("PLATE_LENGTH",)),
        "length_nominal": (part_spec.PLATE_LENGTH, ("PLATE_LENGTH",)),
        "width": (limits(part_spec.PLATE_WIDTH, 1), ("PLATE_WIDTH",)),
        "width_nominal": (part_spec.PLATE_WIDTH, ("PLATE_WIDTH",)),
    },
    precision={"height": 2, "length": 1, "width": 1},
)

requirement(
    "board_seat",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("height",),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "height": (limits(part_spec.PLATE_HEIGHT, 2), ("PLATE_HEIGHT",)),
    },
    precision={"height": 2},
)

requirement(
    "seat_pilot",
    kind="hole",
    faces=(CylinderFace(part_spec.PILOT_DIA, contains_x_mm=part_spec.SEAT_X),),
    requirements=("station", "width", "dia", "depth"),
    fields={
        "at": (
            [part_spec.SEAT_X, part_spec.PLATE_HEIGHT, -part_spec.HOLE_Y],
            ("SEAT_X", "PLATE_HEIGHT", "HOLE_Y"),
        ),
        "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
        "station": (limits(part_spec.SEAT_X, 1), ("SEAT_X",)),
        "station_nominal": (part_spec.SEAT_X, ("SEAT_X",)),
        # Across the plate width from the back long side (the mid-width line).
        "width": (limits(part_spec.HOLE_Y, 2), ("HOLE_Y",)),
        "width_nominal": (part_spec.HOLE_Y, ("HOLE_Y",)),
        "dia": (
            limits(part_spec.PILOT_DIA, 2, part_spec.DRILLED_BAND),
            (
                "PILOT_DIA",
                "DRILLED_BAND",
                ("ch_rocker_arm_tl_trammel_spec", "CENTER_DRILL_PILOT_DIA"),
            ),
        ),
        "dia_nominal": (part_spec.PILOT_DIA, ("PILOT_DIA",)),
        "depth": (
            limits(part_spec.PILOT_DEPTH, 1),
            ("PILOT_DEPTH", "SEAT_APEX_DEPTH_MAX", "PILOT_FLOOR_ROOM"),
        ),
        "depth_ref": (part_spec.PILOT_DEPTH, ("PILOT_DEPTH",)),
        "thru": (False, ("PILOT_DEPTH",)),
    },
    precision={"station": 1, "width": 2, "dia": 2, "depth": 1},
)

requirement(
    "pivot_seat",
    kind="seat",
    faces=(ConeFace(part_spec.SEAT_ANGLE / 2.0, contains_x_mm=part_spec.SEAT_X),),
    requirements=("dia", "angle_deg", "note"),
    fields={
        "parent": (
            "seat_pilot",
            ("PILOT_DIA", ("draw_ch_rocker_arm_tl_trammel_pivot_plate", "build")),
        ),
        "dia": (limits(part_spec.SEAT_DIA, 2), ("SEAT_DIA", "SEAT_FLANK_MIN")),
        "dia_nominal": (part_spec.SEAT_DIA, ("SEAT_DIA",)),
        # The included cone angle; the sheet prints the face-to-flank angle
        # (90 - half the included), whose general band moves each flank.
        "angle_deg": (
            part_spec.SEAT_ANGLE,
            (
                "SEAT_ANGLE",
                "SEAT_FLANK_ANGLE",
                ("ch_rocker_arm_tl_trammel_spec", "CENTER_DRILL_ANGLE"),
                _PIVOT_POINT,
            ),
        ),
        "angle_tol_deg": (
            part_spec.INCLUDED_ANGLE_TOL_DEG,
            ("INCLUDED_ANGLE_TOL_DEG",),
        ),
        "note": (
            part_spec.CALLOUTS_BELOW["SeatDia"],
            ("CALLOUTS_BELOW", "PIVOT_POINT_NUMBER"),
        ),
    },
    precision={"dia": 2, "angle_deg": 0},
)

for side, x in zip(("left", "right"), part_spec.SCREW_X, strict=True):
    requirement(
        f"screw_hole_{side}",
        kind="hole",
        faces=(CylinderFace(part_spec.HOLE_DIA, contains_x_mm=x),),
        requirements=("station", "width", "dia", "thru"),
        fields={
            "at": (
                [x, part_spec.PLATE_HEIGHT, -part_spec.HOLE_Y],
                ("SCREW_X", "PLATE_HEIGHT", "HOLE_Y"),
            ),
            "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
            "station": (limits(x, 1), ("SCREW_X",)),
            "station_nominal": (x, ("SCREW_X",)),
            "width": (limits(part_spec.HOLE_Y, 2), ("HOLE_Y",)),
            "width_nominal": (part_spec.HOLE_Y, ("HOLE_Y",)),
            "dia": (
                limits(part_spec.HOLE_DIA, 2, part_spec.DRILLED_BAND),
                ("HOLE_DIA", "DRILLED_BAND", "SCREW_BODY_DIA"),
            ),
            "dia_nominal": (part_spec.HOLE_DIA, ("HOLE_DIA",)),
            "thru": (True, ("HOLE_DIA",)),
        },
        precision={"station": 1, "width": 2, "dia": 2},
    )
    requirement(
        f"screw_hole_{side}_countersink",
        kind="countersink",
        faces=(ConeFace(part_spec.CSK_ANGLE / 2.0, contains_x_mm=x),),
        requirements=("dia", "angle_deg"),
        fields={
            "parent": (
                f"screw_hole_{side}",
                ("HOLE_DIA", ("draw_ch_rocker_arm_tl_trammel_pivot_plate", "build")),
            ),
            "dia": (
                limits(part_spec.CSK_DIA, 2),
                ("CSK_DIA", "HEAD_TOP_DEPTH_MIN", "SCREW_HEAD_DIA_MAX"),
            ),
            "dia_nominal": (part_spec.CSK_DIA, ("CSK_DIA",)),
            "angle_deg": (part_spec.CSK_ANGLE, ("CSK_ANGLE", "CSK_FLANK_ANGLE")),
            "angle_tol_deg": (
                part_spec.INCLUDED_ANGLE_TOL_DEG,
                ("INCLUDED_ANGLE_TOL_DEG",),
            ),
        },
        precision={"dia": 2, "angle_deg": 0},
    )


def _view_mapper(adapter: Any, view: Any):
    """Return model point (mm) -> sheet xy (m) through the view's transform."""
    transform = _early_bound(
        _early_bound(view, "IView").ModelToViewTransform, "IMathTransform"
    )
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def to_sheet(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([c / 1000.0 for c in model_mm])),
            "IMathPoint",
        )
        data = _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
        return float(data[0]), float(data[1])

    return to_sheet


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot plate source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Template Trammel Pivot Plate Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker template trammel pivot plate; 1018 offcut; MHA-CH-006-TL-19",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    on_top = _view_mapper(adapter, top)
    section = create_section_view(
        adapter,
        top,
        line_start=on_top((CUT_X[0], _H, -HOLE_Y)),
        line_end=on_top((CUT_X[1], _H, -HOLE_Y)),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="pivot plate hole centre-line section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="pivot plate")
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (top, section):
        set_hidden_lines_removed(adapter, view)

    on_section = _view_mapper(adapter, section)
    annotations = [
        *curate_view_dimensions(
            adapter,
            top,
            keep={name: on_top(xyz) for name, xyz in TOP_KEEP.items()},
            view_label="top view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            section,
            keep={name: on_section(xyz) for name, xyz in SECTION_KEEP.items()},
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add center marks to the pivot plate holes")
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Template Trammel Pivot Plate Drawing",
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
