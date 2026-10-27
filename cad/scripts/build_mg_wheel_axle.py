r"""Reproduction script: magnifying-wheel axle (book ch. 21, pp. 50-51).

A plain pin from 3/16 drill rod (mg_wheel_axle_spec): pressed into the
mg-wheel-bar's reamed bore until the shank stands the press gauge off the
bar's front face, the back end then about flush with its back face; the
magnifying wheel runs on the shank; the front end is a #4-40 thread for the
nut and locknut, with a thread relief at the step, finished with a domed tip.
``mg_wheel_group`` sizes the lengths against the whole stack.

Layout: pin axis local +Y, origin on the bar's FRONT face (the assembly's
d = 0); back end y = BACK_Y (-9), shank to STEP_Y (the gauge), relief to
STEP_Y + RELIEF_WIDTH, thread to THREAD_END_Y, dome to TIP_Y. The assembly
mates Axis1 and the Front Plane.

Built as ONE Front-plane revolve (PinProfile -> Pin) plus the relief's two
root rounds (ReliefRoots): every printed diameter and length is a named
dimension, the shank from the back end and the thread from the gauged step,
so the drawing inserts them as model items
(mg_wheel_axle_spec.DRAWING_DIMENSIONS). The relief's sizes are single MAX
limits, and every callout the sheet prints is authored here on its source
dimension (mg_wheel_axle_callouts; the drawing only reads them back, #1942).
The #4-40 end carries a cosmetic thread so the pictorial matches the callout.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_wheel_axle.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import (
    _named_dimension,
    _named_dimensions,
    apply_drawing_precision,
)
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
import _telemetry
import mg_wheel_axle_callouts as callouts
from mg_wheel_axle_spec import (
    BACK_Y,
    DOME_H,
    DOME_R,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    PIN_DIA,
    PIN_DIA_TOL,
    PIN_LEN,
    PRESS_GAUGE,
    SHANK_LEN,
    STEP_Y,
    LIMIT_PAIRS,
    SINGLE_LIMITS,
    SURFACE_FINISHES,
    THREAD,
    THREAD_END_Y,
    THREAD_LEN,
    THREAD_LEN_BAND,
    THREAD_MAJOR,
    RELIEF_DIA,
    RELIEF_ROOT_R,
    RELIEF_WIDTH,
    TOL_TYPE_LIMIT,
    TIP_Y,
)

PART_NAME = "mg-wheel-axle"
MATERIAL = "Plain Carbon Steel"  # drill rod, as the fleet's other drill-rod pins
PIN_R = PIN_DIA / 2.0
THREAD_R = THREAD_MAJOR / 2.0
RELIEF_R = RELIEF_DIA / 2.0
RELIEF_END_Y = STEP_Y + RELIEF_WIDTH
V_SHANK = math.pi * PIN_R**2 * SHANK_LEN
V_RELIEF = math.pi * RELIEF_R**2 * RELIEF_WIDTH
V_THREAD = math.pi * THREAD_R**2 * (THREAD_LEN - RELIEF_WIDTH)
V_DOME = math.pi * DOME_H**2 * (3.0 * DOME_R - DOME_H) / 3.0
V_PROFILE = V_SHANK + V_RELIEF + V_THREAD + V_DOME
# Each relief root fills its concave corner's spandrel, (1 - pi/4) R^2,
# turned about the axis at its centroid, (10 - 3 pi) / (12 - 3 pi) R off both
# legs (Pappus; build_mg_magnifying_vertical_rod).
_ROOT_SPANDREL = (1.0 - math.pi / 4.0) * RELIEF_ROOT_R**2
_ROOT_CENTROID_R = (
    RELIEF_R + (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi) * RELIEF_ROOT_R
)
V_RELIEF_ROOTS = 2.0 * 2.0 * math.pi * _ROOT_CENTROID_R * _ROOT_SPANDREL
V_TOTAL = V_PROFILE + V_RELIEF_ROOTS
# The groove's cut, about 4.0 mm^3: under the whole-part 0.5% (4.4 mm^3) an
# unrelieved solid would pass (codjiflo #1996), so the revolve's gate is a
# quarter of the groove and the roots' fillet is read as its own delta.
V_RELIEF_GROOVE = math.pi * (THREAD_R**2 - RELIEF_R**2) * RELIEF_WIDTH
PIN_VOLUME_TOL = 0.25 * V_RELIEF_GROOVE
ROOTS_VOLUME_TOL = 0.5 * V_RELIEF_ROOTS
NEUTRAL_VOLUME_TOL = 0.01


def _single_limits(adapter) -> None:
    """Each SINGLE_LIMITS dimension printed as a single MAX limit
    (build_mg_magnifying_vertical_rod._single_limits): SOLIDWORKS prints the
    nominal then the limit word, so the model value is the limit itself."""
    for (feature, name), (limit, tol_type) in SINGLE_LIMITS.items():
        label = f"{name}@{feature}"
        _, dimension = _named_dimension(adapter, feature, name)
        value = float(dimension.SystemValue)
        if not math.isclose(value, limit / 1000.0, abs_tol=1e-9):
            raise RuntimeError(
                f"{label}: nominal {value * 1000.0:.7f} is not the limit {limit:.7f}"
            )
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = tol_type
        if not tolerance.SetValues(0.0, 0.0) or int(tolerance.Type) != tol_type:
            raise RuntimeError(f"{label}: cannot retain the single limit {tol_type}")
        _telemetry.success(f"{label}: single limit (swTolType {tol_type})")


def _limit_pairs(adapter) -> None:
    """Each LIMIT_PAIRS dimension printed as its MIN/MAX pair, the model at
    the MAX (build_mg_output_fixture's LIMIT form), at its own places, read
    back."""
    for (feature, name), (low, high) in LIMIT_PAIRS.items():
        label = f"{name}@{feature}"
        display, dimension = _named_dimension(adapter, feature, name)
        value = float(dimension.SystemValue) * 1000.0
        if not math.isclose(value, high, abs_tol=1e-6):
            raise RuntimeError(f"{label}: nominal {value:.7f} is not its MAX {high}")
        lower, upper = (low - high) / 1000.0, 0.0
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = TOL_TYPE_LIMIT
        if tolerance.SetValues(lower, upper) is not True:
            raise RuntimeError(f"{label}: LIMIT deviations were rejected")
        if (
            int(tolerance.Type) != TOL_TYPE_LIMIT
            or not math.isclose(float(tolerance.GetMinValue()), lower, abs_tol=1e-12)
            or not math.isclose(float(tolerance.GetMaxValue()), upper, abs_tol=1e-12)
        ):
            raise RuntimeError(f"{label}: LIMIT tolerance readback changed")
        places = DRAWING_PRECISION[feature][name]
        display = _early_bound(display, "IDisplayDimension")
        display.SetPrecision3(-1, -1, places, -1)
        if int(display.GetPrimaryTolPrecision2()) != places:
            raise RuntimeError(f"{label}: LIMIT precision did not persist")
        _telemetry.success(f"{label}: LIMIT {high:.{places}f}/{low:.{places}f}")


def author_dimension_callouts(adapter) -> None:
    """Write every authored text lane on its source dimension, read it back
    (build_pd_transgear_pin.author_dimension_callouts).

    The drawing only reads these lanes: set from the sheet they would write
    through to this part outside its recipe (#1942).
    """
    for feature, by_name in callouts.authored_text().items():
        displays = _named_dimensions(adapter, feature, set(by_name))
        for name, lanes in by_name.items():
            display, _dimension = displays[name]
            for lane, text in lanes.items():
                display.SetText(lane, text)
                printed = str(display.GetText(lane) or "")
                if callouts.callout_rows(printed) != callouts.callout_rows(text):
                    raise RuntimeError(
                        f"{name}@{feature}: text lane {lane} did not persist: "
                        f"{printed!r}"
                    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import AddThreadParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units. Each profile dim below is driven from these via the
    # deferred drive batch.
    for name, value in (
        ("PinDia", PIN_DIA),
        ("ShankLength", SHANK_LEN),
        ("ThreadDia", THREAD_MAJOR),
        ("ThreadLength", THREAD_LEN),
        ("DomeHeight", DOME_H),
        ("PressGauge", PRESS_GAUGE),
        ("ReliefWidth", RELIEF_WIDTH),
        ("ReliefDia", RELIEF_DIA),
        ("ReliefRootR", RELIEF_ROOT_R),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Half-section about local +Y (Front sketch u, v = model x, y): flat back
    # end, shank, step down to the relief floor, the relief's flank up to the
    # thread at the basic major, spherical dome to the tip.
    profile = SketchDims()
    check("create_sketch pin profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check("pin axis", await adapter.add_centerline(0.0, BACK_Y, 0.0, TIP_Y))
    points = [
        (0.0, BACK_Y),
        (PIN_R, BACK_Y),
        (PIN_R, STEP_Y),
        (RELIEF_R, STEP_Y),
        (RELIEF_R, RELIEF_END_Y),
        (THREAD_R, RELIEF_END_Y),
        (THREAD_R, THREAD_END_Y),
    ]
    back_end, shank, step, relief, flank, thread = await add_line_chain(
        adapter, points, close=False
    )
    dome = check(
        "dome arc",
        await adapter.add_arc(0.0, TIP_Y - DOME_R, THREAD_R, THREAD_END_Y, 0.0, TIP_Y),
    )
    closure = check("pin closure", await adapter.add_line(0.0, TIP_Y, 0.0, BACK_Y))
    set_sketch_direct_db(adapter, False)
    for label, first, second in (
        ("thread-dome", f"{thread}.end", f"{dome}.start"),
        ("dome-closure", f"{dome}.end", f"{closure}.start"),
        ("closure-back", f"{closure}.end", f"{back_end}.start"),
        ("axis start", f"{axis}.start", f"{back_end}.start"),
        ("axis end", f"{axis}.end", f"{dome}.end"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, "coincident"))
    for label, entity, relation in (
        ("back end", back_end, "horizontal"),
        ("shank", shank, "vertical"),
        ("step", step, "horizontal"),
        ("relief floor", relief, "vertical"),
        ("relief flank", flank, "horizontal"),
        ("thread", thread, "vertical"),
        ("closure", closure, "vertical"),
        ("axis", axis, "vertical"),
    ):
        check(label, await adapter.add_sketch_constraint(entity, None, relation))
    await anchor_point_to_origin(
        adapter, f"{back_end}.start", 0.0, BACK_Y, "pin back end"
    )
    profile.record("BackEnd", '"ShankLength" - "PressGauge"')
    await add_diametric_linear_dimension(
        adapter, axis, shank, (PIN_R + 4.0, (BACK_Y + STEP_Y) / 2.0), "PinDia"
    )
    profile.record("PinDia", '"PinDia"')
    check(
        "shank length",
        await adapter.add_sketch_dimension(shank, None, "linear", SHANK_LEN),
    )
    profile.record("ShankLength", '"ShankLength"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        thread,
        (THREAD_R + 4.0, (STEP_Y + THREAD_END_Y) / 2.0),
        "ThreadDia",
    )
    profile.record("ThreadDia", '"ThreadDia"')
    # The thread from the step: the gauged face the nut stack hangs off
    # (drawing-guidelines.md rule 10 (dimension from a real feature)'s functional datum, mg_wheel_axle_spec.THREAD_LEN),
    # to the thread end at the dome's tangent.
    await dimension_between(
        adapter,
        f"{step}.end",
        f"{thread}.end",
        "vertical_distance",
        THREAD_LEN,
        "thread length",
    )
    profile.record("ThreadLength", '"ThreadLength"')
    # The relief: its width along the floor from the step, its Ø MAX.
    check(
        "relief width",
        await adapter.add_sketch_dimension(relief, None, "linear", RELIEF_WIDTH),
    )
    profile.record("ReliefWidth", '"ReliefWidth"')
    await add_diametric_linear_dimension(
        adapter, axis, relief, (RELIEF_R + 4.0, STEP_Y - 3.0), "ReliefDia"
    )
    profile.record("ReliefDia", '"ReliefDia"')
    # Overall from the back end's outer corner (where the drawing's extension
    # lines rise).
    await dimension_between(
        adapter,
        f"{shank}.start",
        f"{closure}.start",
        "vertical_distance",
        PIN_LEN,
        "pin length",
    )
    profile.record("PinLength", '"ShankLength" + "ThreadLength" + "DomeHeight"')
    check(
        "dome radius",
        await adapter.add_sketch_dimension(dome, None, "radial", DOME_R),
    )
    profile.record(
        "DomeR",
        '("ThreadDia" / 2 * "ThreadDia" / 2 + "DomeHeight" * "DomeHeight") '
        '/ (2 * "DomeHeight")',
    )
    await ensure_fully_defined(adapter, "pin profile")
    check("exit_sketch pin profile", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += profile.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    pin_volume = await volume_check(adapter, "pin", V_PROFILE, PIN_VOLUME_TOL)

    # The relief's two internal corners (drawing-guidelines.md rule 16), ONE fillet over both
    # circular edges, each picked on the floor's radius at its corner: the
    # step's FIRST (the drawing's inserted radius lands on the first pick's
    # edge), then the thread flank's.
    check(
        "fillet relief roots",
        await adapter.add_fillet(
            RELIEF_ROOT_R,
            [[RELIEF_R, STEP_Y, 0.0], [RELIEF_R, RELIEF_END_Y, 0.0]],
            propagate=False,
        ),
    )
    name_last_feature(adapter, "ReliefRoots")
    drive_jobs.append(
        (name_dimensions(adapter, "ReliefRoots", ["ReliefRootR"])[0], '"ReliefRootR"')
    )
    rooted = await volume_check(
        adapter, "relief roots", pin_volume + V_RELIEF_ROOTS, ROOTS_VOLUME_TOL
    )

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    driven = await volume_check(
        adapter, "driven pin (equations neutral)", rooted, NEUTRAL_VOLUME_TOL
    )

    # Cosmetic #4-40 from the thread's dome-end edge back to the relief, so
    # the shaded isometric shows the thread the callout names. It cuts nothing.
    adapter._zoom_to_fit(adapter.currentModel)
    check(
        f"cosmetic thread {THREAD}",
        await adapter.add_thread(
            AddThreadParameters(
                edge_point=[THREAD_MAJOR / 2.0, THREAD_END_Y, 0.0],
                standard="ansi_inch",
                size=THREAD,
                end_type="blind",
                depth=THREAD_LEN - RELIEF_WIDTH,
            )
        ),
    )
    await volume_check(adapter, "cosmetic thread cuts nothing", driven, 1e-6)

    # Named pin axis (local Y through the origin) so the magnifying wheel
    # revolves on it in the mated-DOF assembly (Axis1).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "pin axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_symmetric_tolerance(adapter, "PinProfile", "PinDia", PIN_DIA_TOL)
    set_dimension_bilateral_tolerance(
        adapter, "PinProfile", "ThreadLength", *deviations(THREAD_LEN_BAND)
    )
    _single_limits(adapter)
    _limit_pairs(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_dimension_callouts(adapter)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
