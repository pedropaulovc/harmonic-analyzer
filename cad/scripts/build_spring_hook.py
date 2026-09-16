"""Build the channel-spring lower anchor from McMaster 9489T111.

Twenty of these routing eyebolts replace the old formed-wire J-hook. Each one
threads DIRECTLY into a #6-32 tap through the summing lever's coefficient plate
(``summing_lever_spec.HOLE_SPEC``, sourced from this same anchor record) and the
channel spring's lower eye links onto its eye. The SUPPLIED HEX NUT IS OMITTED:
the tapped plate is the nut, so the production part is the bolt body alone.

Two supplier options this production part takes -- the nut above and LENGTH: the
vendor's 19.05 mm shank is cut back to the neck plus 3.4925 mm of engaged thread
(``spring_hook_spec.SHANK_LENGTH_MM``, 6.6675 mm) with the 45 deg deburr
restored at the new end.  Instead of hanging 10.795 mm into the channel bank,
the cut end stops 1/16 in (``PLATE_RECESS_MM``) inside the plate -- adjustment
room for unscrewing each channel's anchor -- and the factory thread phase
survives.

The tracked diagnostic recipe is an exact geometric replay of the supplied
vendor SLDPRT and stays in the vendor's own frame -- eye centre at the origin,
eye plane in XY, shank axis along -Y, threads starting at y -9.525.
``build_channel_assembly`` positions it; nothing here moves it.

Run (SolidWorks already open)::

    uv run python cad\\scripts\\build_spring_hook.py
"""

from __future__ import annotations

from functools import wraps
import math
import sys

from _common import PANEL_BLACK, _early_bound, _read_member, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _drawing_marks import (
    _named_dimension,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
    set_dimension_symmetric_angular_tolerance,
)
from diagnostics.diag_build_9489T111 import build_9489T111
from spring_hook_spec import (
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
from stock_anchor_geom import ANCHOR_9489T111

PART_NAME = "spring-hook"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
ANCHOR = ANCHOR_9489T111

# The vendor ships 9489T111 with a captive hex nut; the anchor threads straight
# into the summing lever, so the nut is never installed and no nut geometry
# belongs in the SLDPRT -- and the trim below would cut through its seat.
NUT = "omitted"


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
        display = _early_bound(display, "IDisplayDimension")
        digits = DIMENSION_PRECISION[name]
        result = display.SetPrecision3(digits, -1, -1, -1)
        if (
            result is None
            or int(_read_member(display, "GetPrimaryPrecision2")) != digits
        ):
            raise RuntimeError(f"{name}@{feature}: native precision did not persist")
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
        (
            "StockDeburrProfile",
            "ChamferAngle",
            math.radians(CHAMFER_ANGLE_TOLERANCE_DEG),
        ),
    ):
        _, dimension = _named_dimension(adapter, feature, name)
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = 11  # swTolType_e.swTolGeneral
        if not tolerance.SetValues(-band, band):
            raise RuntimeError(
                f"{name}@{feature}: cannot retain general tolerance values"
            )
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


@wraps(build_9489T111)
async def _modified_anchor(adapter, truth=None, **parameters):
    receipt = await build_9489T111(adapter, truth, **parameters)
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
                parameters={"nut": NUT, "shank_length_mm": SHANK_LENGTH_MM},
            ),
        ),
        material=MATERIAL,
        color=PANEL_BLACK,  # black-oxide hardware
        # Shank axis = the vendor -Y axis through the eye centre (Front n Right),
        # the stable mate reference the old sketched part named "shank axis".
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
