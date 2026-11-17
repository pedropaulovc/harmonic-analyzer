"""Create the specification-control sheet for the strap fixture's edge clamp.

MHA-CH-13-TL-VN-50 is a Mitee-Bite Pitbull 26000 with the #4-40 x 3/8 socket
head cap screw it is supplied with (tier 2, ASME Y14.24 specification
control): the shared purchased-part sheet's Front/Top/Right/Isometric views
of the installed clamp, the catalogue's lettered sizes A, B, C, D and F and
the screw's 4-40 major as native reference dimensions from the part's hidden
supplier references, and the catalogue's operating data (torque, holding
force, throw, package, O-ring) in the footer. The catalogue governs; the
views are reference.

Front is the plan (part Z toward the viewer: A, C and F); Top looks at the
knife, third-angle above Front, so the clamp's base is up (B, D and the 4-40
chord on the screw's tip).
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
from _supplier_screw_layout import supplier_screw_margins
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
        supplier_margins=supplier_screw_margins(
            SUPPLIER_REFERENCE_DIMENSIONS,
            planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
        ),
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
