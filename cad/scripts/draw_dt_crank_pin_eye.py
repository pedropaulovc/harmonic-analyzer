r"""Create the manufacturing drawing for the keeper-chain anchor eye (MHA-DT-28).

Under ``cad/docs/drawing-guidelines.md``: a formed brass wire eye, a closed
loop with a straight tail running tangent off it, loop and tail in one plane.
The side view (the part's Right view) shows the eye at true shape with its two
controlling sizes from the part's blanked ``EyeReference`` sketch (a torus has
no edge to dimension): the loop's inside diameter, whose callout names the
bead chain that threads it, and the tail's length from the loop centre. The
top view, above it in projection, sees the tail's end and prints the wire's
stock diameter as REFERENCE. An isometric and the property-linked notes
complete the sheet. No datums, no frames, no roughness symbol: the part is
``visual_noncritical``, so every value takes the title block's one-place band.

The decimal places are the PART's (``dt_crank_pin_eye_notes``, applied
natively by ``build_dt_crank_pin_eye``); this script only reads them back.

Drawn 10:1 -- a 5.3 x 6.65 eye of Ø1 wire is a speck on a B sheet at less.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import place_view

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimensions,
)
import _drawing_hidden_sketches as hidden_sketches
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_crank_pin_eye_notes import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
)
from dt_crank_pin_eye_spec import LOOP_R, TAIL_LEN, WIRE_DIA


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_pin_eye"]
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

SHEET_SCALE = (10.0, 1.0)
VIEW_SCALE = (10, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # sheet metres per model mm
# The side view looks along -X: sheet right is model -Z, sheet up model +Y.
# The eye spans Z from +WIRE/2 (the tail) to -(2 LoopR + WIRE/2) (the loop's
# far side) and Y from -(LoopR + WIRE/2) to the tail's end at TailLen.
_BBOX_Z = (WIRE_DIA / 2.0, -(2.0 * LOOP_R + WIRE_DIA / 2.0))
_BBOX_Y = (-(LOOP_R + WIRE_DIA / 2.0), TAIL_LEN)
_BBOX_CZ = sum(_BBOX_Z) / 2.0  # -LoopR: the loop centre
_BBOX_CY = sum(_BBOX_Y) / 2.0
SIDE_CENTER = (0.150, 0.150)
# Third-angle: the top view sits above the side view, turned a quarter so
# its model -Z runs to sheet right like the side view's and the tail's end
# lines up over the tail.
TOP_CENTER = (SIDE_CENTER[0], 0.228)
TOP_ANGLE = -math.pi / 2.0
ISO_CENTER = (0.330, 0.165)
NOTES_XY = (0.020, 0.078)  # left of the title block, below the views
# The top view's tail end must sit over the side view's within this.
ALIGN_TOL_M = 5e-4


def _side_xy(model_z_mm: float, model_y_mm: float) -> tuple[float, float]:
    return (
        SIDE_CENTER[0] - (model_z_mm - _BBOX_CZ) * _S,
        SIDE_CENTER[1] + (model_y_mm - _BBOX_CY) * _S,
    )


LOOP_CENTER_XY = _side_xy(-LOOP_R, 0.0)
TAIL_END_XY = _side_xy(0.0, TAIL_LEN)
HALF_OD = (LOOP_R + WIRE_DIA / 2.0) * _S  # 0.0265

# Side view: the loop's inside diameter labelled down and right of the loop,
# its chain callout in the open field under it; the tail's length on the
# tail's west side, between the loop centre and the tail's end.
SIDE_KEEP = {
    "LoopID": (
        LOOP_CENTER_XY[0] + HALF_OD + 0.012,
        LOOP_CENTER_XY[1] - HALF_OD - 0.008,
    ),
    "TailLen": (
        TAIL_END_XY[0] - WIRE_DIA * _S - 0.016,
        (LOOP_CENTER_XY[1] + TAIL_END_XY[1]) / 2.0,
    ),
}
# Top view: the wire's stock diameter on the tail's end circle, labelled
# up and left: its 18-character callout block stays left of the loop's
# vertical centre line and above its horizontal one.
TOP_KEEP = {
    "WireDia": (TAIL_END_XY[0] - 0.034, TOP_CENTER[1] + 0.020),
}


@_telemetry.traced("drawing.crank_pin_eye.top_view_projection")
def _turn_top_view(adapter: Any, drawing_model: Any, side: Any, top: Any) -> None:
    """Turn the top view into projection over the side view, and prove it."""
    native = _early_bound(top, "IView")
    native.Angle = TOP_ANGLE
    if abs(math.remainder(float(native.Angle) - TOP_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to turn the eye's top view")
    drawing_model.EditRebuild3()
    tail_end = (0.0, TAIL_LEN / 1000.0, 0.0)
    loop_far = (0.0, 0.0, -2.0 * LOOP_R / 1000.0)
    side_tail = model_point_in_view(adapter, side, tail_end, label="side tail end")
    top_tail = model_point_in_view(adapter, top, tail_end, label="top tail end")
    side_loop = model_point_in_view(adapter, side, loop_far, label="side loop far wire")
    top_loop = model_point_in_view(adapter, top, loop_far, label="top loop far wire")
    misaligned = [
        (what, s[0], t[0])
        for what, s, t in (
            ("tail end", side_tail, top_tail),
            ("loop", side_loop, top_loop),
        )
        if abs(s[0] - t[0]) > ALIGN_TOL_M
    ]
    if misaligned:
        raise RuntimeError(
            f"eye top view is not in projection over the side view at angle "
            f"{TOP_ANGLE}: (feature, side x, top x) {misaligned}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open anchor-eye source", await adapter.open_model(str(SOURCE)))
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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Keeper Chain Anchor Eye Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "keeper chain anchor eye; formed brass wire",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    _turn_top_view(adapter, drawing_model, side, top)
    # Solid wire has nothing inside: hidden lines off everywhere
    # (drawing-guidelines.md rule 9 (show internal shape in solid lines)).
    for view in (side, top, iso):
        set_hidden_lines_removed(adapter, view)

    # The loop and tail sizes live on a reference sketch the part saves
    # hidden, in the eye's own plane: the side view curates through
    # _drawing_hidden_sketches, which shows that sketch in this view only.
    side_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*side_annotations, *top_annotations]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # Descriptive words only; every value and its places are the model's.
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # The wire is purchased stock: a native diameter, so the plural helper
    # keeps its Ø inside "( )".
    set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Keeper Chain Anchor Eye Manufacturing Drawing",
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
