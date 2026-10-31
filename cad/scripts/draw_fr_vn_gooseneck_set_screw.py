"""Create the purchased reference drawing for the gooseneck set screw."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import set_view_position

import _telemetry
from _session import run_build
from _drawing_common import rebuild_drawing
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
from _mcmaster_91410a540 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_FORMATS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_SIDES,
    SUPPLIER_REFERENCE_STARTS,
)


SPEC = DRAWINGS_BY_NAME["fr_vn_gooseneck_set_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "1/4-20 x 3/4 SQUARE HEAD SET SCREW, CUP POINT"
# The Ø/thread text is wider than the shank: shelve it right of its witnesses.
SHELVES = {"SupplierThreadDiameter": (True, "right")}


def _origin_drop(adapter: Any, front: Any, right: Any) -> float:
    """Sheet Y of FRONT's projected model origin less RIGHT's."""
    origin = (0.0, 0.0, 0.0)
    front_y = model_point_in_view(
        adapter, front, origin, label="gooseneck Front origin"
    )[1]
    right_y = model_point_in_view(
        adapter, right, origin, label="gooseneck Right origin"
    )[1]
    return front_y - right_y


def _align_right(adapter: Any, views: dict[str, Any]):
    """FRONT's lopsided supplier margins shift it within its cell; move RIGHT
    vertically so both project from the same model origin (third angle)."""
    front, right = views["*Front"], views["*Right"]
    x, y = (float(value) for value in right.Position)
    target_y = y + _origin_drop(adapter, front, right)
    if not set_view_position(adapter, right, x, target_y, move_children=False):
        raise RuntimeError("gooseneck Right: native view translation failed")
    rebuild_drawing(adapter, label="align gooseneck Right with Front")

    def assert_aligned():
        if abs(_origin_drop(adapter, front, right)) > 1e-6:
            raise RuntimeError("gooseneck Front/Right model origins are not aligned")

    assert_aligned()
    return assert_aligned


async def build(adapter: Any) -> dict[str, str]:
    supplier_checks = []
    callback_count = 0
    settled = False
    stations = {}

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
        stations.update(shelve_supplier_text(adapter, displays, SHELVES))

    def assert_supplier_dimensions_settled():
        nonlocal settled
        if settled or callback_count != 1 or len(supplier_checks) != 1:
            raise RuntimeError("supplier dimensions require exactly one settled proof")
        assert_supplier_shelves(adapter, supplier_checks[0](), SHELVES, stations)
        settled = True

    return await build_purchased_fastener_drawing(
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
        view_placement=_align_right,
        unit=part_drawing_unit("fr-vn-gooseneck-set-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
