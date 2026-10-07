r"""Create the drawing for the rocker inspection box's C stop bar (MHA-CH-006-TL-09)."""

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
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    visible_component_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_rocker_arm_tl_c_stop_bar_spec import (
    CBORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_c_stop_bar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 40 x 12.7 x 12.7 bar: 2:1 keeps the lapped height and both screw
# stations legible.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
# The counterbored face (looking at the bar from in front of the box) carries
# every size from the left end and the lapped bottom; the right-side view to
# its right (third angle) shows the stock width; the shaded isometric beyond.
FRONT_CENTER = (0.130, 0.170)
RIGHT_CENTER = (0.230, 0.170)
ISO_CENTER = (0.330, 0.175)
ISO_NOTE_XY = (0.295, 0.230)
FRONT_KEEP = {
    "BarLength": (0.130, 0.215),
    "BarHeight": (0.062, 0.170),
    "HoleY": (0.080, 0.163),
    "HoleLeftX": (0.115, 0.135),
    "HoleRightX": (0.148, 0.120),
}
RIGHT_KEEP = {"BarWidth": (0.230, 0.135)}
CALLOUT_XY = (0.200, 0.150)
# Mating acceptance sits on the feature it governs, not in the notes.
DIMENSION_CALLOUTS = {"HoleY": "2X; SCREWS ENTER MHA-CH-006-TL-08 TAPS FREELY"}


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
            3: "rocker inspection box C stop bar; hardened lapped O1; MHA-CH-006-TL-09",
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
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
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
