r"""Create the manufacturing drawing for the magnifying-wheel drum (MHA-MG-010).

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_wheel_drum.py mg-wheel-drum
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
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from draw_dt_cone_pivot_post_tl_cap_jaw_button import _move_dimension
from mg_wheel_drum_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    DRUM_BORE,
    DRUM_LEN,
    SPIGOT_LIMITS,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["mg_wheel_drum"]
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

# A Ø18.9 x 9 ring: 2:1 keeps the press-fit bore's three places legible.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
FRONT_CENTER = (0.110, 0.180)
RIGHT_CENTER = (0.200, 0.180)
ISO_CENTER = (0.320, 0.180)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

# Both diameters import on the face view, where every diameter line runs
# through the centre: two would cross there. The bore keeps the face view;
# the O.D. is a donor there and moves onto the side view, right of the ring.
FRONT_KEEP = {
    "DrumOd": (0.060, 0.130),
    "DrumBore": (0.150, 0.230),
}
RIGHT_KEEP = {
    "DrumLen": (0.200, 0.215),
}
OD_ON_SIDE = (RIGHT_CENTER[0] + DRUM_LEN / 2.0 * _S + 0.030, RIGHT_CENTER[1])
NOTES_XY = (0.020, 0.085)
# The press fit prints on the bore's own callout, the spigot's limits read
# from the wheel's spec (policy rule 6).
DIMENSION_CALLOUTS = {
    "DrumBore": (
        "REAM THRU\nPRESS ON MG-MAGNIFYING-WHEEL\n"
        f"SPIGOT <MOD-DIAM>{SPIGOT_LIMITS[0]:.3f}-{SPIGOT_LIMITS[1]:.3f}"
    ),
}
# The bore's seat finish (policy rule 5) lands on the bore up-left, clear of
# the Ø line that runs up-right to its callout and through the centre to the
# lower-left rim; the symbol stands outside the O.D. on the same bearing
# (sheet metres from the landing).  Model x and y are the face view's.
_FINISH_LANDING_MODEL = (
    -DRUM_BORE / 2000.0 * 0.5**0.5,
    DRUM_BORE / 2000.0 * 0.5**0.5,
    0.0,
)
_FINISH_SYMBOL_OFFSET = (-0.012, 0.012)
FINISH_CHAR_HEIGHT = 0.0025


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-drum source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Wheel Drum Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying wheel drum; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    od_donors = [a for a in front_annotations if dimension_name(adapter, a) == "DrumOd"]
    if len(od_donors) != 1:
        raise RuntimeError("expected one drum O.D. donor dimension")
    moved_od = _move_dimension(
        adapter, od_donors[0], right, OD_ON_SIDE, source_view=front
    )
    annotations = [
        *(a for a in front_annotations if dimension_name(adapter, a) != "DrumOd"),
        *right_annotations,
        moved_od,
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # The template centre-marks the bore as the view is placed; run 11's
    # explicit AutoInsertCenterMarks2 printed a second, identical mark (the
    # layout audit's duplicate-annotation finding).
    landing = model_point_in_view(
        adapter, front, _FINISH_LANDING_MODEL, label="drum bore finish landing"
    )
    add_surface_finish(
        adapter,
        front,
        edge_entity=visible_circle_edge(adapter, front, DRUM_BORE),
        symbol_xy=(
            landing[0] + _FINISH_SYMBOL_OFFSET[0],
            landing[1] + _FINISH_SYMBOL_OFFSET[1],
        ),
        control=surface_finish_by_key(SURFACE_FINISHES, "mg_drum_bore"),
        label="drum bore finish",
        leader_attach_xy=landing,
        char_height=FINISH_CHAR_HEIGHT,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Wheel Drum Manufacturing Drawing",
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
