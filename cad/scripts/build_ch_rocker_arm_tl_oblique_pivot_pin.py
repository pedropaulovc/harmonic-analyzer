r"""Build the oblique trammel's pivot pin (MHA-CH-06-TL-23; shop tooling).

A stepped turned pin (``ch_rocker_arm_tl_oblique_pivot_pin_spec``). Layout:

* ``PinProfile``: one Right-plane half-profile (sketch u -> model -Z, v ->
  radius; the cam-pin idiom), revolved 360 degrees, so every size imports
  into the *Right view where the pin lies as it is turned. Bottom to top:
  the Ø10 k5 bearing section with its lead chamfer, the Ø12.70 collar and
  the Ø10 h6 carrier section with its lead chamfer. The two equal-nominal
  fit diameters are two independent model dimensions, each with its own
  band; the lengths read from the top end (rule 11).
* ``SeatFillet`` / ``CarrierFillet``: R0.2 MAX at the collar's two
  shoulder corners.
* ``PinAxis``: a hidden reference axis on the turned axis (the Right and Top
  planes' intersection), which the jig assembly mates the carrier on.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_pivot_pin.py
"""

from __future__ import annotations

import math
import sys

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
    TOP_TO_COLLAR_SEAT,
)

PART_NAME = "ch-rocker-arm-tl-oblique-pivot-pin"
MATERIAL = "Plain Carbon Steel"  # the registry row names the 1144 stress-proof
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

FIT_R = FIT_DIA / 2.0
BEARING_R = BEARING_DIA / 2.0
COLLAR_R = COLLAR_DIA / 2.0


def _chamfer_ring(radius: float) -> float:
    """One 45 degree lead chamfer ring (Pappus, centroid at R - c/3)."""
    return 2.0 * math.pi * (radius - LEAD_CHAMFER / 3.0) * LEAD_CHAMFER**2 / 2.0


# The two R0.2 fillets add about 0.5 mm^3 to ~2700 mm^3, inside the 0.5 % gate.
V_TOTAL = (
    math.pi
    * (
        BEARING_R**2 * BEARING_LENGTH
        + COLLAR_R**2 * COLLAR_HEIGHT
        + FIT_R**2 * CARRIER_LENGTH
    )
    - _chamfer_ring(BEARING_R)
    - _chamfer_ring(FIT_R)
)


def _max_limit(adapter, feature: str, dimension_name: str) -> None:
    """A shoulder radius as a single MAX limit: the print shows the model value."""
    _, dimension = _named_dimension(adapter, feature, dimension_name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = RADIUS_TOL_TYPE
    if int(tolerance.Type) != RADIUS_TOL_TYPE:
        raise RuntimeError(
            f"{dimension_name}@{feature}: MAX tolerance type did not persist"
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in (
        ("BearingDia", BEARING_DIA),
        ("FitDia", FIT_DIA),
        ("CollarDia", COLLAR_DIA),
        ("BearingLength", BEARING_LENGTH),
        ("CollarHeight", COLLAR_HEIGHT),
        ("CarrierLength", CARRIER_LENGTH),
        ("LeadChamfer", LEAD_CHAMFER),
        ("FilletR", SHOULDER_FILLET_RADIUS),
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
    await dimension_between(
        adapter,
        f"{collar_seat}.start",
        f"{top_face}.end",
        "horizontal_distance",
        TOP_TO_COLLAR_SEAT,
        "top end to the collar seat",
    )
    pin.record("CollarSeatStation", '"CollarHeight" + "CarrierLength"')
    await dimension_between(
        adapter,
        f"{axis_line}.start",
        f"{axis_line}.end",
        "horizontal_distance",
        OVERALL_LENGTH,
        "overall length",
    )
    pin.record("PinLength", '"BearingLength" + "CollarHeight" + "CarrierLength"')
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

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pivot pin (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
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
    for feature, dimension in (
        ("SeatFillet", "SeatFilletR"),
        ("CarrierFillet", "CarrierFilletR"),
    ):
        _max_limit(adapter, feature, dimension)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
