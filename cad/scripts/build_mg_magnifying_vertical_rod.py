r"""Reproduction script: magnifying-lever vertical rod (book ch. 20, pp. 46-49).

The smaller vertical brass rod that hangs from the clamp block on the
magnifying lever; the output fixture slides on it and the wire to the
magnifying wheel hooks below. #1559: its top end is a #4-40 thread turned
down from the Ø5 bar, with a relief at the shoulder; it screws into the
clamp's bottom-face tap until the shoulder seats (``mg_rod_clamp_joint``).
The bottom end is a full hemisphere.

Layout: rod axis local +X, origin at the thread tip on the axis (the
assembly turns +X straight down). Stations: tip chamfer to TIP_CHAMFER,
thread at the basic major to RELIEF_START_X, relief to the shoulder at
SHOULDER_X, Ø5 body to the dome's tip at ROD_LENGTH.

Built as ONE Front-plane revolve (RodProfile -> Rod): every printed diameter
and length is a named dimension in that sketch, the thread length and the
body length both from the shoulder, so the drawing inserts them as model
items (mg_magnifying_vertical_rod_spec.DRAWING_DIMENSIONS). The overall is a
driven reference dimension shown "(132.5)". The #4-40 end carries a cosmetic
thread so the pictorial matches the callout.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_magnifying_vertical_rod.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
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
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _fit_deviations import deviations
import _telemetry
from mg_magnifying_vertical_rod_spec import (
    BODY_LENGTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISO_VIEW_NOTE,
    REFERENCE_DIMENSIONS,
    RELIEF_DIA,
    RELIEF_START_X,
    RELIEF_WIDTH,
    ROD_DIA,
    ROD_LENGTH,
    ROD_THREAD_LEN,
    ROD_THREAD_LEN_BAND,
    SHOULDER_X,
    SINGLE_LIMITS,
    THREAD,
    THREAD_BASIC_MINOR,
    THREAD_MAJOR,
    TIP_CHAMFER,
)

PART_NAME = "mg-magnifying-vertical-rod"
MATERIAL = "Brass"  # see _appearance.apply_material docstring

R = ROD_DIA / 2.0
THREAD_R = THREAD_MAJOR / 2.0
MINOR_R = THREAD_BASIC_MINOR / 2.0
RELIEF_R = RELIEF_DIA / 2.0
BODY_END_X = ROD_LENGTH - R  # where the body meets the bottom hemisphere
V_CHAMFER = math.pi * TIP_CHAMFER / 3.0 * (MINOR_R**2 + MINOR_R * THREAD_R + THREAD_R**2)
V_THREAD = math.pi * THREAD_R**2 * (RELIEF_START_X - TIP_CHAMFER)
V_RELIEF = math.pi * RELIEF_R**2 * RELIEF_WIDTH
V_BODY = math.pi * R**2 * (BODY_LENGTH - R)
V_DOME = 2.0 / 3.0 * math.pi * R**3
V_TOTAL = V_CHAMFER + V_THREAD + V_RELIEF + V_BODY + V_DOME


def _make_driven(adapter, dimension_id: str, label: str) -> None:
    """Turn a just-made sketch dimension into a DRIVEN (reference) one
    (build_pn_pen_v_block._make_driven)."""
    display = _early_bound(adapter._sketch_entities[dimension_id], "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(dimension.DrivenState) != 1:
        raise RuntimeError(f"{label}: dimension did not become driven")


def _single_limits(adapter) -> None:
    """Each SINGLE_LIMITS dimension printed as a single MIN or MAX limit
    (build_pd_support_bar._single_limit): SOLIDWORKS prints the nominal then
    the limit word, so the model value is the limit itself."""
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


def _author_reference_dimensions(adapter) -> None:
    """Show each driven dimension as a reference: no tolerance, "(132.5)"
    (build_pn_pen_v_block._author_reference_dimensions)."""
    for feature_name, dimension_name in REFERENCE_DIMENSIONS:
        display, dimension = _named_dimension(adapter, feature_name, dimension_name)
        label = f"{dimension_name}@{feature_name}"
        if int(dimension.DrivenState) != 1:
            raise RuntimeError(f"{label}: a reference dimension must be driven")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = 0  # swTolType_e.swTolNONE; property put, no success retval
        # The native prefix/suffix channel around the live model value.
        display.SetText(1, "(")
        display.SetText(2, ")")
        if (
            int(tolerance.Type) != 0
            or (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
            != ("(", ")")
            or not bool(display.ShowDimensionValue)
        ):
            raise RuntimeError(f"{label}: reference display did not persist")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import AddThreadParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units. Each profile dim below is driven from these via the
    # deferred drive batch.
    for name, value in (
        ("RodDia", ROD_DIA),
        ("BodyLength", BODY_LENGTH),
        ("ThreadDia", THREAD_MAJOR),
        ("ThreadMinorDia", THREAD_BASIC_MINOR),
        ("ThreadLength", ROD_THREAD_LEN),
        ("ReliefWidth", RELIEF_WIDTH),
        ("ReliefDia", RELIEF_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Half-section about local +X (Front sketch u, v = model x, y): tip on the
    # axis, 45 deg chamfer to the basic minor, thread at the basic major,
    # relief, shoulder, Ø5 body, bottom hemisphere back to the axis.
    profile = SketchDims()
    check("create_sketch rod profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check("rod axis", await adapter.add_centerline(0.0, 0.0, ROD_LENGTH, 0.0))
    points = [
        (0.0, 0.0),
        (0.0, MINOR_R),
        (TIP_CHAMFER, THREAD_R),
        (RELIEF_START_X, THREAD_R),
        (RELIEF_START_X, RELIEF_R),
        (SHOULDER_X, RELIEF_R),
        (SHOULDER_X, R),
        (BODY_END_X, R),
    ]
    tip_face, chamfer, thread, step, relief, shoulder, body = await add_line_chain(
        adapter, points, close=False
    )
    dome = check(
        "dome arc",
        await adapter.add_arc(BODY_END_X, 0.0, ROD_LENGTH, 0.0, BODY_END_X, R),
    )
    closure = check("rod closure", await adapter.add_line(ROD_LENGTH, 0.0, 0.0, 0.0))
    set_sketch_direct_db(adapter, False)
    for label, first, second in (
        ("body-dome", f"{body}.end", f"{dome}.end"),
        ("dome-closure", f"{dome}.start", f"{closure}.start"),
        ("closure-tip", f"{closure}.end", f"{tip_face}.start"),
        ("axis start", f"{axis}.start", f"{tip_face}.start"),
        ("axis end", f"{axis}.end", f"{dome}.start"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, "coincident"))
    check(
        "anchor thread tip at origin",
        await adapter.add_sketch_constraint(f"{tip_face}.start", "origin", "coincident"),
    )
    for label, entity, relation in (
        ("tip face", tip_face, "vertical"),
        ("thread", thread, "horizontal"),
        ("relief step", step, "vertical"),
        ("relief floor", relief, "horizontal"),
        ("shoulder", shoulder, "vertical"),
        ("body", body, "horizontal"),
        ("closure", closure, "horizontal"),
        ("axis", axis, "horizontal"),
    ):
        check(label, await adapter.add_sketch_constraint(entity, None, relation))
    check(
        "dome tangent to body",
        await adapter.add_sketch_constraint(body, dome, "tangent"),
    )
    # Record each dim into SketchDims as it is emitted (creation order).
    # The tip chamfer: down to the basic minor, 45 deg over its length.
    await add_diametric_linear_dimension(
        adapter, axis, f"{chamfer}.start", (-3.0, MINOR_R), "TipMinorDia"
    )
    profile.record("TipMinorDia", '"ThreadMinorDia"')
    await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{chamfer}.end",
        "horizontal_distance",
        TIP_CHAMFER,
        "tip chamfer",
    )
    profile.record("TipChamfer", '("ThreadDia" - "ThreadMinorDia") / 2')
    await add_diametric_linear_dimension(
        adapter, axis, thread, ((TIP_CHAMFER + RELIEF_START_X) / 2.0, 6.0), "ThreadDia"
    )
    profile.record("ThreadDia", '"ThreadDia"')
    # The thread from the shoulder (drawing-guidelines.md rule 10: the seating
    # face is the functional datum), measured to the tip face.
    await dimension_between(
        adapter,
        f"{shoulder}.end",
        f"{chamfer}.start",
        "horizontal_distance",
        ROD_THREAD_LEN,
        "thread length",
    )
    profile.record("ThreadLength", '"ThreadLength"')
    check(
        "relief width",
        await adapter.add_sketch_dimension(relief, None, "linear", RELIEF_WIDTH),
    )
    profile.record("ReliefWidth", '"ReliefWidth"')
    await add_diametric_linear_dimension(
        adapter, axis, relief, ((RELIEF_START_X + SHOULDER_X) / 2.0, -4.0), "ReliefDia"
    )
    profile.record("ReliefDia", '"ReliefDia"')
    await add_diametric_linear_dimension(
        adapter, axis, body, (ROD_LENGTH / 2.0, R + 4.0), "RodDia"
    )
    profile.record("RodDia", '"RodDia"')
    # The overall, tip to dome tip: made before the body length (so it never
    # over-defines) and turned driven at once, a "(132.5)" reference.
    overall = await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{dome}.start",
        "horizontal_distance",
        ROD_LENGTH,
        "overall length",
    )
    _make_driven(adapter, overall, "overall length")
    profile.record("OverallLength")
    # The body from the shoulder to the dome's tip: the hanging length.
    await dimension_between(
        adapter,
        f"{shoulder}.end",
        f"{dome}.start",
        "horizontal_distance",
        BODY_LENGTH,
        "body length",
    )
    profile.record("BodyLength", '"BodyLength"')
    check(
        "dome radius",
        await adapter.add_sketch_dimension(dome, None, "radial", R),
    )
    profile.record("DomeR", '"RodDia" / 2')
    await ensure_fully_defined(adapter, "rod profile")
    check("exit_sketch rod profile", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += profile.apply(adapter, "RodProfile")
    check("revolve rod", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Rod")
    await volume_check(adapter, "rod", V_TOTAL, 0.005 * V_TOTAL)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    driven = await volume_check(
        adapter, "driven rod (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )

    # Cosmetic #4-40 from the chamfer's major-diameter edge back to the relief,
    # so the shaded isometric shows the thread the callout names. It cuts
    # nothing.
    adapter._zoom_to_fit(adapter.currentModel)
    check(
        f"cosmetic thread {THREAD}",
        await adapter.add_thread(
            AddThreadParameters(
                edge_point=[TIP_CHAMFER, THREAD_R, 0.0],
                standard="ansi_inch",
                size=THREAD,
                end_type="blind",
                depth=RELIEF_START_X - TIP_CHAMFER,
            )
        ),
    )
    await volume_check(adapter, "cosmetic thread cuts nothing", driven, 1e-6)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "RodProfile", "ThreadLength", *deviations(ROD_THREAD_LEN_BAND)
    )
    _single_limits(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _author_reference_dimensions(adapter)
    apply_drawing_properties(adapter, PART_NAME, {"Iso View Note": ISO_VIEW_NOTE})
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
