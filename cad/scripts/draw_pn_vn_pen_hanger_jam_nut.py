"""Create the purchased reference drawing for the pen-hanger jam nut (MHA-PN-VN-55, McMaster 90760A009)."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _com import _early_bound
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_nut_drawing import add_supplier_nut_dimensions
from _supplier_screw_layout import supplier_screw_margins
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
import pn_vn_pen_hanger_jam_nut_spec as supplier


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pn_vn_pen_hanger_jam_nut"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#8-32 THIN HEX JAM NUT"
# Shared Front budget includes the bottom nominal-major/thread callout and
# the physical AF fraction above Front. Margins are (left, bottom, right, top).
SUPPLIER_MARGINS = supplier_screw_margins(
    supplier.SUPPLIER_REFERENCE_DIMENSIONS,
    sides={"ThreadNominalMajor": "bottom"},
)
SUPPLIER_MARGINS["*Right"] = (0.008, 0.018, 0.008, 0.0)
# The three-line nominal-major callout, the ACROSS FLATS line and the .094 in
# height print as wide as or wider than their spans, struck by or touching
# their own witnesses (dabcd16 and c03368c reviews): shelve each text right,
# past its witnesses, at its own height.
SHELVES = {
    "ThreadNominalMajor": (True, "right"),
    "AcrossFlats": (True, "right"),
    "Height": (True, "right"),
}


def _supplier_dimensions(
    adapter: Any, views_by_orientation: dict[str, Any]
) -> Callable[[], None]:
    return add_supplier_nut_dimensions(
        adapter,
        views_by_orientation,
        across_flats_mm=supplier.ACROSS_FLATS,
        thickness_mm=supplier.THICKNESS,
        bore_diameter_mm=supplier.BORE_DIA,
        thread=supplier.THREAD,
        precision=supplier.DRAWING_REFERENCE_PRECISION,
        fraction_denominator=supplier.SUPPLIER_FRACTION_DENOMINATOR,
        reference_dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        reference_starts=supplier.SUPPLIER_REFERENCE_STARTS,
    )


def _shelf_displays(views: dict[str, Any]) -> dict[str, Any]:
    """FRONT's nominal-major chord and AF, and RIGHT's one height dimension."""

    def displays(name: str) -> list[tuple[str, Any]]:
        found = []
        display = _early_bound(views[name], "IView").GetFirstDisplayDimension6()
        while display is not None:
            display = _early_bound(display, "IDisplayDimension")
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            found.append((str(dimension.FullName).split("@")[0], display))
            display = display.GetNext5()
        return found

    front = displays("*Front")
    nominal = [d for name, d in front if name == "ThreadNominalMajor"]
    flats = [d for name, d in front if name != "ThreadNominalMajor"]
    height = [d for _, d in displays("*Right")]
    if len(nominal) != 1 or len(flats) != 1 or len(height) != 1:
        raise RuntimeError("pen-hanger jam nut: shelved references are not unique")
    return {
        "ThreadNominalMajor": nominal[0],
        "AcrossFlats": flats[0],
        "Height": height[0],
    }


async def build(adapter: Any) -> dict[str, str]:
    authored_checks: list[Callable[[], None]] = []
    stations: dict[str, Any] = {}
    shelved_views: dict[str, Any] = {}

    def supplier_dimensions(target: Any, views: dict[str, Any]) -> None:
        authored_checks.append(_supplier_dimensions(target, views))
        shelved_views.update(views)
        stations.update(shelve_supplier_text(target, _shelf_displays(views), SHELVES))

    def assert_settled() -> None:
        if len(authored_checks) != 1:
            raise RuntimeError("supplier nut annotations must be authored exactly once")
        authored_checks[0]()
        assert_supplier_shelves(
            adapter, _shelf_displays(shelved_views), SHELVES, stations
        )

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_settled,),
        unit=part_drawing_unit("pn-vn-pen-hanger-jam-nut"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
