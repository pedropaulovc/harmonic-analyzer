r"""Create the curated machinist drawing for the pen square rod."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    _edge_endpoint_key,
    PmiDrawingPlacement,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    project_part_pmi,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    visible_view_entities,
)
from _gear_drawing_entities import visible_circle_edge
from _hole_spec import blind_cut_dia_mm
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pen_rod_spec import (
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    ROD_LENGTH,
    ROD_SECTION,
    SURFACE_FINISHES,
    WIRE_HOLE_SPEC,
    WIRE_HOLE_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pen_rod"]
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
_WIRE_HOLE_DIA = blind_cut_dia_mm(WIRE_HOLE_SPEC)

SHEET_SCALE = (1.0, 1.0)
TOP_VIEW_SCALE = 4.0
FRONT_CENTER = (0.070, 0.150)
RIGHT_CENTER = (0.140, 0.150)
TOP_CENTER = (0.070, 0.245)
ISO_CENTER = (0.340, 0.195)

FRONT_KEEP = {
    "Length": (FRONT_CENTER[0] - 0.030, FRONT_CENTER[1]),
    # x offset -0.034 (the Depth spelling below), NOT the view centre: Section
    # measures the 5 mm square across, so at 1:1 its two extension lines land
    # 4.7 mm apart (measured x=0.0679 and x=0.0726) while the toleranced text
    # renders 24.5 mm wide. Centred on FRONT_CENTER[0] the text spanned
    # 0.0580..0.0820, so BOTH extension lines ran through it and struck out
    # "+0.00/-0.05". text_xy is the text CENTRE, so -0.034 puts the run at
    # 0.0238..0.0483: clear of the left extension line by 19.6 mm and of the
    # drawn border rule (gray, x=~0.0126) by ~11.2 mm. No gate sees this -- a
    # dimension exposes no GetExtent, so only the render shows it.
    "Section": (
        FRONT_CENTER[0] - 0.034,
        FRONT_CENTER[1] - ROD_LENGTH / 2000.0 - 0.012,
    ),
}
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] - 0.034, TOP_CENTER[1]),
}
# No-oversize bands on both functional slide dimensions live on the source model.
DIMENSION_CALLOUTS: dict[str, str] = {}
TOP_DIMENSION_CALLOUTS: dict[str, str] = {}


@_telemetry.traced("drawing.verify_dimension_value", label_param="label")
def _require_dimension_value(display: Any, expected_mm: float, *, label: str) -> None:
    """Fail if SolidWorks dimensioned a different projected edge."""
    display = _early_bound(display, "IDisplayDimension")
    raw_dimension = display.GetDimension2(0)
    if raw_dimension is None:
        raise RuntimeError(f"{label}: display has no dimension")
    dimension = _early_bound(raw_dimension, "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if not math.isclose(measured_mm, expected_mm, rel_tol=0.0, abs_tol=1e-5):
        raise RuntimeError(
            f"{label}: measured {measured_mm:g}, expected {expected_mm:g} mm"
        )


@_telemetry.traced("drawing.pick_pen_rod_datum_edges")
def _visible_front_datum_edges(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the visible bottom and left edges for locating the front-view hole.

    Each datum has coincident edges at z=0 and z=ROD_SECTION. Because the part
    extrudes +Z from its Front sketch, the canonical maximum is nearest *Front.
    """
    half_section_m = ROD_SECTION / 2000.0
    section_m = ROD_SECTION / 1000.0
    length_m = ROD_LENGTH / 1000.0
    bottom: list[tuple[tuple[float, ...], Any]] = []
    left: list[tuple[tuple[float, ...], Any]] = []
    edges = visible_view_entities(view, 1, label="pen-rod front edges")
    for raw_edge in edges:
        edge = _early_bound(raw_edge, "IEdge")
        endpoints = _edge_endpoint_key(adapter, edge)
        if endpoints is None:
            continue
        x0, y0, z0, x1, y1, z1 = endpoints
        geometry = tuple(sorted((endpoints[:3], endpoints[3:])))
        key = geometry[0] + geometry[1]
        if (
            abs(y0) <= 1e-6
            and abs(y1) <= 1e-6
            and abs(abs(x1 - x0) - section_m) <= 1e-6
            and abs(z1 - z0) <= 1e-6
        ):
            bottom.append((key, edge))
        if (
            abs(x0 + half_section_m) <= 1e-6
            and abs(x1 + half_section_m) <= 1e-6
            and abs(abs(y1 - y0) - length_m) <= 1e-6
            and abs(z1 - z0) <= 1e-6
        ):
            left.append((key, edge))

    span = _telemetry.trace.get_current_span()
    span.set_attribute("edges", len(edges))
    span.set_attribute("bottom_matches", len(bottom))
    span.set_attribute("left_matches", len(left))
    if not bottom:
        raise RuntimeError("pen-rod front view has no exact bottom edge")
    if not left:
        raise RuntimeError("pen-rod front view has no exact left edge")
    return (
        max(bottom, key=lambda candidate: candidate[0])[1],
        max(left, key=lambda candidate: candidate[0])[1],
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-rod source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Top View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen rod; square brass slide rod; wire hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, right)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, top_annotations, TOP_DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the wire hole")
    wire_hole_edge = visible_circle_edge(adapter, front, _WIRE_HOLE_DIA)
    bottom_edge, left_edge = _visible_front_datum_edges(adapter, front)

    front_bottom = (FRONT_CENTER[0], FRONT_CENTER[1] - ROD_LENGTH / 2000.0)
    front_side = (FRONT_CENTER[0] - 0.0025, FRONT_CENTER[1])
    front_far_side = (FRONT_CENTER[0] + 0.0025, FRONT_CENTER[1])
    hole_center_y = front_bottom[1] + WIRE_HOLE_Y / 1000.0
    hole_center = (FRONT_CENTER[0], hole_center_y)

    wire_hole_y = add_edge_dimension(
        adapter,
        front,
        p0=front_bottom,
        p1=hole_center,
        text_xy=(FRONT_CENTER[0] + 0.032, FRONT_CENTER[1] + 0.030),
        label="wire-hole length location",
        orientation="vertical",
        entities=(bottom_edge, wire_hole_edge),
    )
    set_arc_endpoints_to_center(
        adapter, wire_hole_y, label="wire-hole length location"
    )
    _require_dimension_value(
        wire_hole_y, WIRE_HOLE_Y, label="wire-hole length location"
    )
    # Locate the wire hole ACROSS the square section too: the native callout gives
    # only the drill size, so without this the cross-hole could sit off-centre and
    # still satisfy every shown dimension. Both references are exact model edges,
    # and the 2.50 mm value is verified.
    wire_hole_x = add_edge_dimension(
        adapter,
        front,
        p0=front_side,
        p1=hole_center,
        text_xy=(FRONT_CENTER[0] - 0.030, hole_center_y + 0.020),
        label="wire-hole centerline location",
        orientation="horizontal",
        entities=(left_edge, wire_hole_edge),
    )
    set_arc_endpoints_to_center(
        adapter, wire_hole_x, label="wire-hole centerline location"
    )
    _require_dimension_value(
        wire_hole_x, ROD_SECTION / 2.0, label="wire-hole centerline location"
    )
    add_native_hole_callout(
        adapter,
        front,
        edge=wire_hole_edge,
        callout_xy=(FRONT_CENTER[0] + 0.034, hole_center_y + 0.010),
        label="pen-rod wire hole",
    )

    # GD&T is model PMI (pen_rod_spec.PART_DATUMS/GEOMETRIC_CONTROLS, authored
    # by build_pen_rod) — project it and place it where the hand-authored
    # symbols used to sit. All three annotations land in the single front view,
    # and the projection fails loud on any mismatch. The squareness frame stays BELOW the rod: up-right
    # of its target its leader crossed the Ra's leader in an X at the rod's
    # bottom corner; from below the two run on opposite sides of that corner.
    project_part_pmi(
        adapter,
        placements={
            "datum:A": PmiDrawingPlacement(
                view=front,
                position=(front_side[0] - 0.016, FRONT_CENTER[1] - 0.030),
                attachment_xy=front_side,
            ),
            "opposite_slide_face_parallelism": PmiDrawingPlacement(
                view=front,
                position=(FRONT_CENTER[0] + 0.032, FRONT_CENTER[1] - 0.018),
                attachment_xy=front_far_side,
            ),
            "bottom_end_squareness": PmiDrawingPlacement(
                view=front,
                position=(FRONT_CENTER[0] + 0.005, FRONT_CENTER[1] - 0.070),
                attachment_xy=front_bottom,
            ),
        },
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        label="pen rod PMI",
    )
    # Sits RIGHT of the rod and BELOW the right view, reaching back up-left to the
    # slide face. At (0.0415, 0.165) the body printed "Ra 1.6" straight across the
    # rod, which is only 5 mm wide at 1:1 and sits at x 0.0675..0.0725.
    #
    # The symbol may not go LEFT of the rod, even though that corner is empty: the
    # leader leaves the ▽ tip AT the anchor and the ~46 mm body draws up-RIGHT of
    # it (text at x+0.013..x+0.039, y+0.010..y+0.017), so a target up-right forces
    # the leader to thread between the ▽ and its own text -- steeper than the ▽'s
    # ~1.8 flank slope is drawn through the glyph, shallower than ~1.9 clips the
    # text. That window is empty in practice: a 1.5 slope still grazed the "R".
    # Anchoring right of the rod puts the target up-LEFT instead, so the leader
    # runs away from the body and the constraint disappears.
    #
    # y=0.058 routes the leader below the right view while leaving the symbol
    # above the wrapped manufacturing note; the body ends left of the title block.
    add_surface_finish(
        adapter,
        front,
        edge_xy=(front_side[0], FRONT_CENTER[1] - 0.050),
        symbol_xy=(0.170, 0.058),
        control=surface_finish_by_key(SURFACE_FINISHES, "slide_face"),
        label="pen-rod slide face finish",
    )

    # Three explicit lines keep the manufacturing note left of the title block.
    # Lowering its anchor leaves a clear band for the surface-finish symbol.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.015, 0.045)
    add_property_linked_note(adapter, "Top View Note", 0.036, 0.266)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Rod Manufacturing Drawing",
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
