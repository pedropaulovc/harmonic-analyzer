r"""Build the oblique trammel's HUB locator pin (MHA-CH-06-TL-25; shop tooling).

A headed turned pin (``ch_rocker_arm_tl_oblique_hub_pin_spec``). One
Right-plane half-profile (sketch u -> model -Z, v -> radius; the cam-pin
idiom), revolved 360 degrees, so every size imports into the *Right view
where the pin lies as it is turned: ``PinProfile`` carries the Ø16 x 4 head
from the origin, the p6 press seat (modelled at its 10.218 low limit), 12
long, a real step down to the g6 strap locator (modelled at its 10.183 low
limit), 8 long, and the 0.5 x 45 degree lead chamfer at the top. Each fit
diameter carries its +0.011/0 print band, so the printed limits are the fit
limits (the pivot pin's convention). The lengths read as the lathe does
(rule 11): the overall from the head's bottom face, and the head thickness
and the press seat as a baseline from the head's seating face; the locator
is the remainder. ``HeadFillet`` rounds the seat-to-head corner R0.2 MAX
(rule 16; the pivot pin's ``SeatFillet``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_hub_pin.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
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
from ch_rocker_arm_tl_oblique_hub_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FIT_PLACES,
    HEAD_DIA,
    HEAD_LENGTH,
    ISOMETRIC_VIEW_NOTE,
    LEAD_CHAMFER,
    LOCATOR_DIA,
    LOCATOR_LENGTH,
    LOCATOR_PRINT_BAND,
    OVERALL_LENGTH,
    RADIUS_TOL_TYPE,
    SEAT_DIA,
    SEAT_LENGTH,
    SEAT_PRINT_BAND,
    SEAT_STATION,
    SHOULDER_FILLET_RADIUS,
)

PART_NAME = "ch-rocker-arm-tl-oblique-hub-pin"
MATERIAL = "Plain Carbon Steel"  # the registry row names the 1144 stress-proof
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

HEAD_R = HEAD_DIA / 2.0
SEAT_R = SEAT_DIA / 2.0
LOCATOR_R = LOCATOR_DIA / 2.0
V_CHAMFER = 2.0 * math.pi * (LOCATOR_R - LEAD_CHAMFER / 3.0) * LEAD_CHAMFER**2 / 2.0
V_TOTAL = (
    math.pi
    * (
        HEAD_R**2 * HEAD_LENGTH
        + SEAT_R**2 * SEAT_LENGTH
        + LOCATOR_R**2 * LOCATOR_LENGTH
    )
    - V_CHAMFER
)  # the R0.2 fillet adds about 0.3 mm^3, inside the 0.5 % gate


def _max_limit(adapter, feature: str, dimension_name: str) -> None:
    """A single MAX limit (shoulder radius, lead chamfer): the print shows the
    model value."""
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
        ("HeadDia", HEAD_DIA),
        ("HeadLength", HEAD_LENGTH),
        ("SeatDia", SEAT_DIA),
        ("SeatLength", SEAT_LENGTH),
        ("LocatorDia", LOCATOR_DIA),
        ("LocatorLength", LOCATOR_LENGTH),
        ("LeadChamfer", LEAD_CHAMFER),
        ("FilletR", SHOULDER_FILLET_RADIUS),
    ):
        await set_global(adapter, name, f"{value}mm")

    profile = SketchDims()
    check("create_sketch pin profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "pin axis", await adapter.add_centerline(0.0, 0.0, -OVERALL_LENGTH, 0.0)
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (0.0, HEAD_R),
            (-HEAD_LENGTH, HEAD_R),
            (-HEAD_LENGTH, SEAT_R),
            (-SEAT_STATION, SEAT_R),
            (-SEAT_STATION, LOCATOR_R),
            (-(OVERALL_LENGTH - LEAD_CHAMFER), LOCATOR_R),
            (-OVERALL_LENGTH, LOCATOR_R - LEAD_CHAMFER),
            (-OVERALL_LENGTH, 0.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    (
        head_bottom,
        head_od,
        head_top,
        seat_od,
        step,
        locator_od,
        chamfer,
        top,
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
        ("pin axis at the origin", f"{axis}.start", "origin", "coincident"),
        ("pin axis at the top", f"{axis}.end", f"{top}.end", "coincident"),
        ("head bottom at the origin", f"{head_bottom}.start", "origin", "coincident"),
        ("head bottom vertical", head_bottom, None, "vertical"),
        ("head OD horizontal", head_od, None, "horizontal"),
        ("head top vertical", head_top, None, "vertical"),
        ("seat OD horizontal", seat_od, None, "horizontal"),
        ("seat-locator step vertical", step, None, "vertical"),
        ("locator OD horizontal", locator_od, None, "horizontal"),
        ("top face vertical", top, None, "vertical"),
        ("axis line horizontal", axis_line, None, "horizontal"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    await add_diametric_linear_dimension(
        adapter, axis, head_od, (-HEAD_LENGTH / 2.0, HEAD_R + 4.0), "head diameter"
    )
    profile.record("HeadDia", '"HeadDia"')
    # Rule 11: the head thickness and the press seat read from the head's
    # seating face (its top, which bears on the carrier); both extension
    # lines there rise from the head's outer corner, clear of the fillet.
    await dimension_between(
        adapter,
        f"{head_top}.start",
        f"{head_bottom}.end",
        "horizontal_distance",
        HEAD_LENGTH,
        "seating face to the head's bottom face",
    )
    profile.record("HeadLength", '"HeadLength"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        seat_od,
        (-(HEAD_LENGTH + SEAT_LENGTH / 2.0), SEAT_R + 4.0),
        "press seat diameter",
    )
    profile.record("SeatDia", '"SeatDia"')
    await dimension_between(
        adapter,
        f"{head_top}.start",
        f"{step}.start",
        "horizontal_distance",
        SEAT_LENGTH,
        "seating face to the press seat's end",
    )
    profile.record("SeatLength", '"SeatLength"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        locator_od,
        (-(SEAT_STATION + LOCATOR_LENGTH / 2.0), LOCATOR_R + 4.0),
        "strap locator diameter",
    )
    profile.record("LocatorDia", '"LocatorDia"')
    # The overall, head bottom to top; the locator's 8.0 is its remainder.
    await dimension_between(
        adapter,
        f"{head_bottom}.end",
        f"{top}.start",
        "horizontal_distance",
        OVERALL_LENGTH,
        "overall length",
    )
    profile.record("PinLength", '"HeadLength" + "SeatLength" + "LocatorLength"')
    await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{chamfer}.end",
        "horizontal_distance",
        LEAD_CHAMFER,
        "lead chamfer length",
    )
    profile.record("LeadChamfer", '"LeadChamfer"')
    await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{chamfer}.end",
        "vertical_distance",
        LEAD_CHAMFER,
        "lead chamfer depth (45 degrees)",
    )
    profile.record("LeadChamferDepth", '"LeadChamfer"')
    await ensure_fully_defined(adapter, "pin profile")
    check("exit_sketch pin profile", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs = profile.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    await volume_check(adapter, "turned hub pin", V_TOTAL, 0.005 * V_TOTAL)

    # Shoulder radius at the seat's root against the head (rule 16), the
    # printed MAX. The pick lies on the corner circle (model Y = radius,
    # Z = station); the head's outer edges stand 2.9 away.
    check(
        "fillet HeadFillet",
        await adapter.add_fillet(
            SHOULDER_FILLET_RADIUS, [[0.0, SEAT_R, HEAD_LENGTH]], propagate=False
        ),
    )
    name_last_feature(adapter, "HeadFillet")
    drive_jobs.append(
        (name_dimensions(adapter, "HeadFillet", ["HeadFilletR"])[0], '"FilletR"')
    )
    await volume_check(adapter, "filleted hub pin", V_TOTAL, 0.005 * V_TOTAL)

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven hub pin (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The two matched fits, each at its low limit printed +0.011/0: p6 into
    # the carrier's HUB hole, g6 in the strap.
    set_dimension_bilateral_tolerance(
        adapter,
        "PinProfile",
        "SeatDia",
        *deviations(SEAT_PRINT_BAND),
        places=FIT_PLACES,
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "PinProfile",
        "LocatorDia",
        *deviations(LOCATOR_PRINT_BAND),
        places=FIT_PLACES,
    )
    _max_limit(adapter, "HeadFillet", "HeadFilletR")
    _max_limit(adapter, "PinProfile", "LeadChamfer")
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
