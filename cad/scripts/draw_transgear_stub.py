r"""Create the curated machinist drawing for the transgear stud.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
stepped stud turned in one setting carries no datums and no feature-control
frames -- its two fits are the bands on the model diameters, plus one
roughness symbol on the seat the feed pinion and disc turn on. The three
diameters stack left of the profile, the three axial stations baseline
from the base (faced) end on its right (policy rule 7: lengths from one
faced end, with a conspicuous overall), and the shoulder roots carry one
leadered R MAX allowance (machinist review 2026-09-02).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    find_edge_near,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from transgear_stub_spec import (
    BASE_DIA,
    BASE_LEN,
    COLLAR_DIA as COLLAR_DIA,
    COLLAR_LEN,
    ROOT_NOTE,
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
# Base-end view, third-angle: below the front (the template's projection
# symbol is third-angle, _drawing_common). Looking at the base end, the
# O9.525 base is the NEAR circle and the O14 collar shows solid outside it,
# which is what the view draws.
END_CENTER = (0.115, 0.068)
ISO_CENTER = (0.320, 0.190)


def _fx(x_mm: float) -> float:
    """Front-view sheet x for a model radial offset (mm from the axis)."""
    return FRONT_CENTER[0] + x_mm * VIEW_MM


def _fy(y_mm: float) -> float:
    """Front-view sheet y for a model axial station (mm from the base end)."""
    return FRONT_CENTER[1] + (y_mm - TOTAL_LEN / 2.0) * VIEW_MM


# Diameters stack on the left; the axial stations baseline from the base end
# on the right, one lane each, longest outermost.
#
# The Ra symbol beside the gear seat throws its text out to x~0.171 and its
# horizontal ARM 6 mm past that, to x=0.1764 (measured 2026-07-16 on the
# render: text extent is NOT symbol extent, and note text is not a COM
# primitive, so only the render shows it). The 9.10 lane ends at the base
# shoulder (y~0.168), below the symbol (y~0.199), so it may sit inboard of
# the arm; the 22.90 and 26.90 lines run the symbol's full height, so both
# lanes sit clear to the RIGHT of the arm end.
_BASELINE_X = (0.160, 0.186, 0.206)
FRONT_KEEP = {
    "BaseDia": (0.052, _fy(BASE_LEN / 2.0)),
    "SeatDia": (0.052, _fy(BASE_LEN + 3.0)),
    "CollarDia": (0.052, _fy(TOTAL_LEN - COLLAR_LEN / 2.0)),
    "BaseLength": (_BASELINE_X[0], _fy(BASE_LEN / 2.0)),
    "SeatEnd": (_BASELINE_X[1], _fy((BASE_LEN + SEAT_LEN) / 2.0)),
    "Overall": (_BASELINE_X[2], _fy(TOTAL_LEN / 2.0)),
}
# No callout overrides: both diameter bands are toleranced on the MODEL
# dimension by build_transgear_stub (transgear_stub_spec.BASE_DIA_BAND /
# SEAT_DIA_BAND), so SolidWorks renders the limits natively.
DIMENSION_CALLOUTS: dict[str, str] = {}
# The base is the fitted 3/8" conversion (BASE_DIA_BAND on the model
# dimension): three decimals say "hold it" and match the exact 9.525.
DIMENSION_PRECISION = {"BaseDia": 3}

# Shoulder-root callout: leadered onto the base shoulder's rim on the LEFT
# (the base's top face seen edge-on, picked 1 mm inboard of its outer corner
# so only the O9.525 rim is under the cursor).  Its note is pulled left of the
# rim far enough that SolidWorks starts the leader beyond the trailing "MAX"
# instead of drawing the leader through that text.  The right side remains
# reserved for the baseline stack.
ROOT_PICK_XY = (_fx(-(BASE_DIA / 2.0 - 1.0)), _fy(BASE_LEN))
ROOT_NOTE_XY = (0.046, _fy(BASE_LEN) - 0.006)


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
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in every orthographic view (Harvey #30 / Lipton).
    for view in (front, end):
        set_hidden_lines_visible(adapter, view)

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

    # The gear seat is the one running surface (the feed pinion and disc turn
    # on it), so it alone carries a roughness symbol, on the seat's silhouette
    # in the front view.
    add_surface_finish(
        adapter,
        front,
        edge_xy=(_fx(SEAT_DIA / 2.0), _fy(BASE_LEN + SEAT_LEN / 2.0)),
        symbol_xy=(_fx(SEAT_DIA / 2.0) + 0.008, _fy(BASE_LEN + SEAT_LEN / 2.0) + 0.004),
        control=surface_finish_by_key(SURFACE_FINISHES, "gear_seat"),
        label="gear seat finish",
        entity_type="SILHOUETTE",
    )

    # Shoulder roots: the base shoulder's rim carries the 2X root allowance
    # for both steps (policy rule 7: every shoulder fillet has a size).
    root_xy = find_edge_near(
        adapter,
        front,
        ROOT_PICK_XY,
        axis="y",
        label="transgear stud base shoulder",
    )
    add_attached_note(
        adapter,
        front,
        text=ROOT_NOTE,
        entity_xy=root_xy,
        note_xy=ROOT_NOTE_XY,
        label="stud shoulder roots",
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
