r"""Create the drawing for the rocker template trammel's scriber block (MHA-CH-006-TL-15).

The pivot block's sheet (``draw_ch_rocker_arm_tl_trammel_pivot_block``) for
the block with two reamed point holes 16.000 apart, the longer slit and two
pinch screws. Every station along the block is dimensioned from the inner
(R800) point hole's axis.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

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
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from _trammel_block_drawing import (
    TrammelBlockSheet,
    circle_edge,
    hide_thread_labels,
    set_blind_extent_text,
)
import _telemetry
import ch_rocker_arm_tl_trammel_pivot_block_spec as block
import ch_rocker_arm_tl_trammel_scriber_block_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_trammel_scriber_block_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_trammel_scriber_block"]
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
ISO_CENTER = (0.300, 0.210)
ISO_NOTE_XY = (0.270, 0.250)
NOTES_XY = (0.020, 0.060)

# Top face (edge A at the view's top, edge B toward the edge-B view below).
TOP_KEEP = {
    "BlockLength": SHEET.top(0.5 * (part_spec.BLOCK_X0 + part_spec.BLOCK_X1), -10.0),
    "HoleFromEnd": SHEET.top(0.5 * part_spec.BLOCK_X0, -4.5),
    "BlockWidth": SHEET.top(part_spec.BLOCK_X0 - 10.0, 19.0),
    "PointFromEdgeA": SHEET.top(part_spec.BLOCK_X1 + 6.0, 11.0),
    "SlitFromEdgeA": SHEET.top(part_spec.BLOCK_X1 + 12.0, 11.0),
    "SlitWidth": SHEET.top(part_spec.BLOCK_X1 + 6.0, 31.0),
    "SlitEnd": SHEET.top(0.5 * part_spec.SLIT_END_X, 41.0),
    # Below the view, the spacing's checked-on callout under it.
    "ScriberSpacing": SHEET.top(0.5 * part_spec.SCRIBER_SPACING, 47.0),
    "PointHoleDia": SHEET.top(part_spec.BLOCK_X1 - 5.0, -12.0),
}
# Edge B (pinch screw head side): the height and the pinch stations.
FRONT_KEEP = {
    "BlockHeight": SHEET.front(part_spec.BLOCK_X0 - 10.0, -9.5),
    "PinchX1": SHEET.front(0.5 * part_spec.PINCH_X[0], -24.5),
    "PinchX2": SHEET.front(0.5 * part_spec.PINCH_X[1], -24.5),
    "PinchDepth": SHEET.front(part_spec.BLOCK_X1 + 6.0, -7.0),
}
# The end view: the bar slot from edge A (edge A on the view's right).
RIGHT_KEEP = {
    "SlotWidth": SHEET.right(block.SLOT_FROM_EDGE_A, 6.0),
    "SlotFromEdgeA": SHEET.right(0.5 * block.SLOT_FROM_EDGE_A, -24.5),
    "SlotDepth": SHEET.right(-7.0, -5.0),
}
# Edge A: the set-screw stations and their height.
BACK_KEEP = {
    "SetScrewX1": SHEET.back(0.5 * part_spec.SET_SCREW_X[0], -24.5),
    "SetScrewX2": SHEET.back(0.5 * part_spec.SET_SCREW_X[1], -24.5),
    "SetScrewDepth": SHEET.back(part_spec.BLOCK_X1 + 7.0, -2.5),
}
CALLOUTS_ABOVE = {"SlotWidth": block.SLOT_WIDTH_CALLOUT}
CALLOUTS_BELOW = {
    "PointHoleDia": part_spec.POINT_HOLE_CALLOUT,
    "ScriberSpacing": part_spec.SCRIBER_SPACING_CALLOUT,
    "SlotDepth": block.SLOT_CORNER_CALLOUT,
    "SlitWidth": block.SLIT_CALLOUT,
}
SET_SCREW_CALLOUT_XY = (0.345, 0.140)
PINCH_TAP_CALLOUT_XY = (0.345, 0.160)
PINCH_CLEARANCE_CALLOUT_XY = (0.030, 0.140)


_KIT = "ch_rocker_arm_tl_trammel_spec"
_BLOCK = "ch_rocker_arm_tl_trammel_pivot_block_spec"
_BUILD = ("draw_ch_rocker_arm_tl_trammel_scriber_block", "build")
_FROM_TOP = ("block_top", (_BUILD,))
# Distances across the block (Z) are heights from edge A.
_FROM_EDGE_A = ("edge_a", (_BUILD,))
_POINT_HALF_Z = block.SLIT_Z1 + 1.0  # the edge-B jaw's half of a slit hole


part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        ("_drawing_hole_callout", "add_native_hole_callout"),
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
            limits(block.BLOCK_HEIGHT, block.BLOCK_HEIGHT_PLACES),
            ((_BLOCK, "BLOCK_HEIGHT"), (_BLOCK, "BLOCK_HEIGHT_PLACES")),
        ),
        "height_nominal": (block.BLOCK_HEIGHT, ((_BLOCK, "BLOCK_HEIGHT"),)),
    },
    precision={"height": block.BLOCK_HEIGHT_PLACES},
)

requirement(
    "edge_a",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("width",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "width": (limits(block.BLOCK_WIDTH, 1), ((_BLOCK, "BLOCK_WIDTH"),)),
        "width_nominal": (block.BLOCK_WIDTH, ((_BLOCK, "BLOCK_WIDTH"),)),
    },
    precision={"width": 1},
)

# The end nearer the pivot; the slit splits it, so the edge-A side names it.
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
        "length": (limits(block.BLOCK_LENGTH, 1), ((_BLOCK, "BLOCK_LENGTH"),)),
        "length_nominal": (block.BLOCK_LENGTH, ((_BLOCK, "BLOCK_LENGTH"),)),
        "station": (
            limits(part_spec.HOLE_FROM_END, 1),
            ("HOLE_FROM_END", (_KIT, "SCRIBER_HOLE_L")),
        ),
        "station_nominal": (part_spec.HOLE_FROM_END, ("HOLE_FROM_END",)),
    },
    precision={"length": 1, "station": 1},
)

requirement(
    "bar_slot",
    kind="slot",
    faces=(PlanarFace((0.0, 1.0, 0.0), -block.SLOT_DEPTH),),
    requirements=("width", "depth", "height"),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "width": (
            limits(block.SLOT_WIDTH, 2, part_spec.kit.SLOT_WIDTH_BAND),
            ((_BLOCK, "SLOT_WIDTH"), (_KIT, "SLOT_WIDTH_BAND")),
        ),
        "width_nominal": (block.SLOT_WIDTH, ((_BLOCK, "SLOT_WIDTH"),)),
        "depth": (
            limits(block.SLOT_DEPTH, block.SLOT_DEPTH_PLACES),
            ((_BLOCK, "SLOT_DEPTH"), (_BLOCK, "SLOT_DEPTH_PLACES")),
        ),
        "depth_ref": (block.SLOT_DEPTH, ((_BLOCK, "SLOT_DEPTH"),)),
        "height": (
            limits(block.SLOT_FROM_EDGE_A, 1),
            ((_BLOCK, "SLOT_FROM_EDGE_A"),),
        ),
        "height_nominal": (block.SLOT_FROM_EDGE_A, ((_BLOCK, "SLOT_FROM_EDGE_A"),)),
        "height_from": _FROM_EDGE_A,
        "corner_radius_max_design": (
            block.SLOT_CORNER_R_MAX,
            ((_BLOCK, "SLOT_CORNER_R_MAX"), (_BLOCK, "SLOT_CORNER_CALLOUT")),
        ),
        "note": (
            " ".join(block.SLOT_WIDTH_CALLOUT.splitlines()),
            ((_BLOCK, "SLOT_WIDTH_CALLOUT"),),
        ),
    },
    precision={"width": 2, "depth": block.SLOT_DEPTH_PLACES, "height": 1},
)

# The slot's edge-B wall: the set screws push the bar against it.
requirement(
    "bar_slot_datum_wall",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -block.SLOT_Z1),),
    requirements=(),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": block.SLOT_Z1},
            ((_BLOCK, "SLOT_Z1"),),
        ),
        "parent": ("bar_slot", ((_BLOCK, "SLOT_Z1"), _BUILD)),
    },
)

requirement(
    "slit",
    kind="slot",
    faces=(PlanarFace((-1.0, 0.0, 0.0), -part_spec.SLIT_END_X),),
    requirements=("width", "height", "station"),
    fields={
        "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
        "width": (limits(block.SLIT_WIDTH, 1), ((_BLOCK, "SLIT_WIDTH"),)),
        "width_nominal": (block.SLIT_WIDTH, ((_BLOCK, "SLIT_WIDTH"),)),
        "height": (limits(block.SLIT_Z, 1), ((_BLOCK, "SLIT_Z"),)),
        "height_nominal": (block.SLIT_Z, ((_BLOCK, "SLIT_Z"),)),
        "height_from": _FROM_EDGE_A,
        # The slit's inner end, from the inner point-hole axis.
        "station": (limits(part_spec.SLIT_END_X, 1), ("SLIT_END_X",)),
        "station_nominal": (part_spec.SLIT_END_X, ("SLIT_END_X",)),
        "thru": (True, ((_BLOCK, "SLIT_CALLOUT"),)),
    },
    precision={"width": 1, "height": 1, "station": 1},
)

requirement(
    "point_hole_inner",
    kind="hole",
    faces=(
        CylinderFace(
            block.POINT_HOLE_DIA,
            contains_x_mm=part_spec.HOLE_X[0],
            contains_z_mm=_POINT_HALF_Z,
        ),
    ),
    requirements=("dia", "height", "thru"),
    fields={
        "at": (
            [part_spec.HOLE_X[0], 0.0, block.POINT_FROM_EDGE_A],
            ("__frame__", "HOLE_X", (_BLOCK, "POINT_FROM_EDGE_A")),
        ),
        "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
        "dia": (
            limits(block.POINT_HOLE_DIA, 3, block.POINT_HOLE_BAND),
            ((_BLOCK, "POINT_HOLE_DIA"), (_BLOCK, "POINT_HOLE_BAND")),
        ),
        "dia_nominal": (block.POINT_HOLE_DIA, ((_BLOCK, "POINT_HOLE_DIA"),)),
        "height": (
            limits(block.POINT_FROM_EDGE_A, 1),
            ((_BLOCK, "POINT_FROM_EDGE_A"),),
        ),
        "height_nominal": (block.POINT_FROM_EDGE_A, ((_BLOCK, "POINT_FROM_EDGE_A"),)),
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

requirement(
    "point_hole_outer",
    kind="hole",
    faces=(
        CylinderFace(
            block.POINT_HOLE_DIA,
            contains_x_mm=part_spec.HOLE_X[1],
            contains_z_mm=_POINT_HALF_Z,
        ),
    ),
    requirements=("dia", "station", "thru"),
    fields={
        "at": (
            [part_spec.HOLE_X[1], 0.0, block.POINT_FROM_EDGE_A],
            ("HOLE_X", (_BLOCK, "POINT_FROM_EDGE_A")),
        ),
        "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
        "dia": (
            limits(block.POINT_HOLE_DIA, 3, block.POINT_HOLE_BAND),
            ((_BLOCK, "POINT_HOLE_DIA"), (_BLOCK, "POINT_HOLE_BAND")),
        ),
        "dia_nominal": (block.POINT_HOLE_DIA, ((_BLOCK, "POINT_HOLE_DIA"),)),
        # The 16.000 spacing is the outer hole's station from the inner
        # hole's axis, the origin.
        "station": (
            limits(part_spec.SCRIBER_SPACING, 3, part_spec.kit.SCRIBER_SPACING_BAND),
            ("SCRIBER_SPACING", (_KIT, "SCRIBER_SPACING_BAND")),
        ),
        "station_nominal": (part_spec.SCRIBER_SPACING, ("SCRIBER_SPACING",)),
        "thru": (True, ("POINT_HOLE_CALLOUT",)),
        # The rule-4 callouts name the mate (POINT_MATE_NUMBER) and the check.
        "note": (
            " ".join(part_spec.SCRIBER_SPACING_CALLOUT.splitlines()),
            ("SCRIBER_SPACING_CALLOUT", "POINT_HOLE_CALLOUT", "POINT_MATE_NUMBER"),
        ),
    },
    precision={"dia": 3, "station": 3},
)

for _index, _x in enumerate(part_spec.SET_SCREW_X, start=1):
    requirement(
        f"set_screw_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(block.SET_SCREW_TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "station", "height", "thru"),
        fields={
            "at": (
                [_x, -block.SET_SCREW_DEPTH, 0.0],
                ("SET_SCREW_X", (_BLOCK, "SET_SCREW_DEPTH")),
            ),
            "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
            "thread": (f"{block.SET_SCREW_SIZE} UNC-2B", ((_BLOCK, "SET_SCREW_SPEC"),)),
            "tap_drill_mm": (
                block.SET_SCREW_TAP_DRILL,
                ((_BLOCK, "SET_SCREW_TAP_DRILL"),),
            ),
            # Through into the slot: no drill-point face, so the tap carries
            # the printed drill band.
            "dia": (
                limits(round(block.SET_SCREW_TAP_DRILL, 2), 2, block.DRILLED_BAND),
                (
                    (_BLOCK, "SET_SCREW_TAP_DRILL"),
                    (_BLOCK, "DRILLED_BAND"),
                    (_BLOCK, "SET_SCREW_SPEC"),
                ),
            ),
            "dia_nominal": (
                round(block.SET_SCREW_TAP_DRILL, 2),
                ((_BLOCK, "SET_SCREW_TAP_DRILL"),),
            ),
            "thru": (True, ((_BLOCK, "SET_SCREW_SPEC"),)),
            "station": (limits(_x, 1), ("SET_SCREW_X", (_KIT, "SET_SCREW_L"))),
            "station_nominal": (_x, ("SET_SCREW_X",)),
            "height": (
                limits(block.SET_SCREW_DEPTH, 1),
                ((_BLOCK, "SET_SCREW_DEPTH"), (_KIT, "SET_SCREW_Z")),
            ),
            "height_nominal": (block.SET_SCREW_DEPTH, ((_BLOCK, "SET_SCREW_DEPTH"),)),
            "height_from": _FROM_TOP,
        },
        precision={"dia": 2, "station": 1, "height": 1},
    )

for _index, _x in enumerate(part_spec.PINCH_X, start=1):
    requirement(
        f"pinch_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(block.PINCH_TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "station", "height", "thru"),
        fields={
            "at": (
                [_x, -block.PINCH_DEPTH, block.SLIT_Z0],
                ("PINCH_X", (_BLOCK, "PINCH_DEPTH"), (_BLOCK, "SLIT_Z0")),
            ),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "thread": (f"{block.PINCH_THREAD} UNC-2B", ((_BLOCK, "PINCH_TAP_SPEC"),)),
            "tap_drill_mm": (block.PINCH_TAP_DRILL, ((_BLOCK, "PINCH_TAP_DRILL"),)),
            "dia": (
                limits(round(block.PINCH_TAP_DRILL, 2), 2, block.DRILLED_BAND),
                (
                    (_BLOCK, "PINCH_TAP_DRILL"),
                    (_BLOCK, "DRILLED_BAND"),
                    (_BLOCK, "PINCH_TAP_SPEC"),
                ),
            ),
            "dia_nominal": (
                round(block.PINCH_TAP_DRILL, 2),
                ((_BLOCK, "PINCH_TAP_DRILL"),),
            ),
            "thru": (True, ((_BLOCK, "PINCH_TAP_SPEC"),)),
            "station": (limits(_x, 1), ("PINCH_X",)),
            "station_nominal": (_x, ("PINCH_X",)),
            "height": (
                limits(block.PINCH_DEPTH, block.PINCH_PLACES),
                ((_BLOCK, "PINCH_DEPTH"), (_BLOCK, "PINCH_PLACES")),
            ),
            "height_nominal": (block.PINCH_DEPTH, ((_BLOCK, "PINCH_DEPTH"),)),
            "height_from": _FROM_TOP,
        },
        precision={"dia": 2, "station": 1, "height": block.PINCH_PLACES},
    )

for _index, _x in enumerate(part_spec.PINCH_X, start=1):
    requirement(
        f"pinch_clearance_{_index}",
        kind="hole",
        faces=(CylinderFace(block.PINCH_CLEARANCE_DIA, contains_x_mm=_x),),
        requirements=("dia",),
        fields={
            "parent": (
                f"pinch_tap_{_index}",
                ((_BLOCK, "PINCH_CLEARANCE_SPEC"), _BUILD),
            ),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "dia": (
                limits(block.PINCH_CLEARANCE_PRINTED_DIA, 2, block.DRILLED_BAND),
                (
                    (_BLOCK, "PINCH_CLEARANCE_PRINTED_DIA"),
                    (_BLOCK, "DRILLED_BAND"),
                    (_BLOCK, "PINCH_CLEARANCE_SPEC"),
                ),
            ),
            "dia_nominal": (
                block.PINCH_CLEARANCE_PRINTED_DIA,
                ((_BLOCK, "PINCH_CLEARANCE_PRINTED_DIA"),),
            ),
            # Drilled from edge B up to the slit.
            "note": (
                f"{block.PINCH_CLEARANCE_PROCESS} {block.PINCH_CLEARANCE_EXTENT_TEXT}",
                (
                    (_BLOCK, "PINCH_CLEARANCE_PROCESS"),
                    (_BLOCK, "PINCH_CLEARANCE_EXTENT_TEXT"),
                ),
            ),
        },
        precision={"dia": 2},
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open trammel scriber block source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Template Trammel Scriber Block Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker outline-template trammel scriber block; 1018; MHA-CH-006-TL-15",
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
    for view in (top, front, right, back, iso):
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
    for view, label in (
        (top, "point holes"),
        (front, "pinch clearances"),
        (back, "edge-A taps"),
    ):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(
                f"failed to add center marks to the scriber block {label}"
            )
    add_native_hole_callout(
        adapter,
        back,
        callout_xy=SET_SCREW_CALLOUT_XY,
        label="trammel bar set-screw taps",
        edge=circle_edge(
            adapter, back, block.SET_SCREW_TAP_DRILL, "edge A set-screw tap"
        ),
        process=block.SET_SCREW_PROCESS,
    )
    add_native_hole_callout(
        adapter,
        back,
        callout_xy=PINCH_TAP_CALLOUT_XY,
        label="pinch screw taps",
        edge=circle_edge(adapter, back, block.PINCH_TAP_DRILL, "edge A pinch tap exit"),
        process=block.PINCH_TAP_PROCESS,
    )
    pinch_clearance_callout = add_native_hole_callout(
        adapter,
        front,
        callout_xy=PINCH_CLEARANCE_CALLOUT_XY,
        label="pinch screw clearances",
        edge=circle_edge(
            adapter, front, block.PINCH_CLEARANCE_DIA, "edge B pinch clearance"
        ),
        process=block.PINCH_CLEARANCE_PROCESS,
    )
    set_blind_extent_text(
        pinch_clearance_callout,
        block.PINCH_CLEARANCE_EXTENT_TEXT,
        block.PINCH_CLEARANCE_DIA,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # Precise shaded isometrics need the taps' cosmetic threads imported
    # (draw_pn_pen_hanger); the hole callouts already state every thread.
    import_cosmetic_threads(adapter, iso)
    for view in (back, front, iso):
        hide_thread_labels(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Template Trammel Scriber Block Drawing",
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
