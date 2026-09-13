r"""Create the curated machinist drawing for the two-plate harmonic base.

The SLDPRT remains authoritative.  This recipe supplies only the base's views,
overall footprint dimensions, the mounting-hole table, and manufacturing notes; every
shared sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The base is machined from one-piece gray-iron stock: the legacy lower flange and
upper pad retain their front edges and extend 35.415 mm rearward, with four
counterbored lag-screw mounting holes and nine assembly-drilled hardware seats.
The plate is 457 mm long, so the whole sheet runs 1:4; the front elevation is
also 1:4 and the pictorial isometric is 1:10.

Run with SolidWorks open::

    uv run python cad\scripts\draw_harmonic_base.py harmonic-base
"""

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
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    insert_hole_table,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_harmonic_base import (
    BASE_CROSS_TAP_DRILL_DIA,
    BLOCK_SCREW_HOLE_DIA,
    BLOCK_SCREW_XZ,
    COLUMN_X,
    FOOT_SCREW_HOLE_DIA,
    FOOT_SCREW_XZ,
    HOLD_DOWN_TAP_DRILL_DIA,
    HOLE_XZ,
    LOCK_KNOB_XZ,
    LOCK_SCREW_HOLE_DIA,
    NAMEPLATE_SCREW_HOLE_DIA,
    NAMEPLATE_SCREW_XZ,
    PIVOT_SCREW_HOLE_DIA,
    PIVOT_SCREW_XZ,
    STOP_SCREW_HOLE_DIA,
    STOP_SCREW_XZ,
)
from harmonic_base_spec import (
    BOTTOM_FRONT_Z,
    BOTTOM_LENGTH,
    BOTTOM_REAR_Z,
    BOTTOM_WIDTH,
)
from frame_attachment_spec import (
    BASE_SCREW_SEAT_Z,
    BASE_SCREW_Y,
    COLUMN_SOCKET_DIAMETER,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["harmonic_base"]
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

SHEET_SCALE = (1.0, 4.0)  # 1:4 whole sheet keeps this data-dense print legible
PLAN_SCALE = SHEET_SCALE
VIEW_SCALE = PLAN_SCALE[0] / PLAN_SCALE[1]

if abs((BOTTOM_REAR_Z - BOTTOM_FRONT_Z) - BOTTOM_WIDTH) > 1e-12:
    raise AssertionError("base drawing extents disagree with the overall depth")

# Sheet layout (meters). The full-height native hole table owns the left
# column, where it may extend below the title-block top without entering that
# right-side keep-out. Views, controls, and notes occupy the remaining field.
TOP_CENTER = (0.230, 0.205)
SIDE_CENTER = (0.230, 0.145)
SECTION_CENTER = (0.360, 0.150)
ISO_SCALE = (1, 10)
ISO_CENTER = (0.350, 0.240)
SIDE_NOTE_XY = (0.170, 0.128)
SECTION_NOTE_XY = (0.326, 0.126)
ISO_NOTE_XY = (0.305, 0.212)

# Per-view survivors of the native marked-dimension import. Socket locations
# and diameter live in the plan; hidden socket/tap depth geometry lives only
# in section A-A.
TOP_KEEP = {
    "BottomLen": (
        TOP_CENTER[0],
        TOP_CENTER[1]
        + max(abs(BOTTOM_FRONT_Z), abs(BOTTOM_REAR_Z)) * VIEW_SCALE / 1000.0
        + 0.008,
    ),
    "BottomWid": (
        TOP_CENTER[0] + BOTTOM_LENGTH * VIEW_SCALE / 2000.0 + 0.017,
        TOP_CENTER[1],
    ),
    "Socket0X": (TOP_CENTER[0] - 0.050, TOP_CENTER[1] - 0.050),
    "Socket0Z": (TOP_CENTER[0] - 0.085, TOP_CENTER[1]),
    "SocketDia": (TOP_CENTER[0] - 0.058, TOP_CENTER[1] + 0.043),
}
SECTION_KEEP = {
    "SocketDepth": (SECTION_CENTER[0] - 0.040, SECTION_CENTER[1]),
    "SpotFaceDia": (SECTION_CENTER[0] + 0.040, SECTION_CENTER[1] + 0.010),
    "SpotFaceDepth": (SECTION_CENTER[0] + 0.038, SECTION_CENTER[1] - 0.010),
}
DIMENSION_CALLOUTS = {
    "SocketDia": "4X COLUMN SOCKET; MATCH FIT MHA-083",
    "SpotFaceDia": "4X SPOTFACE",
}

# Hole-table origin corner (the plate's lower-left plan corner) plus every
# visible top-seat rim, all in sheet meters. Native callouts read each hole's
# size, end condition, thread depth, and station from the authoritative part.
_DATUM_XY = (
    TOP_CENTER[0] - BOTTOM_LENGTH * VIEW_SCALE / 2000.0,
    TOP_CENTER[1] - BOTTOM_REAR_Z * VIEW_SCALE / 1000.0,
)
HOLE_TABLE_ANCHOR = (0.015, 0.265)


def _plan_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point for a plan station (machine X, Z in mm), top view."""
    return (
        TOP_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        TOP_CENTER[1] - z_mm * VIEW_SCALE / 1000.0,
    )


def _hole_rim(x_mm: float, z_mm: float, diameter_mm: float) -> tuple[float, float]:
    """Sheet pick on a plan-view hole rim, offset in machine +X."""
    return _plan_xy(x_mm + diameter_mm / 2.0, z_mm)


ALL_HOLES = (
    *((x, z, HOLD_DOWN_TAP_DRILL_DIA) for x, z in HOLE_XZ),
    (*PIVOT_SCREW_XZ, PIVOT_SCREW_HOLE_DIA),
    (*STOP_SCREW_XZ, STOP_SCREW_HOLE_DIA),
    *((x, z, BLOCK_SCREW_HOLE_DIA) for x, z in BLOCK_SCREW_XZ),
    *((x, z, FOOT_SCREW_HOLE_DIA) for x, z in FOOT_SCREW_XZ),
    # Keep later seat groups after the existing FCF anchors.
    *((x, z, NAMEPLATE_SCREW_HOLE_DIA) for x, z in NAMEPLATE_SCREW_XZ),
    (*LOCK_KNOB_XZ, LOCK_SCREW_HOLE_DIA),
)


def _visible_hole_table_entities(
    adapter: Any, view: Any
) -> tuple[tuple[Any, ...], Any, Any]:
    """Return hole rims and the B/C datum edges in the top view.

    The plan corners are broken (CornerFillets R3.18), so no B-C corner
    vertex exists to anchor the hole table; the caller passes the two datum
    edges as ``datum_axes`` and the table origin lands on their VIRTUAL
    intersection -- the theoretical sharp corner, keeping every LOC value
    measured from B-C exactly as note 3 states.
    """
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    circles: list[tuple[float, float, float, Any]] = []
    lines: list[tuple[tuple[float, ...], Any]] = []

    for component in components:
        visible_edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(
                    c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
        for edge in visible_edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve.IsCircle():
                parameters = tuple(float(value) for value in curve.CircleParams)
                circles.append((parameters[0], parameters[2], parameters[6], edge))
                continue
            if curve.IsLine():
                parameters = tuple(float(value) for value in curve.LineParams)
                lines.append((parameters, edge))

    selected_edges: list[Any] = []
    used: set[int] = set()
    for x_mm, z_mm, diameter_mm in ALL_HOLES:
        expected = (
            x_mm / 1000.0,
            z_mm / 1000.0,
            diameter_mm / 2000.0,
        )
        candidates = sorted(
            (
                abs(x - expected[0]) + abs(z - expected[1]) + abs(radius - expected[2]),
                index,
                edge,
            )
            for index, (x, z, radius, edge) in enumerate(circles)
            if index not in used
        )
        if not candidates or candidates[0][0] > 5e-5:
            nearest = candidates[0][0] if candidates else None
            raise RuntimeError(
                "harmonic-base plan has no visible circular rim for hole "
                f"({x_mm:g}, {z_mm:g}) diameter {diameter_mm:g} mm; "
                f"nearest error={nearest!r} m"
            )
        _, index, edge = candidates[0]
        used.add(index)
        selected_edges.append(edge)

    datum_b_candidates = [
        edge
        for parameters, edge in lines
        if abs(parameters[2] - BOTTOM_REAR_Z / 1000.0) <= 2e-6
        and abs(parameters[3]) >= 0.99
    ]
    datum_c_candidates = [
        edge
        for parameters, edge in lines
        if abs(parameters[0] + BOTTOM_LENGTH / 2000.0) <= 2e-6
        and abs(parameters[5]) >= 0.99
    ]
    if not datum_b_candidates or not datum_c_candidates:
        raise RuntimeError(
            "harmonic-base plan is missing a visible outer B/C datum edge"
        )

    return (
        tuple(selected_edges),
        datum_b_candidates[0],
        datum_c_candidates[0],
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open harmonic-base source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Manufacturing Notes B",
            "Quantity",
            "Manufacturing Notes",
            "Side View Note",
            "Section View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes B",
            "Manufacturing Notes",
            "Side View Note",
            "Section View Note",
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
            0: "Harmonic Base Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "harmonic base; stepped; gray iron stock",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set end-only section cutting line")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
        raise RuntimeError("section cutting-line style did not persist")

    # Explicit per-view scale prevents coordinate-based picks drifting.
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=PLAN_SCALE)
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=(1, 4))
    section_line_x = _plan_xy(COLUMN_X, 0.0)[0]
    section = create_section_view(
        adapter,
        top,
        line_start=(section_line_x, TOP_CENTER[1] - 0.040),
        line_end=(section_line_x, TOP_CENTER[1] + 0.040),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 4),
        label="base column-socket section",
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (top, side):
        set_hidden_lines_visible(adapter, view)
    for view in (section, iso):
        set_hidden_lines_removed(adapter, view)

    top_dimensions = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    section_dimensions = curate_view_dimensions(
        adapter, section, keep=SECTION_KEEP, view_label="section A-A"
    )
    set_dimension_callouts(
        adapter, [*top_dimensions, *section_dimensions], DIMENSION_CALLOUTS
    )
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the base hole pattern")

    hole_entities, datum_b_edge, datum_c_edge = _visible_hole_table_entities(
        adapter, top
    )

    # One complete hole table for the top-side mounting seats. Section A-A
    # separately defines the horizontal column-retention taps.
    insert_hole_table(
        adapter,
        top,
        datum_xy=_DATUM_XY,
        hole_points=tuple(_hole_rim(x, z, diameter) for x, z, diameter in ALL_HOLES),
        datum_axes=(datum_b_edge, datum_c_edge),
        hole_entities=hole_entities,
        # Every printed LOC is re-derived from the shared stations: X from the
        # C face (x = -L/2), Y from the B face (z = +W/2).
        expected_locations_mm=tuple(
            (x + BOTTOM_LENGTH / 2.0, BOTTOM_WIDTH / 2.0 - z)
            for x, z, _diameter in ALL_HOLES
        ),
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="harmonic-base mounting",
    )
    tap_edge = model_point_in_view(
        adapter,
        section,
        (
            COLUMN_X / 1000.0,
            (BASE_SCREW_Y + BASE_CROSS_TAP_DRILL_DIA / 2.0) / 1000.0,
            (BASE_SCREW_SEAT_Z - COLUMN_SOCKET_DIAMETER) / 1000.0,
        ),
        label="base cross-tap longitudinal edge",
    )
    add_native_hole_callout(
        adapter,
        section,
        edge_xy=tap_edge,
        callout_xy=(SECTION_CENTER[0] + 0.050, SECTION_CENTER[1] - 0.025),
        label="4X base column-retention bottoming taps",
    )

    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.170, 0.115, char_height=0.002
    )
    add_property_linked_note(
        adapter, "Manufacturing Notes B", 0.305, 0.115, char_height=0.002
    )
    add_property_linked_note(adapter, "Side View Note", *SIDE_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    add_property_linked_note(adapter, "Section View Note", *SECTION_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Harmonic Base Manufacturing Drawing",
        scale=SHEET_SCALE,
        redundant_note_substrings=("Tapped Hole",),
        # Seven top-side tapped groups plus the sectioned cross-tap group.
        expected_redundant_notes=8,
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
