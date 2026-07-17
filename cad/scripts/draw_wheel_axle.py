r"""Create the curated machinist drawing for the magnifying-wheel axle."""

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
    add_surface_finish,
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
from wheel_axle_spec import (
    COLLAR_DIA,
    COLLAR_LEN,
    FLANGE_DIA,
    FLANGE_LEN,
    STUD_DIA,
    STUD_LEN,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    view_name,
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
_TOTAL_LEN = FLANGE_LEN + STUD_LEN

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


FRONT_KEEP = {
    "FlangeLength": (
        FRONT_CENTER[0] - FLANGE_DIA / 2.0 * _K - 0.018,
        _front_y(FLANGE_LEN / 2.0),
    ),
    "StudLength": (
        FRONT_CENTER[0] + FLANGE_DIA / 2.0 * _K + 0.030,
        _front_y(FLANGE_LEN + STUD_LEN / 2.0),
    ),
    "CollarLength": (
        FRONT_CENTER[0] + FLANGE_DIA / 2.0 * _K + 0.012,
        _front_y(_TOTAL_LEN - COLLAR_LEN / 2.0),
    ),
}
END_KEEP = {
    "FlangeDia": (
        END_CENTER[0] - FLANGE_DIA / 2.0 * _K - 0.012,
        END_CENTER[1] + 0.045,
    ),
    "CollarDia": (
        END_CENTER[0] + FLANGE_DIA / 2.0 * _K + 0.015,
        END_CENTER[1] + 0.028,
    ),
    "StudDia": (
        END_CENTER[0] + FLANGE_DIA / 2.0 * _K + 0.015,
        END_CENTER[1] - 0.028,
    ),
}
# The magnifying wheel's O5 bore rides the stud: unilateral-minus keeps a
# 0.02..0.05 running clearance against the nominal-on-nominal bore.
DIMENSION_CALLOUTS = {"StudDia": "-0.02/-0.05"}


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


def _find_edge(
    adapter: Any,
    view: Any,
    xy: tuple[float, float],
    *,
    axis: str,
    label: str,
    span: float = 0.0015,
    step: float = 0.00025,
) -> tuple[float, float]:
    """Refine an approximate sheet point to one a typed EDGE pick actually hits.

    The projected geometry sits up to ~0.75 mm off the outline-derived
    position (measured live) while the pick tolerance is sub-millimeter, so a
    formula-exact coordinate can miss its edge. Scan outward along ``axis``
    (the direction perpendicular to the target edge) and return the first
    point SolidWorks answers; the nearest OTHER edge on every use here is
    >= 6 mm away, so the +-1.5 mm band can never latch onto the wrong one.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate view for {label}")
    steps = int(round(span / step))
    offsets = sorted((k * step for k in range(-steps, steps + 1)), key=abs)
    for offset in offsets:
        x = xy[0] + (offset if axis == "x" else 0.0)
        y = xy[1] + (offset if axis == "y" else 0.0)
        draw.ClearSelection2(True)
        if draw.Extension.SelectByID2(
            "", "EDGE", x, y, 0.0, False, 0, null_callout(), 0
        ):
            draw.ClearSelection2(True)
            if offset:
                _telemetry.debug(
                    f"{label}: edge found {offset * 1000:+.2f} mm off the "
                    f"nominal pick along {axis}"
                )
            return (x, y)
    raise RuntimeError(
        f"{label}: no edge within {span * 1000:.1f} mm of sheet "
        f"({xy[0]:g}, {xy[1]:g}) along {axis}"
    )


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
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    # The O5 stud hides under the O9 collar from the tip side; show it greyed
    # so its diameter and GD&T attach to a real circle.
    set_hidden_lines_visible(adapter, end)

    fdx, fdy = _view_center_delta(adapter, front, FRONT_CENTER, "front")
    edx, edy = _view_center_delta(adapter, end, END_CENTER, "end")

    def fpt(x: float, y: float) -> tuple[float, float]:
        return (x + fdx, y + fdy)

    def ept(x: float, y: float) -> tuple[float, float]:
        return (x + edx, y + edy)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=_shift(FRONT_KEEP, fdx, fdy), view_label="front"
    )
    end_annotations = curate_view_dimensions(
        adapter, end, keep=_shift(END_KEEP, edx, edy), view_label="end"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *end_annotations], DIMENSION_CALLOUTS
    )
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to axle end view")

    flange_face_edge = _find_edge(
        adapter, front,
        fpt(FRONT_CENTER[0] + FLANGE_DIA / 4.0 * _K, _front_y(0.0)),
        axis="y", label="flange seating face pick",
    )
    stud_circle_top = _find_edge(
        adapter, end,
        ept(END_CENTER[0], END_CENTER[1] + STUD_DIA / 2.0 * _K),
        axis="y", label="stud circle top pick",
    )
    stud_circle_right = _find_edge(
        adapter, end,
        ept(END_CENTER[0] + STUD_DIA / 2.0 * _K, END_CENTER[1]),
        axis="x", label="stud circle right pick",
    )
    collar_circle_left = _find_edge(
        adapter, end,
        ept(END_CENTER[0] - COLLAR_DIA / 2.0 * _K, END_CENTER[1]),
        axis="x", label="collar circle left pick",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=flange_face_edge,
        symbol_xy=fpt(FRONT_CENTER[0] + FLANGE_DIA / 4.0 * _K + 0.006,
                      _front_y(0.0) - 0.016),
        datum="A",
        label="flange seating face",
    )
    add_datum_feature(
        adapter,
        end,
        edge_xy=stud_circle_right,
        symbol_xy=ept(END_CENTER[0] + 0.038, END_CENTER[1] - 0.052),
        datum="B",
        label="stud bearing axis",
    )
    add_feature_control_frame(
        adapter,
        end,
        edge_xy=stud_circle_top,
        # +0.052 in y put the frame's 8 mm half-box 8.3 mm over the top margin.
        # Held to +0.045 (box top ~0.261) and pushed out to +0.058 in x, which
        # keeps it clear of the flange circle (52.5 mm radius) without reaching
        # the 0.4191 right margin.
        #
        # STALE ARITHMETIC, placement still good: the "8 mm half-box" was the
        # audit's old model. An FCF's anchor is its frame's TOP-LEFT corner, so
        # it reaches only ~0.1 mm ABOVE the anchor (and ~7.0 mm below) -- the top
        # overrun that forced this move was never real. Kept as-is because the
        # placement is fine and re-tuning costs a COM rebuild for nothing. The
        # direction that DOES bite is the RIGHT: the frame grows right by its
        # full width (20-30 mm, not 8), which is what put platen_guide's frame
        # over the right margin. That is why the x note above still matters.
        frame_xy=ept(END_CENTER[0] + 0.058, END_CENTER[1] + 0.045),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        diameter=True,
        label="stud perpendicular to seating face",
    )
    add_feature_control_frame(
        adapter,
        end,
        edge_xy=collar_circle_left,
        frame_xy=ept(END_CENTER[0] - 0.075, END_CENTER[1] - 0.045),
        characteristic="circular_runout",
        tolerance="0.05",
        datums=("B",),
        label="collar runout on the stud",
    )
    # The stud OD is dimensioned in the end view, but its Ra belongs on the
    # FRONT view. The symbol's TEXT renders ABOVE its arm (ASME Y14.36) and runs
    # ~13..39 mm to the RIGHT of the anchor, so in the end view it cannot clear
    # the O35 flange circle at ANY height the 12.7 mm left margin allows -- the
    # arc reaches x=0.0534 at bore height while the text would need to stop by
    # x=0.0144 -- and it printed over the arc. (The audit cannot catch that: it
    # boxes the symbol as a nominal square about its anchor.) On the profile the
    # stud's left flank has ~45 mm of empty sheet beside it, which takes the
    # short, roughly horizontal leader this symbol wants.
    stud_flank_y = _front_y(FLANGE_LEN + STUD_LEN / 2.0)
    add_surface_finish(
        adapter,
        front,
        # A cylinder's side outline is a SILHOUETTE, not a model edge.
        edge_xy=fpt(FRONT_CENTER[0] - STUD_DIA / 2.0 * _K, stud_flank_y),
        # Text lands at x~0.058..0.084: clear of the stud flank (x=0.0975) and
        # of the O9 collar (x>=0.0915), which starts a further 9 mm up.
        symbol_xy=fpt(0.045, stud_flank_y),
        roughness_ra="1.6",
        label="stud bearing finish",
        entity_type="SILHOUETTE",
    )

    # x=0.020: a note is left-aligned on its anchor, and the drawn frame rule is
    # at x=0.0159 -- 0.014 printed the first glyph through it (the audit's bound
    # is the 12.7 mm zone margin, so it cannot see this).
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
