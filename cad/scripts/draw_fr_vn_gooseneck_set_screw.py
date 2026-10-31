"""Create the purchased reference drawing for the gooseneck set screw.

The package declares ``drawing_unit: in``: the sheet, its TOL_* rows and the
source part print decimal inch. The McMaster 91410A540 sizes stay supplier
references in the supplier's own form: fractional head width and height,
decimal length and thread diameter, each labelled ``in``. The diameter/thread
text uses a measured native shelf, preserving the source value and physical
witness stations. A post-fit translation aligns the actual FRONT/RIGHT model
origins without changing the model or calibrated view scales; placement and
alignment are required again after the final rebuild.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any
from math import isfinite

from solidworks_mcp.adapters.solidworks.drawing import set_view_position

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_projection import model_point_in_view
from _drawing_common import rebuild_drawing
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
# The sheet's own registry package; its drawing_unit selects the sheet units.
PACKAGE = "fr-vn-gooseneck-set-screw"
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "1/4-20 x 3/4 SQUARE HEAD SET SCREW, CUP POINT"
# Text-only movement: keep the model-owned diameter, thread and witness span.
TEXT_SHELVES = {"SupplierThreadDiameter": ("horizontal", "right")}
SUPPLIER_MARGINS = supplier_screw_margins(
    SUPPLIER_REFERENCE_DIMENSIONS,
    planes=SUPPLIER_REFERENCE_PLANES,
    sides=SUPPLIER_REFERENCE_SIDES,
)


def _legacy_text_shelves():
    """Translate the recipe's axis names only at the legacy helper boundary."""
    return {
        name: (axis == "horizontal", side)
        for name, (axis, side) in TEXT_SHELVES.items()
    }


def _align_right_origin(adapter: Any, views: dict[str, Any]):
    """Translate RIGHT.Y only, retaining all other native placement state."""
    before = {}
    for name, view in views.items():
        position = tuple(float(value) for value in view.Position)
        scale = tuple(float(value) for value in view.ScaleRatio)
        angle = float(view.Angle)
        if (
            len(position) != 2
            or len(scale) != 2
            or not all(isfinite(value) for value in (*position, *scale, angle))
        ):
            raise RuntimeError(f"gooseneck {name}: unreadable fitted view placement")
        before[name] = (
            position,
            scale,
            angle,
            str(view.GetReferencedModelName()),
            str(view.ReferencedConfiguration),
            str(view.GetOrientationName()),
        )
    front_origin = model_point_in_view(
        adapter, views["*Front"], (0.0, 0.0, 0.0), label="gooseneck Front fitted origin"
    )
    right_origin = model_point_in_view(
        adapter, views["*Right"], (0.0, 0.0, 0.0), label="gooseneck Right fitted origin"
    )
    if not all(isfinite(value) for value in (*front_origin, *right_origin)):
        raise RuntimeError("gooseneck alignment: unreadable projected model origins")
    right_position = before["*Right"][0]
    target = (right_position[0], right_position[1] + front_origin[1] - right_origin[1])
    if not set_view_position(adapter, views["*Right"], *target, move_children=False):
        raise RuntimeError("gooseneck alignment: native RIGHT translation failed")
    rebuild_drawing(adapter, label="align gooseneck RIGHT model origin")

    def settled():
        for name, view in views.items():
            position, scale, angle, source, configuration, orientation = before[name]
            expected = target if name == "*Right" else position
            actual = tuple(float(value) for value in view.Position)
            if (
                len(actual) != 2
                or not all(isfinite(value) for value in actual)
                or any(abs(a - b) > 1e-8 for a, b in zip(actual, expected, strict=True))
                or tuple(view.ScaleRatio) != scale
                or float(view.Angle) != angle
                or str(view.GetReferencedModelName()) != source
                or str(view.ReferencedConfiguration) != configuration
                or str(view.GetOrientationName()) != orientation
            ):
                raise RuntimeError(
                    f"gooseneck {name}: native placement/source/scale drift"
                )
        _assert_projection_alignment(adapter, views)

    settled()
    return settled


def _assert_projection_alignment(adapter: Any, views: dict[str, Any]) -> None:
    front, right = views["*Front"], views["*Right"]
    origins = [
        model_point_in_view(
            adapter, view, (0.0, 0.0, 0.0), label=f"gooseneck {name} model origin"
        )
        for name, view in (("Front", front), ("Right", right))
    ]
    if (
        not all(isfinite(value) for origin in origins for value in origin)
        or abs(origins[0][1] - origins[1][1]) > 1e-6
        or origins[1][0] <= origins[0][0]
        or tuple(front.ScaleRatio) != tuple(right.ScaleRatio)
    ):
        raise RuntimeError(
            "gooseneck Front/Right model origins are not third-angle aligned"
        )


async def build(adapter: Any) -> dict[str, str]:
    supplier_checks = []
    callback_count = 0
    settled = False
    shelf_stations = {}
    supplier_views = {}

    def supplier_dimensions(adapter, views_by_orientation):
        nonlocal callback_count
        callback_count += 1
        if callback_count != 1:
            raise RuntimeError("supplier dimensions callback must run exactly once")
        supplier_views.update(views_by_orientation)
        _assert_projection_alignment(adapter, supplier_views)
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
        shelf_stations.update(
            shelve_supplier_text(adapter, displays, _legacy_text_shelves())
        )

    def assert_supplier_dimensions_settled():
        nonlocal settled
        if settled or callback_count != 1 or len(supplier_checks) != 1:
            raise RuntimeError("supplier dimensions require exactly one settled proof")
        displays = supplier_checks[0]()
        assert_supplier_shelves(
            adapter, displays, _legacy_text_shelves(), shelf_stations
        )
        _assert_projection_alignment(adapter, supplier_views)
        settled = True

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions_settled,),
        supplier_margins=SUPPLIER_MARGINS,
        view_placement=_align_right_origin,
        package_name=PACKAGE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
