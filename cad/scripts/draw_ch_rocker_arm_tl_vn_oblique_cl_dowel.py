"""Create the purchased reference drawing for the oblique-trammel CL dowel."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any
from collections.abc import Callable

import _telemetry
from _com import _early_bound
from _session import run_build
from _drawing_centerline import add_view_centerline
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _supplier_pin_model import _cylinder_radii_mm
from _supplier_screw_dimensions import annotate_supplier_screw, assert_supplier_screw
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
from _part_properties import part_drawing_unit
import ch_rocker_arm_tl_vn_oblique_cl_dowel_spec as part
from _machinist_review_mode import MachinistReviewMode

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_cl_dowel"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "1/4 X 1 ALLOY STEEL DOWEL PIN (ASME B18.8.2)"
# Machinist review mr1 (rule 14): centred on their short spans, the texts ran
# across their own witnesses and, for the 1 in length, over the pin. Each now
# shelves past its outer witness on the Front: the diameter right of its
# bottom lane, the length left of its lane. Only the Front is annotated; the
# projection fit keeps the Top on its column.
SHELVES = {
    "SupplierDowelDiameter": (True, "right"),
    "SupplierDowelLength": (False, "left"),
}
SUPPLIER_MARGINS = {"*Front": (0.070, 0.026, 0.065, 0.020)}


def _assert_supplier_bands(displays: dict[str, Any]) -> None:
    for name, display in displays.items():
        display = _early_bound(display, "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        band = part.SUPPLIER_REFERENCE_TOLERANCES_MM.get(name)
        if band is None:
            if int(tolerance.Type) != 0:
                raise RuntimeError(f"{name}: unsourced supplier length tolerance")
            continue
        lower, upper = band
        if int(tolerance.Type) != 2 or not all(
            math.isclose(actual, expected / 1000.0, rel_tol=0.0, abs_tol=1e-12)
            for actual, expected in (
                (float(tolerance.GetMinValue()), lower),
                (float(tolerance.GetMaxValue()), upper),
            )
        ):
            raise RuntimeError(f"{name}: supplier diameter band changed")
        if int(display.GetPrimaryTolPrecision2()) != part.SUPPLIER_REFERENCE_FORMATS[name][0]:
            raise RuntimeError(f"{name}: supplier diameter tolerance precision changed")


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []
    callback_count = 0

    def supplier_dimensions(adapter: Any, views: dict[str, Any]) -> None:
        nonlocal callback_count
        callback_count += 1
        if callback_count != 1:
            raise RuntimeError(f"{part.SKU}: repeated supplier dimension callback")
        displays = annotate_supplier_screw(
            adapter, views,
            dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=part.SUPPLIER_REFERENCE_FORMATS,
            starts=part.SUPPLIER_REFERENCE_STARTS,
            planes=part.SUPPLIER_REFERENCE_PLANES,
            sides=part.SUPPLIER_REFERENCE_SIDES,
            units=part.SUPPLIER_REFERENCE_UNITS,
        )
        _assert_supplier_bands(displays)
        stations = shelve_supplier_text(adapter, displays, SHELVES)
        # The length's line lies on the silhouette, so the Front carries the
        # axis as a native centerline, picked on the pin face at mid-length
        # (frame: axis +Y from the chamfered end).
        front = views["*Front"]
        add_view_centerline(
            adapter, front, label="CL dowel FRONT axis",
            face_xy=model_point_in_view(
                adapter, front, (0.0, part.LENGTH / 2000.0, part.DIA / 2000.0),
                label="CL dowel FRONT face",
            ),
        )

        def assert_references() -> None:
            fresh = assert_supplier_screw(
                adapter, views,
                dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
                formats=part.SUPPLIER_REFERENCE_FORMATS,
                planes=part.SUPPLIER_REFERENCE_PLANES,
                units=part.SUPPLIER_REFERENCE_UNITS,
            )
            _assert_supplier_bands(fresh)
            assert_supplier_shelves(adapter, fresh, SHELVES, stations)
            model = _early_bound(views["*Front"], "IView").ReferencedDocument
            radii = _cylinder_radii_mm(model, 1, label=part.SKU)
            if not math.isclose(2.0 * max(radii), part.DIA, rel_tol=0.0, abs_tol=1e-6):
                raise RuntimeError(f"{part.SKU}: nominal OD differs from the real cylinder")

        proofs.append(assert_references)

    def assert_supplier_dimensions() -> None:
        if callback_count != 1 or len(proofs) != 1:
            raise RuntimeError(f"{part.SKU}: supplier references omitted or repeated")
        proofs[0]()

    # The 18-character registry number overruns the template's DWG. NO.
    # cell into REV; fit it there, measured.
    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, number_fit=NumberFit.SHRINK_TO_CELL,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_supplier_dimensions,),
        supplier_data=part.SUPPLIER_DATA,
        unit=part_drawing_unit("ch-rocker-arm-tl-vn-oblique-cl-dowel"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
