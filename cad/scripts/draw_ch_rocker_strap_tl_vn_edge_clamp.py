"""Create the specification-control sheet for the strap fixture's edge clamp.

MHA-CH-13-TL-VN-50 is a Mitee-Bite Pitbull 26000 with the #4-40 x 3/8 socket
head cap screw it is supplied with (tier 2, ASME Y14.24 specification
control): the shared purchased-part sheet's Front/Top/Right/Isometric views
of the installed clamp, the catalogue's lettered sizes A, B, C, D and F and
the screw's 4-40 major as native reference dimensions from the part's hidden
supplier references, and the catalogue's operating data (torque, holding
force, throw, package, O-ring) in the footer. The catalogue governs; the
views are reference.

Front is the plan (part Z toward the viewer: A and C on the side faces, F
under the heel); Top looks at the knife, third-angle above Front, so the
clamp's base is up (D and B on opposite side faces, the 4-40 chord on the
screw's tip).

The sheet is 4:1. At the shared lanes' 20 mm text allowance a side, the
Top band set the scale to 1:1, a .375 part postage-stamp sized under a 4:1
isometric, with D's and B's shelved texts on each other (r3 review, run
20261117T235437892Z). The pre-fit margins reserve only the room each lane's
text takes, and only on the sides that carry one.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_lane_plan
from ch_rocker_strap_tl_vn_edge_clamp_spec import (
    ITEM,
    SUPPLIER_DATA,
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_FORMATS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_SIDES,
    SUPPLIER_REFERENCE_STARTS,
)


MACHINIST_REVIEW = MachinistReviewMode.LEARN
SPEC = DRAWINGS_BY_NAME["ch_rocker_strap_tl_vn_edge_clamp"]

# Pre-fit room past each lane, sheet metres, from the native ink of farm r3
# (1:1, every text shelved) and r7 (4:1). The shared plan sets each lane's
# annotation position 6 mm past the view outline. A vertical reference's line
# stands on that position and its text is 12.5-13.6 mm wide: centred on the
# line, or (D, a 7.6 mm span at 4:1) shelved 3.2 mm past it, ~17 mm out. A
# horizontal reference's position is its value's baseline: the value's caps
# stand 3.8 mm above it, the letter's baseline 5.6 mm below, and the line and
# arrows ink 6.55 mm below (r7: F at y .097639 inked to .091085). r7 also
# dropped F a further 8 mm, which put that ink 2.9 mm under FRONT's cell;
# undropped, F's value stands 2.2 mm under the outline, 7.8 mm under the heel.
TEXT_BESIDE_M = 0.022
TEXT_ABOVE_M = 0.006
INK_BELOW_M = 0.008
# A span too short for its text and arrows draws them outside, the dimension
# line running 6.35 mm past each witness (r3). A ends on the knife and D
# .002 in past the top, so their lines can pass the outlines' 5.59 mm pads by
# ~0.8 and ~1.0 mm at 4:1: each view with a side lane keeps room past both
# ends of it.
ARROW_OVERSHOOT_M = 0.0015
_SIDE_INDEX = {"left": 0, "bottom": 1, "right": 2, "top": 3}


def supplier_margins() -> dict[str, tuple[float, float, float, float]]:
    """Each annotated view's (left, bottom, right, top) room, sides without a
    lane none: the views' own outline pads keep them off the cell edges."""
    plan = supplier_screw_lane_plan(
        SUPPLIER_REFERENCE_DIMENSIONS,
        planes=SUPPLIER_REFERENCE_PLANES,
        sides=SUPPLIER_REFERENCE_SIDES,
    )
    room_past = {
        "left": TEXT_BESIDE_M,
        "right": TEXT_BESIDE_M,
        "top": TEXT_ABOVE_M,
        "bottom": INK_BELOW_M,
    }
    margins: dict[str, list[float]] = {}
    for name, (side, offset) in plan.items():
        view = f"*{SUPPLIER_REFERENCE_PLANES.get(name, 'Front')}"
        room = margins.setdefault(view, [0.0] * 4)
        index = _SIDE_INDEX[side]
        room[index] = max(room[index], offset + room_past[side])
        if side in ("left", "right"):
            for end in ("bottom", "top"):
                index = _SIDE_INDEX[end]
                room[index] = max(room[index], ARROW_OVERSHOOT_M)
    return {
        view: (room[0], room[1], room[2], room[3]) for view, room in margins.items()
    }


def build(adapter: Any) -> dict[str, str]:
    supplier_checks = []
    callback_count = 0
    settled = False

    def supplier_dimensions(adapter, views_by_orientation):
        nonlocal callback_count
        callback_count += 1
        if callback_count != 1:
            raise RuntimeError("supplier dimensions callback must run exactly once")
        annotate_supplier_screw(
            adapter,
            views_by_orientation,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            formats=SUPPLIER_REFERENCE_FORMATS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
            settled_checks=supplier_checks,
        )

    def assert_supplier_dimensions_settled():
        nonlocal settled
        if settled or callback_count != 1 or len(supplier_checks) != 1:
            raise RuntimeError("supplier dimensions require exactly one settled proof")
        supplier_checks[0]()
        settled = True

    return build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions_settled,),
        supplier_margins=supplier_margins(),
        supplier_data=SUPPLIER_DATA,
        unit=part_drawing_unit(SPEC.artifact_stem),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
