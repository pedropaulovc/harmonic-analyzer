"""Create the modified purchased drawing for the oblique-trammel left clamp screw.

The screw is cut to fit at assembly (TL-21's receiver is blind): the solid is
the installed screw, its length a CUT TO FIT reference, and the as-supplied
3/4 in a separate stock witness that lands on the uncut tip drawn in phantom
(the TL-VN-64 carriage-screw sheet's idiom).  The catalogue sizes print as
supplier references; the cut end's chamfer prints from the part's own
driving, toleranced ``TipChamferProfile`` controls (the transgear pivot
screw's modified-stock idiom), re-read on the settled sheet.
"""

from __future__ import annotations

import argparse
import math
import sys
from functools import partial
from typing import Any

import _telemetry
from solidworks_mcp.adapters.solidworks.drawing import dimension_name
from _com import _early_bound
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_common import rebuild_drawing
from _drawing_dimensions import offset_dimension_text, set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _purchased_title_fit import fit_purchased_title_block
from _stock_trim_drawing import verify_machining_controls
from _supplier_screw_dimensions import _supplier_top_record, annotate_supplier_screw
from _drawing_projection import model_points_in_view
from _supplier_screw_layout import supplier_screw_margins, supplier_top_text_geometry
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
from _transgear_zone_line import require_placed, sketch_lines
import ch_rocker_arm_tl_vn_oblique_left_clamp_screw_spec as supplier


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_left_clamp_screw"]
# The footer's ITEM row: the fastener table's callout for the screw.
ITEM = "#10-24 X 3/4 LOW-HEAD SHCS"
VIEW_LAYOUT = "supplier_top"
# Each text shelves past its own witnesses: the 3/4 stock length and its
# qualifier fully left of the screw, the cut length and CUT TO FIT fully right
# of it (the carriage-screw sheet's shelves).  The Ø texts keep the screw
# family's right-hand shelves.
SHELVES = {
    "SupplierLength": (False, "left"),
    "CutLength": (False, "right"),
    "SupplierHeadHeight": (False, "left"),
    "SupplierThreadDiameter": (True, "right"),
    "SupplierHeadDiameter": (True, "right"),
    "SupplierDriveWidth": (True, "right"),
}
# swDimensionArrowsSide_e.swDimArrowsInside: both lengths keep their arrows
# inside their spans, so no outside tail strikes the head-height text.
_DIM_ARROWS_INSIDE = 0
ARROWS_INSIDE = ("SupplierLength", "CutLength")
# The 3/32 low head is shorter than its text, so the head-height shelf rises
# above the head's top witness.
LIFTED = "SupplierHeadHeight"
# Front and Top reserve the same left/right space, so the fit keeps them on
# one projection line: left, the stock-length lane and its qualifier; right,
# the cut length's lane and its text.
_SIDE_ROOM = (0.082, 0.036)
# Front also reserves room under the uncut tip for the cut-end chamfer's
# five-row text (value, band and its four-row callout).
_CUT_END_TEXT_ROOM = 0.042


def _margins() -> dict[str, tuple[float, float, float, float]]:
    margins = supplier_screw_margins(
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
        sides=supplier.SUPPLIER_REFERENCE_SIDES,
    )
    left, right = _SIDE_ROOM
    return {
        name: (
            left,
            max(bottom, _CUT_END_TEXT_ROOM) if name == "*Front" else bottom,
            right,
            top,
        )
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
    # GetAnnotation: VT_DISPATCH; GetPosition: VT_VARIANT (x, y, z) or None;
    # SetPosition2: VT_BOOL.  Tested by identity, never by truth.
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"{LIFTED}: display dimension has no annotation")
    dy = CLEAR_GAP_M + PLACE_SETTLE_M - _lift_clearance(_measure(adapter, display))
    position = annotation.GetPosition()
    if position is None:
        raise RuntimeError(f"{LIFTED}: annotation position is unreadable")
    x, y, _z = (float(value) for value in position)
    if annotation.SetPosition2(x, y + max(dy, 0.0), 0.0) is not True:
        raise RuntimeError(f"{LIFTED}: failed to lift its text above the head")
    rebuild_drawing(adapter, label="left clamp screw head-height text lifted")


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
# (swLineStyles_e.swLinePHANTOM, thin): the stock witness's lower extension
# lands on its end, not in empty space.
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
        label="left clamp screw uncut tip",
    )
    sheet_ends = {key: (sheet[2 * i], sheet[2 * i + 1]) for i, key in enumerate(keys)}
    lines = sketch_lines(
        adapter,
        front,
        sheet_ends,
        style=_PHANTOM_LINE_STYLE,
        width=_THIN_LINE_WEIGHT,
        label="left clamp screw uncut tip",
    )
    rebuild_drawing(adapter, label="left clamp screw uncut tip in phantom")
    _assert_uncut_tip(adapter, lines, stage="drawn")
    return lines


def _assert_uncut_tip(adapter: Any, lines: Any, *, stage: str) -> None:
    require_placed(
        adapter,
        lines,
        style=_PHANTOM_LINE_STYLE,
        width=_THIN_LINE_WEIGHT,
        label="left clamp screw uncut tip",
        stage=stage,
    )


# The cut end's controls (sheet metres from their projected model points).
# The chamfer is cut on the screw's left (-X) silhouette, so its axial length's
# dimension line stands just left of the major, inside the stock-length lane,
# and its text leaves on a leader to the lower left, under the uncut tip's end
# and clear of the thread Ø's bottom lane; the 45 deg text sits on the angle's
# bisector, outside the cut wedge.
_CHAMFER_LINE_GAP = 0.005
_CHAMFER_TEXT_OFFSET = (-0.034, -0.016)
_ANGLE_TEXT_RADIUS = 0.008
EXPECTED_CONTROLS = {
    "ChamferLength": (
        supplier.TIP_CHAMFER_LENGTH / 1000,
        supplier.TIP_CHAMFER_BAND[1] / 1000,
        supplier.TIP_CHAMFER_BAND[0] / 1000,
    ),
    "ChamferAngle": (
        math.radians(supplier.TIP_CHAMFER_ANGLE),
        -math.radians(supplier.TIP_CHAMFER_ANGLE_TOLERANCE),
        math.radians(supplier.TIP_CHAMFER_ANGLE_TOLERANCE),
    ),
}


def _verify_cut_end_controls(adapter: Any, annotations: list[Any]) -> None:
    verify_machining_controls(
        annotations,
        expected=EXPECTED_CONTROLS,
        tolerance_types=supplier.DIMENSION_TOLERANCE_TYPES,
        precision=supplier.DIMENSION_PRECISION,
    )
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        display = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        if str(display.GetText(4) or "").replace("\r", "") != (
            supplier.DIMENSION_CALLOUTS.get(name, "")
        ):
            raise RuntimeError(f"{name}: cut-end control callout did not persist")


def _cut_end_controls(adapter: Any, front: Any) -> list[Any]:
    """Import, place, call out and re-read the cut end's native controls."""
    r = supplier.DIMS.major_dia / 2000.0
    tip = -supplier.CUT_LENGTH / 1000.0
    chamfer = supplier.TIP_CHAMFER_LENGTH / 1000.0
    corner, vertex, stock_end = model_points_in_view(
        adapter,
        front,
        [
            (-r, tip + chamfer, 0.0),
            (-(r - chamfer), tip, 0.0),
            (-r, -supplier.DIMS.length / 1000.0, 0.0),
        ],
        label="left clamp screw cut-end chamfer",
    )
    bisector = math.radians(180.0 - supplier.TIP_CHAMFER_ANGLE / 2.0)
    annotations = curate_view_dimensions(
        adapter,
        front,
        keep={
            "ChamferLength": (corner[0] - _CHAMFER_LINE_GAP, (corner[1] + vertex[1]) / 2.0),
            "ChamferAngle": (
                vertex[0] + _ANGLE_TEXT_RADIUS * math.cos(bisector),
                vertex[1] + _ANGLE_TEXT_RADIUS * math.sin(bisector),
            ),
        },
        view_label="left clamp screw cut-end chamfer",
        dimensions_by_feature=supplier.DRAWING_DIMENSIONS,
    )
    names = sorted(dimension_name(adapter, annotation) for annotation in annotations)
    if names != sorted(EXPECTED_CONTROLS):
        raise RuntimeError(f"cut-end controls on *Front are {names}")
    set_dimension_callouts(adapter, annotations, supplier.DIMENSION_CALLOUTS)
    offset_dimension_text(
        adapter,
        annotations,
        {
            "ChamferLength": (
                corner[0] + _CHAMFER_TEXT_OFFSET[0],
                stock_end[1] + _CHAMFER_TEXT_OFFSET[1],
            )
        },
    )
    _verify_cut_end_controls(adapter, annotations)
    return annotations


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
            settled_checks=checks,
        )
        _set_arrows_inside(displays)
        stations = shelve_supplier_text(adapter, displays, SHELVES)
        _lift_head_height(adapter, displays)
        _assert_layout(adapter, displays, stations)
        tip = _phantom_uncut_tip(adapter, views["*Front"])
        controls = _cut_end_controls(adapter, views["*Front"])
        settled_references = checks[0]

        def assert_layout() -> None:
            _assert_layout(adapter, settled_references(), stations)
            _assert_uncut_tip(adapter, tip, stage="settled")
            _verify_cut_end_controls(adapter, controls)

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
        unit=part_drawing_unit("ch-rocker-arm-tl-vn-oblique-left-clamp-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
