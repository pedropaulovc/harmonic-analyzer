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
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _supplier_pin_model import _cylinder_radii_mm
from _supplier_screw_dimensions import annotate_supplier_screw, assert_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
import ch_rocker_arm_tl_vn_oblique_cl_dowel_spec as part

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_cl_dowel"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "Ø6 X 20 M6 DOWEL PIN (DIN 6325)"


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
            raise RuntimeError("91595A452: repeated supplier dimension callback")
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

        def assert_references() -> None:
            fresh = assert_supplier_screw(
                adapter, views,
                dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
                formats=part.SUPPLIER_REFERENCE_FORMATS,
                planes=part.SUPPLIER_REFERENCE_PLANES,
                units=part.SUPPLIER_REFERENCE_UNITS,
            )
            _assert_supplier_bands(fresh)
            model = _early_bound(views["*Front"], "IView").ReferencedDocument
            radii = _cylinder_radii_mm(model, 1, label=part.SKU)
            if not math.isclose(2.0 * max(radii), part.DIA, rel_tol=0.0, abs_tol=1e-6):
                raise RuntimeError("91595A452: nominal OD differs from the real cylinder")

        proofs.append(assert_references)

    def assert_supplier_dimensions() -> None:
        if callback_count != 1 or len(proofs) != 1:
            raise RuntimeError("91595A452: supplier references omitted or repeated")
        proofs[0]()

    # The 18-character registry number overruns the template's DWG. NO.
    # cell into REV; fit it there, measured.
    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, number_fit=NumberFit.SHRINK_TO_CELL,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=supplier_screw_margins(
            part.SUPPLIER_REFERENCE_DIMENSIONS,
            planes=part.SUPPLIER_REFERENCE_PLANES,
            sides=part.SUPPLIER_REFERENCE_SIDES,
        ),
        settled_checks=(assert_supplier_dimensions,),
        supplier_data=part.SUPPLIER_DATA,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
