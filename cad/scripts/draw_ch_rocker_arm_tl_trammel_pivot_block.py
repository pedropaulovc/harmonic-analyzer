r"""Create the drawing for the rocker template trammel's pivot block (MHA-CH-006-TL-14).

Four orthographic views at 2:1, section A-A and a 1:1 shaded isometric: the
top face (length, width, the reamed point hole, the slit and its drilled
relief, and the bar-contact finishes), edge B below it (the stock height and
the pinch screw's clearance), the end view to its right (the bar slot), edge
A beyond (the set-screw taps and the pinch taps' exits) and the section
through the pinch screw's axis (the clearance, the slit and the tapped jaw
together, and the slot floor's corners). Every station along the block is
dimensioned from the point-hole axis.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import place_view

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
from _trammel_block_drawing import (
    TrammelBlockSheet,
    circle_edge,
    create_pinch_section,
    hide_thread_labels,
    mm_in_view,
    near,
    set_blind_extent_text,
    straight_edge,
    strip_thread_class,
)
import _telemetry
import ch_rocker_arm_tl_trammel_pivot_block_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_trammel_pivot_block_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    SURFACE_FINISHES,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_trammel_pivot_block"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 50 x 38.1 x 19.05 block: 2:1 keeps the 1.0 slit and the 6.45 slot legible.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 1)
SHEET = TrammelBlockSheet(part_spec.BLOCK_X0, part_spec.BLOCK_X1)
# Upper right, from the top view out: the reamed hole's callout, section A-A
# (recentred on its outline; caption below it, clear of edge A's callouts)
# and the isometric right of it (farm r4: the section's ink landed over the
# isometric).
SECTION_CENTER = (0.285, 0.192)
SECTION_CAPTION_XY = (0.285, 0.1695)
ISO_CENTER = (0.380, 0.225)
ISO_NOTE_XY = (0.345, 0.262)
NOTES_XY = (0.020, 0.060)

# Top face (edge A at the view's top, edge B toward the edge-B view below).
# The distance from edge A stands left of the view (one 28.0: the slit's is
# the point hole's by equation); the right side keeps only the slit width, so
# the reamed hole's leader rises up and right to its callout beside the top
# view, clear of the 50.0 and inside the border. The relief's diameter hangs
# below edge B, right of the slit end's station, its leader rising up-left
# (the 38.1 dimensions the near end, so its extension lines stop short of
# the leader).
TOP_KEEP = {
    "BlockLength": SHEET.top(0.5 * (part_spec.BLOCK_X0 + part_spec.BLOCK_X1), -10.0),
    "HoleFromEnd": SHEET.top(0.5 * part_spec.BLOCK_X0, -4.5),
    "BlockWidth": SHEET.top(part_spec.BLOCK_X0 - 17.0, 19.0),
    "PointFromEdgeA": SHEET.top(part_spec.BLOCK_X0 - 11.0, 8.0),
    "SlitWidth": SHEET.top(part_spec.BLOCK_X1 + 6.0, 31.0),
    "SlitEnd": SHEET.top(0.5 * part_spec.SLIT_END_X, 44.0),
    "SlitReliefDia": SHEET.top(part_spec.SLIT_END_X + 16.0, 42.05),
    "PointHoleDia": SHEET.top(part_spec.BLOCK_X1 + 26.0, -5.5),
}
# Edge B (pinch screw head side): the pinch station below, its row low enough
# to clear section A-A's lower letter; the pinch depth and, outside it, the
# stock height right of the view, where their extension lines are short (the
# height's two rows past the end of the pinch depth's lower extension line,
# above the height's own lower one and left of the end view, whose padded
# outline starts 1.6 right of farm r4's "19.05"). Farm r2: the height left
# of the view ran its extension lines the block's length, across the pinch
# clearance callout's leader.
FRONT_KEEP = {
    "BlockHeight": SHEET.front(part_spec.BLOCK_X1 + 10.5, -14.5),
    "PinchX": SHEET.front(0.5 * part_spec.PINCH_X[0], -29.0),
    "PinchDepth": SHEET.front(part_spec.BLOCK_X1 + 5.5, -7.0),
}
# The end view: the bar slot from edge A (edge A on the view's right). The
# slot width's value stands left of its extension lines (farm r2: centred, the
# toleranced value straddled them, extension-through-own-text).
RIGHT_KEEP = {
    "SlotWidth": SHEET.right(part_spec.SLOT_FROM_EDGE_A + 13.0, 6.0),
    "SlotFromEdgeA": SHEET.right(0.5 * part_spec.SLOT_FROM_EDGE_A, -24.5),
    "SlotDepth": SHEET.right(-7.0, -5.0),
}
# Edge A: the set-screw stations and their height.
BACK_KEEP = {
    "SetScrewX1": SHEET.back(0.5 * part_spec.SET_SCREW_X[0], -24.5),
    "SetScrewX2": SHEET.back(0.5 * part_spec.SET_SCREW_X[1], -24.5),
    "SetScrewDepth": SHEET.back(part_spec.BLOCK_X1 + 7.0, -2.5),
}
# One line above the slot width (a multi-line above-lane callout does not
# print); the stacked callouts hang below their values.
CALLOUTS_ABOVE = {"SlotWidth": part_spec.SLOT_WIDTH_CALLOUT}
CALLOUTS_BELOW = {
    "PointHoleDia": part_spec.POINT_HOLE_CALLOUT,
    "SlitWidth": part_spec.SLIT_CALLOUT,
    "SlitReliefDia": part_spec.SLIT_RELIEF_CALLOUT,
    "BlockHeight": part_spec.BLOCK_HEIGHT_CALLOUT,
}
# The set-screw leader runs from the callout's right end down to the tap
# right in the view (farm r2: to the left tap it crossed the set-screw depth's
# extension line); the pinch-tap callout stands right so its leader slants
# past that tap's circle to the pinch tap's exit.
SET_SCREW_CALLOUT_XY = (0.345, 0.140)
SET_SCREW_LEADER_X = min(part_spec.SET_SCREW_X)
PINCH_TAP_CALLOUT_XY = (0.3665, 0.160)
# Two rows ("#15 DRILL" over the size and extent) inside the left border.
PINCH_CLEARANCE_CALLOUT_XY = (0.042, 0.074)
# The bar-contact finishes: right of the top view, under the reamed hole's
# leader. The wall lands on its top edge 2.5 short of the far end, the floor
# on its end edge.
WALL_FINISH_XY = (0.170, 0.195)
FLOOR_FINISH_XY = (0.172, 0.208)
WALL_FINISH_X = part_spec.BLOCK_X1 - 2.5
# The floor-corner note: above section A-A, right of its slot, its leader down
# through the slot opening to the floor's edge-A corner (farm r4 landed it
# there).
SLOT_CORNER_NOTE_XY = (0.2765, 0.2247)


_KIT = "ch_rocker_arm_tl_trammel_spec"
_BUILD = ("draw_ch_rocker_arm_tl_trammel_pivot_block", "build")
_FROM_TOP = ("block_top", (_BUILD,))
# Distances across the block (Z) are heights from edge A.
_FROM_EDGE_A = ("edge_a", (_BUILD,))
_POINT_HALF_Z = part_spec.SLIT_Z1 + 1.0  # the edge-B jaw's half of a slit hole


part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        ("_drawing_hole_callout", "add_native_hole_callout"),
        ("_surface_finish", "ra"),
    )
)

requirement(
    "block_top",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), 0.0),),
    requirements=("height",),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "height": (
            limits(part_spec.BLOCK_HEIGHT, part_spec.BLOCK_HEIGHT_PLACES),
            ("BLOCK_HEIGHT", "BLOCK_HEIGHT_PLACES"),
        ),
        "height_nominal": (part_spec.BLOCK_HEIGHT, ("BLOCK_HEIGHT",)),
    },
    precision={"height": part_spec.BLOCK_HEIGHT_PLACES},
)

requirement(
    "edge_a",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("width",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "width": (limits(part_spec.BLOCK_WIDTH, 1), ("BLOCK_WIDTH",)),
        "width_nominal": (part_spec.BLOCK_WIDTH, ("BLOCK_WIDTH",)),
    },
    precision={"width": 1},
)

# The end that sits flush with the bar's pivot end; the slit splits it, so
# the edge-A side names it.
requirement(
    "near_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), -part_spec.BLOCK_X0, contains_z_mm=5.0),),
    requirements=("length", "station"),
    fields={
        "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "x", "value": part_spec.BLOCK_X0},
            ("BLOCK_X0",),
        ),
        "length": (limits(part_spec.BLOCK_LENGTH, 1), ("BLOCK_LENGTH",)),
        "length_nominal": (part_spec.BLOCK_LENGTH, ("BLOCK_LENGTH",)),
        "station": (
            limits(part_spec.HOLE_FROM_END, 1),
            ("HOLE_FROM_END", (_KIT, "PIVOT_HOLE_L")),
        ),
        "station_nominal": (part_spec.HOLE_FROM_END, ("HOLE_FROM_END",)),
    },
    precision={"length": 1, "station": 1},
)

requirement(
    "bar_slot",
    kind="slot",
    faces=(PlanarFace((0.0, 1.0, 0.0), -part_spec.SLOT_DEPTH),),
    requirements=("width", "depth", "height"),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "width": (
            limits(part_spec.SLOT_WIDTH, 2, part_spec.kit.SLOT_WIDTH_BAND),
            ("SLOT_WIDTH", (_KIT, "SLOT_WIDTH_BAND")),
        ),
        "width_nominal": (part_spec.SLOT_WIDTH, ("SLOT_WIDTH",)),
        "depth": (
            limits(part_spec.SLOT_DEPTH, part_spec.SLOT_DEPTH_PLACES),
            ("SLOT_DEPTH", "SLOT_DEPTH_PLACES"),
        ),
        "depth_ref": (part_spec.SLOT_DEPTH, ("SLOT_DEPTH",)),
        "height": (limits(part_spec.SLOT_FROM_EDGE_A, 1), ("SLOT_FROM_EDGE_A",)),
        "height_nominal": (part_spec.SLOT_FROM_EDGE_A, ("SLOT_FROM_EDGE_A",)),
        "height_from": _FROM_EDGE_A,
        "corner_radius_max_design": (
            part_spec.SLOT_CORNER_R_MAX,
            ("SLOT_CORNER_R_MAX", "SLOT_CORNER_CALLOUT"),
        ),
        "note": (
            " ".join(part_spec.SLOT_WIDTH_CALLOUT.splitlines()),
            ("SLOT_WIDTH_CALLOUT",),
        ),
    },
    precision={"width": 2, "depth": part_spec.SLOT_DEPTH_PLACES, "height": 1},
)

# The slot's edge-B wall: the set screws push the bar against it.
requirement(
    "bar_slot_datum_wall",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -part_spec.SLOT_Z1),),
    requirements=(),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.SLOT_Z1},
            ("SLOT_Z1",),
        ),
        "parent": (
            "bar_slot",
            ("SLOT_Z1", ("draw_ch_rocker_arm_tl_trammel_pivot_block", "build")),
        ),
    },
)

# The slit runs in from the near end through the point hole and ends in the
# drilled relief; its edge-B jaw face beside the relief names it. Its
# distance from edge A is the point hole's by equation (one 28.0 prints).
requirement(
    "slit",
    kind="slot",
    faces=(
        PlanarFace(
            (0.0, 0.0, -1.0),
            -part_spec.SLIT_Z1,
            contains_x_mm=part_spec.SLIT_END_X - part_spec.SLIT_RELIEF_DIA,
        ),
    ),
    requirements=("width", "height"),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "width": (limits(part_spec.SLIT_WIDTH, 1), ("SLIT_WIDTH",)),
        "width_nominal": (part_spec.SLIT_WIDTH, ("SLIT_WIDTH",)),
        "height": (limits(part_spec.SLIT_Z, 1), ("SLIT_Z", "POINT_FROM_EDGE_A")),
        "height_nominal": (part_spec.SLIT_Z, ("SLIT_Z", "POINT_FROM_EDGE_A")),
        "height_from": _FROM_EDGE_A,
        "thru": (True, ("SLIT_CALLOUT",)),
    },
    precision={"width": 1, "height": 1},
)

# The relief that ends the slit: its station from the point-hole axis.
requirement(
    "slit_relief",
    kind="hole",
    faces=(
        CylinderFace(part_spec.SLIT_RELIEF_DIA, contains_x_mm=part_spec.SLIT_END_X),
    ),
    requirements=("station", "dia", "thru"),
    fields={
        "at": (
            [part_spec.SLIT_END_X, 0.0, part_spec.SLIT_Z],
            ("__frame__", "SLIT_END_X", "SLIT_Z"),
        ),
        "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
        "station": (limits(part_spec.SLIT_END_X, 1), ("SLIT_END_X",)),
        "station_nominal": (part_spec.SLIT_END_X, ("SLIT_END_X",)),
        "dia": (
            limits(part_spec.SLIT_RELIEF_DIA, 1, part_spec.DRILLED_BAND),
            ("SLIT_RELIEF_DIA", "DRILLED_BAND"),
        ),
        "dia_nominal": (part_spec.SLIT_RELIEF_DIA, ("SLIT_RELIEF_DIA",)),
        "thru": (True, ("SLIT_RELIEF_CALLOUT",)),
        "parent": ("slit", ("SLIT_END_X", _BUILD)),
    },
    precision={"station": 1, "dia": 1},
)

requirement(
    "point_hole",
    kind="hole",
    faces=(
        CylinderFace(
            part_spec.POINT_HOLE_DIA, contains_x_mm=0.0, contains_z_mm=_POINT_HALF_Z
        ),
    ),
    requirements=("dia", "height", "thru"),
    fields={
        "at": (
            [0.0, 0.0, part_spec.POINT_FROM_EDGE_A],
            ("__frame__", "POINT_FROM_EDGE_A"),
        ),
        "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
        "dia": (
            limits(part_spec.POINT_HOLE_DIA, 3, part_spec.POINT_HOLE_BAND),
            ("POINT_HOLE_DIA", "POINT_HOLE_BAND"),
        ),
        "dia_nominal": (part_spec.POINT_HOLE_DIA, ("POINT_HOLE_DIA",)),
        "height": (limits(part_spec.POINT_FROM_EDGE_A, 1), ("POINT_FROM_EDGE_A",)),
        "height_nominal": (part_spec.POINT_FROM_EDGE_A, ("POINT_FROM_EDGE_A",)),
        "height_from": _FROM_EDGE_A,
        "thru": (True, ("POINT_HOLE_CALLOUT",)),
        # The rule-4 callout names the mate (POINT_MATE_NUMBER).
        "note": (
            " ".join(part_spec.POINT_HOLE_CALLOUT.splitlines()),
            ("POINT_HOLE_CALLOUT", "POINT_MATE_NUMBER"),
        ),
    },
    precision={"dia": 3, "height": 1},
)

for _index, _x in enumerate(part_spec.SET_SCREW_X, start=1):
    requirement(
        f"set_screw_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.SET_SCREW_TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "station", "height", "thru"),
        fields={
            "at": (
                [_x, -part_spec.SET_SCREW_DEPTH, 0.0],
                ("SET_SCREW_X", "SET_SCREW_DEPTH"),
            ),
            "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
            "thread": (f"{part_spec.SET_SCREW_SIZE} UNC-2B", ("SET_SCREW_SPEC",)),
            "tap_drill_mm": (part_spec.SET_SCREW_TAP_DRILL, ("SET_SCREW_TAP_DRILL",)),
            # Through into the slot: no drill-point face, so the tap carries
            # the printed drill band.
            "dia": (
                limits(
                    round(part_spec.SET_SCREW_TAP_DRILL, 2), 2, part_spec.DRILLED_BAND
                ),
                ("SET_SCREW_TAP_DRILL", "DRILLED_BAND", "SET_SCREW_SPEC"),
            ),
            "dia_nominal": (
                round(part_spec.SET_SCREW_TAP_DRILL, 2),
                ("SET_SCREW_TAP_DRILL",),
            ),
            "thru": (True, ("SET_SCREW_SPEC",)),
            "station": (limits(_x, 1), ("SET_SCREW_X", (_KIT, "SET_SCREW_L"))),
            "station_nominal": (_x, ("SET_SCREW_X",)),
            "height": (
                limits(part_spec.SET_SCREW_DEPTH, 1),
                ("SET_SCREW_DEPTH", (_KIT, "SET_SCREW_Z")),
            ),
            "height_nominal": (part_spec.SET_SCREW_DEPTH, ("SET_SCREW_DEPTH",)),
            "height_from": _FROM_TOP,
        },
        precision={"dia": 2, "station": 1, "height": 1},
    )

for _index, _x in enumerate(part_spec.PINCH_X, start=1):
    requirement(
        f"pinch_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.PINCH_TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "station", "height", "thru"),
        fields={
            "at": (
                [_x, -part_spec.PINCH_DEPTH, part_spec.SLIT_Z0],
                ("PINCH_X", "PINCH_DEPTH", "SLIT_Z0"),
            ),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "thread": (f"{part_spec.PINCH_THREAD} UNC-2B", ("PINCH_TAP_SPEC",)),
            "tap_drill_mm": (part_spec.PINCH_TAP_DRILL, ("PINCH_TAP_DRILL",)),
            "dia": (
                limits(round(part_spec.PINCH_TAP_DRILL, 2), 2, part_spec.DRILLED_BAND),
                ("PINCH_TAP_DRILL", "DRILLED_BAND", "PINCH_TAP_SPEC"),
            ),
            "dia_nominal": (round(part_spec.PINCH_TAP_DRILL, 2), ("PINCH_TAP_DRILL",)),
            "thru": (True, ("PINCH_TAP_SPEC",)),
            "station": (limits(_x, 1), ("PINCH_X",)),
            "station_nominal": (_x, ("PINCH_X",)),
            "height": (
                limits(part_spec.PINCH_DEPTH, part_spec.PINCH_PLACES),
                ("PINCH_DEPTH", "PINCH_PLACES"),
            ),
            "height_nominal": (part_spec.PINCH_DEPTH, ("PINCH_DEPTH",)),
            "height_from": _FROM_TOP,
        },
        precision={"dia": 2, "station": 1, "height": part_spec.PINCH_PLACES},
    )

for _index, _x in enumerate(part_spec.PINCH_X, start=1):
    requirement(
        f"pinch_clearance_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.PINCH_CLEARANCE_DIA, contains_x_mm=_x),),
        requirements=("dia",),
        fields={
            "parent": (
                f"pinch_tap_{_index}",
                (
                    "PINCH_CLEARANCE_SPEC",
                    ("draw_ch_rocker_arm_tl_trammel_pivot_block", "build"),
                ),
            ),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "dia": (
                limits(
                    part_spec.PINCH_CLEARANCE_PRINTED_DIA, 2, part_spec.DRILLED_BAND
                ),
                ("PINCH_CLEARANCE_PRINTED_DIA", "DRILLED_BAND", "PINCH_CLEARANCE_SPEC"),
            ),
            "dia_nominal": (
                part_spec.PINCH_CLEARANCE_PRINTED_DIA,
                ("PINCH_CLEARANCE_PRINTED_DIA",),
            ),
            # Drilled from edge B up to the slit.
            "note": (
                f"{part_spec.PINCH_CLEARANCE_PROCESS} {part_spec.PINCH_CLEARANCE_EXTENT_TEXT}",
                ("PINCH_CLEARANCE_PROCESS", "PINCH_CLEARANCE_EXTENT_TEXT"),
            ),
        },
        precision={"dia": 2},
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open trammel pivot block source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Template Trammel Pivot Block Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker outline-template trammel pivot block; 1018; MHA-CH-006-TL-14",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *SHEET.top_center, scale=VIEW_SCALE)
    front = place_view(
        adapter, str(SOURCE), "*Front", *SHEET.front_center, scale=VIEW_SCALE
    )
    right = place_view(
        adapter, str(SOURCE), "*Right", *SHEET.right_center, scale=VIEW_SCALE
    )
    back = place_view(
        adapter, str(SOURCE), "*Back", *SHEET.back_center, scale=VIEW_SCALE
    )
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    section = create_pinch_section(
        adapter,
        front,
        part_spec.PINCH_X[0],
        view_xy=SECTION_CENTER,
        caption_xy=SECTION_CAPTION_XY,
        scale=VIEW_SCALE,
    )
    for view in (top, front, right, back, section, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="top face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="edge B",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="end",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            back,
            keep=BACK_KEEP,
            view_label="edge A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # No explicit centre marks: the template marks every hole as each view is
    # placed, and AutoInsertCenterMarks2 printed a second, identical mark
    # (farm r2 duplicate-annotation; draw_mg_wheel_drum, #913).
    set_screw_callout = add_native_hole_callout(
        adapter,
        back,
        callout_xy=SET_SCREW_CALLOUT_XY,
        label="trammel bar set-screw taps",
        edge=circle_edge(
            adapter,
            back,
            part_spec.SET_SCREW_TAP_DRILL,
            "edge A set-screw tap",
            center_x_mm=SET_SCREW_LEADER_X,
        ),
        process=part_spec.SET_SCREW_PROCESS,
    )
    strip_thread_class(set_screw_callout, label="set-screw tap callout")
    pinch_tap_callout = add_native_hole_callout(
        adapter,
        back,
        callout_xy=PINCH_TAP_CALLOUT_XY,
        label="pinch screw tap",
        edge=circle_edge(
            adapter,
            back,
            part_spec.PINCH_TAP_DRILL,
            "edge A pinch tap exit",
            center_x_mm=part_spec.PINCH_X[0],
        ),
        process=part_spec.PINCH_TAP_PROCESS,
    )
    strip_thread_class(pinch_tap_callout, label="pinch tap callout")
    pinch_clearance_callout = add_native_hole_callout(
        adapter,
        front,
        callout_xy=PINCH_CLEARANCE_CALLOUT_XY,
        label="pinch screw clearance",
        edge=circle_edge(
            adapter,
            front,
            part_spec.PINCH_CLEARANCE_DIA,
            "edge B pinch clearance",
            center_x_mm=part_spec.PINCH_X[0],
        ),
        process=part_spec.PINCH_CLEARANCE_PROCESS + "\n",
    )
    set_blind_extent_text(
        pinch_clearance_callout,
        part_spec.PINCH_CLEARANCE_EXTENT_TEXT,
        part_spec.PINCH_CLEARANCE_DIA,
    )
    # The bar's contact faces (rule 6), on the top view: the edge-B wall at
    # its top edge, the floor at its end edge.
    add_surface_finish(
        adapter,
        top,
        symbol_xy=WALL_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "slot_datum_wall"),
        label="bar slot datum-wall finish",
        char_height=0.0025,
        entity=straight_edge(
            top,
            "slot datum wall's top edge",
            lambda a, b: (
                near(a[1], 0.0)
                and near(b[1], 0.0)
                and near(a[2], part_spec.SLOT_Z1)
                and near(b[2], part_spec.SLOT_Z1)
            ),
        ),
        leader_attach_xy=mm_in_view(
            adapter,
            top,
            (WALL_FINISH_X, 0.0, part_spec.SLOT_Z1),
            label="datum wall finish landing",
        ),
    )
    add_surface_finish(
        adapter,
        top,
        symbol_xy=FLOOR_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "slot_floor"),
        label="bar slot floor finish",
        char_height=0.0025,
        entity=straight_edge(
            top,
            "slot floor's far end edge",
            lambda a, b: (
                near(a[0], part_spec.BLOCK_X1)
                and near(b[0], part_spec.BLOCK_X1)
                and near(a[1], -part_spec.SLOT_DEPTH)
                and near(b[1], -part_spec.SLOT_DEPTH)
            ),
        ),
        leader_attach_xy=mm_in_view(
            adapter,
            top,
            (part_spec.BLOCK_X1, -part_spec.SLOT_DEPTH, part_spec.SLOT_FROM_EDGE_A),
            label="slot floor finish landing",
        ),
    )
    # Rule 16's corner cap, off the views: down through the slot's opening in
    # section A-A to the floor beside the edge-B wall.
    add_attached_note(
        adapter,
        section,
        text=part_spec.SLOT_CORNER_CALLOUT,
        note_xy=SLOT_CORNER_NOTE_XY,
        label="slot floor corners",
        # Selected directly (draw_dt_crankshaft, and the swing platform's
        # section finishes): r3's sheet pick plus attached_to read
        # same_entity=False on section A-A. Pinned to the cut plane so a
        # coincident edge behind it cannot stand in for the cut floor.
        entity=straight_edge(
            section,
            "slot floor in section A-A",
            lambda a, b: (
                near(a[0], part_spec.PINCH_X[0])
                and near(b[0], part_spec.PINCH_X[0])
                and near(a[1], -part_spec.SLOT_DEPTH)
                and near(b[1], -part_spec.SLOT_DEPTH)
                and near(a[2], part_spec.SLOT_Z0)
                and near(b[2], part_spec.SLOT_Z1)
            ),
        ),
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # Precise shaded isometrics need the taps' cosmetic threads imported
    # (draw_pn_pen_hanger); the hole callouts already state every thread.
    import_cosmetic_threads(adapter, iso)
    for view in (back, front, section, iso):
        hide_thread_labels(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Template Trammel Pivot Block Drawing",
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
