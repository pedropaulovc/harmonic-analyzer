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
    assert_imported_precision,
    create_section_view,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_registry import DRAWINGS_BY_NAME
from dt_cone_pivot_post_tl_bond_cradle_spec import (
    CONE_PIN_NEAR_Y,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    SECTION_REFERENCE_SKETCHES,
    TAIL_SADDLE_THICK,
    TAIL_SADDLE_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["dt_cone_pivot_post_tl_bond_cradle"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 134 x 80 x 25 block: 1:1 fits plan, elevation and two sections on a B
# sheet; the pictorial goes 1:2 and says so in its note.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 2)
# Plan ("*Front", looking down -Z) and elevation ("*Right") are both turned
# so the post axis (+Y) runs left to right from foot B; the elevation sits
# under the plan, third-angle, with +Z up. Both sections are cut on the
# elevation: A-A through the near cone pin looks back at the body saddle
# (-Y), B-B through the tail saddle looks on to the tail (+Y), so each shows
# one seat alone.
PLAN_CENTER = (0.115, 0.190)
ELEVATION_CENTER = (0.115, 0.100)
SECTION_A_CENTER = (0.252, 0.130)
SECTION_B_CENTER = (0.372, 0.130)
ISO_CENTER = (0.360, 0.228)
ISO_NOTE_XY = (0.215, 0.230)
TAIL_SECTION_Y = TAIL_SADDLE_Y + TAIL_SADDLE_THICK / 2.0
# Cutting lines run from just above the saddle tops to just below the base.
CUT_TOP_Z = -9.0
CUT_FOOT_Z = -43.0

# Dimension text positions as MODEL points (mm); each view projects its own
# after it is placed and turned. Stations print from foot B, heights from
# the base top, transverse locations from the base's west side (X -40; the
# plan's top edge).
PLAN_KEEP = {
    "StopWidth": (0.0, -30.0, 0.0),
    "StopSideX": (-28.0, -21.0, 0.0),
    "SaddleSideX": (-35.0, 5.0, 0.0),
    "SaddleWidth": (0.0, 128.0, 0.0),
    "BaseWidth": (0.0, 137.0, 0.0),
    "CrankPinWestX": (-23.0, 82.0, 0.0),
    "CrankPinEastX": (-17.0, 90.0, 0.0),
    "ConePinNearY": (-48.0, 14.0, 0.0),
    "ConePinFarY": (-56.0, 19.0, 0.0),
    "CrankPinY": (-64.0, 36.0, 0.0),
    "CrankPinDia": (-52.0, 100.0, 0.0),
}
ELEVATION_KEEP = {
    "BaseLength": (0.0, 55.0, -50.0),
    "BaseThick": (0.0, -22.0, -35.0),
    "StopHeight": (0.0, -22.0, -22.0),
    "StopThick": (0.0, -6.0, 6.0),
    "BodySaddleThick": (0.0, 15.0, 6.0),
    "TailSaddleThick": (0.0, 110.0, 6.0),
    "BodySaddleY": (0.0, 5.0, 16.0),
    "TailSaddleY": (0.0, 50.0, 16.0),
    "BodySaddleHeight": (0.0, 46.0, -22.0),
    "CrankPinHeight": (0.0, 82.0, -25.0),
    "TailSaddleHeight": (0.0, 130.0, -22.0),
}
# Each seat's profile sketch is parallel to its section, so the section
# imports its diameter. The text stands up and outboard of the axis, steep,
# so the through-centre leader lands on the seat arc.
SECTION_A_KEEP = {
    "BodySeatDia": (10.0, CONE_PIN_NEAR_Y, 25.0),
    "BodySeatAxisX": (-20.0, CONE_PIN_NEAR_Y, 12.0),
    "BodySeatAxisHeight": (-48.0, CONE_PIN_NEAR_Y, -12.0),
    "ConePinEntryX": (-28.0, CONE_PIN_NEAR_Y, -50.0),
    # On the bisector of the gauge line and the pin axis, so the angle reads
    # the acute tilt.
    "ConePinTilt": (-4.2, CONE_PIN_NEAR_Y, -8.0),
    "ConePinHighEdge": (-58.0, CONE_PIN_NEAR_Y, -25.0),
}
SECTION_B_KEEP = {
    "TailSeatDia": (12.0, TAIL_SECTION_Y, 28.0),
    "TailSeatAxisX": (-20.0, TAIL_SECTION_Y, 12.0),
    "TailSeatAxisHeight": (-48.0, TAIL_SECTION_Y, -12.0),
}
DIMENSION_CALLOUTS = {
    "CrankPinDia": "4X DOWEL, REAM THRU",
    "SaddleWidth": "2X",
    "SaddleSideX": "2X",
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
    dx, dy = _direction(adapter, native, axis, label)
    if abs(math.remainder(math.atan2(dy, dx) - sheet_angle, 2.0 * math.pi)) > 1e-6:
        raise RuntimeError(f"{label}: model {axis} points {math.atan2(dy, dx):g} rad after the turn")


def _require_up(adapter: Any, view: Any, *, label: str) -> None:
    dx, dy = _direction(adapter, view, (0.0, 0.0, 1.0), label)
    if dy <= 0.0 or abs(dx) > 1e-9:
        raise RuntimeError(f"{label}: model +Z is not sheet-up ({dx:g}, {dy:g})")


def _orient_section(adapter: Any, section: Any, *, x_right: bool, label: str) -> None:
    """Turn a section +Z up and make it look the intended way along the post.

    Looking down -Y with +Z up puts model -X on the sheet's right; looking
    down +Y puts +X there. A section that looks the wrong way has its cut
    direction reversed, then is turned again.
    """
    native = _early_bound(section, "IView")
    _turn(adapter, native, (0.0, 0.0, 1.0), math.pi / 2.0, label=label)
    dx, _ = _direction(adapter, native, (1.0, 0.0, 0.0), label)
    if (dx > 0.0) != x_right:
        drawing_section = _early_bound(native.GetSection(), "IDrSection")
        reversed_cut = not bool(drawing_section.GetReversedCutDirection())
        drawing_section.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label=f"reverse {label}")
        if bool(drawing_section.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError(f"{label}: cutting direction did not persist")
        _turn(adapter, native, (0.0, 0.0, 1.0), math.pi / 2.0, label=label)
        dx, _ = _direction(adapter, native, (1.0, 0.0, 0.0), label)
        if (dx > 0.0) != x_right:
            raise RuntimeError(f"{label}: still looks the wrong way after reversing")
    _require_up(adapter, native, label=label)


def _cut(
    adapter: Any,
    elevation: Any,
    y: float,
    *,
    center: tuple[float, float],
    letter: str,
    x_right: bool,
    label: str,
) -> Any:
    section = create_section_view(
        adapter,
        elevation,
        line_start=_sheet(adapter, elevation, (0.0, y, CUT_TOP_Z), f"{label} line top"),
        line_end=_sheet(adapter, elevation, (0.0, y, CUT_FOOT_Z), f"{label} line foot"),
        view_xy=center,
        section_label=letter,
        scale=VIEW_SCALE,
        label=label,
    )
    _orient_section(adapter, section, x_right=x_right, label=label)
    set_hidden_lines_removed(adapter, section)
    return section


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
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    _turn(adapter, plan, (0.0, 1.0, 0.0), 0.0, label="plan")
    _turn(adapter, elevation, (0.0, 1.0, 0.0), 0.0, label="elevation")
    _require_up(adapter, elevation, label="elevation")
    for view in (plan, elevation):
        set_hidden_lines_removed(adapter, view)

    plan_annotations = _curate(adapter, plan, PLAN_KEEP, "plan")
    elevation_annotations = _curate(adapter, elevation, ELEVATION_KEEP, "elevation")

    # Each section's reference sketch (seat axis from the west side; the cone
    # pin's tilt, hole position and gauge height) lies in its cutting plane
    # and is saved hidden: the sections are cut and dimensioned while the
    # part shows them.
    with part_sketches_shown(
        adapter,
        source_model,
        SECTION_REFERENCE_SKETCHES,
        label="seat sections",
        base_view=elevation,
    ):
        section_a = _cut(
            adapter,
            elevation,
            CONE_PIN_NEAR_Y,
            center=SECTION_A_CENTER,
            letter="A",
            x_right=False,
            label="section A-A",
        )
        section_b = _cut(
            adapter,
            elevation,
            TAIL_SECTION_Y,
            center=SECTION_B_CENTER,
            letter="B",
            x_right=True,
            label="section B-B",
        )
        section_a_annotations = _curate(adapter, section_a, SECTION_A_KEEP, "section A-A")
        section_b_annotations = _curate(adapter, section_b, SECTION_B_KEEP, "section B-B")

    annotations = [
        *plan_annotations,
        *elevation_annotations,
        *section_a_annotations,
        *section_b_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
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
