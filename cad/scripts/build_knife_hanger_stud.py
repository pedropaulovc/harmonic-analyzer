"""Build the shortened knife-hanger bolt from McMaster 91247A720 stock."""

from __future__ import annotations

from functools import wraps
import math
import sys

from _common import _early_bound, _read_member, run_build
from _drawing_marks import (
    _named_dimension,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_angular_tolerance,
)
from _fastener_catalog import fastener
from _saved_part_guard import require_saved_drawing_properties
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_91247A720 import (
    GB_HH,
    GB_HW,
    GB_LEN,
    GB_MAJOR_R,
    GB_UNDERSIDE,
    GB_WASHER_T,
    build_91247A720,
)
from knife_hanger_stud_spec import (
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    CHAMFER_WIDTH_MM,
    DIMENSION_PRECISION,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FINISHED_UNDERHEAD_MM,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "knife-hanger-stud"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

HEAD_AF = GB_HW
HEAD_H = GB_HH
SHANK_DIA = 2.0 * GB_MAJOR_R
STOCK_SHANK_LEN = GB_LEN
SHANK_LEN = FINISHED_UNDERHEAD_MM
UNDERHEAD_LEN = FINISHED_UNDERHEAD_MM
UNDERHEAD_Y_MM = GB_UNDERSIDE - GB_WASHER_T
THREAD_TIP_Y_MM = UNDERHEAD_Y_MM - UNDERHEAD_LEN

# These are source-owned fit/readback values for the measured-stack assembly
# gate. The post-purchase cut's flat is the modeled thread-root radius.
THREAD_MAJOR_RADIUS_MM = GB_MAJOR_R
THREAD_TIP_ROOT_RADIUS_MM = THREAD_MAJOR_RADIUS_MM - CHAMFER_WIDTH_MM
THREAD_TIP_ROOT_DIAMETER_MM = 2.0 * THREAD_TIP_ROOT_RADIUS_MM
THREAD_TIP_CHAMFER_RADIAL_MM = CHAMFER_WIDTH_MM
THREAD_TIP_CHAMFER_AXIAL_MM = CHAMFER_WIDTH_MM
THREAD_TIP_CHAMFER_ANGLE_DEG = CHAMFER_ANGLE_DEG


def _clear_native_tolerance(adapter, feature: str, name: str) -> None:
    """Keep nominal controls free of fixed bands for sheet references."""
    _, dimension = _named_dimension(adapter, feature, name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 0  # swTolType_e.swTolNONE
    if int(tolerance.Type) != 0:
        raise RuntimeError(f"{name}@{feature}: native tolerance did not clear")


def _manufacturing_controls(adapter) -> None:
    """Set and mark the native trim and end-deburr controls before saving."""
    clear_dimensions_for_drawing(adapter)
    for feature, name, nominal in (
        ("StockTrimProfile", "FinishedOverall", FINISHED_UNDERHEAD_MM / 1000),
        ("StockDeburrProfile", "ChamferWidth", CHAMFER_WIDTH_MM / 1000),
        ("StockDeburrProfile", "ChamferAngle", math.radians(CHAMFER_ANGLE_DEG)),
    ):
        display, dimension = _named_dimension(adapter, feature, name)
        if int(dimension.DrivenState) != 2:
            raise RuntimeError(f"{name}@{feature} must control the cutting sketch")
        if not math.isclose(float(dimension.SystemValue), nominal, abs_tol=1e-9):
            raise RuntimeError(f"{name}@{feature}: modified stock nominal changed")
        display = _early_bound(display, "IDisplayDimension")
        digits = DIMENSION_PRECISION[name]
        result = display.SetPrecision3(digits, -1, -1, -1)
        if (
            result is None
            or int(_read_member(display, "GetPrimaryPrecision2")) != digits
        ):
            raise RuntimeError(f"{name}@{feature}: native precision did not persist")
    _clear_native_tolerance(adapter, "StockTrimProfile", "FinishedOverall")
    _clear_native_tolerance(adapter, "StockDeburrProfile", "ChamferWidth")
    set_dimension_symmetric_angular_tolerance(
        adapter, "StockDeburrProfile", "ChamferAngle", CHAMFER_ANGLE_TOLERANCE_DEG
    )
    _, dimension = _named_dimension(adapter, "StockDeburrProfile", "ChamferAngle")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    band = math.radians(CHAMFER_ANGLE_TOLERANCE_DEG)
    tolerance.Type = 11  # swTolType_e.swTolGeneral
    if not tolerance.SetValues(-band, band):
        raise RuntimeError("ChamferAngle@StockDeburrProfile: general tolerance rejected")
    if (
        int(tolerance.Type) != 11
        or not math.isclose(float(tolerance.GetMinValue()), -band, abs_tol=1e-9)
        or not math.isclose(float(tolerance.GetMaxValue()), band, abs_tol=1e-9)
    ):
        raise RuntimeError(
            "ChamferAngle@StockDeburrProfile: general tolerance readback changed"
        )
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


@wraps(build_91247A720)
async def _prepared_stud(adapter, truth=None, **parameters):
    """Build and author the post-purchase trim controls before the final save."""
    receipt = await build_91247A720(adapter, truth, **parameters)
    _manufacturing_controls(adapter)
    return receipt


async def build(adapter) -> dict[str, str]:
    artefacts = await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "91247A720",
                _prepared_stud,
                parameters={"finished_underhead_mm": FINISHED_UNDERHEAD_MM},
            ),
        ),
        material=MATERIAL,
    )
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
