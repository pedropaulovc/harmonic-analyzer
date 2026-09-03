r"""Create the curated machinist drawing for the cone platform lock knob.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
turned thumb knob carries no datums, no feature-control frames, no roughness
symbols and no bands -- the title block's general tolerances govern
everything.  It is dimensioned as it sits in the lathe (policy rule 7): the
three turned diameters read on the ELEVATION as linear diameter dimensions
(the washer and the threaded stud below the stud end, the body across its
straight wall), the lengths chain from the washer seat on the right with the
overall as a reference, and the dome radius is leadered from the left.  The
end view carries only its centre marks.
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
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    find_edge_near,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_lock_knob_spec import (
    BODY_DIA,
    BODY_TOP,
    DOME_R as DOME_R,
    STUD_LEN,
    STUD_THREAD,
    WASHER_DIA,
    WASHER_T,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_lock_knob"]
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

SHEET_SCALE = (3.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# x=0.100: the body diameter and the dome radius sit on the LEFT of the
# elevation (text out to x~0.030, inside the 0.020 frame margin) and the three
# chained lengths plus the reference overall on the RIGHT, out to x~0.184,
# short of the isometric at 0.220.
FRONT_CENTER = (0.100, 0.150)
TOP_CENTER = (0.100, 0.232)
ISO_CENTER = (0.220, 0.190)

# The front view centres on the part bounding box (dome apex at BODY_TOP,
# stud end at -STUD_LEN below the washer seat / model origin), so a model
# height y projects on-sheet at FRONT_CENTER[1] + (y - _MID_Y) * _S.
_MID_Y = (BODY_TOP - STUD_LEN) / 2.0

# Measured with a one-off edge probe (2026-07-15): the placed view's washer
# seat silhouette sits 0.725 mm (sheet) BELOW the bbox-midpoint prediction
# (probe hits at y=0.13855/0.14305 -- their 4.5 mm gap is exactly
# WasherT * 3, so the scale is right and the whole map is shifted).  Edge
# picks tolerate only ~0.3 mm, so the map carries the measured offset.
_FRONT_Y_OFFSET = -0.000725


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - _MID_Y) * _S + _FRONT_Y_OFFSET


# Sheet landmarks of the elevation (before the measured view-centre shift).
_STUD_END_Y = _front_y(-STUD_LEN)
_WASHER_SEAT_Y = _front_y(0.0)
_APEX_Y = _front_y(BODY_TOP)
_WASHER_HALF_W = WASHER_DIA * _S / 2.0
_BODY_HALF_W = BODY_DIA * _S / 2.0

# Every marked dimension reads on the elevation (a turned part dimensioned
# as it sits in the lathe).  SolidWorks inserts each marked model dimension
# into ONE view, so the elevation is curated first and the end view is never
# asked (draw_pivot_shaft, 2026-09-02 seat build).
#
# Diameters: the stud (with its thread callout below the value) and the
# washer as linear diameters stacked BELOW the stud end -- their witness
# lines drop from the flanks past nothing (the stud is narrower than the
# washer, so the washer's witnesses clear it) -- and the body as a linear
# diameter ACROSS its straight wall at mid-height, text out to the left.
# Lengths: stud length and body height chained from the washer seat on the
# right, the washer thickness between them with its text parked above the
# 4.5 mm flange gap, the reference overall outermost.  The dome radius is
# leadered from the upper left, where no witness line can cross it.
FRONT_KEEP = {
    "StudDia": (FRONT_CENTER[0], _STUD_END_Y - 0.012),
    "WasherDia": (FRONT_CENTER[0], _STUD_END_Y - 0.032),
    "BodyDia": (0.052, _front_y((WASHER_T + BODY_TOP - DOME_R) / 2.0)),
    "DomeR": (0.040, _APEX_Y + 0.013),
    "StudLen": (FRONT_CENTER[0] + _WASHER_HALF_W + 0.015, _front_y(-STUD_LEN / 2.0)),
    "WasherT": (FRONT_CENTER[0] + _WASHER_HALF_W + 0.023, _front_y(WASHER_T) + 0.013),
    "BodyTop": (FRONT_CENTER[0] + _WASHER_HALF_W + 0.033, _front_y(BODY_TOP / 2.0)),
}
TOP_KEEP: dict[str, tuple[float, float]] = {}
OVERALL_TEXT_XY = (FRONT_CENTER[0] + _WASHER_HALF_W + 0.049, _front_y(_MID_Y))
DIMENSION_CALLOUTS = {
    "StudDia": f"{STUD_THREAD} UNC",
}


def _outline_center(adapter: Any, view: Any) -> tuple[float, float]:
    """A view's actual on-sheet geometry center, read from its outline.

    ``CreateDrawViewFromModelView3`` documents its LocX/LocY as the view
    center, but the achieved center can differ from the requested one (the
    proven failure: every model-mapped edge pick missing by one constant
    offset).  The outline pads the geometry with a uniform whitespace margin,
    so its midpoint IS the geometry center; measuring it and shifting every
    pick keeps the recipe correct whatever the placement anchored.
    """
    x0, y0, x1, y1 = (float(v) for v in adapter._get_attr_or_call(view, "GetOutline"))
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _shifted(
    positions: dict[str, tuple[float, float]], delta: tuple[float, float]
) -> dict[str, tuple[float, float]]:
    return {name: (x + delta[0], y + delta[1]) for name, (x, y) in positions.items()}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-lock-knob source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Lock Knob Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone lock knob; turned thumb knob; chromed steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(3, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(3, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in every orthographic view (policy rule 7).
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    # Measured before any annotation lands (dims would grow the outline).
    front_center = _outline_center(adapter, front)
    front_delta = (
        front_center[0] - FRONT_CENTER[0],
        front_center[1] - FRONT_CENTER[1],
    )
    _telemetry.info(
        f"view-center delta: front=({front_delta[0]:.4f}, {front_delta[1]:.4f})"
    )

    # The elevation claims every marked dimension; the end view keeps nothing.
    front_annotations = curate_view_dimensions(
        adapter, front, keep=_shifted(FRONT_KEEP, front_delta), view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")

    # Overall length, stud end to dome apex, as a REFERENCE: the controlling
    # lengths are the body height and stud length chained from the washer
    # seat.  Both end faces are edge-on circles (the dome's O3 apex flat and
    # the stud end); the picks are refined along the axis so the measured
    # view offset cannot miss them.
    stud_end = find_edge_near(
        adapter,
        front,
        (front_center[0], _STUD_END_Y + front_delta[1]),
        axis="y",
        label="stud end face",
    )
    apex = find_edge_near(
        adapter,
        front,
        (front_center[0], _APEX_Y + front_delta[1]),
        axis="y",
        label="dome apex flat",
    )
    overall = add_edge_dimension(
        adapter,
        front,
        p0=stud_end,
        p1=apex,
        text_xy=(OVERALL_TEXT_XY[0] + front_delta[0], OVERALL_TEXT_XY[1] + front_delta[1]),
        label="overall length",
        orientation="vertical",
    )
    # add_edge_dimension hands back the IDisplayDimension (late-bound); bind
    # it before reading the IAnnotation the reference helper wants.
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall length",
    )

    # 0.020: the note is left-aligned on its anchor, so the ink starts here. The
    # left bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame
    # rule now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    # Parked under the washer-diameter dimension (its text sits at y~0.087).
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.072)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Lock Knob Manufacturing Drawing",
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
