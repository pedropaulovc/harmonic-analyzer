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

from _gear_drawing_entities import visible_circle_edge
from rocker_arm_spec import ARM_DEPTH, GEOMETRIC_TOLERANCES_MM

import _telemetry
from _hole_spec import blind_cut_dia_mm
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    check_drawing_layout,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_basic_dimension,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    sheet_drawable_region,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from rocker_arm_notes import DRAWING_DIMENSIONS
from rocker_arm_spec import (
    ARM_THICKNESS,
    PIVOT_HOLE_DIA,
    R_TOP,
    ROD_HOLE_X,
    ROD_HOLE_SPEC,
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
_ROD_HOLE_DIA = blind_cut_dia_mm(ROD_HOLE_SPEC)
_BBOX_CY = TOP_END_Y / 2.0

FRONT_CENTER = (0.180, 0.175)
RIGHT_CENTER = (0.300, 0.165)
ISO_CENTER = (0.345, 0.205)
# The rod-pin position frame's top-left corner; it draws 7 mm tall.
FCF_XY = (0.300, 0.195)
# The iso caption's top-left, under the iso's right half: below the FCF and
# right of the end view. Beside the end view (0.315, 0.150) it read as that
# view's label, 0.4 mm from HubLength's "+0.05" (r743-p1s-B2 render).
ISO_CAPTION_XY = (0.325, 0.183)

# General notes. The linked block renders ~4.1 mm a line, so its 18 lines run
# ~75 mm. Anchored by its top at y 0.082, the last two ran past the bottom
# border into the zone band (r743-p1s-B2 render). The block is now seated from
# its MEASURED extent: rendered bottom NOTES_BORDER_CLEARANCE above the
# sheet's drawable region, left edge on NOTES_LEFT. A block that then reaches
# NOTES_CEILING, under the front view's O6.50 text (y ~0.117), fails the build.
NOTES_LEFT = 0.020
NOTES_BORDER_CLEARANCE = 0.003
NOTES_CEILING = 0.110
NOTES_SEAT_PASSES = 3
NOTES_SEAT_SETTLE = 0.00005

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
# The hub length (+0.05/0, #743 PR2) under the end view, where the hub shows
# its full length (the end view is 1:1, centred on the pivot mid-depth).
RIGHT_KEEP: dict[str, tuple[float, float]] = {
    "HubLength": (RIGHT_CENTER[0], RIGHT_CENTER[1] - (_PIVOT_MID_Y + 12.0) / 1000.0),
}
TOP_KEEP: dict[str, tuple[float, float]] = {}


def _note_extent(adapter: Any, note: Any) -> tuple[float, float, float, float]:
    """The rendered sheet-space box (x0, y0, x1, y1) of a free note."""
    adapter.currentModel.GraphicsRedraw2()
    extent = tuple(
        float(value) for value in (_early_bound(note, "INote").GetExtent() or ())
    )
    if len(extent) != 6 or extent[3] <= extent[0] or extent[4] <= extent[1]:
        raise RuntimeError(f"manufacturing notes have no rendered extent: {extent!r}")
    return (extent[0], extent[1], extent[3], extent[4])


def _seat_notes_on_border(
    adapter: Any, note: Any, sheet: Any
) -> tuple[float, float, float, float]:
    """Steer the notes' RENDERED bottom-left corner onto NOTES_LEFT,
    NOTES_BORDER_CLEARANCE above the sheet's drawable region (the insertion
    point is neither the text box's corner nor tracked by it 1:1)."""
    template = DRAWING_TEMPLATES[SPEC.layout]
    region = sheet_drawable_region(
        adapter, sheet, width=template.width_m, height=template.height_m
    )
    target = (NOTES_LEFT, region.ymin + NOTES_BORDER_CLEARANCE)
    annotation = _early_bound(
        _early_bound(note, "INote").GetAnnotation(), "IAnnotation"
    )
    extent = _note_extent(adapter, note)
    for _pass in range(NOTES_SEAT_PASSES):
        shift = (target[0] - extent[0], target[1] - extent[1])
        if max(abs(shift[0]), abs(shift[1])) <= NOTES_SEAT_SETTLE:
            break
        position = tuple(float(value) for value in (annotation.GetPosition() or ()))
        if len(position) != 3:
            raise RuntimeError(f"manufacturing notes position unreadable: {position!r}")
        if not annotation.SetPosition(
            position[0] + shift[0], position[1] + shift[1], position[2]
        ):
            raise RuntimeError("manufacturing notes SetPosition failed")
        extent = _note_extent(adapter, note)
    extent_mm = tuple(round(value * 1000.0, 2) for value in extent)
    _telemetry.info(
        f"manufacturing notes seated: extent_mm={extent_mm!r}, "
        f"drawable bottom {region.ymin * 1000.0:.2f} mm"
    )
    if extent[1] < region.ymin or extent[3] > NOTES_CEILING:
        raise RuntimeError(
            "manufacturing notes do not fit between the border "
            f"({region.ymin * 1000.0:.2f} mm) and the front view's annotations "
            f"({NOTES_CEILING * 1000.0:.1f} mm): rendered extent {extent_mm!r}"
        )
    return extent


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
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    # The hub length only shows its length in the end view; the front looks
    # down the hub's axis. Codex #936 (PRRT_kwDOPHDy386mRk__): RIGHT_KEEP was
    # declared but never curated, so the +0.05/0 band that sets all 20
    # channel stations never printed. Targeted by feature, so only Hub's
    # dimensions arrive.
    curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Rod-pin hole native callout (the #47 wizard hole near the +X tip).
    # Both bores are picked by DIAMETER (the visible-entity walk), never by a
    # rim coordinate: r743-p1s-B's coordinate pick on the #47 rim resolved to
    # the strap's tapered end-face line 1.6 mm (sheet) away, so AddHoleCallout2
    # had no hole to call out; the pivot bore's rim pick already had the same
    # fate against the concentric hub (see its finish below).
    rod_rim = _sheet_xy(ROD_HOLE_X, ROD_HOLE_Y - _ROD_HOLE_DIA / 2.0)
    rod_hole_edge = visible_circle_edge(adapter, front, _ROD_HOLE_DIA)
    pivot_bore_edge = visible_circle_edge(adapter, front, PIVOT_HOLE_DIA)
    add_native_hole_callout(
        adapter,
        front,
        edge=rod_hole_edge,
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
        entities=(pivot_bore_edge, rod_hole_edge),
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
        entities=(pivot_bore_edge, rod_hole_edge),
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
        # The tag stands only 20 mm off the rim, so a snap-back onto the
        # attachment would sit at the default bound; the live readback is
        # 0.0109 mm from the request.
        position_tolerance_m=0.010,
    )
    # Ra on the bore rim at 1:30 -- oblique to both centre-mark axes like the
    # datum above -- with the symbol up-right of it, over the strap. The
    # symbol's body always draws up-right of its leader end, so the leader has
    # to run DOWN-left into the rim to stay off the body. From the old 7:30
    # rim, low-left, it ran up through the symbol, whose default-height
    # "Ra 1.6" sat across the strap's bottom edge and the centre mark
    # (r743-p1s-B2 render). Note text height, as on the other part sheets.
    pivot_finish_angle = math.radians(45.0)
    pivot_finish_rim = _sheet_xy(
        pivot_radius * math.cos(pivot_finish_angle),
        _PIVOT_MID_Y + pivot_radius * math.sin(pivot_finish_angle),
    )
    # The bore circle picked by DIAMETER above (the visible-entity walk the
    # cone-gear drawing uses): a coordinate pick on the concentric O6.5 / O10
    # rims resolves to the hub's outer circle within SolidWorks' tolerance.
    add_surface_finish(
        adapter,
        front,
        edge_entity=pivot_bore_edge,
        symbol_xy=(pivot_finish_rim[0] + 0.012, pivot_finish_rim[1] + 0.011),
        leader_attach_xy=pivot_finish_rim,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
        char_height=0.0025,
    )
    # Then a position FCF tying the rod-pin hole to the complete A-B-C frame.
    # Datum B (broad face, on the end view) orients the hole axes; datum C
    # (the +X tip face) clocks rotation about the pivot axis, so the X/Y BASIC
    # coordinates above have an inspectable direction.
    # Datum B on the strap's broad face in the end view, picked ABOVE the hub
    # band (the O10 hub hides the flank over y 3..13 since 2026-09-02); the
    # end view is centred on the strap's mid-depth (_PIVOT_MID_Y).
    broad_face = (
        RIGHT_CENTER[0] - ARM_THICKNESS / 2000.0,
        RIGHT_CENTER[1]
        + (ARM_DEPTH - 1.0 - _PIVOT_MID_Y) / 1000.0,  # right view is 1:1,
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
        edge_entity=rod_hole_edge,
        frame_xy=FCF_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["rod-pin hole position"],
        datums=("A", "B", "C"),
        diameter=True,
        label="rod-pin hole position",
    )

    notes = add_property_linked_note(
        adapter, "Manufacturing Notes", NOTES_LEFT, NOTES_CEILING
    )
    _seat_notes_on_border(adapter, notes, sheet)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_CAPTION_XY)
    # The shared gate: no overlaps, border crossings or leader crossings.
    rebuild_drawing(adapter, label="rocker-arm layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Manufacturing Drawing",
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
