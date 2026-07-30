r"""Create the curated machinist drawing for the gray-iron top-frame ring.

The SLDPRT remains authoritative.  This recipe supplies only the ring's views,
profile dimensions, datum-controlled bores, and manufacturing notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The finished envelope is 442 x 307.415 x 41 with a 416 x 281.415 rectangular rail
outside profile, four Ø48 corner bosses bored Ø25.5 to clamp the columns, and
a Ø17 gooseneck bore through one rail. The sheet runs 1:2; the front elevation
drops to 1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_top_frame.py top-frame
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_top_frame import (
    BORE_DIA,
    BOSS_DIA,
    COLUMN_X,
    FRONT_COLUMN_Z,
    GOOSENECK_BORE_DIA,
    GOOSENECK_X,
    GOOSENECK_Z,
    OUTER_FRONT_Z,
    OUTER_REAR_Z,
    OUTER_X,
    REAR_COLUMN_Z,
    RING_HEIGHT,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["top_frame"]
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

SHEET_SCALE = (1.0, 2.0)   # 1:2 whole sheet (442 mm finished envelope)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 0.5

# Sheet layout (meters). The plan defines the profile and bore pattern; the
# front elevation makes the full 41 mm rail/boss thickness and datum A visible.
TOP_CENTER = (0.135, 0.175)
FRONT_CENTER = (0.345, 0.150)
DATUM_C_SYMBOL_XY = (0.210, 0.105)


# Per-view survivors of the marked-dimension import. Width/Depth are the straight
# rail outside profile, not the boss envelope; note 2 states both explicitly.
TOP_KEEP = {
    "Width": (
        TOP_CENTER[0],
        TOP_CENTER[1]
        + max(abs(OUTER_FRONT_Z), abs(OUTER_REAR_Z)) * VIEW_SCALE / 1000.0
        + 0.012,
    ),
    "Depth": (TOP_CENTER[0] + OUTER_X * VIEW_SCALE / 1000.0 + 0.016, TOP_CENTER[1]),
}


def _visible_plan_controls(adapter: Any, view: Any) -> tuple[Any, Any, Any, Any, Any]:
    """Return one column bore/OD pair, gooseneck bore, and B/C rail edges."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    circles: list[tuple[float, float, float, Any]] = []
    lines: list[tuple[tuple[float, ...], Any]] = []
    for component in components:
        edges = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 1), default=()
        ) or ()
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve.IsCircle():
                values = tuple(float(value) for value in curve.CircleParams)
                circles.append((values[0], values[2], values[6], edge))
                continue
            if curve.IsLine():
                lines.append((tuple(float(value) for value in curve.LineParams), edge))

    def _circle(
        x_mm: float,
        z_mm: float,
        diameter_mm: float,
        label: str,
        *,
        allow_coincident: bool = False,
    ) -> Any:
        matches = [
            edge
            for x, z, radius, edge in circles
            if abs(x - x_mm / 1000.0)
            + abs(z - z_mm / 1000.0)
            + abs(radius - diameter_mm / 2000.0)
            <= 5e-5
        ]
        if not matches or (len(matches) != 1 and not allow_coincident):
            raise RuntimeError(f"top-frame plan expected one visible {label}, got {len(matches)}")
        # A boss projects both coincident end rims in the plan view. They are
        # the same cylindrical feature at the same model coordinates, so either
        # visible rim is a valid annotation attachment.
        return matches[0]

    datum_b = [
        edge
        for values, edge in lines
        if abs(values[0] + OUTER_X / 1000.0) <= 2e-6 and abs(values[5]) >= 0.99
    ]
    datum_c = [
        edge
        for values, edge in lines
        if abs(values[2] - OUTER_REAR_Z / 1000.0) <= 2e-6
        and abs(values[3]) >= 0.99
    ]
    if not datum_b or not datum_c:
        raise RuntimeError("top-frame plan is missing the B/C outer rail datum edges")
    return (
        _circle(-COLUMN_X, REAR_COLUMN_Z, BORE_DIA, "column bore"),
        # Use the upper-left representative for the 4X boss control so its
        # leader stays separate from the lower-left bore and gooseneck controls.
        _circle(
            -COLUMN_X,
            FRONT_COLUMN_Z,
            BOSS_DIA,
            "column boss OD",
            allow_coincident=True,
        ),
        _circle(GOOSENECK_X, GOOSENECK_Z, GOOSENECK_BORE_DIA, "gooseneck bore"),
        datum_b[0],
        datum_c[0],
    )


def _visible_front_datum_a(adapter: Any, view: Any) -> Any:
    """Return the finished bottom-face edge in the front elevation."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    matches: list[Any] = []
    for component in components:
        edges = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 1), default=()
        ) or ()
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            values = tuple(float(value) for value in curve.LineParams)
            if abs(values[1] + RING_HEIGHT / 2000.0) <= 2e-6 and abs(values[3]) >= 0.99:
                matches.append(edge)
    if not matches:
        raise RuntimeError("top-frame front view has no visible bottom datum-A edge")
    return matches[0]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open top-frame source", await adapter.open_model(str(SOURCE)))
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
            "Inspection Notes",
            "Top View Note",
            "Front View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Inspection Notes",
            "Top View Note",
            "Front View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Top Frame Ring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "top frame; machined gray iron ring; column bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 4))
    for view in (top, front):
        set_hidden_lines_removed(adapter, view)

    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the ring bores")

    (
        column_bore,
        column_boss,
        gooseneck_bore,
        datum_b_edge,
        datum_c_edge,
    ) = _visible_plan_controls(adapter, top)
    datum_a_edge = _visible_front_datum_a(adapter, front)
    add_datum_feature(
        adapter, front, symbol_xy=(0.285, 0.125), datum="A",
        label="finished bottom-face datum", entity=datum_a_edge, shoulder=True,
    )
    add_datum_feature(
        adapter, top, symbol_xy=(0.020, 0.175), datum="B",
        label="left outer rail-face datum", entity=datum_b_edge, shoulder=True,
    )
    add_datum_feature(
        adapter, top, symbol_xy=DATUM_C_SYMBOL_XY, datum="C",
        label="lower outer rail-face datum", entity=datum_c_edge, shoulder=True,
    )
    add_feature_control_frame(
        adapter, top, frame_xy=(0.175, 0.150), characteristic="position",
        tolerance="0.20", datums=("A", "B", "C"), diameter=True,
        quantity="4X COLUMN BORES", label="column-bore true position",
        entity=column_bore,
    )
    add_feature_control_frame(
        adapter, top, frame_xy=(0.130, 0.220), characteristic="position",
        tolerance="0.20", datums=("A", "B", "C"), diameter=True,
        quantity="4X BOSS ODS", label="column-boss true position",
        entity=column_boss,
    )
    add_feature_control_frame(
        adapter, top, frame_xy=(0.080, 0.165), characteristic="position",
        tolerance="0.20", datums=("A", "B", "C"), diameter=True,
        quantity="GOOSENECK BORE", label="gooseneck-bore true position",
        entity=gooseneck_bore,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.100)
    add_property_linked_note(adapter, "Inspection Notes", 0.270, 0.255)
    add_property_linked_note(adapter, "Top View Note", 0.280, 0.200)
    add_property_linked_note(adapter, "Front View Note", 0.300, 0.095)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Frame Ring Manufacturing Drawing",
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
