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
import math
import sys
from typing import Any

import _telemetry
from _com import _early_bound
from _drawing_common import rebuild_drawing
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

# A horizontal reference prints its value and letter as two lines (~10.2 mm)
# above its dimension line. On FRONT's bottom lane, 6 mm under the outline's
# 5.6 mm pad, F's text would stand ~1.6 mm under the heel; dropping the whole
# dimension 8 mm leaves ~4 mm of paper between its text and the outline.
F_DROP_M = 0.008
# name -> (dx, dy) sheet metres, applied to the whole dimension before the
# purchased builder shelves struck text (the pivot screw's lane moves).
LANE_MOVES = {"SupplierF": (0.0, -F_DROP_M)}
# Pre-fit room past each lane, sheet metres. A vertical reference's text is
# ~11.2 mm wide: centred on its lane, or (D, a 7.6 mm span at 4:1) shelved
# past its witnesses' ends, ~14 mm out. A top lane's two text lines stand
# above its line; a bottom lane's sit between its line and the view, so only
# the line, arrows and witness overshoot pass it.
TEXT_BESIDE_M = 0.018
TEXT_ABOVE_M = 0.012
LINE_BELOW_M = 0.002
_SIDE_INDEX = {"left": 0, "bottom": 1, "right": 2, "top": 3}


def supplier_margins() -> dict[str, tuple[float, float, float, float]]:
    """Each annotated view's (left, bottom, right, top) room, sides without a
    lane none: the views' own outline pads keep them off the cell edges."""
    plan = supplier_screw_lane_plan(
        SUPPLIER_REFERENCE_DIMENSIONS,
        planes=SUPPLIER_REFERENCE_PLANES,
        sides=SUPPLIER_REFERENCE_SIDES,
    )
    margins: dict[str, list[float]] = {}
    for name, (side, offset) in plan.items():
        view = f"*{SUPPLIER_REFERENCE_PLANES.get(name, 'Front')}"
        room = margins.setdefault(view, [0.0] * 4)
        _, drop = LANE_MOVES.get(name, (0.0, 0.0))
        if side in ("left", "right"):
            need = offset + TEXT_BESIDE_M
        elif side == "top":
            need = offset + TEXT_ABOVE_M
        else:
            need = offset - drop + LINE_BELOW_M
        room[_SIDE_INDEX[side]] = max(room[_SIDE_INDEX[side]], need)
    return {
        view: (room[0], room[1], room[2], room[3]) for view, room in margins.items()
    }


def _move_lanes(adapter: Any, displays: dict[str, Any]) -> None:
    """Move each whole dimension (line and text) by its sheet offset."""
    targets = {}
    for name, (dx, dy) in LANE_MOVES.items():
        display = _early_bound(displays[name], "IDisplayDimension")
        # A model annotation may inherit offset mode; move the line, not text alone.
        display.OffsetText = False
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        x, y, _z = (float(value) for value in annotation.GetPosition())
        targets[name] = (annotation, (x + dx, y + dy))
        if not annotation.SetPosition2(*targets[name][1], 0.0):
            raise RuntimeError(f"26000: failed to move {name} to its lane")
    rebuild_drawing(adapter, label="26000 supplier lanes")
    for name, (annotation, target) in targets.items():
        moved = tuple(float(value) for value in annotation.GetPosition())[:2]
        if not all(
            math.isclose(a, b, rel_tol=0.0, abs_tol=5e-4)
            for a, b in zip(moved, target, strict=True)
        ):
            raise RuntimeError(f"26000: {name} lane read back at {moved!r}")


def build(adapter: Any) -> dict[str, str]:
    supplier_checks = []
    callback_count = 0
    settled = False

    def supplier_dimensions(adapter, views_by_orientation):
        nonlocal callback_count
        callback_count += 1
        if callback_count != 1:
            raise RuntimeError("supplier dimensions callback must run exactly once")
        displays = annotate_supplier_screw(
            adapter,
            views_by_orientation,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            formats=SUPPLIER_REFERENCE_FORMATS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
            settled_checks=supplier_checks,
        )
        _move_lanes(adapter, displays)

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
