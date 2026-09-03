r"""Create the curated machinist drawing for the rocker arm.

The SLDPRT remains authoritative.  This recipe supplies only the rocker-arm
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The strap is a long thin curved seesaw (~292 mm tip to tip, 16 mm deep, 2.5 mm
thick).  A projected side view of the curved strap is a messy band, so the
strap section is dimensioned on a 1:1 right end view and the print shows the
profile (front) plus a 1:4 isometric.  The sheet runs at 1:2.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): the
rod-pin hole is an X/Y coordinate pair from the pivot bore that the block
tolerance holds identically on all 20 rockers, so the sheet carries no datums,
no feature-control frames and no basic dimensions.  The pivot bore keeps its
roughness symbol -- the rocker swings on the pivot shaft in service.

The ends are view dimensions (machinist review 2026-09-02): each arc's end x
from the pivot (``TopRodX`` / ``BottomRodX``), the radial tip face
(``RodTipLen``) and a (REF) tip-to-tip overall; the two large radii stay in
the notes with their common centre on the pivot's vertical centreline.

Run with SolidWorks open::

    uv run python cad\scripts\draw_rocker_arm.py rocker-arm
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from rocker_arm_spec import (
    ARM_THICKNESS,
    PIVOT_HOLE_DIA,
    ROD_HOLE_X,
    ROD_HOLE_Y,
    ROD_TIP_X,
    ROD_TIP_Y,
    SURFACE_FINISHES,
    TOP_END_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["rocker_arm"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.5)

# Front-view model bbox: X symmetric about 0, Y from the centre bottom (0) up to
# the top-arc tip (TOP_END_Y).
_PIVOT_MID_Y = 8.0  # pivot bore centre = ArmDepth / 2
_ROD_HOLE_DIA = 1.994  # #47 drill
_BBOX_CY = TOP_END_Y / 2.0

FRONT_CENTER = (0.180, 0.175)
RIGHT_CENTER = (0.300, 0.165)
ISO_CENTER = (0.345, 0.205)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:2)."""
    return (
        FRONT_CENTER[0] + mx * _S / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


# The large concentric radii are carried in the manufacturing note: imported
# radius dimensions retain off-sheet centre witnesses even in shortened-radius
# mode.  Keeping them as notes avoids clipped geometry without losing values.
# The arc-end x dims run from the sketch origin (the strap's bottom centre, on
# the pivot's vertical C/L): the bottom-arc end below the arm (nearer than the
# rod-pin X it nearly equals), the top-arc end above; the radial tip face
# sits right of the rod tip.
FRONT_KEEP = {
    "PivotDia": (0.180, 0.120),
    "TopRodX": (0.225, 0.202),
    "BottomRodX": (0.215, 0.152),
    "RodTipLen": (0.264, 0.196),
}
NOTE_ONLY_DIMENSIONS = {"TopRadius", "BottomRadius"}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}
OVERALL_TEXT_XY = (0.180, 0.222)

# Process text beneath the pivot-bore diameter (Harvey #13: say ream); the
# reamed bore prints three decimals (its band rides the model dimension).
DIMENSION_CALLOUTS = {"PivotDia": "REAM THRU"}
DIMENSION_PRECISION = {"PivotDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm; tapered strap; seesaw pivot",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # Explicit per-view scale (an auto-scaled view shifts every coordinate pick).
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    # 1:1 right end view: the 2.50 x ~29 strap section -- gives the through
    # direction and carries the strap thickness.
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Tip-to-tip overall: the two tip corners (radial tip face meets the
    # tapered end face) are the strap's widest points.  REFERENCE -- the
    # arc-end x dims and the tip face already fix each end.
    overall = add_edge_dimension(
        adapter,
        front,
        p0=_sheet_xy(-ROD_TIP_X, ROD_TIP_Y),
        p1=_sheet_xy(ROD_TIP_X, ROD_TIP_Y),
        text_xy=OVERALL_TEXT_XY,
        label="overall length",
        orientation="horizontal",
        entity_types=("VERTEX", "VERTEX"),
    )
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall length",
    )

    # Rod-pin hole native callout (the #47 wizard hole near the +X tip), the
    # drill riding as its prefix.
    rod_rim = _sheet_xy(ROD_HOLE_X, ROD_HOLE_Y - _ROD_HOLE_DIA / 2.0)
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=rod_rim,
        callout_xy=(0.300, 0.128),
        label="rod-pin hole",
        process="#47 DRILL",
    )

    # Locate the rod-pin hole from the pivot bore with X and Y coordinate
    # components (one origin per view).  The rod-pin centre is NOT collinear
    # with the pivot (7.30 mm above its mid-height), so a single slant centre
    # distance would leave the angular component uninspectable.
    pivot_rim = _sheet_xy(0.0, _PIVOT_MID_Y - PIVOT_HOLE_DIA / 2.0)
    add_edge_dimension(
        adapter,
        front,
        p0=pivot_rim,
        p1=rod_rim,
        text_xy=(0.180, 0.138),
        label="rod-pin X location",
        orientation="horizontal",
    )
    add_edge_dimension(
        adapter,
        front,
        p0=pivot_rim,
        p1=rod_rim,
        text_xy=(0.267, 0.162),
        label="rod-pin Y location",
        orientation="vertical",
    )

    # Ra on the pivot bore at 6 o'clock: the rocker swings on the pivot shaft.
    pivot_bottom = _sheet_xy(0.0, _PIVOT_MID_Y - PIVOT_HOLE_DIA / 2.0)
    add_surface_finish(
        adapter,
        front,
        edge_xy=pivot_bottom,
        symbol_xy=(pivot_bottom[0] + 0.010, pivot_bottom[1] - 0.020),
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
    )
    # Strap thickness (2.50) across the two broad faces on the right end view.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - ARM_THICKNESS / 2000.0, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + ARM_THICKNESS / 2000.0, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.024),
        label="strap thickness",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.082)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.150)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Manufacturing Drawing",
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
