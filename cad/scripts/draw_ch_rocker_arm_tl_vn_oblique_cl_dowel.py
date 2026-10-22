"""Create the purchased reference drawing for the oblique-trammel CL dowel."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any
from collections.abc import Callable

import _telemetry
from _com import _early_bound
from _drawing_dimensions import offset_dimension_text
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_pin_model import _cylinder_radii_mm
from _supplier_screw_dimensions import annotate_supplier_screw, assert_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
import ch_rocker_arm_tl_vn_oblique_cl_dowel_spec as part

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_cl_dowel"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "Ø6 X 20 M6 DOWEL PIN (DIN 6325)"

# Exact 6d68291fd native audit: the Front label ends at x125.3866 mm,
# beyond both its x103.412 dimension line and the x109.412 view outline.
# Top's full diameter/tolerance label ends at x141.9257, over witnesses at
# x112/118 and an outside-arrow tail starting at x105.65. Shelf the COMPLETE
# native text blocks left, following _supplier_chain_dimensions' width label.
# These shifts leave 3.0254 mm to Front's line and 3.7243 mm to Top's tail;
# text still fits the purchased cells. Keep all source references and bands.
# Fresh native ink/review must prove these predicted gaps after regeneration.
_REFERENCE_TEXT_SHIFTS_M = {
    "SupplierDowelLength": (-0.025, 0.0),
    "SupplierDowelDiameter": (-0.040, 0.0),
}


def _assert_supplier_text_positions(
    displays: dict[str, Any], positions: dict[str, tuple[float, float]]
) -> None:
    for name, expected in positions.items():
        display = _early_bound(displays[name], "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        actual = tuple(float(value) for value in annotation.GetPosition())
        if not bool(display.OffsetText) or len(actual) < 2 or not all(
            math.isclose(actual[index], value, rel_tol=0.0, abs_tol=1e-5)
            for index, value in enumerate(expected)
        ):
            raise RuntimeError(
                f"{name}: supplier text shelf did not persist: {actual!r} != {expected!r}"
            )


def _shelve_supplier_text(
    adapter: Any, displays: dict[str, Any]
) -> dict[str, tuple[float, float]]:
    annotations = []
    positions = {}
    for name, (dx, dy) in _REFERENCE_TEXT_SHIFTS_M.items():
        display = _early_bound(displays[name], "IDisplayDimension")
        if int(display.Type2) not in (2, 11, 12):
            raise RuntimeError(f"{name}: supplier text shelf requires a linear carrier")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        origin = tuple(float(value) for value in annotation.GetPosition())
        if len(origin) < 2 or not all(math.isfinite(value) for value in origin[:2]):
            raise RuntimeError(f"{name}: supplier text has no finite native position")
        positions[name] = (origin[0] + dx, origin[1] + dy)
        annotations.append(annotation)
    offset_dimension_text(adapter, annotations, positions)
    _assert_supplier_text_positions(displays, positions)
    return positions


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
        text_positions = _shelve_supplier_text(adapter, displays)

        def assert_references() -> None:
            fresh = assert_supplier_screw(
                adapter, views,
                dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
                formats=part.SUPPLIER_REFERENCE_FORMATS,
                planes=part.SUPPLIER_REFERENCE_PLANES,
                units=part.SUPPLIER_REFERENCE_UNITS,
            )
            _assert_supplier_bands(fresh)
            _assert_supplier_text_positions(fresh, text_positions)
            model = _early_bound(views["*Front"], "IView").ReferencedDocument
            radii = _cylinder_radii_mm(model, 1, label=part.SKU)
            if not math.isclose(2.0 * max(radii), part.DIA, rel_tol=0.0, abs_tol=1e-6):
                raise RuntimeError("91595A452: nominal OD differs from the real cylinder")

        proofs.append(assert_references)

    def assert_supplier_dimensions() -> None:
        if callback_count != 1 or len(proofs) != 1:
            raise RuntimeError("91595A452: supplier references omitted or repeated")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=supplier_dimensions,
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
