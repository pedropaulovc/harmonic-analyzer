r"""Build the oblique trammel's pivot pin (MHA-CH-06-TL-23; shop tooling).

A stepped turned pin (``ch_rocker_arm_tl_oblique_pivot_pin_spec``). Layout:

* ``PinProfile`` is a single native Right-plane half-profile revolved about
  +Z: unchanged bearing fit, narrow lower boss, integral captive flange,
  raised carrier seat and the extended h6 carrier journal.
* ``CrossHole`` is a real transverse through cut, not a cosmetic hole.
* ``SeatFillet`` / ``CarrierFillet`` retain R0.2 MAX seating corners.
* Hidden ``PinAxis``, ``CrossPinAxis``, ``CarrierSeat`` and
  ``FlangeLowerFace`` provide stable assembly mate references.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_pivot_pin.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_oblique_pivot_pin_spec import (
    AXIS_NAME,
    BEARING_DIA,
    BEARING_PRINT_BAND,
    BEARING_LENGTH,
    CARRIER_BAND,
    CARRIER_LENGTH,
    CARRIER_STATION,
    COLLAR_DIA,
    COLLAR_HEIGHT,
    COLLAR_STATION,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FIT_DIA,
    FIT_PLACES,
    ISOMETRIC_VIEW_NOTE,
    LEAD_CHAMFER,
    OVERALL_LENGTH,
    RADIUS_TOL_TYPE,
    SHOULDER_FILLET_RADIUS,
    CARRIER_SEAT_PLANE,
    CROSS_HOLE_DIA,
    CROSS_HOLE_BAND,
    CROSS_HOLE_FROM_END,
    CROSS_HOLE_STATION,
    CROSS_PIN_AXIS_NAME,
    FLANGE_BOTTOM_STATION,
    FLANGE_DIA,
    FLANGE_DIA_BAND,
    FLANGE_LOWER_PLANE,
    FLANGE_THICK,
    FLANGE_TOP_STATION,
    LOWER_BOSS_HEIGHT,
    UPPER_BOSS_HEIGHT,
    STOP_FACE_INSPECTION_NOTE,
)

PART_NAME = "ch-rocker-arm-tl-oblique-pivot-pin"
MATERIAL = "Plain Carbon Steel"  # the registry row names the 1144 stress-proof
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
    "Stop Face Inspection",
)

FIT_R = FIT_DIA / 2.0
BEARING_R = BEARING_DIA / 2.0
COLLAR_R = COLLAR_DIA / 2.0


def _chamfer_ring(radius: float) -> float:
    """One 45 degree lead chamfer ring (Pappus, centroid at R - c/3)."""
    return 2.0 * math.pi * (radius - LEAD_CHAMFER / 3.0) * LEAD_CHAMFER**2 / 2.0


# The shoulder fillets' sub-mm³ correction stays inside the volume gate.
V_TOTAL = (
    math.pi
    * (
        BEARING_R**2 * BEARING_LENGTH
        + COLLAR_R**2 * COLLAR_HEIGHT
        + FIT_R**2 * CARRIER_LENGTH
        + ((FLANGE_DIA / 2.0) ** 2 - COLLAR_R**2) * FLANGE_THICK
    )
    - _chamfer_ring(BEARING_R)
    - _chamfer_ring(FIT_R)
)


def _max_limit(adapter, feature: str, dimension_name: str) -> None:
    """One native MAX limit: the print shows the model value."""
    _, dimension = _named_dimension(adapter, feature, dimension_name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = RADIUS_TOL_TYPE
    if int(tolerance.Type) != RADIUS_TOL_TYPE:
        raise RuntimeError(
            f"{dimension_name}@{feature}: MAX tolerance type did not persist"
        )


def _log_equation_targets(
    adapter, drive_jobs: list[tuple[str, str]], phase: str
) -> None:
    """Identify an unintended reference driver without changing native state."""
    for target, _ in drive_jobs:
        name, feature = target.split("@", 1)
        _, dimension = _named_dimension(adapter, feature, name)
        _telemetry.info(
            f"pin equation target {phase}: {target}; "
            f"DrivenState={int(dimension.DrivenState)}; "
            f"SystemValue_mm={float(dimension.SystemValue) * 1000.0:.12g}"
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in (
        ("BearingDia", BEARING_DIA),
        ("FitDia", FIT_DIA),
        ("CollarDia", COLLAR_DIA),
        ("BearingLength", BEARING_LENGTH),
        ("UpperBossHeight", UPPER_BOSS_HEIGHT),
        ("CarrierLength", CARRIER_LENGTH),
        ("LeadChamfer", LEAD_CHAMFER),
        ("FilletR", SHOULDER_FILLET_RADIUS),
        ("FlangeDia", FLANGE_DIA),
        ("FlangeThick", FLANGE_THICK),
        ("LowerBossHeight", LOWER_BOSS_HEIGHT),
        ("CrossHoleDia", CROSS_HOLE_DIA),
        ("CrossHoleFromEnd", CROSS_HOLE_FROM_END),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Turned profile: bottom end at the origin, top at u = -OVERALL ----------
    pin = SketchDims()
    check("create_sketch pin profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "pin axis", await adapter.add_centerline(0.0, 0.0, -OVERALL_LENGTH, 0.0)
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (0.0, BEARING_R - LEAD_CHAMFER),
            (-LEAD_CHAMFER, BEARING_R),
            (-COLLAR_STATION, BEARING_R),
            (-COLLAR_STATION, COLLAR_R),
            (-FLANGE_BOTTOM_STATION, COLLAR_R),
            (-FLANGE_BOTTOM_STATION, FLANGE_DIA / 2.0),
            (-FLANGE_TOP_STATION, FLANGE_DIA / 2.0),
            (-FLANGE_TOP_STATION, COLLAR_R),
            (-CARRIER_STATION, COLLAR_R),
            (-CARRIER_STATION, FIT_R),
            (-(OVERALL_LENGTH - LEAD_CHAMFER), FIT_R),
            (-OVERALL_LENGTH, FIT_R - LEAD_CHAMFER),
            (-OVERALL_LENGTH, 0.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    (
        bottom_face,
        bottom_chamfer,
        bearing_od,
        collar_seat,
        lower_boss_od,
        flange_lower,
        flange_od,
        flange_upper,
        collar_od,
        collar_top,
        carrier_od,
        top_chamfer,
        top_face,
        axis_line,
    ) = lines
    for i in range(len(lines)):
        check(
            f"pin profile junction {i}",
            await adapter.add_sketch_constraint(
                f"{lines[i]}.end", f"{lines[(i + 1) % len(lines)]}.start", "coincident"
            ),
        )
    for label, first, second, relation in (
        ("pin axis horizontal", axis, None, "horizontal"),
        ("pin axis at the bottom end", f"{axis}.start", "origin", "coincident"),
        ("pin axis at the top end", f"{axis}.end", f"{top_face}.end", "coincident"),
        ("bottom face at the origin", f"{bottom_face}.start", "origin", "coincident"),
        ("bottom face vertical", bottom_face, None, "vertical"),
        ("bearing OD horizontal", bearing_od, None, "horizontal"),
        ("collar seat vertical", collar_seat, None, "vertical"),
        ("lower boss OD horizontal", lower_boss_od, None, "horizontal"),
        ("flange lower face vertical", flange_lower, None, "vertical"),
        ("flange OD horizontal", flange_od, None, "horizontal"),
        ("flange upper face vertical", flange_upper, None, "vertical"),
        (
            "narrow bosses same diameter",
            f"{lower_boss_od}.start", f"{collar_od}.start", "horizontal_points",
        ),
        ("collar OD horizontal", collar_od, None, "horizontal"),
        ("collar top vertical", collar_top, None, "vertical"),
        ("carrier OD horizontal", carrier_od, None, "horizontal"),
        ("top face vertical", top_face, None, "vertical"),
        ("axis line horizontal", axis_line, None, "horizontal"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    await add_diametric_linear_dimension(
        adapter,
        axis,
        bearing_od,
        (-BEARING_LENGTH / 2.0, BEARING_R + 4.0),
        "bearing section diameter",
    )
    pin.record("BearingDia", '"BearingDia"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        collar_od,
        (-(COLLAR_STATION + COLLAR_HEIGHT / 2.0), COLLAR_R + 4.0),
        "collar diameter",
    )
    pin.record("CollarDia", '"CollarDia"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        carrier_od,
        (-(CARRIER_STATION + CARRIER_LENGTH / 2.0), FIT_R + 4.0),
        "carrier section diameter",
    )
    pin.record("CarrierDia", '"FitDia"')
    await add_diametric_linear_dimension(
        adapter, axis, flange_od,
        (-(FLANGE_BOTTOM_STATION + FLANGE_THICK / 2.0), FLANGE_DIA / 2.0 + 4.0),
        "captive flange diameter",
    )
    pin.record("FlangeDia", '"FlangeDia"')
    for line, name, value in (
        (lower_boss_od, "LowerBossHeight", LOWER_BOSS_HEIGHT),
        (flange_od, "FlangeThick", FLANGE_THICK),
        (collar_od, "UpperBossHeight", UPPER_BOSS_HEIGHT),
    ):
        await dimension_between(
            adapter, f"{line}.start", f"{line}.end", "horizontal_distance",
            value, name,
        )
        pin.record(name, f'"{name}"')
    # Lengths from the top end, faced in the turning chucking (rule 11).
    await dimension_between(
        adapter,
        f"{collar_top}.end",
        f"{top_face}.end",
        "horizontal_distance",
        CARRIER_LENGTH,
        "top end to the collar top",
    )
    pin.record("CarrierLength", '"CarrierLength"')
    # Journal length is a shop control, not the difference of a loose overall
    # and four collar dimensions. The overall below is a genuine reference.
    await dimension_between(
        adapter, f"{bottom_face}.start", f"{collar_seat}.start",
        "horizontal_distance", BEARING_LENGTH, "bearing journal length",
    )
    pin.record("BearingLength", '"BearingLength"')
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [axis_line], 0)
    extension = _early_bound(model.Extension, "IModelDocExtension")
    display, status = extension.AddSpecificDimension(
        -OVERALL_LENGTH / 2000.0, 0.025, 0.0,
        11,  # swDimensionType_e.swHorLinearDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"pin overall reference: AddSpecificDimension failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    overall = _early_bound(display.GetDimension2(0), "IDimension")
    overall.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(overall.DrivenState) != 1:
        raise RuntimeError("pin overall reference did not become driven")
    pin.record("PinLength")
    for chamfer, name in ((bottom_chamfer, "Bottom"), (top_chamfer, "Top")):
        await dimension_between(
            adapter,
            f"{chamfer}.start",
            f"{chamfer}.end",
            "horizontal_distance",
            LEAD_CHAMFER,
            f"{name.lower()} lead chamfer length",
        )
        pin.record(f"{name}Chamfer", '"LeadChamfer"')
        await dimension_between(
            adapter,
            f"{chamfer}.start",
            f"{chamfer}.end",
            "vertical_distance",
            LEAD_CHAMFER,
            f"{name.lower()} lead chamfer depth (45 degrees)",
        )
        pin.record(f"{name}ChamferDepth", '"LeadChamfer"')
    await ensure_fully_defined(adapter, "pin profile")
    check("exit_sketch pin profile", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += pin.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    await volume_check(adapter, "turned pin", V_TOTAL, 0.005 * V_TOTAL)

    # Shoulder radii (rule 16), each the printed MAX. A pick lies on its
    # corner circle (model Y = radius, Z = station); the collar's outer edges
    # stand 1.25 away.
    for feature, dimension, radius, station in (
        ("SeatFillet", "SeatFilletR", BEARING_R, COLLAR_STATION),
        ("CarrierFillet", "CarrierFilletR", FIT_R, CARRIER_STATION),
    ):
        check(
            f"fillet {feature}",
            await adapter.add_fillet(
                SHOULDER_FILLET_RADIUS, [[0.0, radius, station]], propagate=False
            ),
        )
        name_last_feature(adapter, feature)
        drive_jobs.append(
            (name_dimensions(adapter, feature, [dimension])[0], '"FilletR"')
        )
    await volume_check(adapter, "filleted pin", V_TOTAL, 0.005 * V_TOTAL)
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pin axis")
    name_last_feature(adapter, AXIS_NAME)


    for name, station, expression in (
        (
            CARRIER_SEAT_PLANE, CARRIER_STATION,
            '"BearingLength" + "LowerBossHeight" + "FlangeThick" + "UpperBossHeight"',
        ),
        (
            FLANGE_LOWER_PLANE, FLANGE_BOTTOM_STATION,
            '"BearingLength" + "LowerBossHeight"',
        ),
    ):
        check(
            f"create_plane {name}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Front Plane", offset=station
                )
            ),
        )
        name_last_feature(adapter, name)
        drive_jobs.append((name_dimensions(adapter, name, [f"{name}Offset"])[0], expression))
        blank_reference_geometry(adapter, ((name, "PLANE"),))
    await name_bore_axis(
        adapter, "Front Plane", CROSS_HOLE_STATION, "Top Plane", 0.0,
        "clevis cross pin",
        drive_a='"BearingLength" + "LowerBossHeight" + "FlangeThick" + "UpperBossHeight" + "CarrierLength" - "CrossHoleFromEnd"',
        drive_jobs=drive_jobs,
    )
    name_last_feature(adapter, CROSS_PIN_AXIS_NAME)

    # Right-plane circle normal to X; the end datum is the actual top-end
    # station, so the printed six-mm ligament does not stack from the bottom.
    cross = SketchDims()
    check("create_sketch cross hole", await adapter.create_sketch("Right"))
    end_line = check(
        "cross hole top end reference",
        await adapter.add_centerline(0.0, 0.0, -OVERALL_LENGTH, 0.0),
    )
    check("cross end reference horizontal", await adapter.add_sketch_constraint(end_line, None, "horizontal"))
    check("cross end reference origin", await adapter.add_sketch_constraint(f"{end_line}.start", "origin", "coincident"))
    await dimension_between(
        adapter, f"{end_line}.start", f"{end_line}.end", "horizontal_distance",
        OVERALL_LENGTH, "cross hole top end station",
    )
    cross.record("CrossEndStation", '"BearingLength" + "LowerBossHeight" + "FlangeThick" + "UpperBossHeight" + "CarrierLength"')
    circle = check(
        "cross hole circle", await adapter.add_circle(-CROSS_HOLE_STATION, 0.0, CROSS_HOLE_DIA / 2.0)
    )
    check(
        "cross hole on pin centre",
        await adapter.add_sketch_constraint(f"{circle}.center", f"{end_line}.end", "horizontal_points"),
    )
    await dimension_between(
        adapter, f"{circle}.center", f"{end_line}.end", "horizontal_distance",
        CROSS_HOLE_FROM_END, "cross hole from end",
    )
    cross.record("CrossHoleFromEnd", '"CrossHoleFromEnd"')
    check("cross hole diameter", await adapter.add_sketch_dimension(circle, None, "diameter", CROSS_HOLE_DIA))
    cross.record("CrossHoleDia", '"CrossHoleDia"')
    await ensure_fully_defined(adapter, "clevis cross hole")
    check("exit_sketch cross hole", await adapter.exit_sketch())
    name_last_feature(adapter, "CrossHoleProfile")
    drive_jobs += cross.apply(adapter, "CrossHoleProfile")
    check(
        "cut cross hole through pin",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=FIT_DIA * 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CrossHole")
    # Intersection volume of the perpendicular cylinders, integrated across
    # the drilled diameter (Simpson's rule); no fictitious cylindrical length.
    n = 2000
    step = CROSS_HOLE_DIA / n
    removed = 0.0
    for index in range(n + 1):
        y = -CROSS_HOLE_DIA / 2.0 + index * step
        area = 4.0 * math.sqrt(max(0.0, (CROSS_HOLE_DIA / 2.0) ** 2 - y * y)) * math.sqrt(FIT_R**2 - y * y)
        weight = 1 if index in (0, n) else (4 if index % 2 else 2)
        removed += weight * area
    finished_volume = V_TOTAL - removed * step / 3.0
    await force_rebuild(adapter)
    _log_equation_targets(adapter, drive_jobs, "before")
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    _log_equation_targets(adapter, drive_jobs, "after")
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pivot pin (equations neutral)", finished_volume, 0.005 * V_TOTAL
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The two matched fits: k5 in the 6200 inner races, h6 in the carrier.
    set_dimension_bilateral_tolerance(
        adapter,
        "PinProfile",
        "BearingDia",
        *deviations(BEARING_PRINT_BAND),
        places=FIT_PLACES,
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "PinProfile",
        "CarrierDia",
        *deviations(CARRIER_BAND),
        places=FIT_PLACES,
    )
    set_dimension_bilateral_tolerance(
        adapter, "PinProfile", "FlangeDia", *deviations(FLANGE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "CrossHoleProfile", "CrossHoleDia", *deviations(CROSS_HOLE_BAND)
    )
    # The fitted boss nominal is reference-only; its callout, not a loose
    # title-block stack, controls the actual floor gap with no bearing preload.
    for name in ("LowerBossHeight", "PinLength"):
        display, dimension = _named_dimension(adapter, "PinProfile", name)
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = 0
        display.SetText(1, "(")
        display.SetText(2, ")")
        if (str(display.GetText(1) or ""), str(display.GetText(2) or "")) != ("(", ")"):
            raise RuntimeError(f"{name} reference display did not persist")
    for feature, dimension in (
        ("PinProfile", "TopChamfer"),
        ("PinProfile", "TopChamferDepth"),
        ("SeatFillet", "SeatFilletR"),
        ("CarrierFillet", "CarrierFilletR"),
    ):
        _max_limit(adapter, feature, dimension)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "Stop Face Inspection": STOP_FACE_INSPECTION_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
