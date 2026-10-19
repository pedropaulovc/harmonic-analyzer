r"""Build MHA-PD-VN-57 from complete 90325A174 stock, then face and deburr the tip.

The hanger arm (MHA-PD-18) swings on the shoulder: the head sits in the
arm's rear spot face, the shoulder runs through the arm and the pivot spacer
(MHA-PD-20), and the shoulder end bears on the support bar's (MHA-PD-07)
back face with the thread in the bar's THROUGH #8-32 tap.  At fit-up the tip
is faced to stand TIP_RECESS below the bar's front face and staked there
(``pd_vn_transgear_pivot_screw_spec``).

Frame (the stock recipe's): axis +Y, head up, the under-head shoulder face at
y = 0 (Top Plane), the faced tip at TIP_Y.  The assembly mates the screw axis
(``ScrewAxis``, Front Plane ∩ Right Plane) to the arm's pivot bore axis and
the Top Plane to the arm's spot-face floor plus the head play.

The native CutLength (shoulder end to faced tip) is a REFERENCE: the fit-up
sets it.  After its equations are solved, select the completed deburr sketch
with mark 0 and its construction centreline with mark 4; create_revolve does
not select them (``build_sm_vn_knife_hanger_stud``'s recipe).
"""

from __future__ import annotations

from functools import wraps
import math
import sys

import _config
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _fastener_catalog import fastener
from _feature_tree import _feature_by_name, name_last_feature
from _rebuild import force_rebuild
from _session import run_build
from _simplified_part import save_simplified_part
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
)
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_90325A174 import build_90325A174
from diagnostics.diag_mcmaster_lib import no_sketch_inference
from pd_vn_transgear_pivot_screw_spec import (
    CHAMFER_ANGLE,
    CHAMFER_ANGLE_TOLERANCE,
    CHAMFER_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FITTED_THREAD_LEN,
    REFERENCE_DIMENSIONS,
    SHOULDER_END_Y,
    SKU,
    THREAD_LEN,
    THREAD_LENGTH_MIN,
    THREAD_MAJOR,
    TIP_Y,
)

PART_NAME = "pd-vn-transgear-pivot-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def _shoulder_end_point(adapter, label: str) -> str:
    """A sketch point on the shoulder's end face, anchored on the axis."""
    point = adapter.currentSketchManager.CreatePoint(0, SHOULDER_END_Y / 1000, 0)
    if point is None:
        raise RuntimeError(f"cannot create the {label} shoulder-end reference")
    ref = adapter._register_sketch_entity("Point", point)
    await anchor_point_to_origin(adapter, ref, 0.0, SHOULDER_END_Y, "shoulder end")
    return ref


async def _trim_stock(adapter) -> None:
    """The native CutLength places the actual facing plane from the shoulder's
    end face."""
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    radius = THREAD_MAJOR / 2
    bottom = SHOULDER_END_Y - THREAD_LEN - THREAD_MAJOR
    with no_sketch_inference(adapter):
        check("create trim sketch", await adapter.create_sketch("Front"))
        lines = await add_line_chain(
            adapter,
            [
                (-2 * radius, bottom),
                (2 * radius, bottom),
                (2 * radius, TIP_Y),
                (-2 * radius, TIP_Y),
            ],
        )
        dims = SketchDims()
        for line, direction in zip(
            lines, ("horizontal", "vertical", "horizontal", "vertical"), strict=True
        ):
            check(
                "trim profile relation",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        await anchor_point_to_origin(
            adapter, f"{lines[0]}.start", -2 * radius, bottom, "trim cutter margin"
        )
        dims.record("CutterLeft")
        dims.record("CutterBottom")
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            f"{lines[0]}.end",
            "horizontal_distance",
            4 * radius,
            "trim cutter width",
        )
        dims.record("CutterWidth")
        shoulder = await _shoulder_end_point(adapter, "trim")
        dims.record("ShoulderEndY")
        await dimension_between(
            adapter,
            shoulder,
            f"{lines[2]}.start",
            "vertical_distance",
            FITTED_THREAD_LEN,
            "fitted thread length",
        )
        dims.record("CutLength")
        await ensure_fully_defined(adapter, "stock trim profile")
        check("exit trim sketch", await adapter.exit_sketch())
        name_last_feature(adapter, "StockTrimProfile")
        dims.apply(adapter, "StockTrimProfile")
        check(
            "face stock to length",
            await adapter.create_cut_extrude(
                ExtrusionParameters(depth=4 * THREAD_MAJOR, both_directions=True)
            ),
        )
        name_last_feature(adapter, "StockTrim")

        chamfer = CHAMFER_WIDTH
        check("create deburr sketch", await adapter.create_sketch("Front"))
        lines = await add_line_chain(
            adapter,
            [
                (radius - chamfer, TIP_Y),
                (radius + chamfer, TIP_Y),
                (radius + chamfer, TIP_Y + chamfer),
                (radius, TIP_Y + chamfer),
            ],
            close=True,
        )
        dims = SketchDims()
        for line, direction in zip(
            lines[:3], ("horizontal", "vertical", "horizontal"), strict=True
        ):
            check(
                "deburr profile relation",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        await dimension_between(
            adapter,
            f"{lines[1]}.start",
            "origin",
            "horizontal_distance",
            radius + chamfer,
            "cutter outer radius",
        )
        dims.record("CutterRadius")
        shoulder = await _shoulder_end_point(adapter, "deburr")
        dims.record("ShoulderEndY")
        # A nonzero length from the real shoulder end locates the cutter. Its
        # equation follows CutLength.
        await dimension_between(
            adapter,
            shoulder,
            f"{lines[1]}.start",
            "vertical_distance",
            FITTED_THREAD_LEN,
            "faced tip from shoulder end",
        )
        dims.record("CutEndFromShoulder")
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
            "horizontal_distance",
            chamfer,
            "end chamfer width",
        )
        dims.record("ChamferWidth")
        model = adapter.currentModel
        model.ClearSelection2(True)
        _select_sketch_entities(adapter, [lines[0], lines[3]], 0)
        display, status = _early_bound(
            model.Extension, "IModelDocExtension"
        ).AddSpecificDimension(
            (radius + 2 * chamfer) / 1000, (TIP_Y + chamfer / 2) / 1000, 0, 3, 0
        )
        model.ClearSelection2(True)
        if display is None:
            raise RuntimeError(f"cannot create native end-chamfer angle: {status}")
        display = _early_bound(display, "IDisplayDimension")
        angle = _early_bound(display.GetDimension2(0), "IDimension")
        nominal = math.radians(CHAMFER_ANGLE)
        actual = abs(float(angle.SystemValue))
        if not math.isclose(actual, nominal, abs_tol=1e-8):
            if (
                not math.isclose(math.pi - actual, nominal, abs_tol=1e-8)
                or not display.SupplementaryAngle()
            ):
                raise RuntimeError("end-chamfer angle is not the specified 45 degrees")
        angle.DrivenState = 2  # swDimensionDriving
        if int(angle.DrivenState) != 2 or not math.isclose(
            abs(float(angle.SystemValue)), nominal, abs_tol=1e-8
        ):
            raise RuntimeError("end-chamfer angle is not a driving 45-degree control")
        dims.record("ChamferAngle")
        axis = adapter.currentSketchManager.CreateCenterLine(
            0, (TIP_Y - chamfer) / 1000, 0, 0, (TIP_Y + 2 * chamfer) / 1000, 0
        )
        if axis is None:
            raise RuntimeError("cannot create stock deburr axis")
        axis_id = adapter._register_sketch_entity("Line", axis)
        # The construction axis only represents the fixed stock shank axis.
        check(
            "fix deburr axis", await adapter.add_sketch_constraint(axis_id, None, "fix")
        )
        await ensure_fully_defined(adapter, "stock deburr profile")
        check("exit deburr sketch", await adapter.exit_sketch())
        name_last_feature(adapter, "StockDeburrProfile")
        dims.apply(adapter, "StockDeburrProfile")
        await drive_dimension(
            adapter,
            "ShoulderEndY@StockDeburrProfile",
            '"ShoulderEndY@StockTrimProfile"',
        )
        await drive_dimension(
            adapter,
            "CutEndFromShoulder@StockDeburrProfile",
            '"CutLength@StockTrimProfile"',
        )
        # FeatureRevolve2 consumes selections; the adapter does not recover a
        # profile/axis after equation solving. exit_sketch also resets the
        # registry, so select the captured native centreline.
        model.ClearSelection2(True)
        if not _feature_by_name(adapter, "StockDeburrProfile").Select2(False, 0):
            raise RuntimeError("cannot select stock deburr profile")
        selection = _early_bound(model.SelectionManager, "ISelectionMgr")
        data = _early_bound(selection.CreateSelectData(), "ISelectData")
        if data is None:
            raise RuntimeError("cannot create stock deburr axis selection")
        data.Mark = 4  # FeatureRevolve2: axis of revolution.
        if not _early_bound(axis, "ISketchSegment").Select4(True, data):
            raise RuntimeError("cannot select stock deburr axis")
        check(
            "deburr faced tip",
            await adapter.create_revolve(RevolveParameters(angle=360, is_cut=True)),
        )
        name_last_feature(adapter, "StockDeburr")


async def _thread_tail_acceptance(adapter) -> None:
    """Retain the native thread-tail MIN from the faced tip."""
    radius = THREAD_MAJOR / 2
    check("create tail inspection", await adapter.create_sketch("Front"))
    lines = await add_line_chain(
        adapter,
        [(radius, TIP_Y), (radius, TIP_Y + THREAD_LENGTH_MIN)],
        close=False,
    )
    dims = SketchDims()
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", radius, TIP_Y, "faced tip plane"
    )
    dims.record("TailMajorRadius")
    dims.record("TailTipY")
    check(
        "tail direction",
        await adapter.add_sketch_constraint(lines[0], None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{lines[0]}.start",
        f"{lines[0]}.end",
        "vertical_distance",
        THREAD_LENGTH_MIN,
        "continuous inspected thread tail",
    )
    dims.record("ThreadLengthMin")
    await ensure_fully_defined(adapter, "tail inspection length")
    check("exit tail inspection", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadTailAcceptance")
    dims.apply(adapter, "ThreadTailAcceptance")
    # The tail starts at the faced tip wherever the fit-up puts it.
    await drive_dimension(
        adapter,
        "TailTipY@ThreadTailAcceptance",
        '"ShoulderEndY@StockTrimProfile" + "CutLength@StockTrimProfile"',
    )


def _reference_length(adapter) -> None:
    """CutLength prints as a reference, "(9.15)": no band, the fit-up sets it
    (build_pn_pen_v_block._author_reference_dimensions' recipe)."""
    for feature, name in REFERENCE_DIMENSIONS:
        display, dimension = _named_dimension(adapter, feature, name)
        label = f"{name}@{feature}"
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = 0  # swTolType_e.swTolNONE
        # The native prefix/suffix channel around the live model value, not
        # ShowParenthesis (which brackets above-line text).
        display.SetText(1, "(")
        display.SetText(2, ")")
        if (
            int(tolerance.Type) != 0
            or (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
            != ("(", ")")
            or not bool(display.ShowDimensionValue)
        ):
            raise RuntimeError(f"{label}: reference display did not persist")


def _manufacturing_controls(adapter) -> None:
    clear_dimensions_for_drawing(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _reference_length(adapter)
    # The leg prints as a MAX: past the thread root, inside the charged pitch.
    feature, name = "StockDeburrProfile", "ChamferWidth"
    _, dimension = _named_dimension(adapter, feature, name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 6  # swTolMAX: nominal is the maximum acceptance size.
    if not tolerance.SetValues(0.0, 0.0) or int(tolerance.Type) != 6:
        raise RuntimeError(f"{name}@{feature}: cannot retain MAX acceptance")
    # The driving 45-degree angle keeps its title-block band natively;
    # swTolGeneral prints no band and leaves the title block's row in force.
    feature, name = "StockDeburrProfile", "ChamferAngle"
    band = math.radians(CHAMFER_ANGLE_TOLERANCE)
    _, dimension = _named_dimension(adapter, feature, name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 11  # swTolType_e.swTolGeneral
    if (
        not tolerance.SetValues(-band, band)
        or int(tolerance.Type) != 11
        or not math.isclose(float(tolerance.GetMinValue()), -band, abs_tol=1e-9)
        or not math.isclose(float(tolerance.GetMaxValue()), band, abs_tol=1e-9)
    ):
        raise RuntimeError(f"{name}@{feature}: cannot retain general tolerance")
    feature, name = "ThreadTailAcceptance", "ThreadLengthMin"
    _, dimension = _named_dimension(adapter, feature, name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 5  # swTolMIN: nominal is the minimum acceptance size.
    if not tolerance.SetValues(0.0, 0.0) or int(tolerance.Type) != 5:
        raise RuntimeError(f"{name}@{feature}: cannot retain MIN acceptance")
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    row = _config.parts(PART_NAME)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Purchased Screw Note": str(row["purchased_note"])},
    )


@wraps(build_90325A174)
async def _face_to_fit(adapter, truth=None, **parameters):
    receipt = await build_90325A174(adapter, truth, **parameters)
    await _trim_stock(adapter)
    await drive_dimension(
        adapter,
        "CutterRadius@StockDeburrProfile",
        '"StockMajorRadius@StockDeburrProfile" + "ChamferWidth@StockDeburrProfile"',
    )
    await _thread_tail_acceptance(adapter)
    _manufacturing_controls(adapter)
    await force_rebuild(adapter)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError("finished pivot screw must have one solid body")
    body = _early_bound(bodies[0], "IBody2")
    tip = body.GetExtremePoint(0, -1, 0)
    if not tip[0] or not math.isclose(float(tip[2]), TIP_Y / 1000, abs_tol=1e-9):
        raise RuntimeError(f"finished pivot screw tip is not at Y={TIP_Y}")
    return receipt


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(SKU, _face_to_fit),),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
