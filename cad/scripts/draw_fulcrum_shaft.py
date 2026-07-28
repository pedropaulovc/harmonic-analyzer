r"""Create the curated machinist drawing for the lever fulcrum shaft."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
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
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import MACHINED
from fulcrum_shaft_spec import SHAFT_DIA, SHAFT_LENGTH
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["fulcrum_shaft"]
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
END_VIEW_SCALE = 2.0
FRONT_CENTER = (0.055, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.045,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.355, 0.205)
# 1:2, like the near-identical 187 arbor on MHA-028: at 1:1 the 182 shaft's
# isometric is a ~136 mm diagonal bar whose outline ran x=0.287..0.423 -- over
# the right zone border (0.4191) AND far enough left to swallow the right-end
# perpendicularity frame at x=0.296, so that frame's leader was read as crossing
# the isometric.  At 1:2 the outline is ~x=0.321..0.389: inside the border, and
# clear of the frame.
ISO_SCALE = (1, 2)

# Left of the end circle, ON its centre height so the diameter line runs
# horizontally through the centre instead of diagonally.  x=0.030, not the old
# bbox-derived 0.0173: the callout is centred on its anchor and ~22 mm wide now
# that it renders horizontally, so 0.0173 printed it across the border rule at
# ~0.0126.  The layout audit cannot catch that: it boxes a dim as a nominal 4 mm
# half-square (_NOMINAL_DIM_HALF_M), far narrower than the real text, and even
# that box cleared the 12.7 mm zone margin at 0.0173.
FRONT_KEEP = {
    "ShaftDia": (0.030, FRONT_CENTER[1]),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.025),
}
DIMENSION_CALLOUTS = {"ShaftDia": "+0.00/-0.02"}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open fulcrum-shaft source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
            "Iso View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Fulcrum Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fulcrum shaft; bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to shaft end view")

    end_radius = SHAFT_DIA * END_VIEW_SCALE / 2000.0
    end_circle = (
        FRONT_CENTER[0] + end_radius,
        FRONT_CENTER[1],
    )
    # The cylindricity frame's terminus: 50 deg up the arc, NOT `end_circle`.
    # Identical defect to MHA-028's 187 arbor, identical cause -- the frame and
    # the Ra both picked `end_circle` (3 o'clock), so their leaders ended on the
    # same point and printed as ONE blob: measured arrowheads x 0.0609..0.0613
    # and x 0.0620..0.0628, a 0.7 mm gap edge-to-edge, centroids 1.3 mm apart.
    #
    # 50 deg, not the arbor's 55 deg, because this circle is SMALLER (r=6.35 mm
    # at 2:1 vs the arbor's 9.525) while carrying the same three obstacles, so
    # the same angles buy less arc length and the optimum shifts.  Swept at
    # 5 deg steps against the measured obstacles -- Ra arrowhead at 0 deg, the
    # ShaftDia diametral line's terminus at 27 deg / (0.0605, 0.2078), and
    # datum A's triangle base on the circle at 90 deg spanning x 0.0531..0.0568
    # -- 50 deg reads 5.4 / 2.5 / 2.7 mm.
    #
    # Honest limit: 2.5 mm is the best available here, vs 3.6 mm on the arbor.
    # It clears the ~1 mm stacking tell by 2.5x and the Ra separation (the
    # actual defect) goes 0.7 -> 5.4 mm, but this arc is genuinely crowded: no
    # angle on it exceeds 2.5 mm.  Anything tighter would need an obstacle to
    # move, not this terminus.
    end_upper = (
        FRONT_CENTER[0] + end_radius * math.cos(math.radians(50.0)),
        FRONT_CENTER[1] + end_radius * math.sin(math.radians(50.0)),
    )
    left_end = (RIGHT_CENTER[0] - SHAFT_LENGTH / 2000.0, RIGHT_CENTER[1])
    right_end = (RIGHT_CENTER[0] + SHAFT_LENGTH / 2000.0, RIGHT_CENTER[1])
    # Picked at 12 o'clock (not `end_circle`, which is the 3 o'clock point the
    # cylindricity/Ra leaders use) because this symbol goes straight ABOVE the
    # circle.  A datum tag is pinned to the entity it attaches to -- on a circle
    # that is the circumference, so it re-attaches at the point nearest the
    # symbol and symbol_xy goes inert.  Picking 3 o'clock while placing the
    # symbol at 12 collapsed the tag onto the circle, printing its box over the
    # geometry with the triangle across the "A".  Matching the pick to the
    # symbol's clock position lets the leader run radially out to it (the
    # draw_pivot_bushing.py spelling).
    end_top = (
        FRONT_CENTER[0],
        FRONT_CENTER[1] + SHAFT_DIA * END_VIEW_SCALE / 2000.0,
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=end_top,
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.024),
        datum="A",
        label="fulcrum shaft axis",
        # SolidWorks snaps this circular-edge attachment to its nearest legal
        # anchor.  The live readback is 0.0168 mm from the requested point;
        # tolerate that native normalization without weakening the shared
        # 0.001 mm persistence check for freely positioned annotations.
        position_tolerance_m=0.0001,
    )
    # Up-RIGHT of the end circle it annotates, not out at RIGHT_CENTER[0]
    # (0.191): that put the frame 130 mm from its own anchor, so its leader ran
    # as one long diagonal across the whole sheet, skimming just over the side
    # view.  The side view starts at x=0.100 and tops out at y=0.208, so this
    # band is empty; the 8 mm half-box tops out at 0.258, inside the 0.2667 zone
    # margin.  (STALE ARITHMETIC, conclusion unchanged: the "8 mm half-box" was
    # the audit's old model. An FCF's anchor is its frame's TOP-LEFT corner, so
    # it reaches ~0.1 mm above the anchor, not 8 -- even further inside the
    # margin. The side that under-reads is the RIGHT, where the frame grows by
    # its full 20-30 mm width; this frame is nowhere near the right margin.)
    #
    # x=0.065 sits the frame almost directly ABOVE the end_circle pick, which
    # makes its leader near-vertical (it hugs x=0.062..0.065 the whole way down).
    # That matters because the Ra symbol below shares this anchor: at x=0.078 the
    # leader raked down at an angle and printed straight through the Ra symbol's
    # bar and triangle.  Near-vertical, it passes x=0.064 at the Ra's top edge --
    # clear left of the Ra's arm at 0.072.
    #
    # That arm-clearance reasoning still HOLDS, and re-terminating at `end_upper`
    # only strengthens it: the leader now runs x=0.0591..0.063, i.e. it moves
    # FURTHER LEFT, away from the Ra's arm at 0.072, and stays near-vertical
    # (3.9 mm of horizontal run over 38 mm of drop).  It also stays outside the
    # circle (its low end IS the circle) and clears datum A's box (x<=0.0585) by
    # 2.6 mm at y=0.229.  The Ra keeps `end_circle`; only this terminus moved.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=end_upper,
        frame_xy=(0.065, 0.250),
        characteristic="cylindricity",
        tolerance="0.01",
        label="fulcrum bearing cylindricity",
    )
    # The frame extends ~0.027 m right of its anchor, so the LEFT one needs 0.042
    # (not 0.014, which spanned x=0.086..0.113) to keep its far edge clear of the
    # Depth extension line rising at the shaft's left end, x=0.100 -- the same
    # offset, for the same reason, as the 187 arbor on MHA-028.
    for edge, x, label in (
        (left_end, left_end[0] - 0.042, "left end perpendicularity"),
        (right_end, right_end[0] + 0.014, "right end perpendicularity"),
    ):
        add_feature_control_frame(
            adapter,
            right,
            edge_xy=edge,
            frame_xy=(x, 0.180),
            characteristic="perpendicularity",
            tolerance="0.05",
            datums=("A",),
            label=label,
        )
    # Up-RIGHT of the end circle, on the same side as the `end_circle` pick
    # (the circle's RIGHTMOST point), so the leader comes in from the right and
    # never crosses the circle.  Two constraints forced this side:
    #   * it used to sit at RIGHT_CENTER[0] and drag a 130 mm diagonal leader
    #     back to this circle; and
    #   * placing it up-LEFT instead only traded that for a leader that raked
    #     across the circle and landed on the datum A tag -- which rests ON the
    #     circle at ~(0.052..0.058, 0.211..0.218) and cannot be moved away.
    #     IAnnotation::SetPosition2 on a DATUM FEATURE symbol sets the "point
    #     where the leader hits the symbol", so a tag that attaches straight to
    #     its edge ignores the requested Y and sits against the geometry.
    # The symbol's ARM extends left of the anchor and its TEXT renders ABOVE the
    # arm and to the RIGHT (ASME Y14.36): ~x=0.072..0.111 / y=0.222..0.237,
    # which clears the side view (it tops out at y=0.208) and leaves the arm at
    # 0.072, right of the cylindricity frame's near-vertical leader above.
    add_surface_finish(
        adapter,
        front,
        edge_xy=end_circle,
        symbol_xy=(0.075, 0.222),
        roughness_ra=MACHINED,
        label="fulcrum bearing finish",
    )

    # 0.020: the note is left-aligned on its anchor, so the ink starts here. The
    # left bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame
    # rule now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.170)
    # The iso renders at 1:2 while the title block reads 1:1, so the pictorial
    # needs its own scale callout or the sheet misstates it. Placed at the same
    # offset from ISO_CENTER that cylinder-gear-shaft uses for its identical 1:2
    # iso (dx -0.030, dy -0.048), so the two sibling shafts read alike.
    add_property_linked_note(adapter, "Iso View Note", 0.325, 0.157)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Shaft Manufacturing Drawing",
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
