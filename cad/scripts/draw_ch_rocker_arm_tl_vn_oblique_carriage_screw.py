"""Create the purchased reference drawing for the oblique-trammel carriage screw."""

from __future__ import annotations

import argparse
import sys
from functools import partial
from typing import Any

import _telemetry
from _com import _early_bound
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_common import rebuild_drawing
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _purchased_title_fit import fit_purchased_title_block
from _supplier_screw_dimensions import _supplier_top_record, annotate_supplier_screw
from _drawing_projection import model_points_in_view
from _supplier_screw_layout import supplier_screw_margins, supplier_top_text_geometry
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
from _transgear_zone_line import require_placed, sketch_lines
import ch_rocker_arm_tl_vn_oblique_carriage_screw_spec as supplier


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_carriage_screw"]
# The footer's ITEM row: the fastener table's callout for the screw.
ITEM = "M4 X 20 SHCS"
VIEW_LAYOUT = "supplier_top"
# Each text shelves past its own witnesses: the 20 mm stock length and its
# qualifier fully left of the screw, the cut length and CUT TO FIT fully right
# of it. Centred on their lines the two qualifiers crossed the thread and ran
# into each other ('LENGTHCUT TO FIT', machinist review 3/3 runs). The Ø texts
# keep the screw family's right-hand shelves.
SHELVES = {
    "SupplierLength": (False, "left"),
    "CutLength": (False, "right"),
    "SupplierHeadHeight": (False, "left"),
    "SupplierThreadDiameter": (True, "right"),
    "SupplierHeadDiameter": (True, "right"),
    "SupplierDriveWidth": (True, "right"),
}
# swDimensionArrowsSide_e.swDimArrowsInside: left smart, the two lengths drew
# their arrows outside, and the 20 mm's upper tail struck the (4 mm) text.
_DIM_ARROWS_INSIDE = 0
ARROWS_INSIDE = ("SupplierLength", "CutLength")
# The 4 mm head is shorter than its text, so the (4 mm) shelf rises above the
# head's top witness: at mid-head it sat on the 20 mm's underside witness.
LIFTED = "SupplierHeadHeight"
# Front and Top reserve the same left/right space, so the fit keeps them on
# one projection line: left, the 20 mm lane (14 mm out) and its 62 mm
# qualifier; right, the cut length's lane (6 mm) and its 24 mm text.
_SIDE_ROOM = (0.082, 0.036)


def _margins() -> dict[str, tuple[float, float, float, float]]:
    margins = supplier_screw_margins(
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
        sides=supplier.SUPPLIER_REFERENCE_SIDES,
    )
    left, right = _SIDE_ROOM
    return {
        name: (left, bottom, right, top)
        for name, (_left, bottom, _right, top) in margins.items()
    }


SUPPLIER_MARGINS = _margins()


def _measure(adapter: Any, display: Any) -> dict[str, Any]:
    return supplier_top_text_geometry(
        _supplier_top_record(adapter, display), horizontal=False
    )


def _lift_clearance(actual: dict[str, Any]) -> float:
    """Text bottom above the head's top witness (its higher arrow tip)."""
    return actual["text"].ymin - max(tip[1] for tip in actual["tips"])


def _set_arrows_inside(displays: dict[str, Any]) -> None:
    for name in ARROWS_INSIDE:
        display = _early_bound(displays[name], "IDisplayDimension")
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"{name} did not keep its arrows inside")


def _lift_head_height(adapter: Any, displays: dict[str, Any]) -> None:
    display = _early_bound(displays[LIFTED], "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    dy = CLEAR_GAP_M + PLACE_SETTLE_M - _lift_clearance(_measure(adapter, display))
    x, y, _z = (float(value) for value in annotation.GetPosition())
    if not annotation.SetPosition2(x, y + max(dy, 0.0), 0.0):
        raise RuntimeError(f"{LIFTED}: failed to lift its text above the head")
    rebuild_drawing(adapter, label="carriage screw head-height text lifted")


def _assert_layout(adapter: Any, displays: dict[str, Any], stations: Any) -> None:
    assert_supplier_shelves(adapter, displays, SHELVES, stations)
    for name in ARROWS_INSIDE:
        if int(_early_bound(displays[name], "IDisplayDimension").ArrowSide) != (
            _DIM_ARROWS_INSIDE
        ):
            raise RuntimeError(f"{name}: arrows left the span")
    if _lift_clearance(_measure(adapter, displays[LIFTED])) < CLEAR_GAP_M:
        raise RuntimeError(f"{LIFTED}: text is not clear above the head")


# The as-supplied screw's uncut tip, below the installed cut end, in phantom
# (swLineStyles_e.swLinePHANTOM, thin): the 20 mm stock witness's lower
# extension lands on its end, not in empty space (machinist review, 3/3 runs).
_PHANTOM_LINE_STYLE = 2
_THIN_LINE_WEIGHT = 0


def _uncut_tip_ends() -> dict[str, tuple[tuple[float, float, float], ...]]:
    """The uncut tip's sides and end in model metres (Front: x, y, 0)."""
    r = supplier.DIMS.major_dia / 2000.0
    cut, stock = -supplier.CUT_LENGTH / 1000.0, -supplier.DIMS.length / 1000.0
    return {
        "left": ((-r, cut, 0.0), (-r, stock, 0.0)),
        "end": ((-r, stock, 0.0), (r, stock, 0.0)),
        "right": ((r, stock, 0.0), (r, cut, 0.0)),
    }


def _phantom_uncut_tip(adapter: Any, front: Any) -> Any:
    model_ends = _uncut_tip_ends()
    keys = list(model_ends)
    sheet = model_points_in_view(
        adapter,
        front,
        [point for key in keys for point in model_ends[key]],
        label="carriage screw uncut tip",
    )
    sheet_ends = {key: (sheet[2 * i], sheet[2 * i + 1]) for i, key in enumerate(keys)}
    lines = sketch_lines(
        adapter,
        front,
        sheet_ends,
        style=_PHANTOM_LINE_STYLE,
        width=_THIN_LINE_WEIGHT,
        label="carriage screw uncut tip",
    )
    rebuild_drawing(adapter, label="carriage screw uncut tip in phantom")
    _assert_uncut_tip(adapter, lines, stage="drawn")
    return lines


def _assert_uncut_tip(adapter: Any, lines: Any, *, stage: str) -> None:
    require_placed(
        adapter,
        lines,
        style=_PHANTOM_LINE_STYLE,
        width=_THIN_LINE_WEIGHT,
        label="carriage screw uncut tip",
        stage=stage,
    )


async def build(adapter: Any) -> dict[str, str]:
    checks = []

    def supplier_dimensions(adapter: Any, views: Any) -> None:
        if checks:
            raise RuntimeError("supplier reference callback repeated")
        displays = annotate_supplier_screw(
            adapter,
            views,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=supplier.SUPPLIER_REFERENCE_FORMATS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
            units=supplier.SUPPLIER_REFERENCE_UNITS,
            settled_checks=checks,
        )
        _set_arrows_inside(displays)
        stations = shelve_supplier_text(adapter, displays, SHELVES)
        _lift_head_height(adapter, displays)
        _assert_layout(adapter, displays, stations)
        tip = _phantom_uncut_tip(adapter, views["*Front"])
        settled_references = checks[0]

        def assert_layout() -> None:
            _assert_layout(adapter, settled_references(), stations)
            _assert_uncut_tip(adapter, tip, stage="settled")

        checks.append(assert_layout)

    def assert_supplier_dimensions() -> None:
        if len(checks) != 2:
            raise RuntimeError("supplier references omitted or repeated")
        checks[1]()

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        cut_to_suit=True,
        title_block_setup=partial(
            fit_purchased_title_block, spec=SPEC, material_property="Material"
        ),
        view_layout=VIEW_LAYOUT,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_supplier_dimensions,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
