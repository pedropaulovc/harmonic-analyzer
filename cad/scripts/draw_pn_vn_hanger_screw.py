"""Create the purchased reference drawing for the hanger screw."""

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
from _mcmaster_93075a199 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_SIDES,
    SUPPLIER_REFERENCE_FORMATS,
)


SPEC = DRAWINGS_BY_NAME["pn_vn_hanger_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#8-32 x 1 HEX HEAD SCREW, FULLY THREADED"
# The 1 in screw stands along Top's height. With the standard 64 mm Top row
# and default 20 mm reserves its native outline only fit at 1:8 (dabcd16 fit
# events: Top 68.1 mm tall at 2:1). The tall Top row with thin reserves on
# the free bottom sides holds Front/Top/Right at 2:1.
VIEW_LAYOUT = "tall_top"
SUPPLIER_MARGINS = supplier_screw_margins(
    SUPPLIER_REFERENCE_DIMENSIONS,
    planes=SUPPLIER_REFERENCE_PLANES,
    sides=SUPPLIER_REFERENCE_SIDES,
)
SUPPLIER_MARGINS["*Top"] = (0.026, 0.006, 0.026, 0.020)
SUPPLIER_MARGINS["*Front"] = (0.020, 0.006, 0.020, 0.026)
# Texts wider than their short spans shelve past their own witnesses; the
# 1 in length keeps its centred text.
SHELVES = {
    "SupplierHeadHeight": (False, "left"),
    "SupplierHeadWidth": (True, "right"),
    "SupplierThreadDiameter": (True, "right"),
}


def _origin_offset(adapter: Any, front: Any, view: Any, axis: int, name: str) -> float:
    """Sheet coordinate of FRONT's projected model origin less ``view``'s."""
    origin = (0.0, 0.0, 0.0)
    front_at = model_point_in_view(adapter, front, origin, label="hanger screw Front origin")
    view_at = model_point_in_view(adapter, view, origin, label=f"hanger screw {name} origin")
    return front_at[axis] - view_at[axis]


def _align_to_front(adapter: Any, views: dict[str, Any]):
    """FRONT's lopsided reserves shift it within its cell; move TOP across and
    RIGHT vertically so all three project from one model origin (third angle)."""
    front = views["*Front"]
    moves = (("*Top", 0), ("*Right", 1))
    for name, axis in moves:
        view = views[name]
        position = [float(value) for value in view.Position]
        position[axis] += _origin_offset(adapter, front, view, axis, name)
        if not set_view_position(adapter, view, *position, move_children=False):
            raise RuntimeError(f"hanger screw {name}: native view translation failed")
    rebuild_drawing(adapter, label="align hanger screw Top/Right with Front")

    def assert_aligned():
        for name, axis in moves:
            if abs(_origin_offset(adapter, front, views[name], axis, name)) > 1e-6:
                raise RuntimeError(f"hanger screw {name} is off Front's projection axis")

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
        adapter, SPEC, item=ITEM,
        view_layout=VIEW_LAYOUT,
        supplier_margins=SUPPLIER_MARGINS,
        supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions_settled,),
        view_placement=_align_to_front,
        unit=part_drawing_unit("pn-vn-hanger-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
