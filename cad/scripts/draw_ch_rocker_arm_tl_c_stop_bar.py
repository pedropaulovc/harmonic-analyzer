r"""Create the drawing for the rocker inspection box's C stop bar (MHA-CH-006-TL-09)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    visible_component_entities,
)

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
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_c_stop_bar_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_c_stop_bar_spec import (
    CBORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_c_stop_bar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 40 x 12.7 x 12.7 bar: 2:1 keeps the gauge height and both screw
# stations legible.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
# The counterbored face (looking at the bar from in front of the box) carries
# every size from the left end and the bottom; the right-side view to
# its right (third angle) shows the stock width; the shaded isometric beyond.
FRONT_CENTER = (0.130, 0.170)
RIGHT_CENTER = (0.230, 0.170)
ISO_CENTER = (0.330, 0.175)
ISO_NOTE_XY = (0.295, 0.230)
FRONT_KEEP = {
    "BarLength": (0.130, 0.215),
    # The height alone left of the view; the hole height to its right, so
    # the height's two callout lanes have the whole left margin.
    "BarHeight": (0.051, 0.170),
    # Text above the bar's top extension line, clear of both extensions.
    "HoleY": (0.184, 0.182),
    "HoleLeftX": (0.115, 0.135),
    "HoleRightX": (0.120, 0.120),
}
RIGHT_KEEP = {"BarWidth": (0.230, 0.135)}


_Z = [0.0, 0.0, 1.0]


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME", ("_drawing_hole_callout", "add_native_hole_callout")))

requirement("c_stop_top",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), part_spec.BAR_HEIGHT),),
    requirements=("height", "length", "width"),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": part_spec.BAR_HEIGHT}, ("BAR_HEIGHT",)),
        "height": (
            limits(part_spec.BAR_HEIGHT, 3, part_spec.BAR_HEIGHT_BAND),
            ("BAR_HEIGHT", "BAR_HEIGHT_BAND"),
        ),
        "height_nominal": (part_spec.BAR_HEIGHT, ("BAR_HEIGHT",)),
        "length_nominal": (part_spec.BAR_LENGTH, ("BAR_LENGTH",)),
        "width_nominal": (part_spec.BAR_WIDTH, ("BAR_WIDTH",)),
        "length": (
            limits(part_spec.BAR_LENGTH, 1),
            ("BAR_LENGTH", "C_LAND_X0", ("ch_rocker_arm_spec", "TIP_FACE")),
        ),
        "width": (
            limits(part_spec.BAR_WIDTH, 1),
            ("BAR_WIDTH", ("ch_rocker_arm_spec", "ARM_THICKNESS")),
        ),
    },
    precision={"height": 3, "length": 1, "width": 1},
)

requirement("base_seat",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("height",),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "height": (
            limits(part_spec.BAR_HEIGHT, 3, part_spec.BAR_HEIGHT_BAND),
            ("BAR_HEIGHT", "BAR_HEIGHT_BAND"),
        ),
    },
    precision={"height": 3},
)

requirement("box_face_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("width",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "width": (limits(part_spec.BAR_WIDTH, 1), ("BAR_WIDTH",)),
    },
    precision={"width": 1},
)

# Below the hole-height arrows and left of the side view's 12.7 extensions.
CALLOUT_XY = (0.183, 0.138)
# Functional acceptance sits on the dimension it governs, not in the notes.
# The size band is the stop's only tilt control (no GD&T on fixture prints).
CALLOUTS_ABOVE = {"BarHeight": "DATUM C STOP: BAND IS TILT", "HoleY": "2X"}
CALLOUTS_BELOW = {
    "BarHeight": "LIMIT FOR MHA-CH-006 CHECK",
    # Inside the 30.00 extension lines: the stations' matching requirement.
    "HoleRightX": "SCREWS ENTER TL-08 TAPS",
}


for side, x in zip(("left", "right"), part_spec.SCREW_X, strict=True):
    requirement(f"screw_hole_{side}",
        kind="hole",
        faces=(CylinderFace(part_spec.CLEARANCE_DIA, contains_x_mm=x),),
        requirements=("station", "height", "dia", "thru"),
        fields={
            "at": ([x, part_spec.SCREW_Y, part_spec.BAR_WIDTH], ("SCREW_X", "SCREW_Y", "BAR_WIDTH")),
            "axis": (_Z, ("__frame__",)),
            "station": (limits(x, 2, part_spec.SCREW_POSITION_BAND), ("SCREW_X", "SCREW_POSITION_BAND")),
            "station_nominal": (x, ("SCREW_X",)),
            "height": (limits(part_spec.SCREW_Y, 2, part_spec.SCREW_POSITION_BAND), ("SCREW_Y", "SCREW_POSITION_BAND")),
            "height_nominal": (part_spec.SCREW_Y, ("SCREW_Y",)),
            "dia_nominal": (part_spec.CLEARANCE_DIA, ("CLEARANCE_DIA",)),
            "dia": (
                limits(part_spec.CLEARANCE_DIA, 2, part_spec.DRILLED_BAND),
                ("CLEARANCE_DIA", "DRILLED_BAND", "SCREW_HOLE_SPEC"),
            ),
            "thru": (True, ("SCREW_HOLE_SPEC",)),
        },
        precision={"station": 2, "height": 2, "dia": 2},
    )

for side, x in zip(("left", "right"), part_spec.SCREW_X, strict=True):
    requirement(f"screw_hole_{side}_counterbore",
        kind="counterbore",
        faces=(
            CylinderFace(part_spec.CBORE_DIA, contains_x_mm=x),
            PlanarFace((0.0, 0.0, 1.0), part_spec.BAR_WIDTH - part_spec.CBORE_DEPTH, contains_x_mm=x),
        ),
        requirements=("dia", "depth"),
        fields={
            "parent": (f"screw_hole_{side}", ("SCREW_HOLE_SPEC", ("draw_ch_rocker_arm_tl_c_stop_bar", "build"))),
            "dia": (limits(part_spec.CBORE_DIA, 2), ("CBORE_DIA", "SCREW_HOLE_SPEC")),
            "dia_nominal": (part_spec.CBORE_DIA, ("CBORE_DIA",)),
            "depth": (limits(part_spec.CBORE_DEPTH, 2), ("CBORE_DEPTH", "SCREW_HOLE_SPEC")),
            "depth_ref": (part_spec.CBORE_DEPTH, ("CBORE_DEPTH",)),
        },
        precision={"dia": 2, "depth": 2},
    )



def _counterbore_edge(adapter: Any, view: Any) -> Any:
    radius_m = CBORE_DIA / 2000.0
    for component in adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ():
        for raw in visible_component_entities(view, component, 1) or ():
            edge = _early_bound(raw, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve.IsCircle() and abs(float(curve.CircleParams[6]) - radius_m) <= 1e-6:
                return edge
    raise RuntimeError("C stop bar front view shows no counterbore rim")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open C stop bar source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Inspection C Stop Bar Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker inspection box C stop bar; hardened O1; MHA-CH-006-TL-09",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="counterbored face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="right side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add center marks to the C stop bar screw holes")
    add_native_hole_callout(
        adapter,
        front,
        callout_xy=CALLOUT_XY,
        label="C stop bar #8 counterbored screw holes",
        edge=_counterbore_edge(adapter, front),
        process="DRILL",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Inspection C Stop Bar Drawing",
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
