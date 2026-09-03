r"""Create the curated machinist drawing for the magnifying-wheel axle.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
flanged stud turned in one setting carries no datums and no feature-control
frames -- the stud's running fit is the band on the model diameter, plus one
roughness symbol on the OD the wheel spins on. The three diameters and the
axial stations all read on the profile view (policy rule 7: a turned part
is dimensioned as it sits in the lathe, lengths from one faced end with a
conspicuous overall), the end view carries only its centre mark, and the
shoulder roots carry one leadered R MAX allowance (machinist review
2026-09-02).
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
    add_edge_dimension,
    add_property_linked_note,
    add_surface_finish,
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
from _surface_finish import surface_finish_by_key
from wheel_axle_spec import (
    COLLAR_DIA,
    COLLAR_LEN,
    COLLAR_START,
    FLANGE_DIA,
    FLANGE_LEN,
    OVERALL_LEN,
    ROOT_NOTE,
    STUD_DIA,
    STUD_LEN,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_outline,
)


SPEC = DRAWINGS_BY_NAME["wheel_axle"]
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
_K = SHEET_SCALE[0] / 1000.0  # model mm -> sheet meters
_TOTAL_LEN = OVERALL_LEN

# Front view: the profile (axle axis vertical, flange at the bottom).
# End view: the tip-side circles, third-angle above the front view.
FRONT_CENTER = (0.105, 0.100)
# The O35 flange at 3:1 makes this view a 105 mm circle, so y=0.215 ran its
# outline 3.4 mm into the top zone band. 0.208 clears it by ~3.6 mm and keeps
# the third-angle stack (end view above front, both on x=0.105) intact; the gap
# to the front view's upper dimensions is ~27 mm, so nothing crowds below.
END_CENTER = (0.105, 0.208)
ISO_CENTER = (0.310, 0.185)


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - _TOTAL_LEN / 2.0) * _K


# Profile-view landmarks (sheet meters, about the intended geometry centre):
# the flange's bar-side face is the bottom of the view, the stud tip its top.
_BOTTOM_Y = _front_y(0.0)
_TIP_Y = _front_y(_TOTAL_LEN)
_FLANGE_RIGHT_X = FRONT_CENTER[0] + FLANGE_DIA / 2.0 * _K
_STUD_RIGHT_X = FRONT_CENTER[0] + STUD_DIA / 2.0 * _K
_COLLAR_RIGHT_X = FRONT_CENTER[0] + COLLAR_DIA / 2.0 * _K
# Two vertical lanes right of the flange: the base-end stations (13.00 to the
# collar, then its 4.00 as a chained reference) inboard, the 17.00 overall
# outboard -- the old CollarLength / StudLength lanes.
_STATION_LANE_X = _FLANGE_RIGHT_X + 0.012
_OVERALL_LANE_X = _FLANGE_RIGHT_X + 0.030

# Every marked dimension reads on the profile view. The axis is vertical, so
# each diameter's dimension line runs HORIZONTALLY at its text height: the
# O35 below the flange, the O9 above the tip (between the two views), the O5
# across the stud mid-span with its toleranced text out to the right, clear
# of the Ra symbol on the left. The end view keeps nothing -- SolidWorks
# inserts each marked model dimension into ONE view, so the profile is
# curated first and the end view is never asked (draw_pinion_bracket,
# 2026-09-02 seat build).
FRONT_KEEP = {
    "FlangeDia": (FRONT_CENTER[0], _BOTTOM_Y - 0.014),
    "StudDia": (FRONT_CENTER[0] + 0.040, _front_y(FLANGE_LEN + STUD_LEN / 2.0) - 0.008),
    "CollarDia": (FRONT_CENTER[0], _TIP_Y + 0.012),
    "FlangeLength": (
        FRONT_CENTER[0] - FLANGE_DIA / 2.0 * _K - 0.018,
        _front_y(FLANGE_LEN / 2.0),
    ),
    "CollarStart": (_STATION_LANE_X, _front_y(COLLAR_START / 2.0)),
    "CollarLength": (_STATION_LANE_X, _front_y(_TOTAL_LEN - COLLAR_LEN / 2.0)),
}
END_KEEP: dict[str, tuple[float, float]] = {}
# The stud's unilateral-minus running-fit band lives on its source-model dimension.
DIMENSION_CALLOUTS: dict[str, str] = {}
# The collar's own length chains off the 13.00 station as a reference; the
# 17.00 overall between the end faces is the controlling dimension.
REFERENCE_DIMENSIONS = ("CollarLength",)

# Shoulder-root callout: leadered onto the collar's bar-side rim (the O9
# step face seen edge-on, picked midway across the 2 mm annulus right of
# the stud so only that rim is under the cursor), the note down-right of it
# under the collar and above the O5 text, inboard of the station lane.
ROOT_PICK_XY = (
    FRONT_CENTER[0] + (STUD_DIA / 2.0 + (COLLAR_DIA - STUD_DIA) / 4.0) * _K,
    _front_y(COLLAR_START),
)
ROOT_NOTE_XY = (0.128, _front_y(COLLAR_START) - 0.0105)


def _view_center_delta(
    adapter: Any, view: Any, intended: tuple[float, float], label: str
) -> tuple[float, float]:
    """Measured-vs-intended geometry-center delta for coordinate picks.

    ``place_view`` anchors on the model origin's projection, not the geometry
    box center, so a part that is not origin-symmetric (this axle spans
    y 0..17) lands its geometry offset from the requested center. Every
    layout constant in this recipe is authored about the intended geometry
    center; shifting by this delta makes the edge picks and text positions
    track wherever SolidWorks actually put the geometry.
    """
    outline = view_outline(adapter, view)
    if outline is None:
        raise RuntimeError(f"{label} drawing view has no outline")
    cx = (outline[0] + outline[2]) / 2.0
    cy = (outline[1] + outline[3]) / 2.0
    _telemetry.debug(
        f"{label} view geometry center ({cx:.4f}, {cy:.4f}) vs intended "
        f"({intended[0]:.4f}, {intended[1]:.4f})"
    )
    return cx - intended[0], cy - intended[1]


def _shift(
    points: dict[str, tuple[float, float]], dx: float, dy: float
) -> dict[str, tuple[float, float]]:
    return {name: (x + dx, y + dy) for name, (x, y) in points.items()}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-axle source", await adapter.open_model(str(SOURCE)))
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
            0: "Wheel Axle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "wheel axle; flanged stud; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=(3, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(3, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in every orthographic view (Harvey #30 / Lipton):
    # the O5 stud hides under the O9 collar from the tip side.
    for view in (front, end):
        set_hidden_lines_visible(adapter, view)

    fdx, fdy = _view_center_delta(adapter, front, FRONT_CENTER, "front")

    def fpt(x: float, y: float) -> tuple[float, float]:
        return (x + fdx, y + fdy)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=_shift(FRONT_KEEP, fdx, fdy), view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # Parenthesize the chained collar length (a plain "(" prefix -- the batch
    # helper's "(<MOD-DIAM>" would put a diameter glyph on a length). Fails
    # loud on an unmatched name, as the batch helper does: an unparenthesized
    # 4.00 beside 13.00 and 17.00 would ship an over-constrained chain.
    referenced: set[str] = set()
    for annotation in front_annotations:
        name = dimension_name(adapter, annotation)
        if name not in REFERENCE_DIMENSIONS:
            continue
        set_reference_dimension(adapter, annotation, label=f"{name} reference")
        referenced.add(name)
    missing = set(REFERENCE_DIMENSIONS) - referenced
    if missing:
        raise RuntimeError(f"reference dimensions not applied: {sorted(missing)}")
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to axle end view")

    # The 17.00 overall, bar-side face to stud tip, as the controlling axial
    # dimension in the outboard lane (Harvey #25: the overall is real and
    # conspicuous): the flange's bottom face edge to the collar's tip face
    # edge, both seen edge-on.
    add_edge_dimension(
        adapter,
        front,
        p0=fpt(FRONT_CENTER[0] + 0.040, _BOTTOM_Y),
        p1=fpt(FRONT_CENTER[0] + 0.010, _TIP_Y),
        text_xy=fpt(_OVERALL_LANE_X, _front_y(_TOTAL_LEN / 2.0)),
        label="overall length",
        orientation="vertical",
    )

    # The stud OD is the one running surface (the magnifying wheel spins on
    # it), so it alone carries a roughness symbol, on the stud's left flank
    # (a SILHOUETTE pick: a cylinder carries no model edge along its side).
    # The symbol's TEXT renders ABOVE its arm (ASME Y14.36) and runs ~13..39 mm
    # to the RIGHT of the anchor, so the anchor sits well left of the flank:
    # text lands at x~0.058..0.084, clear of the stud flank (x=0.0975) and of
    # the O9 collar (x>=0.0915), which starts a further 9 mm up.
    stud_flank_y = _front_y(FLANGE_LEN + STUD_LEN / 2.0)
    add_surface_finish(
        adapter,
        front,
        edge_xy=fpt(FRONT_CENTER[0] - STUD_DIA / 2.0 * _K, stud_flank_y),
        symbol_xy=fpt(0.045, stud_flank_y),
        control=surface_finish_by_key(SURFACE_FINISHES, "stud_bearing"),
        label="stud bearing finish",
        entity_type="SILHOUETTE",
    )

    # Shoulder roots: the collar's bar-side rim carries the 2X root allowance
    # for both steps (policy rule 7: every shoulder fillet has a size).
    root_xy = find_edge_near(
        adapter,
        front,
        fpt(*ROOT_PICK_XY),
        axis="y",
        label="wheel axle collar shoulder",
    )
    add_attached_note(
        adapter,
        front,
        text=ROOT_NOTE,
        entity_xy=root_xy,
        note_xy=fpt(*ROOT_NOTE_XY),
        label="axle shoulder roots",
    )

    # x=0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.048)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Wheel Axle Manufacturing Drawing",
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
