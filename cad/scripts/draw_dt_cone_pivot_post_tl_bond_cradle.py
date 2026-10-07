r"""Create the drawing for the cone pivot post's bond cradle (MHA-DT-005-TL-01)."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_view_centerline,
    assert_imported_precision,
    create_section_view,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_registry import DRAWINGS_BY_NAME
from dt_cone_pivot_post_tl_bond_cradle_spec import (
    BODY_SADDLE_Y,
    BODY_SEAT_DIA,
    CONE_PIN_NEAR_Y,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    SECTION_REFERENCE_SKETCHES,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["dt_cone_pivot_post_tl_bond_cradle"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 134 x 80 x 25 block: 1:1 fits plan, elevation, end view and the cone-pin
# section on a B sheet; the pictorial goes 1:2 and says so in its note.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 2)
# Plan ("*Front", looking down -Z) and elevation ("*Right") are both turned
# so the post axis (+Y) runs left to right from foot B; the elevation sits
# under the plan, third-angle, with +Z up. The end view looks back down the
# post from the tail ("*Top" turned +Z up), where both seats show true.
# Section A-A is cut on the elevation through the near cone pin.
PLAN_CENTER = (0.115, 0.190)
ELEVATION_CENTER = (0.115, 0.100)
END_CENTER = (0.250, 0.100)
SECTION_CENTER = (0.360, 0.100)
ISO_CENTER = (0.330, 0.210)
ISO_NOTE_XY = (0.280, 0.163)

# Dimension text positions as MODEL points (mm); each view projects its own
# after it is placed and turned. Stations print from foot B, heights from the
# base top.
PLAN_KEEP = {
    "StopWidth": (0.0, -24.0, 0.0),
    "ConePinNearY": (-48.0, 14.0, 0.0),
    "ConePinFarY": (-56.0, 19.0, 0.0),
    "CrankPinY": (-64.0, 36.0, 0.0),
    "CrankPinWestX": (-3.0, 86.0, 0.0),
    "CrankPinEastX": (3.0, 86.0, 0.0),
    "CrankPinDia": (-16.0, 84.0, 0.0),
}
ELEVATION_KEEP = {
    "BaseLength": (0.0, 55.0, -50.0),
    "BaseThick": (0.0, -22.0, -35.0),
    "StopHeight": (0.0, -22.0, -22.0),
    "SeatAxisHeight": (0.0, -34.0, -15.0),
    "StopThick": (0.0, -6.0, -7.0),
    "BodySaddleThick": (0.0, 15.0, -7.0),
    "TailSaddleThick": (0.0, 110.0, -7.0),
    "BodySaddleY": (0.0, 5.0, 4.0),
    "TailSaddleY": (0.0, 50.0, 4.0),
    "BodySaddleHeight": (0.0, 26.0, -22.0),
    "CrankPinHeight": (0.0, 82.0, -25.0),
    "TailSaddleHeight": (0.0, 130.0, -22.0),
}
END_KEEP = {
    "BaseWidth": (0.0, 122.0, -50.0),
    "SaddleWidth": (0.0, 122.0, -8.0),
    "BodySeatDia": (-22.0, 122.0, 6.0),
    "TailSeatDia": (22.0, 122.0, 12.0),
}
SECTION_KEEP = {
    "ConePinEntryX": (-3.0, CONE_PIN_NEAR_Y, -50.0),
    "ConePinTilt": (-12.0, CONE_PIN_NEAR_Y, -10.0),
    "ConePinHighEdge": (-20.0, CONE_PIN_NEAR_Y, -25.0),
}
DIMENSION_CALLOUTS = {
    "CrankPinDia": "4X PINS",
    "SaddleWidth": "2X",
    "ConePinEntryX": "2X",
    "ConePinTilt": "2X",
    "ConePinHighEdge": "2X",
}


def _sheet(adapter: Any, view: Any, xyz_mm: tuple[float, float, float], label: str) -> tuple[float, float]:
    return model_point_in_view(
        adapter, view, tuple(v / 1000.0 for v in xyz_mm), label=label
    )


def _direction(adapter: Any, view: Any, axis: tuple[float, float, float], label: str) -> tuple[float, float]:
    """Sheet direction of a model axis in ``view``."""
    origin = _sheet(adapter, view, (0.0, 0.0, 0.0), f"{label} origin")
    tip = _sheet(adapter, view, axis, f"{label} axis")
    return tip[0] - origin[0], tip[1] - origin[1]


def _turn(
    adapter: Any,
    view: Any,
    axis: tuple[float, float, float],
    sheet_angle: float,
    *,
    label: str,
) -> None:
    """Turn ``view`` about its centre until model ``axis`` points along
    ``sheet_angle`` (radians, counter-clockwise from sheet +x)."""
    native = _early_bound(view, "IView")
    dx, dy = _direction(adapter, native, axis, label)
    angle = float(native.Angle) + sheet_angle - math.atan2(dy, dx)
    native.Angle = angle
    adapter.currentModel.EditRebuild3()
    applied = float(native.Angle)
    if abs(math.remainder(applied - angle, 2.0 * math.pi)) > 1e-6:
        raise RuntimeError(f"{label} view did not turn: {applied:g} rad, expected {angle:g}")
    dx, dy = _direction(adapter, native, axis, label)
    if abs(math.remainder(math.atan2(dy, dx) - sheet_angle, 2.0 * math.pi)) > 1e-6:
        raise RuntimeError(f"{label}: model {axis} points {math.atan2(dy, dx):g} rad after the turn")


def _require_up(adapter: Any, view: Any, *, label: str) -> None:
    dx, dy = _direction(adapter, view, (0.0, 0.0, 1.0), label)
    if dy <= 0.0 or abs(dx) > 1e-9:
        raise RuntimeError(f"{label}: model +Z is not sheet-up ({dx:g}, {dy:g})")


def _keep(adapter: Any, view: Any, points: dict[str, tuple[float, float, float]], label: str) -> dict[str, tuple[float, float]]:
    return {name: _sheet(adapter, view, xyz, f"{label} {name}") for name, xyz in points.items()}


def _curate(adapter: Any, view: Any, points: dict[str, tuple[float, float, float]], label: str) -> list[Any]:
    return curate_view_dimensions(
        adapter,
        view,
        keep=_keep(adapter, view, points, label),
        view_label=label,
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open bond-cradle source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
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
    drawing_model, _sheet_model = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Post Bond Cradle Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "cone pivot post bond cradle; steel, built up and doweled; MHA-DT-005-TL-01",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    elevation = place_view(adapter, str(SOURCE), "*Right", *ELEVATION_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    _turn(adapter, plan, (0.0, 1.0, 0.0), 0.0, label="plan")
    _turn(adapter, elevation, (0.0, 1.0, 0.0), 0.0, label="elevation")
    _require_up(adapter, elevation, label="elevation")
    _turn(adapter, end, (0.0, 0.0, 1.0), math.pi / 2.0, label="end view")
    for view in (plan, elevation, end):
        set_hidden_lines_removed(adapter, view)

    plan_annotations = _curate(adapter, plan, PLAN_KEEP, "plan")
    elevation_annotations = _curate(adapter, elevation, ELEVATION_KEEP, "elevation")
    end_annotations = _curate(adapter, end, END_KEEP, "end view")

    # The cone pin's tilt, hole position and gauge height live in a reference
    # sketch on the section plane, which the part saves hidden: the section is
    # cut and dimensioned while the part shows it.
    with part_sketches_shown(
        adapter,
        source_model,
        SECTION_REFERENCE_SKETCHES,
        label="cone pin section",
        base_view=elevation,
    ):
        top = _sheet(adapter, elevation, (0.0, CONE_PIN_NEAR_Y, 0.0), "section line top")
        bottom = _sheet(adapter, elevation, (0.0, CONE_PIN_NEAR_Y, -50.0), "section line foot")
        section = create_section_view(
            adapter,
            elevation,
            line_start=top,
            line_end=bottom,
            view_xy=SECTION_CENTER,
            section_label="A",
            scale=VIEW_SCALE,
            label="cone pin section",
        )
        dx, dy = _direction(adapter, section, (0.0, 0.0, 1.0), "section")
        if dy <= 0.0 or abs(dx) > 1e-9:
            _turn(adapter, section, (0.0, 0.0, 1.0), math.pi / 2.0, label="section")
        set_hidden_lines_removed(adapter, section)
        section_annotations = _curate(adapter, section, SECTION_KEEP, "section A-A")

    annotations = [
        *plan_annotations,
        *elevation_annotations,
        *end_annotations,
        *section_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # The post axis on the plan, through the body seat's lowest line.
    add_view_centerline(
        adapter,
        plan,
        face_xy=_sheet(
            adapter, plan, (0.0, BODY_SADDLE_Y + 5.0, -BODY_SEAT_DIA / 2.0), "plan seat"
        ),
        label="post axis",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Post Bond Cradle Drawing",
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
