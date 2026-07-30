r"""Create the curated machinist drawing for the transgear stud."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    PmiDrawingPlacement,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    project_part_pmi,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from transgear_stub_spec import (
    BASE_DIA,
    BASE_LEN,
    COLLAR_DIA as COLLAR_DIA,
    COLLAR_LEN,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    SEAT_DIA,
    SEAT_LEN,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["transgear_stub"]
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

# A 26.9 mm stud reads at 4:1 everywhere, so the sheet scale IS the view
# scale -- no per-view blow-up note needed.
SHEET_SCALE = (4.0, 1.0)
VIEW_MM = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm in the views
TOTAL_LEN = BASE_LEN + SEAT_LEN + COLLAR_LEN

FRONT_CENTER = (0.115, 0.185)
END_CENTER = (0.115, 0.068)  # base-end view, third-angle: below the front
ISO_CENTER = (0.320, 0.190)


def _fx(x_mm: float) -> float:
    """Front-view sheet x for a model radial offset (mm from the axis)."""
    return FRONT_CENTER[0] + x_mm * VIEW_MM


def _fy(y_mm: float) -> float:
    """Front-view sheet y for a model axial station (mm from the base end)."""
    return FRONT_CENTER[1] + (y_mm - TOTAL_LEN / 2.0) * VIEW_MM


# Diameters stack on the left, land lengths chain on the right; the callout
# texts sit clear of each other's extension lines (steps at different y).
#
# The chain runs at x=0.176 rather than 0.162: the Ra symbol beside the gear
# seat throws its text out to x~0.171 (the text starts ~13 mm right of the
# anchor and runs ~26 mm), and at 0.162 the chain's dimension line printed
# straight through "Ra 1.6". The seat silhouette at x=0.125 leaves too little
# room to walk the symbol left instead, so the chain moves right; ~7 mm of gap.
#
# CAVEAT (measured 2026-07-16): that "~7 mm of gap" is TEXT-only, and the text is
# not the symbol's rightmost ink. Verified against the render: the text does end
# at x=0.1703 (so 5.6 mm to the chain line, which sits at x=0.1759..0.1760), but
# the Ra symbol's horizontal ARM extends 6.1 mm PAST its own text, to x=0.1764 --
# it crosses the chain line by ~0.5 mm. Left as-is: a 0.5 mm hairline does not
# justify a rebuild. Recorded so the next reader does not "confirm" this clearance
# by measuring the text and miss the arm. Do not treat text extent as symbol
# extent for ANY Ra placement -- and note text is not a COM primitive, so
# GetLineAtIndex will not show it to you either; only the render will.
_LENGTH_CHAIN_X = 0.176
FRONT_KEEP = {
    "BaseDia": (0.052, _fy(BASE_LEN / 2.0)),
    "SeatDia": (0.052, _fy(BASE_LEN + 3.0)),
    "CollarDia": (0.052, _fy(TOTAL_LEN - COLLAR_LEN / 2.0)),
    "BaseLength": (_LENGTH_CHAIN_X, _fy(BASE_LEN / 2.0)),
    "SeatLength": (_LENGTH_CHAIN_X, _fy(BASE_LEN + SEAT_LEN / 2.0)),
    "CollarLength": (_LENGTH_CHAIN_X, _fy(TOTAL_LEN - COLLAR_LEN / 2.0)),
}
# No callout overrides: both diameter bands are toleranced on the MODEL
# dimension by build_transgear_stub (transgear_stub_spec.BASE_DIA_BAND /
# SEAT_DIA_BAND), so SolidWorks renders the limits natively.
DIMENSION_CALLOUTS: dict[str, str] = {}
# The base is a 3/8" conversion: display 9.525, not a false-precision 9.53.
DIMENSION_PRECISION = {"BaseDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-stub source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Stud Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear stud; stepped gear stud; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    for view in (front, end, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    # SolidWorks classifies the solid circular end silhouettes under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to stud end view")

    base_circle = (END_CENTER[0] + BASE_DIA / 2.0 * VIEW_MM, END_CENTER[1])
    seat_left = _fx(-SEAT_DIA / 2.0)

    # GD&T is model PMI (transgear_stub_spec.PART_DATUMS/GEOMETRIC_CONTROLS,
    # authored by build_transgear_stub) — project it and place it where the
    # hand-authored symbols used to sit. Which VIEW receives each annotation
    # depends on its attachment (a datum tag only lands in a view aligned
    # with its face), and the projection fails loud on any mismatch.
    project_part_pmi(
        adapter,
        placements={
            "datum:A": PmiDrawingPlacement(
                view=end,
                position=(END_CENTER[0] + 0.040, END_CENTER[1] - 0.018),
                attachment_xy=base_circle,
                position_tolerance_m=0.003,
            ),
            "seat_cylindricity": PmiDrawingPlacement(
                view=front,
                position=(0.038, _fy(BASE_LEN + 9.0)),
                attachment_xy=(seat_left, _fy(BASE_LEN + 9.0)),
                attachment_type="SILHOUETTE",
            ),
            "seat_runout": PmiDrawingPlacement(
                view=front,
                position=(0.038, _fy(BASE_LEN + 12.0)),
                attachment_xy=(seat_left, _fy(BASE_LEN + 12.0)),
                attachment_type="SILHOUETTE",
            ),
        },
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        label="transgear stud PMI",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(_fx(SEAT_DIA / 2.0), _fy(BASE_LEN + SEAT_LEN / 2.0)),
        symbol_xy=(_fx(SEAT_DIA / 2.0) + 0.008, _fy(BASE_LEN + SEAT_LEN / 2.0) + 0.004),
        control=surface_finish_by_key(SURFACE_FINISHES, "gear_seat"),
        label="gear seat finish",
        entity_type="SILHOUETTE",
    )

    # x=0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.112)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Stud Manufacturing Drawing",
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
