"""Build the counter-spring lower anchor from McMaster 9490T1.

The single open routing eyebolt that hangs the master (counter) spring from the
summing lever's summation-anchor boss. It threads DIRECTLY into the #10-24 tap
through that boss (``summing_lever_spec.COUNTER_HOLE_SPEC``, sourced from this
same anchor record) -- no nut, no separate link ring.

The one supplier option this production part takes is LENGTH: the vendor's
58.7375 mm shank is cut back to the boss height it engages (19.05 mm, the
lever's ``ANCHOR_H``) with the 45 deg deburr restored at the new end, so the
thread ends at y -27.84475 and the factory thread phase is preserved.

The tracked diagnostic recipe is an exact geometric replay of the supplied
vendor SLDPRT and stays in the vendor's own frame -- eye centre at the origin,
eye plane in XY, shank axis along -Y, thread starting at y -8.79475.
``build_summing_assembly`` positions it; nothing here moves it.

Run (SolidWorks already open)::

    uv run python cad\\scripts\\build_boss_hook.py
"""

from __future__ import annotations

from functools import wraps
import math
import sys

from _common import _early_bound, _read_member, run_build
from _fastener_catalog import fastener
from _drawing_common import set_dimension_precision
from _stock_fastener import StockComponent, build_stock_fastener
from _drawing_marks import (
    _named_dimension,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
    set_dimension_symmetric_angular_tolerance,
)
from boss_hook_spec import (
    SHANK_LENGTH_MM,
    FINISHED_OVERALL_MM,
    FINISHED_OVERALL_TOLERANCE_MM,
    CHAMFER_WIDTH_MM,
    CHAMFER_WIDTH_TOLERANCE_MM,
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    DRAWING_DIMENSIONS,
    DIMENSION_PRECISION,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
)
from diagnostics.diag_build_9490T1 import build_9490T1
from stock_anchor_geom import ANCHOR_9490T1

PART_NAME = "boss-hook"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
ANCHOR = ANCHOR_9490T1


def _manufacturing_controls(adapter) -> None:
    """Tolerance and mark actual cutting dimensions before the stock helper saves."""
    clear_dimensions_for_drawing(adapter)
    for feature, name, nominal in (
        ("StockTrimProfile", "FinishedOverall", FINISHED_OVERALL_MM / 1000),
        ("StockDeburrProfile", "ChamferWidth", CHAMFER_WIDTH_MM / 1000),
        ("StockDeburrProfile", "ChamferAngle", math.radians(CHAMFER_ANGLE_DEG)),
    ):
        display, dimension = _named_dimension(adapter, feature, name)
        if int(dimension.DrivenState) != 2:
            raise RuntimeError(f"{name}@{feature} must control the cutting sketch")
        if not math.isclose(float(dimension.SystemValue), nominal, abs_tol=1e-9):
            raise RuntimeError(f"{name}@{feature}: modified stock nominal changed")
        set_dimension_precision(
            adapter,
            [_read_member(display, "GetAnnotation")],
            {name: DIMENSION_PRECISION[name]},
        )
    set_dimension_symmetric_tolerance(
        adapter, "StockTrimProfile", "FinishedOverall", FINISHED_OVERALL_TOLERANCE_MM
    )
    set_dimension_symmetric_tolerance(
        adapter, "StockDeburrProfile", "ChamferWidth", CHAMFER_WIDTH_TOLERANCE_MM
    )
    set_dimension_symmetric_angular_tolerance(
        adapter, "StockDeburrProfile", "ChamferAngle", CHAMFER_ANGLE_TOLERANCE_DEG
    )
    # General dimensions retain their numerical acceptance bands natively;
    # swTolGeneral omits the redundant printed band in favour of the title block.
    for feature, name, band in (
        ("StockTrimProfile", "FinishedOverall", FINISHED_OVERALL_TOLERANCE_MM / 1000),
        ("StockDeburrProfile", "ChamferAngle", math.radians(CHAMFER_ANGLE_TOLERANCE_DEG)),
    ):
        _, dimension = _named_dimension(adapter, feature, name)
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = 11  # swTolType_e.swTolGeneral
        if not tolerance.SetValues(-band, band):
            raise RuntimeError(f"{name}@{feature}: cannot retain general tolerance values")
        if (
            int(tolerance.Type) != 11
            or not math.isclose(float(tolerance.GetMinValue()), -band, abs_tol=1e-9)
            or not math.isclose(float(tolerance.GetMaxValue()), band, abs_tol=1e-9)
        ):
            raise RuntimeError(f"{name}@{feature}: general tolerance readback changed")
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )


@wraps(build_9490T1)
async def _modified_anchor(adapter, truth=None, **parameters):
    receipt = await build_9490T1(adapter, truth, **parameters)
    _manufacturing_controls(adapter)
    return receipt


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                ANCHOR.sku,
                _modified_anchor,
                parameters={"shank_length_mm": SHANK_LENGTH_MM},
            ),
        ),
        material=MATERIAL,
        # Shank axis = the vendor -Y axis through the eye centre (Front n Right),
        # the stable mate reference the old sketched part named "shank axis".
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
