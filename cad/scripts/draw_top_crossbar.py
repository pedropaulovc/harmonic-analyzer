r"""Create the curated machinist drawing for the cast-iron top crossbar."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from top_crossbar_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_edge_dimension,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)
from top_crossbar_spec import (
    BAR_HEIGHT,
    BAR_LENGTH,
    BAR_WIDTH,
    STUD_HOLE_DIA,
    STUD_HOLE_Z,
)


SPEC = DRAWINGS_BY_NAME["top_crossbar"]
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

SHEET_SCALE = (1.0, 1.0)
# The 202 mm bar at the view's 1:2 override is ~101 mm tall, so y=0.215 put its
# outline 1.4 mm into the top zone band. 0.211 clears it by ~2.6 mm while its
# lower edge (~0.158) still stays above the TOP VIEW SCALE note at y=0.155.
TOP_CENTER = (0.090, 0.211)
FRONT_CENTER = (0.165, 0.135)
ISO_CENTER = (0.355, 0.200)

TOP_KEEP = {
    "Depth": (TOP_CENTER[0] - 0.035, TOP_CENTER[1]),
}
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], FRONT_CENTER[1] - 0.034),
    # -0.047, not -0.035: datum B's tag sits at x=0.138 (16 mm off the bar's
    # left face), and the now-horizontal "41.00" text centred on x=0.130 ran
    # straight through it ("41.0B"). This lane clears the tag by ~5 mm and still
    # starts right of the top view (which ends at x~0.100).
    "Height": (FRONT_CENTER[0] - 0.047, FRONT_CENTER[1]),
}


@_telemetry.traced("drawing.top_crossbar_stud_hole_scan")
def _stud_hole_edge(adapter: Any, view: Any) -> Any:
    """Return the model edge for the lone top-view stud hole by radius."""
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="crossbar stud-hole edges"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        candidates.append((params[6], edge))
    if not candidates:
        raise RuntimeError("top view has no circular stud-hole model edge")
    radius, edge = min(candidates, key=lambda item: abs(item[0] - STUD_HOLE_DIA / 2.0))
    if abs(radius - STUD_HOLE_DIA / 2.0) > 0.01:
        raise RuntimeError(
            f"no top-view circle matches stud-hole radius {STUD_HOLE_DIA / 2.0:.3f} mm"
        )
    return edge


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open top-crossbar source", await adapter.open_model(str(SOURCE)))
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
            "Top View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Top View Note",
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
            0: "Top Crossbar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "top crossbar; cast iron; clearance hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to top-view stud hole")

    hole_radius_sheet = STUD_HOLE_DIA / 4000.0
    hole_center_y = TOP_CENTER[1] + STUD_HOLE_Z / 2000.0
    length_location = add_edge_dimension(
        adapter,
        top,
        p0=(TOP_CENTER[0], TOP_CENTER[1] - BAR_LENGTH / 4000.0),
        p1=(TOP_CENTER[0], hole_center_y - hole_radius_sheet),
        text_xy=(TOP_CENTER[0] + 0.030, TOP_CENTER[1] - 0.025),
        label="stud-hole length location",
    )
    set_arc_endpoints_to_center(
        adapter, length_location, label="stud-hole length location"
    )
    set_basic_dimension(adapter, length_location, label="stud-hole length location")

    front_bottom = (
        FRONT_CENTER[0],
        FRONT_CENTER[1] - BAR_HEIGHT / 2000.0,
    )
    front_left = (
        FRONT_CENTER[0] - BAR_WIDTH / 2000.0,
        FRONT_CENTER[1],
    )
    lower_end = (TOP_CENTER[0], TOP_CENTER[1] - BAR_LENGTH / 4000.0)
    upper_end = (TOP_CENTER[0], TOP_CENTER[1] + BAR_LENGTH / 4000.0)
    hole_edge = _stud_hole_edge(adapter, top)
    add_datum_feature(
        adapter,
        front,
        edge_xy=front_bottom,
        # Offset in X from the bottom face's midpoint: directly below it the
        # tag's leader ran down through the 22.00 width text, which is centred
        # on the same x. From here the leader passes x~0.186 at the dimension
        # line's height -- outside the bar's right face (0.176) -- so it reaches
        # the face without touching the dimension.
        symbol_xy=(FRONT_CENTER[0] + 0.025, front_bottom[1] - 0.016),
        datum="A",
        label="crossbar bottom face",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=front_left,
        symbol_xy=(front_left[0] - 0.016, FRONT_CENTER[1]),
        datum="B",
        label="crossbar side face",
    )
    add_datum_feature(
        adapter,
        top,
        edge_xy=lower_end,
        # The standoff must be PERPENDICULAR to the edge. This edge is the top
        # view's horizontal lower end face, so it needs a Y offset: at the edge's
        # own y the attachment triangle had nowhere to go and drew INSIDE the
        # box, its apex striking into the "C". The x-offset alone runs ALONG the
        # edge and buys no room. y-0.012 drops it into empty sheet -- clear of
        # the TOP VIEW SCALE note (which ends at x=0.092) and of the top view
        # itself (whose outline starts at y=0.158).
        symbol_xy=(TOP_CENTER[0] + 0.018, lower_end[1] - 0.012),
        datum="C",
        label="crossbar reference end seat",
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_entity=hole_edge,
        frame_xy=(0.020, 0.235),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["crossbar stud-hole position"],
        datums=("A", "B", "C"),
        diameter=True,
        label="crossbar stud-hole position",
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=lower_end,
        frame_xy=(0.115, 0.175),
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_MM["crossbar reference-end squareness"],
        datums=("A", "B"),
        label="crossbar reference-end squareness",
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=upper_end,
        frame_xy=(0.115, 0.255),
        characteristic="parallelism",
        tolerance=GEOMETRIC_TOLERANCES_MM["crossbar end-seat parallelism"],
        datums=("C",),
        label="crossbar end-seat parallelism",
    )
    # x=0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    # y=0.084, not 0.090: the anchor is the block's TOP and it grows down, so at
    # 0.090 its first line ran to y=0.0898 against datum A's tag bottom at
    # 0.0914 -- a measured 1.6 mm, which one more note line would close. The 6 mm
    # drop takes it to ~7.6 mm and costs nothing: the block's bottom lands at
    # ~0.071, still ~58 mm above the frame, and it ends at x=0.206 so it never
    # approaches the title block (x>=0.264).
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.084)
    add_property_linked_note(adapter, "Top View Note", 0.045, 0.155)
    add_native_hole_callout(
        adapter,
        top,
        edge=hole_edge,
        callout_xy=(0.125, TOP_CENTER[1] - 0.010),
        label="crossbar stud hole",
    )
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.155)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Crossbar Manufacturing Drawing",
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
