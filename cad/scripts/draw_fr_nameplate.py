r"""Create the curated machinist drawing for the engraved brass nameplate (#628).

The SLDPRT remains authoritative.  This recipe supplies only the nameplate's
views, dimension layout, section and hole callout; sheet/template and export
behaviour lives in ``_drawing_common``.

One B sheet at 2:1: the decorated face (front) carries the outline's width
and height and each screw hole's station from its two adjacent edges; the
edge view (right) carries the plate thickness; removed section A-A, cut
through the left border and into the sunk field, carries the field's depth
and the engraving floor below the decorated face.  The outline's corners, the
sunk field's notched edge and the engraving are the vendored DXF contours the
build imports (``fr_nameplate_drawing_spec.MANUFACTURING_NOTES`` names them).
The base's seats are spotted through this plate at assembly, so no datums.

Run with SolidWorks open::

    uv run python cad\scripts\draw_fr_nameplate.py fr-nameplate
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from fr_nameplate_drawing_spec import (
    DIMENSION_CALLOUTS,
    DIMENSION_PREFIXES,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    ENGRAVING_DEPTH_CALLOUT,
    ENGRAVING_FLOOR_DEPTH,
    FIELD_DEPTH,
    FIELD_DEPTH_CALLOUT,
    HOLE_CALLOUT_PROCESS,
    SCREW_HOLE_DIA,
    STATION_PREFIX,
)
from fr_nameplate_spec import PLATE_HEIGHT, PLATE_WIDTH, SCREW_XY


SPEC = DRAWINGS_BY_NAME["fr_nameplate"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 1)
SECTION_SCALE = (8, 1)
SECTION_LABEL = "A"
_M_PER_MM = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0

# Sheet layout (metres).  At 2:1 the face is 200 x 90.7 mm, x 0.050..0.250,
# y 0.125..0.215.  Third angle: the 1.5 edge view stands right of it, the
# isometric top-right, removed section A-A bottom-right above the title
# block, the notes bottom-left below the face's dimensions.
FRONT_CENTER = (0.150, 0.170)
RIGHT_CENTER = (0.276, 0.170)
ISO_CENTER = (0.366, 0.222)
ISO_NOTE_XY = (0.330, 0.183)
NOTES_XY = (0.030, 0.085)
SECTION_CENTER = (0.335, 0.115)


def _front_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a plate-face point in the front view (2:1, bbox-centred)."""
    return (
        FRONT_CENTER[0] + (x_mm - PLATE_WIDTH / 2.0) * _M_PER_MM,
        FRONT_CENTER[1] + (y_mm - PLATE_HEIGHT / 2.0) * _M_PER_MM,
    )


_LEFT, _BOTTOM = _front_xy(0.0, 0.0)
_RIGHT, _TOP = _front_xy(PLATE_WIDTH, PLATE_HEIGHT)

# Holes by role (plate-local mm): SCREW_XY runs bottom-left, bottom-right,
# top-left, top-right.  The model's S0X/S0Z place the bottom-left hole from
# the part origin, the plate's lower-left corner; the sheet locates the right
# column from the right edge (bottom-right hole) and the top row from the top
# edge (top-left hole), each "2X".  The hole callout hangs on the top-left
# hole and rises to its text above the plate.
BOTTOM_LEFT, BOTTOM_RIGHT, TOP_LEFT, TOP_RIGHT = SCREW_XY
HOLE_R = SCREW_HOLE_DIA / 2.0


def _rim(hole: tuple[float, float], degrees: float) -> tuple[float, float, float]:
    """Model point (mm) on a hole's rim in the decorated face.

    The engraved screw-head mark's counter runs 0.185 outside the rim and its
    slot crosses it, so each pick takes an angle the offline test proves 0.15
    clear of every engraved edge; the measured value of each dimension
    proves the pick again on the sheet.
    """
    angle = math.radians(degrees)
    return (
        hole[0] + HOLE_R * math.cos(angle),
        hole[1] + HOLE_R * math.sin(angle),
        0.0,
    )


# Front-view picks (model mm, on the decorated face) and their expected values.
FRONT_PICKS: dict[str, dict[str, Any]] = {
    "plate width": {
        "p0": (0.0, PLATE_HEIGHT / 2.0, 0.0),
        "p1": (PLATE_WIDTH, PLATE_HEIGHT / 2.0, 0.0),
        "expected_mm": PLATE_WIDTH,
        "orientation": "horizontal",
        "text_xy": (FRONT_CENTER[0], _BOTTOM - 0.022),
        "center": False,
    },
    "plate height": {
        "p0": (PLATE_WIDTH / 2.0, 0.0, 0.0),
        "p1": (PLATE_WIDTH / 2.0, PLATE_HEIGHT, 0.0),
        "expected_mm": PLATE_HEIGHT,
        "orientation": "vertical",
        "text_xy": (_LEFT - 0.022, FRONT_CENTER[1]),
        "center": False,
    },
    "right hole station": {
        "p0": (PLATE_WIDTH, PLATE_HEIGHT / 2.0, 0.0),
        "p1": _rim(BOTTOM_RIGHT, 0.0),
        "expected_mm": PLATE_WIDTH - BOTTOM_RIGHT[0],
        "orientation": "horizontal",
        "text_xy": (_RIGHT - 0.022, _BOTTOM - 0.012),
        "center": True,
    },
    "top hole station": {
        "p0": (PLATE_WIDTH / 2.0, PLATE_HEIGHT, 0.0),
        "p1": _rim(TOP_LEFT, 180.0),
        "expected_mm": PLATE_HEIGHT - TOP_LEFT[1],
        "orientation": "vertical",
        "text_xy": (_LEFT - 0.010, _TOP - 0.024),
        "center": True,
    },
}
STATION_DIMENSIONS = ("right hole station", "top hole station")

# Imported model dimensions: the bottom-left hole's stations from the origin
# corner (text clear of the extension lines, the S0Z text below the top
# station's), and the thickness above the edge view with its reason over it.
FRONT_KEEP = {
    "S0X": (_LEFT + 0.025, _BOTTOM - 0.012),
    "S0Z": (_LEFT - 0.010, _BOTTOM + 0.018),
}
RIGHT_KEEP = {"PlateThick": (RIGHT_CENTER[0], _TOP + 0.012)}
HOLE_CALLOUT_XY = (_LEFT + 0.045, _TOP + 0.021)


def _hole_rim_edge(edges: ViewEdges, hole: tuple[float, float]) -> Any:
    """The visible rim circle of ``hole`` in the face view, picked by entity.

    A coordinate pick on the rim took a head-mark slot edge instead (r1 leaf,
    worker 10, 2026-10-14: AddHoleCallout2 refused the EngravingCut line), so
    the callout's edge is the scanned circle of the hole's own radius and
    centre; of its face and back rims, the decorated-face one (highest z).
    """
    rims = [
        item
        for item in edges.circles
        if abs(item.circle[6] - HOLE_R) < 0.01
        and math.dist(item.circle[:2], hole) < 0.02
    ]
    if not rims:
        raise RuntimeError(
            f"no visible r={HOLE_R:g} rim at {hole} in the {edges.label!r} scan; "
            f"{len(edges.circles)} circles: "
            + "; ".join(
                f"({item.circle[0]:.3f}, {item.circle[1]:.3f}, "
                f"{item.circle[2]:.3f}) r={item.circle[6]:.3f}"
                for item in edges.circles
            )
        )
    return max(rims, key=lambda item: item.circle[2]).edge


# Section A-A: a removed cut across the left border into the sunk field at
# SECTION_Y (plate-local), from just outside the left edge to SECTION_X_END.
# At that height the cut crosses the raised border (x 0..3.16), the border
# pinstripe groove, the sunk field from x 3.61, a letter groove at x
# 7.65..8.11 and ends on that letter's counter, at field level (the offline
# test proves each station against the DXFs).  Both depths stand right of
# the profile, one above and one below it, each from the decorated face (the
# raised border top).
SECTION_Y = 35.0
SECTION_X_START = -1.5
SECTION_X_END = 8.6
SECTION_BORDER_X = 1.5
SECTION_FIELD_X = 5.5
SECTION_LETTER_X = 7.87
SECTION_TEXT_X = SECTION_CENTER[0] + 0.058
SECTION_PICKS: dict[str, dict[str, Any]] = {
    "sunk field depth": {
        "floor": (SECTION_FIELD_X, -FIELD_DEPTH),
        "expected_mm": FIELD_DEPTH,
        "text_xy": (SECTION_TEXT_X, SECTION_CENTER[1] + 0.013),
        "callout": FIELD_DEPTH_CALLOUT,
    },
    "engraving depth": {
        "floor": (SECTION_LETTER_X, -ENGRAVING_FLOOR_DEPTH),
        "expected_mm": ENGRAVING_FLOOR_DEPTH,
        "text_xy": (SECTION_TEXT_X, SECTION_CENTER[1] - 0.015),
        "callout": ENGRAVING_DEPTH_CALLOUT,
    },
}


def _mm_to_m(point: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(value / 1000.0 for value in point)


def _set_prefix(display: Any, prefix: str, *, label: str) -> None:
    """Write a native dimension prefix and read it back."""
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(1, prefix)  # swDimensionTextPrefix
    if str(display.GetText(1) or "") != prefix:
        raise RuntimeError(f"{label}: dimension prefix {prefix!r} did not persist")


def _set_dimension_prefixes(
    adapter: Any, annotations: list[Any], prefixes: dict[str, str]
) -> None:
    """Write a native prefix on named imported dimensions and read it back."""
    remaining = dict(prefixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        prefix = remaining.pop(name, None)
        if prefix is None:
            continue
        _set_prefix(annotation.GetSpecificAnnotation(), prefix, label=name)
    if remaining:
        raise RuntimeError(f"dimension prefixes not applied: {sorted(remaining)}")


def _set_reference_precision(display: Any, label: str) -> None:
    """Give a sheet-derived dimension its spec-authored decimal places."""
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    # -1: do-not-change for the dual and both tolerance places.
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != places:
        raise RuntimeError(f"{label}: prints {applied} decimal places, not {places}")


def _checked_dimension(
    adapter: Any,
    view: Any,
    *,
    label: str,
    points: tuple[tuple[float, float], tuple[float, float]],
    text_xy: tuple[float, float],
    expected_mm: float,
    orientation: str,
    center: bool = False,
    entities: tuple[Any, Any] | None = None,
) -> Any:
    """Add one sheet dimension and prove it measures ``expected_mm``."""
    display = add_edge_dimension(
        adapter,
        view,
        p0=points[0],
        p1=points[1],
        text_xy=text_xy,
        label=label,
        orientation=orientation,
        entities=entities,
    )
    if center:
        set_arc_endpoints_to_center(adapter, display, label=label)
    native = _early_bound(display, "IDisplayDimension")
    measured = (
        abs(float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue))
        * 1000.0
    )
    if abs(measured - expected_mm) > 1e-3:
        raise RuntimeError(
            f"{label}: measured {measured:g}, expected {expected_mm:g} mm"
        )
    _set_reference_precision(native, label)
    return native


def _front_dimensions(adapter: Any, front: Any) -> None:
    """Width, height and the far-edge hole stations, on the decorated face."""
    names = list(FRONT_PICKS)
    projected = model_points_in_view(
        adapter,
        front,
        [_mm_to_m(FRONT_PICKS[name][end]) for name in names for end in ("p0", "p1")],
        label="nameplate front picks",
    )
    for index, name in enumerate(names):
        pick = FRONT_PICKS[name]
        native = _checked_dimension(
            adapter,
            front,
            label=name,
            points=(projected[2 * index], projected[2 * index + 1]),
            text_xy=pick["text_xy"],
            expected_mm=pick["expected_mm"],
            orientation=pick["orientation"],
            center=pick["center"],
        )
        if name in STATION_DIMENSIONS:
            _set_prefix(native, STATION_PREFIX, label=name)


def _orient_section(adapter: Any, view: Any) -> None:
    """Cut faces only, plate X to the right and the decorated face (+Z) up."""
    view = _early_bound(view, "IView")
    section = _early_bound(view.GetSection(), "IDrSection")
    section.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="section A-A cut surface")
    if not section.GetDisplayOnlySurfaceCut() or not section.GetPartialSection():
        raise RuntimeError("section A-A must be a removed, cut-surface-only section")

    def axes() -> tuple[tuple[float, float], tuple[float, float]]:
        origin, east, up = model_points_in_view(
            adapter,
            view,
            [(0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.0, 0.001)],
            label="section A-A orientation",
        )
        return (
            (east[0] - origin[0], east[1] - origin[1]),
            (up[0] - origin[0], up[1] - origin[1]),
        )

    horizontal, vertical = axes()
    if horizontal[0] * vertical[1] - horizontal[1] * vertical[0] < 0.0:
        reversed_cut = not bool(section.GetReversedCutDirection())
        section.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section A-A cut direction")
        if bool(section.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section A-A cut direction did not persist")
        horizontal, vertical = axes()
    view.Angle = float(view.Angle) - math.atan2(horizontal[1], horizontal[0])
    rebuild_drawing(adapter, label="section A-A angle")
    horizontal, vertical = axes()
    if (
        horizontal[0] <= 0.0
        or abs(horizontal[1]) > 1e-8
        or vertical[1] <= 0.0
        or abs(vertical[0]) > 1e-8
    ):
        raise RuntimeError(
            f"section A-A orientation did not persist: {horizontal=}, {vertical=}"
        )


def _center_on_outline(adapter: Any, view: Any, target: tuple[float, float]) -> None:
    """Move ``view`` so its outline (its ink) is centred on ``target``."""
    view = _early_bound(view, "IView")
    for _attempt in range(3):
        outline = tuple(float(value) for value in view.GetOutline())
        center = ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0)
        if math.dist(center, target) < 0.0002:
            return
        position = tuple(float(value) for value in view.Position)
        moved = [position[axis] + target[axis] - center[axis] for axis in range(2)]
        if not view.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to position section A-A")
        rebuild_drawing(adapter, label="center section A-A")
    raise RuntimeError(f"section A-A outline did not settle on {target!r}")


def _section(adapter: Any, front: Any) -> Any:
    """Removed section A-A through the left border into the sunk field."""
    line = model_points_in_view(
        adapter,
        front,
        [
            _mm_to_m((SECTION_X_START, SECTION_Y, 0.0)),
            _mm_to_m((SECTION_X_END, SECTION_Y, 0.0)),
        ],
        label="section A-A line",
    )
    view = create_section_view(
        adapter,
        front,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CENTER,
        section_label=SECTION_LABEL,
        scale=SECTION_SCALE,
        partial=True,
        label="nameplate field and engraving depths",
    )
    view = _early_bound(view, "IView")
    view.UseParentScale = False
    view.ScaleRatio = double_array([float(value) for value in SECTION_SCALE])
    _orient_section(adapter, view)
    set_hidden_lines_removed(adapter, view)
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if bool(view.UseParentScale) or ratio != tuple(float(v) for v in SECTION_SCALE):
        raise RuntimeError(f"section A-A must keep its own {SECTION_SCALE} scale")
    _center_on_outline(adapter, view, SECTION_CENTER)
    return view


def _cut_face_line(
    edges: ViewEdges, *, x_mm: float, z_mm: float, label: str
) -> tuple[Any, tuple[float, float, float]]:
    """The visible cut-face line at height ``z_mm`` spanning ``x_mm``.

    A cut-surface-only section shows its cut face alone, so every visible line
    lies in the plane y = SECTION_Y; the decorated face, the field floor and
    an engraving floor are its horizontal lines at their own heights.
    """
    for item in edges.lines:
        start, end = item.line
        if max(abs(start[1] - SECTION_Y), abs(end[1] - SECTION_Y)) > 1e-4:
            continue
        if max(abs(start[2] - z_mm), abs(end[2] - z_mm)) > 1e-4:
            continue
        if min(start[0], end[0]) <= x_mm <= max(start[0], end[0]):
            return item.edge, (x_mm, SECTION_Y, z_mm)
    seen = sorted(
        (
            tuple(round(value, 3) for value in item.line[0]),
            tuple(round(value, 3) for value in item.line[1]),
        )
        for item in edges.lines
    )
    raise RuntimeError(f"{label}: no cut-face line at x={x_mm}, z={z_mm}; lines {seen}")


def _section_dimensions(adapter: Any, section: Any) -> None:
    """The sunk field's and the engraving floor's depths from the decorated face."""
    edges = scan_view_edges(section, label="section A-A")
    face_edge, face_point = _cut_face_line(
        edges, x_mm=SECTION_BORDER_X, z_mm=0.0, label="decorated face"
    )
    for label, pick in SECTION_PICKS.items():
        floor_edge, floor_point = _cut_face_line(
            edges, x_mm=pick["floor"][0], z_mm=pick["floor"][1], label=label
        )
        points = model_points_in_view(
            adapter, section, [_mm_to_m(face_point), _mm_to_m(floor_point)], label=label
        )
        native = _checked_dimension(
            adapter,
            section,
            label=label,
            points=(points[0], points[1]),
            text_xy=pick["text_xy"],
            expected_mm=pick["expected_mm"],
            orientation="vertical",
            entities=(face_edge, floor_edge),
        )
        annotation = _early_bound(native.GetAnnotation(), "IAnnotation")
        set_dimension_callouts(
            adapter,
            [annotation],
            {dimension_name(adapter, annotation): pick["callout"]},
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open nameplate source", await adapter.open_model(str(SOURCE)))
    properties = (
        "Number",
        "Revision",
        "Title",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel,
        properties,
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Nameplate Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "engraved brass nameplate; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # Places live on the part; the sheet only proves the import kept them.
    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="right",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, location="above")

    _front_dimensions(adapter, front)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    add_native_hole_callout(
        adapter,
        front,
        edge=_hole_rim_edge(scan_view_edges(front, label="front"), TOP_LEFT),
        callout_xy=HOLE_CALLOUT_XY,
        label="nameplate screw holes",
        process=HOLE_CALLOUT_PROCESS,
    )

    section = _section(adapter, front)
    _section_dimensions(adapter, section)

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    _telemetry.info("nameplate drawing views, dimensions and notes placed")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Nameplate Manufacturing Drawing",
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
