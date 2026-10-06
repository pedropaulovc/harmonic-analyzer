r"""Create the pen square-rod drawing with settled native ink reservations."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_annotation_extent import (
    assert_annotation_reservations,
    place_annotation_in_field,
    require_clear,
)
from _drawing_common import (
    DrawingOutputs,
    _edge_endpoint_key,
    PmiDrawingPlacement,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    dimension_name,
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
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _surface_finish import surface_finish_by_key
from pn_pen_rod_spec import (
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


SPEC = DRAWINGS_BY_NAME["pn_pen_rod"]
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

# Separate the two tolerance stacks, hole locator and view caption; the complete
# property-linked process note uses the otherwise empty mid-right shelf.
ANNOTATION_FIELDS = {
    "Section": (0.020, 0.052, 0.055, 0.071),
    "Depth": (0.020, 0.234, 0.055, 0.255),
    "wire-hole centerline location": (0.020, 0.219, 0.052, 0.234),
    "bottom_end_squareness": (0.073, 0.060, 0.112, 0.072),
    "Manufacturing Notes": (0.155, 0.085, 0.415, 0.111),
    "Top View Note": (0.095, 0.252, 0.150, 0.266),
}


def _assert_release_readability(
    adapter: Any, annotations: dict[str, Any], views: tuple[Any, ...]
) -> None:
    """Read the ink the final export will print, not insertion coordinates."""
    inks = assert_annotation_reservations(
        adapter,
        annotations,
        ANNOTATION_FIELDS,
        row_limits={"Manufacturing Notes": 2, "Top View Note": 1},
        check_own_lines=("Section", "Depth", "wire-hole centerline location"),
    )
    template = DRAWING_TEMPLATES[SPEC.layout]
    title = {
        "title-block": (
            template.title_block_left_m, 0.0,
            template.width_m, template.title_block_top_m,
        )
    }
    view_boxes = {
        f"view {index}": tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
        for index, view in enumerate(views)
    }
    for label in ANNOTATION_FIELDS:
        ink = inks[label]
        require_clear(label, ink.text, {**title, **view_boxes})
        for line in ink.lines:
            box = line.box()
            require_clear(label, (box.xmin, box.ymin, box.xmax, box.ymax), title)


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
        text_xy=(FRONT_CENTER[0] - 0.040, hole_center_y + 0.010),
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
    wire_hole_callout = add_native_hole_callout(
        adapter,
        front,
        edge=wire_hole_edge,
        callout_xy=(FRONT_CENTER[0] + 0.046, hole_center_y + 0.015),
        label="pen-rod wire hole",
    )

    # Keep the bottom squareness frame below the 145.00 witness at y=0.075.
    # Its model PMI, native attachment and tolerance remain unchanged.
    pmi_annotations = project_part_pmi(
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
                position=(FRONT_CENTER[0] + 0.010, FRONT_CENTER[1] - 0.082),
                attachment_xy=front_bottom,
            ),
        },
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        label="pen rod PMI",
    )
    # The established native 2.5 mm slide-finish symbol stays left of the rod.
    slide_finish = add_surface_finish(
        adapter,
        front,
        edge_xy=(front_side[0], FRONT_CENTER[1] - 0.050),
        symbol_xy=(0.0448, 0.105),
        control=surface_finish_by_key(SURFACE_FINISHES, "slide_face"),
        label="pen-rod slide face finish",
        char_height=0.0025,
    )

    manufacturing_note = add_property_linked_note(
        adapter, "Manufacturing Notes", 0.160, 0.106
    )
    top_note = add_property_linked_note(adapter, "Top View Note", 0.100, 0.263)
    annotations = {
        dimension_name(adapter, annotation): annotation
        for annotation in (*front_annotations, *top_annotations)
    }
    annotations.update(pmi_annotations)
    annotations.update({
        "wire-hole length location": _early_bound(wire_hole_y, "IDisplayDimension").GetAnnotation(),
        "wire-hole centerline location": _early_bound(wire_hole_x, "IDisplayDimension").GetAnnotation(),
        "wire-hole callout": _early_bound(wire_hole_callout, "IDisplayDimension").GetAnnotation(),
        "slide face finish": _early_bound(slide_finish, "ISFSymbol").GetAnnotation(),
        "Manufacturing Notes": _early_bound(manufacturing_note, "INote").GetAnnotation(),
        "Top View Note": _early_bound(top_note, "INote").GetAnnotation(),
    })
    for label, field in ANNOTATION_FIELDS.items():
        place_annotation_in_field(adapter, annotations[label], label=label, field=field)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        spec=SPEC,
        pdf_title="Pen Rod Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_release_readability(adapter, annotations, (front, right, top, iso)),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
