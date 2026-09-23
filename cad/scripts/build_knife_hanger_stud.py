"""Build the turned-and-threaded knife-hanger stud from McMaster 91247A720 stock."""

from __future__ import annotations

from functools import wraps
import json
import math
import sys
from typing import Any

import _telemetry
from _common import (
    SketchDims,
    _early_bound,
    _read_member,
    add_line_chain,
    check,
    dimension_between,
    drive_dimension,
    force_rebuild,
    name_last_feature,
    run_build,
)
from _drawing_marks import (
    _named_dimension,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
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
from diagnostics.diag_mcmaster_lib import no_sketch_inference
from knife_hanger_stud_spec import (
    DIMENSION_PRECISION,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FINISHED_UNDERHEAD_MM,
    ISOMETRIC_VIEW_NOTE,
    SHOULDER_UNDERHEAD_MM,
    TIP_CHAMFER_MM,
    TIP_CHAMFER_TOLERANCE_TYPE,
    TIP_DIA_MM,
    TIP_LENGTH_DEVIATIONS_MM,
    TIP_LENGTH_MM,
    TIP_LENGTH_TOLERANCE_TYPE,
    TIP_THREAD_CALLOUT,
    TIP_THREAD_MINOR_DIA_MM,
)

PART_NAME = "knife-hanger-stud"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

HEAD_AF = GB_HW
HEAD_H = GB_HH
SHANK_DIA = 2.0 * GB_MAJOR_R
STOCK_SHANK_LEN = GB_LEN
# Bearing face (washer lower face) to the faced end: the assembly places the
# stud by it (HANGER_STUD_Y = washer top - UNDERHEAD_LEN).
UNDERHEAD_LEN = FINISHED_UNDERHEAD_MM
SHOULDER_LEN = SHOULDER_UNDERHEAD_MM
UNDERHEAD_Y_MM = GB_UNDERSIDE - GB_WASHER_T
SHOULDER_Y_MM = UNDERHEAD_Y_MM - SHOULDER_LEN
TIP_END_Y_MM = UNDERHEAD_Y_MM - UNDERHEAD_LEN
TIP_RADIUS_MM = TIP_DIA_MM / 2.0

# The turning cutter's outside: past the stock thread's crest, and below the
# faced end, so the revolve removes all stock around the tip and no sliver.
TURN_CUTTER_CLEARANCE_MM = 1.0
TURN_CUTTER_RADIUS_MM = GB_MAJOR_R + TURN_CUTTER_CLEARANCE_MM
# The faced end in the trim sketch's own terms, so the turn follows a refit.
TIP_END_EQUATION = '"FinishedOverall@StockTrimProfile" - "StockEyeTop@StockTrimProfile"'


def _clear_native_tolerance(adapter, feature: str, name: str) -> None:
    """Keep nominal controls free of fixed bands for sheet references."""
    _, dimension = _named_dimension(adapter, feature, name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 0  # swTolType_e.swTolNONE
    if int(tolerance.Type) != 0:
        raise RuntimeError(f"{name}@{feature}: native tolerance did not clear")


def _set_tolerance(
    adapter, feature: str, name: str, kind: int, lower_mm: float, upper_mm: float
) -> None:
    """Give one control its swTolType_e ``kind`` and signed deviations."""
    _, dimension = _named_dimension(adapter, feature, name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = kind
    tolerance.SetValues(lower_mm / 1000.0, upper_mm / 1000.0)
    state = (
        int(tolerance.Type),
        float(tolerance.GetMinValue()) * 1000.0,
        float(tolerance.GetMaxValue()) * 1000.0,
    )
    if state[0] != kind or not all(
        math.isclose(read, wanted, abs_tol=1e-6)
        for read, wanted in zip(state[1:], (lower_mm, upper_mm), strict=True)
    ):
        raise RuntimeError(
            f"{name}@{feature}: tolerance reads {state!r}, wanted "
            f"{(kind, lower_mm, upper_mm)!r}"
        )


async def _turn_stepped_tip(adapter) -> None:
    """Turn the #10-24 tip below the shoulder and chamfer its end.

    One revolve cut, profile on Front (x radial, y axial): the chamfer, the
    tip at the thread's major diameter up to the shoulder face, the shoulder
    out past the stock crest, and the cutter's outside. ``TipLength`` runs
    from the shoulder face's OUTER corner (the stock crest, a drawn corner)
    to the faced end, so its imported extension lines leave real edges.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    end_y, shoulder_y = TIP_END_Y_MM, SHOULDER_Y_MM
    r_tip, chamfer = TIP_RADIUS_MM, TIP_CHAMFER_MM
    below = end_y - TURN_CUTTER_CLEARANCE_MM
    dims = SketchDims()
    with no_sketch_inference(adapter):
        check("create stud turn sketch", await adapter.create_sketch("Front"))
        lines = await add_line_chain(
            adapter,
            [
                [r_tip - chamfer, end_y],
                [r_tip, end_y + chamfer],
                [r_tip, shoulder_y],
                [GB_MAJOR_R, shoulder_y],
                [TURN_CUTTER_RADIUS_MM, shoulder_y],
                [TURN_CUTTER_RADIUS_MM, below],
                [r_tip - chamfer, below],
            ],
        )
        for line, direction in zip(
            lines[1:],
            (
                "vertical",
                "horizontal",
                "horizontal",
                "vertical",
                "horizontal",
                "vertical",
            ),
            strict=True,
        ):
            check(
                "stud turn profile relation",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        # The faced end, from the origin: the chamfer's small end sits on it.
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            "origin",
            "vertical_distance",
            abs(end_y),
            "faced end",
        )
        dims.record("TipEnd", TIP_END_EQUATION)
        await dimension_between(
            adapter,
            f"{lines[1]}.start",
            "origin",
            "horizontal_distance",
            r_tip,
            "tip radius",
        )
        dims.record("TipRadius")
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            f"{lines[0]}.end",
            "horizontal_distance",
            chamfer,
            "tip chamfer radial",
        )
        dims.record("TipChamferRadial")
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            f"{lines[0]}.end",
            "vertical_distance",
            chamfer,
            "tip chamfer",
        )
        dims.record("TipChamfer")
        await dimension_between(
            adapter,
            f"{lines[3]}.start",
            f"{lines[0]}.start",
            "vertical_distance",
            TIP_LENGTH_MM,
            "tip length",
        )
        dims.record("TipLength")
        await dimension_between(
            adapter,
            f"{lines[3]}.start",
            "origin",
            "horizontal_distance",
            GB_MAJOR_R,
            "shoulder outer radius",
        )
        dims.record("ShoulderRadius")
        await dimension_between(
            adapter,
            f"{lines[4]}.start",
            "origin",
            "horizontal_distance",
            TURN_CUTTER_RADIUS_MM,
            "turn cutter radius",
        )
        dims.record("CutterRadius")
        await dimension_between(
            adapter,
            f"{lines[5]}.start",
            f"{lines[0]}.start",
            "vertical_distance",
            TURN_CUTTER_CLEARANCE_MM,
            "turn cutter below the end",
        )
        dims.record("CutterBelow")
        axis = adapter.currentSketchManager.CreateCenterLine(
            0, (below - 1.0) / 1000, 0, 0, (shoulder_y + 1.0) / 1000, 0
        )
        if axis is None:
            raise RuntimeError("stud turn axis failed")
        axis_id = adapter._register_sketch_entity("Line", axis)
        check(
            "fix stud axis",
            await adapter.add_sketch_constraint(axis_id, None, "fix"),
        )
        check("close stud turn sketch", await adapter.exit_sketch())
        name_last_feature(adapter, "StudTurnProfile")
        drives = dims.apply(adapter, "StudTurnProfile")
        check(
            "turn the stud tip",
            await adapter.create_revolve(RevolveParameters(angle=360, is_cut=True)),
        )
        name_last_feature(adapter, "StudTurn")
    for name, expression in drives:
        await drive_dimension(adapter, name, expression)
    await force_rebuild(adapter)


def _tip_thread_problem(state: dict[str, object]) -> str | None:
    """Why the cosmetic thread read back from the part is not the spec's."""
    if state["callout"] != TIP_THREAD_CALLOUT:
        return f"tip thread callout reads {state['callout']!r}"
    if not math.isclose(
        float(state["diameter_mm"]), TIP_THREAD_MINOR_DIA_MM, abs_tol=1e-6
    ):
        return f"tip thread minor reads {state['diameter_mm']!r} mm"
    if not math.isclose(
        float(state["depth_mm"]), TIP_LENGTH_MM - TIP_CHAMFER_MM, abs_tol=1e-6
    ):
        return f"tip thread depth reads {state['depth_mm']!r} mm"
    return None


def _read_tip_thread(part: Any, name: str) -> dict[str, object]:
    """Read the cosmetic thread ``name`` back through the part's IPartDoc.

    ``FeatureByName`` is declared on IPartDoc, not IModelDoc2 (stud-17, leaf
    20260923T003348Z), and a cosmetic thread is a sub-feature of the face's
    feature, so it is found by the name its creator returned -- renaming "the
    last feature" renamed the StudTurn cut instead.
    """
    feature = _early_bound(part, "IPartDoc").FeatureByName(name)
    if feature is None:
        raise RuntimeError(f"cosmetic thread {name!r} is missing after its creation")
    data = _early_bound(
        _early_bound(feature, "IFeature").GetDefinition(), "ICosmeticThreadFeatureData"
    )
    return {
        "name": name,
        "callout": str(data.ThreadCallout or ""),
        "diameter_mm": float(data.Diameter) * 1000.0,
        "depth_mm": float(data.BlindDepth) * 1000.0,
    }


async def _thread_tip(adapter) -> None:
    """Cosmetic thread over the whole turned tip, callout and minor explicit.

    stud-16 passed only a standard and a size: the thread carried no minor
    diameter and no callout, so the lathe view drew no thread and no
    "#10-24" (render of leaf 20260923T001846Z). With no standard the
    thread's minor line and callout come from this spec alone, and both are
    read back from the feature.
    """
    from solidworks_mcp.adapters.base import AddThreadParameters

    created = check(
        f"cosmetic thread {TIP_THREAD_CALLOUT}",
        await adapter.add_thread(
            AddThreadParameters(
                edge_point=[TIP_RADIUS_MM, TIP_END_Y_MM + TIP_CHAMFER_MM, 0.0],
                standard="none",
                diameter=TIP_THREAD_MINOR_DIA_MM,
                end_type="blind",
                depth=TIP_LENGTH_MM - TIP_CHAMFER_MM,
                note=TIP_THREAD_CALLOUT,
            )
        ),
    )
    state = _read_tip_thread(adapter.currentModel, str(created["name"]))
    _telemetry.info("tip thread: " + json.dumps(state, sort_keys=True))
    problem = _tip_thread_problem(state)
    if problem is not None:
        raise RuntimeError(f"{problem}: {state!r}")


def _manufacturing_controls(adapter) -> None:
    """Set and mark the native turned-tip controls before saving."""
    clear_dimensions_for_drawing(adapter)
    for feature, name, nominal in (
        ("StockTrimProfile", "FinishedOverall", FINISHED_UNDERHEAD_MM / 1000),
        ("StudTurnProfile", "TipLength", TIP_LENGTH_MM / 1000),
        ("StudTurnProfile", "TipChamfer", TIP_CHAMFER_MM / 1000),
    ):
        display, dimension = _named_dimension(adapter, feature, name)
        if int(dimension.DrivenState) != 2:
            raise RuntimeError(f"{name}@{feature} must control the cutting sketch")
        if not math.isclose(float(dimension.SystemValue), nominal, abs_tol=1e-9):
            raise RuntimeError(f"{name}@{feature}: turned stud nominal changed")
        display = _early_bound(display, "IDisplayDimension")
        digits = DIMENSION_PRECISION[name]
        result = display.SetPrecision3(digits, -1, -1, -1)
        if (
            result is None
            or int(_read_member(display, "GetPrimaryPrecision2")) != digits
        ):
            raise RuntimeError(f"{name}@{feature}: native precision did not persist")
    _clear_native_tolerance(adapter, "StockTrimProfile", "FinishedOverall")
    _set_tolerance(
        adapter, "StudTurnProfile", "TipChamfer", TIP_CHAMFER_TOLERANCE_TYPE, 0.0, 0.0
    )
    _set_tolerance(
        adapter,
        "StudTurnProfile",
        "TipLength",
        TIP_LENGTH_TOLERANCE_TYPE,
        *TIP_LENGTH_DEVIATIONS_MM,
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
    """Cut, turn and thread the purchased bolt before the final save."""
    receipt = await build_91247A720(adapter, truth, **parameters)
    await _turn_stepped_tip(adapter)
    await _thread_tip(adapter)
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
