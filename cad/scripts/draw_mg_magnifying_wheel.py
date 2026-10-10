r"""Create the curated machinist drawing for the magnifying wheel.

A Ø100 cast-iron spider: six tapered spokes, a grooved rim, a Ø25 boss with
the Ø14.5 drum spigot, a reamed axle bore and two wire-tie holes.  The wheel
axis is local +Z, so the FRONT view is the face (rim, spokes, fillets, bore,
ties) and the RIGHT view is the side elevation carrying the hub profile, the
groove and the axial widths.  Every size rides the part's marked dimensions;
only the rim's axial width is added on the sheet.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_wheel.py mg-magnifying-wheel
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _check import check
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from mg_magnifying_wheel_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    RIM_AXIAL,
    RIM_OUTER_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["mg_magnifying_wheel"]
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
FRONT_CENTER = (0.125, 0.150)
RIGHT_CENTER = (0.255, 0.150)
ISO_CENTER = (0.350, 0.150)

_RIM_R = RIM_OUTER_DIA * SHEET_SCALE[0] / 2000.0

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

# Face view: text in the windows between the spokes (spokes at 0, 60, ... deg).
FRONT_KEEP = {
    "RimOuterDiaDim": (
        FRONT_CENTER[0] - _RIM_R - 0.028,
        FRONT_CENTER[1] + _RIM_R + 0.006,
    ),
    "RimInnerDiaDim": (FRONT_CENTER[0] + 0.030, FRONT_CENTER[1] + _RIM_R + 0.012),
    "BoreDiaDim": (FRONT_CENTER[0] + 0.024, FRONT_CENTER[1] + 0.014),
    "HubFilletR": (FRONT_CENTER[0] - 0.024, FRONT_CENTER[1] + 0.014),
    "RimFilletR": (FRONT_CENTER[0] - 0.020, FRONT_CENTER[1] + 0.036),
    "SpokeRootWidth": (FRONT_CENTER[0] + 0.020, FRONT_CENTER[1] - 0.012),
    "SpokeTipWidth": (FRONT_CENTER[0] + 0.040, FRONT_CENTER[1] - 0.014),
    "Tie1Y": (FRONT_CENTER[0] - 0.008, FRONT_CENTER[1] - 0.022),
    "Tie1HoleDia": (FRONT_CENTER[0] + 0.008, FRONT_CENTER[1] - 0.034),
    "Tie2Angle": (FRONT_CENTER[0] - 0.030, FRONT_CENTER[1] - 0.014),
    "Tie2HoleDia": (FRONT_CENTER[0] - 0.062, FRONT_CENTER[1] - 0.050),
}
# Side view: sheet right = model -Z (the pen side, where the spigot stands).
RIGHT_KEEP = {
    "HubDia": (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1] + 0.020),
    "SpigotDia": (RIGHT_CENTER[0] + 0.032, RIGHT_CENTER[1] + 0.016),
    "HubBackZ": (RIGHT_CENTER[0] - 0.012, RIGHT_CENTER[1] - 0.060),
    "SpigotLength": (RIGHT_CENTER[0] + 0.010, RIGHT_CENTER[1] - 0.060),
    "HubLength": (RIGHT_CENTER[0] + 0.003, RIGHT_CENTER[1] - 0.070),
    "SpokeAxial": (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1] - 0.020),
    "GrooveR": (RIGHT_CENTER[0] - 0.025, RIGHT_CENTER[1] + 0.060),
    "GrooveBottomDia": (RIGHT_CENTER[0] + 0.040, RIGHT_CENTER[1] + 0.035),
    # The rim-bore round, top left, between the groove and the hub.
    "CastRoundR": (RIGHT_CENTER[0] - 0.028, RIGHT_CENTER[1] + 0.038),
}
DIMENSION_CALLOUTS = {
    "BoreDiaDim": "THRU - REAM",
    "SpokeRootWidth": "6X ROOT",
    "SpokeTipWidth": "6X TIP",
    "HubFilletR": "12X",
    "RimFilletR": "12X",
    "CastRoundR": "2X RIM BORE EDGES",
    "Tie1HoleDia": "THRU - TIE 1",
    "Tie2HoleDia": "TIE 2, GROOVE TO RIM BORE",
}

RIGHT_HALF_RIM = RIM_AXIAL * SHEET_SCALE[0] / 2000.0


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-wheel source", await adapter.open_model(str(SOURCE)))
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
            "Section View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
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
            0: "Magnifying Wheel Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying wheel; cast-iron spider; six spokes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (iso,):
        set_hidden_lines_removed(adapter, view)
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

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
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to wheel bore")

    # The rim's axial width across the side view, up at the rim.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_RIM, RIGHT_CENTER[1] + _RIM_R),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_RIM, RIGHT_CENTER[1] + _RIM_R),
        text_xy=(RIGHT_CENTER[0] + 0.028, RIGHT_CENTER[1] + _RIM_R),
        label="rim axial width",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(
        adapter, "Section View Note", RIGHT_CENTER[0] - 0.022, 0.075
    )
    add_property_linked_note(adapter, "Isometric View Note", 0.320, 0.085)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Wheel Manufacturing Drawing",
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
