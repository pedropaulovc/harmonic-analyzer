r"""Create the curated machinist drawing for the green-painted top-frame casting.

The SLDPRT remains authoritative.  This recipe supplies only the ring's views,
profile dimensions, datum-controlled bores, and manufacturing notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The finished envelope is 446.2 x 276.2 x 47.3 over the corner bosses, with a
428.2 x 262.0 rectangular rail outside profile around the 359.8 x 186.0 clear
window, a 36.5-tall webbed ring band, four Ø52.2 corner bosses bored Ø25.5 to
clamp the columns, a Ø17 gooseneck bore through the east-rail hub, and an
integral crossbar carrying two Ø13.49 hanger-stud holes.  The side-facing
tapped holes (#8-32 side screws and keeper feet, 1/4-20 set screw) stay in
the notes.  The sheet runs 1:2; the front elevation drops to 1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_top_frame.py top-frame
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from top_frame_spec import GEOMETRIC_TOLERANCES_MM

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
    BAR_X0,
    BAR_X1,
    BORE_DIA,
    BOSS_ABOVE,
    BOSS_BELOW,
    BOSS_DIA,
    COLUMN_X,
    FRONT_COLUMN_Z,
    GOOSENECK_BORE_DIA,
    GOOSENECK_X,
    GOOSENECK_Z,
    OUTER_X,
    OUTER_Z,
    REAR_COLUMN_Z,
    RING_HEIGHT,
    STUD_HOLE_DIA,
    STUD_Z_REAR,
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

SHEET_SCALE = (1.0, 2.0)  # 1:2 whole sheet (446.2 mm envelope over the bosses)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 0.5

# Plan extents including the proud corner bosses (the straight rails alone
# stop at x +/-214.1 / z +/-131.0): x +/-223.1 -> 446.2 and z +/-138.1 ->
# 276.2 envelope; the boss stack is 47.3 tall around the 36.5 rail band.
PLAN_HALF_X = COLUMN_X + BOSS_DIA / 2.0  # 223.1
PLAN_HALF_Z = abs(FRONT_COLUMN_Z) + BOSS_DIA / 2.0  # 138.1
BOSS_BAND = RING_HEIGHT + BOSS_ABOVE + BOSS_BELOW  # 47.3
STUD_X = (BAR_X0 + BAR_X1) / 2.0  # -15.0 crossbar centreline

# Sheet layout (meters). The plan defines the profile, the bore pattern and
# the hanger-stud holes; the front elevation makes the 36.5 rail band, the
# 47.3 boss stack and datum A visible.
TOP_CENTER = (0.135, 0.175)
FRONT_CENTER = (0.345, 0.130)
DATUM_C_SYMBOL_XY = (0.210, 0.105)


# Per-view survivors of the marked-dimension import. Width/Depth are the straight
# rail outside profile, not the boss envelope; note 2 states both explicitly.
TOP_KEEP = {
    "Width": (
        TOP_CENTER[0],
        TOP_CENTER[1] + PLAN_HALF_Z * VIEW_SCALE / 1000.0 + 0.012,
    ),
    # Depth rides the LEFT flank: the right flank hosts the notes-B block
    # and the text landed mid-block (eye-pass 2026-08-03).
    "Depth": (
        TOP_CENTER[0] - PLAN_HALF_X * VIEW_SCALE / 1000.0 - 0.006,
        TOP_CENTER[1] - 0.030,
    ),
}


def _visible_plan_controls(
    adapter: Any, view: Any
) -> tuple[Any, Any, Any, Any, Any, Any]:
    """Return a column bore/OD pair, gooseneck bore, stud hole, and B/C edges."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    circles: list[tuple[float, float, float, Any]] = []
    lines: list[tuple[tuple[float, ...], Any]] = []
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1), default=()
            )
            or ()
        )
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
            raise RuntimeError(
                f"top-frame plan expected one visible {label}, got {len(matches)}"
            )
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
        if abs(values[2] - OUTER_Z / 1000.0) <= 2e-6 and abs(values[3]) >= 0.99
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
        # The rear hanger-stud hole carries the 2X position control; its rim
        # stays one top-face circle even where the hole nicks the junction.
        _circle(STUD_X, STUD_Z_REAR, STUD_HOLE_DIA, "hanger-stud hole"),
        datum_b[0],
        datum_c[0],
    )


def _visible_front_datum_a(adapter: Any, view: Any) -> Any:
    """Return the finished bottom-face edge in the front elevation."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    matches: list[Any] = []
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1), default=()
            )
            or ()
        )
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
            "Manufacturing Notes B",
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
            "Manufacturing Notes B",
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
            3: "top frame; webbed gray iron ring casting; column bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 4))
    for view in (top, front):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError(
            "failed to add ASME center marks to the ring bores and stud holes"
        )

    (
        column_bore,
        column_boss,
        gooseneck_bore,
        stud_hole,
        datum_b_edge,
        datum_c_edge,
    ) = _visible_plan_controls(adapter, top)
    datum_a_edge = _visible_front_datum_a(adapter, front)
    add_datum_feature(
        adapter,
        front,
        symbol_xy=(0.285, 0.125),
        datum="A",
        label="finished bottom-face datum",
        entity=datum_a_edge,
        shoulder=True,
    )
    add_datum_feature(
        adapter,
        top,
        symbol_xy=(0.020, 0.175),
        datum="B",
        label="east outer rail-face datum",
        entity=datum_b_edge,
        shoulder=True,
    )
    add_datum_feature(
        adapter,
        top,
        symbol_xy=DATUM_C_SYMBOL_XY,
        datum="C",
        label="rear outer rail-face datum",
        entity=datum_c_edge,
        shoulder=True,
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.175, 0.150),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["column-bore true position"],
        datums=("A", "B", "C"),
        diameter=True,
        quantity="4X COLUMN BORES",
        label="column-bore true position",
        entity=column_bore,
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.130, 0.220),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["column-boss true position"],
        datums=("A", "B", "C"),
        diameter=True,
        quantity="4X BOSS ODS",
        label="column-boss true position",
        entity=column_boss,
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.080, 0.165),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["gooseneck-bore true position"],
        datums=("A", "B", "C"),
        diameter=True,
        quantity="GOOSENECK BORE",
        label="gooseneck-bore true position",
        entity=gooseneck_bore,
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.205, 0.125),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["hanger-stud-hole true position"],
        datums=("A", "B", "C"),
        diameter=True,
        quantity="2X HANGER-STUD HOLES",
        label="hanger-stud-hole true position",
        entity=stud_hole,
    )

    # y=0.102 (physical 0.204): the finishing rework left note 1 one line
    # taller than the original block and note 5's tail printed on the
    # bottom border at y=0.100 -- one line-height up restores the margin.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.102)
    # NOTE anchors pass through IAnnotation::SetPosition, which this 2:1
    # sheet MULTIPLIES by the sheet scale -- physical = 2x the argument
    # (Inspection Notes (0.270, 0.255) render at (0.54, 0.51); the first
    # notes-B anchor (0.560, 0.300) landed off-sheet at (1.12, 0.60)).
    # (0.259, 0.089) -> physical (0.518, 0.178): the free band between
    # the FRONT VIEW label and the title block top edge.
    add_property_linked_note(adapter, "Manufacturing Notes B", 0.2585, 0.200)
    add_property_linked_note(adapter, "Inspection Notes", 0.2965, 0.260)
    add_property_linked_note(adapter, "Top View Note", 0.280, 0.2055)
    add_property_linked_note(adapter, "Front View Note", 0.300, 0.0785)

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
