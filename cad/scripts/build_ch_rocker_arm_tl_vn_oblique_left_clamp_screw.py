r"""Modified purchased MHA-CH-06-TL-VN-86 oblique-trammel left clamp screw: McMaster 92220A165.

The ``#10-24 X 3/4 LOW-HEAD SHCS`` (``ch_rocker_arm_tl_vn_oblique_left_clamp_screw_spec``) that holds the strap blank's outboard left tail down through the riser into TL-21's flat-bottom blind tap.
The stock recipe ``diagnostics/diag_build_92220A165.py`` builds the catalogue screw on
the 91251A family recipe (``diag_mcmaster_socket_head.build_socket_head``);
the recipe's standalone run is catalog-only (no replica gate, user ruling
2026-10-17).  Each screw is cut to fit at assembly (the receiver is blind),
so the recipe draws it at ``CUT_LENGTH`` under the head.

The cut end is then re-cut natively (``TipChamferProfile`` / ``TipChamfer``,
the transgear pivot screw's deburr recipe): a revolve cut whose driving axial
``ChamferLength`` and driving 45 deg ``ChamferAngle`` are the part's
manufacturing controls, toleranced, marked and read back here, so the sheet
prints them from the model.  The native chamfer contains the recipe's 0.75P
one, so the finished tip is the dimension's, not the recipe's.

Frame: screw axis +Y, head up, the bearing face (head underside) at y = 0,
the cut end at y = -CUT_LENGTH.  The axis is published as ``ScrewAxis``
(Front ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_left_clamp_screw.py
"""

from __future__ import annotations

import math
import sys
from functools import partial, wraps

from _check import check
from _com import _early_bound
from _dimensions import drive_dimension
from _drawing_marks import clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _fastener_catalog import fastener
from _feature_tree import _feature_by_name, name_last_feature
from _fit_deviations import deviations
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, add_line_chain, dimension_between, ensure_fully_defined
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from ch_rocker_arm_tl_vn_oblique_left_clamp_screw_spec import (
    CUT_LENGTH,
    DIMS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    SKU,
    TIP_CHAMFER_ANGLE,
    TIP_CHAMFER_ANGLE_TOLERANCE,
    TIP_CHAMFER_BAND,
    TIP_CHAMFER_FEATURE,
    TIP_CHAMFER_LENGTH,
    UNIT,
)
from diagnostics.diag_build_92220A165 import build_92220A165
from diagnostics.diag_mcmaster_lib import no_sketch_inference
import ch_rocker_arm_tl_vn_oblique_left_clamp_screw_spec as supplier

PART_NAME = "ch-rocker-arm-tl-vn-oblique-left-clamp-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def _tip_chamfer(adapter) -> None:
    """Re-cut the cut end's 45 deg chamfer from its native driving controls.

    Profile (Front, sketch x = model X, y = model Y), drawn on -X so the
    imported controls sit on the sheet's left, clear of the right lane's CUT
    TO FIT reference: the cutter's square outside the major plus the chamfer
    triangle, the hypotenuse from the major ``ChamferLength`` above the cut
    end down to the cut end face.
    After the equation is solved, select the completed sketch with mark 0 and
    its construction centreline with mark 4; create_revolve does not select
    them (``build_pd_vn_transgear_pivot_screw``'s recipe).
    """
    from solidworks_mcp.adapters.base import RevolveParameters
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    radius = DIMS.major_dia / 2.0
    tip = -CUT_LENGTH
    chamfer = TIP_CHAMFER_LENGTH
    with no_sketch_inference(adapter):
        check("create tip chamfer sketch", await adapter.create_sketch("Front"))
        lines = await add_line_chain(
            adapter,
            [
                (-(radius - chamfer), tip),
                (-(radius + chamfer), tip),
                (-(radius + chamfer), tip + chamfer),
                (-radius, tip + chamfer),
            ],
            close=True,
        )
        dims = SketchDims()
        for line, direction in zip(
            lines[:3], ("horizontal", "vertical", "horizontal"), strict=True
        ):
            check(
                "tip chamfer profile relation",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        await dimension_between(
            adapter,
            f"{lines[1]}.start",
            "origin",
            "horizontal_distance",
            radius + chamfer,
            "tip chamfer cutter outer radius",
        )
        dims.record("CutterRadius")
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            "origin",
            "vertical_distance",
            CUT_LENGTH,
            "cut end from the bearing face",
        )
        dims.record("CutEndFromBearing")
        await dimension_between(
            adapter,
            f"{lines[3]}.start",
            "origin",
            "horizontal_distance",
            radius,
            "stock major radius",
        )
        dims.record("StockMajorRadius")
        await dimension_between(
            adapter,
            f"{lines[3]}.start",
            f"{lines[3]}.end",
            "vertical_distance",
            chamfer,
            "tip chamfer axial length",
        )
        dims.record("ChamferLength")
        model = adapter.currentModel
        model.ClearSelection2(True)
        _select_sketch_entities(adapter, [lines[0], lines[3]], 0)
        display, status = _early_bound(
            model.Extension, "IModelDocExtension"
        ).AddSpecificDimension(
            -(radius + 2 * chamfer) / 1000, (tip + chamfer / 2) / 1000, 0, 3, 0
        )
        model.ClearSelection2(True)
        if display is None:
            raise RuntimeError(f"cannot create native tip-chamfer angle: {status}")
        display = _early_bound(display, "IDisplayDimension")
        angle = _early_bound(display.GetDimension2(0), "IDimension")
        nominal = math.radians(TIP_CHAMFER_ANGLE)
        actual = abs(float(angle.SystemValue))
        if not math.isclose(actual, nominal, abs_tol=1e-8):
            if (
                not math.isclose(math.pi - actual, nominal, abs_tol=1e-8)
                or not display.SupplementaryAngle()
            ):
                raise RuntimeError("tip-chamfer angle is not the specified 45 degrees")
        angle.DrivenState = 2  # swDimensionDriving
        if int(angle.DrivenState) != 2 or not math.isclose(
            abs(float(angle.SystemValue)), nominal, abs_tol=1e-8
        ):
            raise RuntimeError("tip-chamfer angle is not a driving 45-degree control")
        dims.record("ChamferAngle")
        axis = adapter.currentSketchManager.CreateCenterLine(
            0, (tip - chamfer) / 1000, 0, 0, (tip + 2 * chamfer) / 1000, 0
        )
        if axis is None:
            raise RuntimeError("cannot create the tip chamfer axis")
        axis_id = adapter._register_sketch_entity("Line", axis)
        # The construction axis only represents the fixed screw axis.
        check(
            "fix tip chamfer axis",
            await adapter.add_sketch_constraint(axis_id, None, "fix"),
        )
        await ensure_fully_defined(adapter, "tip chamfer profile")
        check("exit tip chamfer sketch", await adapter.exit_sketch())
        name_last_feature(adapter, TIP_CHAMFER_FEATURE)
        dims.apply(adapter, TIP_CHAMFER_FEATURE)
        # The cutter's outer edge follows the chamfer, so the axial control
        # alone sizes the cut.
        await drive_dimension(
            adapter,
            f"CutterRadius@{TIP_CHAMFER_FEATURE}",
            f'"StockMajorRadius@{TIP_CHAMFER_FEATURE}"'
            f' + "ChamferLength@{TIP_CHAMFER_FEATURE}"',
        )
        # FeatureRevolve2 consumes selections; exit_sketch resets the registry,
        # so select the captured native centreline.
        model.ClearSelection2(True)
        if not _feature_by_name(adapter, TIP_CHAMFER_FEATURE).Select2(False, 0):
            raise RuntimeError("cannot select the tip chamfer profile")
        selection = _early_bound(model.SelectionManager, "ISelectionMgr")
        data = _early_bound(selection.CreateSelectData(), "ISelectData")
        if data is None:
            raise RuntimeError("cannot create the tip chamfer axis selection")
        data.Mark = 4  # FeatureRevolve2: axis of revolution.
        if not _early_bound(axis, "ISketchSegment").Select4(True, data):
            raise RuntimeError("cannot select the tip chamfer axis")
        check(
            "re-cut the cut end's chamfer",
            await adapter.create_revolve(RevolveParameters(angle=360, is_cut=True)),
        )
        name_last_feature(adapter, "TipChamfer")


def _manufacturing_controls(adapter) -> None:
    """Tolerance, place and mark the cut end's controls before the save."""
    clear_dimensions_for_drawing(adapter)
    # Axial length: .030-.035 as .035 -.005/0 (bilateral, both ends checked by
    # the spec's runout and engagement proofs).
    set_dimension_bilateral_tolerance(
        adapter,
        TIP_CHAMFER_FEATURE,
        "ChamferLength",
        *deviations(TIP_CHAMFER_BAND),
        places=DRAWING_PRECISION[TIP_CHAMFER_FEATURE]["ChamferLength"],
        display_unit=UNIT,
    )
    # The driving 45 degrees keeps the title block's angular band natively;
    # swTolGeneral prints no band and leaves the title block's row in force.
    band = math.radians(TIP_CHAMFER_ANGLE_TOLERANCE)
    _, dimension = _named_dimension(adapter, TIP_CHAMFER_FEATURE, "ChamferAngle")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 11  # swTolType_e.swTolGeneral
    if (
        not tolerance.SetValues(-band, band)
        or int(tolerance.Type) != 11
        or not math.isclose(float(tolerance.GetMinValue()), -band, abs_tol=1e-9)
        or not math.isclose(float(tolerance.GetMaxValue()), band, abs_tol=1e-9)
    ):
        raise RuntimeError(f"ChamferAngle@{TIP_CHAMFER_FEATURE}: cannot retain general tolerance")
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)


@wraps(build_92220A165)
async def _cut_to_fit(adapter, truth=None, **parameters):
    """The catalogue screw at the cut length, then the native cut-end chamfer."""
    receipt = await build_92220A165(adapter, truth, **parameters)
    await _tip_chamfer(adapter)
    _manufacturing_controls(adapter)
    await force_rebuild(adapter)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError("the cut left clamp screw must have one solid body")
    tip = _early_bound(bodies[0], "IBody2").GetExtremePoint(0, -1, 0)
    if not tip[0] or not math.isclose(float(tip[2]), -CUT_LENGTH / 1000, abs_tol=1e-9):
        raise RuntimeError(f"the cut end is not at Y={-CUT_LENGTH}")
    return receipt


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=SKU,
                author=_cut_to_fit,
                parameters={"cut_length": supplier.CUT_LENGTH},
            ),
        ),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
        ),
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
