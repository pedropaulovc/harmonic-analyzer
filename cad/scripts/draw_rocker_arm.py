r"""Create the curated machinist drawing for the rocker arm.

The SLDPRT remains authoritative.  This recipe supplies only the rocker-arm
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The strap is a long thin curved seesaw (~292 mm tip to tip, 16 mm deep, 2.5 mm
thick).  A projected side view of the curved strap is a messy band, so the
16 x 2.5 section is carried in the notes and the print shows the profile (front)
plus a 1:2 isometric.  The sheet runs at 1:2.

Run with SolidWorks open::

    uv run python cad\scripts\draw_rocker_arm.py rocker-arm
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from rocker_arm_spec import ARM_DEPTH, GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    visible_circle_edge,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_basic_dimension,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from rocker_arm_spec import (
    ARM_THICKNESS,
    PIVOT_HOLE_DIA,
    R_TOP,
    ROD_HOLE_X,
    ROD_HOLE_Y,
    SURFACE_FINISHES,
    TIP_FACE,
    TOP_ARC_LEN,
    TOP_END_X,
    TOP_END_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["rocker_arm"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 2.0)  # 1:2
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.5)

# Front-view model bbox: X symmetric about 0, Y from the centre bottom (0) up to
# the top-arc tip (TOP_END_Y).
_PIVOT_MID_Y = 8.0  # pivot bore centre = ArmDepth / 2
_ROD_HOLE_DIA = 1.994  # #47 drill
_BBOX_CY = TOP_END_Y / 2.0

FRONT_CENTER = (0.180, 0.175)
RIGHT_CENTER = (0.300, 0.165)
ISO_CENTER = (0.345, 0.205)

# Tip-face midpoint (model mm): the top-arc endpoint pushed half the tip face
# outward along the end radius -- where datum C (clocking) attaches.
_TIP_FACE_MID_X = TOP_END_X + (TIP_FACE / 2.0) * (TOP_END_X / R_TOP)
_TIP_FACE_MID_Y = TOP_END_Y - (TIP_FACE / 2.0) * math.cos(TOP_ARC_LEN / 2.0 / R_TOP)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:2)."""
    return (
        FRONT_CENTER[0] + mx * _S / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


# The large concentric radii are carried in the manufacturing note: imported
# radius dimensions retain off-sheet centre witnesses even in shortened-radius
# mode.  Keeping them as notes avoids clipped geometry without losing values.
FRONT_KEEP = {
    "PivotDia": (0.180, 0.120),
}
NOTE_ONLY_DIMENSIONS = {"TopRadius", "BottomRadius"}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm; tapered strap; seesaw pivot",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # Explicit per-view scale (an auto-scaled view shifts every coordinate pick).
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    # 1:1 right end view: the 2.50 x ~29 strap section -- shows the section the
    # profile notes describe, gives the through direction, and carries datum B
    # (the broad face) so the rod-pin position frame has an orientation datum.
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Rod-pin hole native callout (the #47 wizard hole near the +X tip).
    rod_rim = _sheet_xy(ROD_HOLE_X, ROD_HOLE_Y - _ROD_HOLE_DIA / 2.0)
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=rod_rim,
        callout_xy=(0.300, 0.128),
        label="rod-pin hole",
    )

    # Locate the rod-pin hole from the pivot bore with X and Y BASIC coordinate
    # components.  The rod-pin centre is NOT collinear with the pivot (7.30 mm
    # above its mid-height), so a single slant centre distance would leave the
    # angular component uninspectable; two component dimensions fully define
    # the true position the FCF below controls.
    pivot_rim = _sheet_xy(0.0, _PIVOT_MID_Y - PIVOT_HOLE_DIA / 2.0)
    rod_location_x = add_edge_dimension(
        adapter,
        front,
        p0=pivot_rim,
        p1=rod_rim,
        text_xy=(0.180, 0.138),
        label="rod-pin X location",
        orientation="horizontal",
    )
    set_basic_dimension(adapter, rod_location_x, label="rod-pin X location")
    rod_location_y = add_edge_dimension(
        adapter,
        front,
        p0=pivot_rim,
        p1=rod_rim,
        text_xy=(0.267, 0.162),
        label="rod-pin Y location",
        orientation="vertical",
    )
    set_basic_dimension(adapter, rod_location_y, label="rod-pin Y location")

    # Datum A identifies the pivot bore's cylindrical surface.  Keep its leader
    # oblique to both centre-mark axes so the triangle unmistakably terminates
    # on the circumference rather than appearing to identify the bore centre.
    pivot_datum_angle = math.radians(135.0)
    pivot_radius = PIVOT_HOLE_DIA / 2.0
    pivot_datum_rim = _sheet_xy(
        pivot_radius * math.cos(pivot_datum_angle),
        _PIVOT_MID_Y + pivot_radius * math.sin(pivot_datum_angle),
    )
    pivot_datum_standoff = 0.020
    add_datum_feature(
        adapter,
        front,
        edge_xy=pivot_datum_rim,
        symbol_xy=(
            pivot_datum_rim[0] + pivot_datum_standoff * math.cos(pivot_datum_angle),
            pivot_datum_rim[1] + pivot_datum_standoff * math.sin(pivot_datum_angle),
        ),
        datum="A",
        label="pivot bore cylindrical datum feature",
        shoulder=True,
        # SolidWorks snaps this circular bore attachment to its nearest legal
        # anchor.  The live readback is 0.0109 mm from the requested point;
        # allow that native normalization while retaining the shared strict
        # persistence check for freely positioned annotations.
        position_tolerance_m=0.0001,
    )
    # Ra on the bore rim at 7:30 -- oblique to both centre-mark axes like the
    # datum above: since the integral hub (2026-09-02) the 6 o'clock point on
    # the bore lies on the centre mark's vertical extension and the coordinate
    # pick resolved to the hub's O10 rim instead of the O6.5 bore edge. Then a
    # position FCF tying the rod-pin hole to the complete A-B-C frame.
    pivot_finish_angle = math.radians(225.0)
    pivot_bottom = _sheet_xy(
        pivot_radius * math.cos(pivot_finish_angle),
        _PIVOT_MID_Y + pivot_radius * math.sin(pivot_finish_angle),
    )
    # Pick the bore circle by DIAMETER (the visible-entity walk the cone-gear
    # drawing uses): a coordinate pick on the concentric O6.5 / O10 rims
    # resolves to the hub's outer circle within SolidWorks' tolerance.
    pivot_bore_edge = visible_circle_edge(adapter, front, PIVOT_HOLE_DIA)
    add_surface_finish(
        adapter,
        front,
        edge_entity=pivot_bore_edge,
        symbol_xy=(pivot_bottom[0] - 0.012, pivot_bottom[1] - 0.020),
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
    )
    # Datum B (broad face, on the end view) orients the hole axes; datum C
    # (the +X tip face) clocks rotation about the pivot axis, so the X/Y BASIC
    # coordinates above have an inspectable direction.
    # Datum B on the strap's broad face in the end view, picked ABOVE the hub
    # band (the O10 hub hides the flank over y 3..13 since 2026-09-02); the
    # end view is centred on the strap's mid-depth (_PIVOT_MID_Y).
    broad_face = (
        RIGHT_CENTER[0] - ARM_THICKNESS / 2000.0,
        RIGHT_CENTER[1] + (ARM_DEPTH - 1.0 - _PIVOT_MID_Y) * _S / 1000.0,
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=broad_face,
        symbol_xy=(broad_face[0] - 0.016, broad_face[1] - 0.014),
        datum="B",
        label="broad face",
    )
    tip_face = _sheet_xy(_TIP_FACE_MID_X, _TIP_FACE_MID_Y)
    add_datum_feature(
        adapter,
        front,
        edge_xy=tip_face,
        symbol_xy=(tip_face[0] + 0.012, tip_face[1] + 0.012),
        datum="C",
        label="rod-side tip face",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=rod_rim,
        frame_xy=(0.300, 0.195),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["rod-pin hole position"],
        datums=("A", "B", "C"),
        diameter=True,
        label="rod-pin hole position",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.082)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.150)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
