r"""Reproduction script: pinion lift rod (book ch. 25).

The second Ø6.35 rod of the swing rig, running through the pivot
blocks' LOW west bores, parallel to (and 4.51 below) the strap torque
shaft. Turning it by the engage lever (build_pinion_lever.py, clamped
on its front end) spins the two eccentric cam collars pinned to it
(build_pinion_cam.py, PR8); their rising ODs lift the straps' follower
pins resting on them from above and swing the drum east into mesh
(page001_img01). PR5's integral radial cam pins are RETIRED -- the
photo shows plain rod + separate set-pinned collars, and the collar
mechanism replaced the crossed-pin lift.

Layout: rod axis Z, z 0..202, plain cylinder; crowned back end. U36: the
MHA-135 pin hole crosses it along local X, 4.0 in from the flat front end
(the lever hub's mid-engagement), match-drilled at assembly.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_lift_rod.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_prefix,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from pinion_lever_geometry import PIN_HOLE_DIA, ROD_PIN_HOLE_FROM_END
from pinion_lift_rod_spec import (
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    END_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    ROD_DIA,
    ROD_DIA_BAND,
    ROD_LEN,
    SURFACE_FINISHES,
)

PART_NAME = "pinion-lift-rod"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.68)

# ROD_DIA rides the block bores, same stock as the torque shaft (derived).
# ROD_LEN spans machine z -114..+88 (PR7): back end FLUSH with the back
# block's outer face (+88, crowned below); the front end reaches just far
# enough south of the front block (-104) for the lever's clamp hub.
# CAP_SAG is the back-end crown sagitta (the p.69 dome; the front end hides
# under the lever hub's own domed cap). All three live in
# pinion_lift_rod_spec.py, the dimensional contract the drawing shares.

ROD_R = ROD_DIA / 2.0
CAP_R = (ROD_R**2 + CAP_SAG**2) / (2.0 * CAP_SAG)  # 4.80 crown sphere radius
V_CAP = math.pi * CAP_SAG**2 * (3.0 * CAP_R - CAP_SAG) / 3.0  # 19.85

V_ROD = math.pi * ROD_R**2 * ROD_LEN


def _pin_hole_removed() -> float:
    """Volume a diametral X hole of PIN_HOLE_DIA takes out of the solid rod:
    the hole's chord width times the rod's full chord at each height
    (Simpson over the hole's y extent)."""
    r = PIN_HOLE_DIA / 2.0
    n = 2000
    h = 2.0 * r / n

    def slab(y: float) -> float:
        width = 2.0 * math.sqrt(max(r * r - y * y, 0.0))
        return width * 2.0 * math.sqrt(max(ROD_R**2 - y * y, 0.0))

    total = slab(-r) + slab(r)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * slab(-r + i * h)
    return total * h / 3.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the rod diameter, length and crown
    # sagitta -- RodDia/RodLen drive the marked drawing dims, CapSag the crown
    # profile. The mm suffix is load-bearing -- this is an INCH document and
    # the equation manager reads BARE numbers in document units (an unsuffixed
    # 6.35 = 6.35 in).
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "RodLen", f"{ROD_LEN}mm")
    await set_global(adapter, "CapSag", f"{CAP_SAG}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    await set_global(adapter, "PinHoleFromEnd", f"{ROD_PIN_HOLE_FROM_END}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Rod along +Z: on-axis circle (origin centre), only the diameter recorded.
    rod = SketchDims()
    check("create_sketch rod", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        ROD_R,
        "rod",
        dims=rod,
        names=("RodCx", "RodCz", "RodDia"),
        drives=(None, None, '"RodDia"'),
    )
    await ensure_fully_defined(adapter, "rod sketch")
    check("exit_sketch rod", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += rod.apply(adapter, "RodProfile")
    check(
        "extrude rod",
        await adapter.create_extrusion(ExtrusionParameters(depth=ROD_LEN)),
    )
    name_last_feature(adapter, "Rod")
    depth_dim = name_dimensions(adapter, "Rod", ["Depth"])
    drive_jobs += [(depth_dim[0], '"RodLen"')]
    volume = await volume_check(adapter, "rod", V_ROD, 0.005 * V_ROD)

    expected = volume

    # Back-end crown (PR7, item 13): shallow spherical cap proud of the flush
    # back end -- a rim->apex profile on the RIGHT Plane revolved about the
    # axis.  The Right Plane (sketch u = -z, v along y) is the plane the side
    # view looks at, so the crown's SR imports into that view beside the length
    # and the pin hole (U36).  With the axis running along sketch u the rim ->
    # apex arc is the minor CCW lobe: rim at ~139 deg, apex at 180 deg about
    # the on-axis centre.
    from solidworks_mcp.adapters.base import RevolveParameters

    u_base, u_apex = -ROD_LEN, -(ROD_LEN + CAP_SAG)
    u_centre = -(ROD_LEN + CAP_SAG - CAP_R)
    cap = SketchDims()
    check("create_sketch back cap", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    check(
        "back cap centerline",
        await adapter.add_centerline(u_base, 0.0, u_apex, 0.0),
    )
    base = check(
        "back cap base",
        await adapter.add_line(u_base, 0.0, u_base, ROD_R),
    )
    arc = check(
        "back cap arc",
        await adapter.add_arc(u_centre, 0.0, u_base, ROD_R, u_apex, 0.0),
    )
    close = check(
        "back cap close",
        await adapter.add_line(u_apex, 0.0, u_base, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "back cap base vertical",
        await adapter.add_sketch_constraint(base, None, "vertical"),
    )
    check(
        "back cap close horizontal",
        await adapter.add_sketch_constraint(close, None, "horizontal"),
    )
    check(
        "back cap rim reach",
        await adapter.add_sketch_dimension(
            f"{base}.end", "origin", "vertical_distance", ROD_R
        ),
    )
    cap.record("CapRim", '"RodDia" / 2')
    check(
        "back cap sagitta",
        await adapter.add_sketch_dimension(
            f"{close}.start", f"{close}.end", "horizontal_distance", CAP_SAG
        ),
    )
    cap.record("CapSagDim", '"CapSag"')
    check(
        "back cap on axis",
        await adapter.add_sketch_constraint(
            f"{base}.start", "origin", "horizontal_points"
        ),
    )
    check(
        "back cap station",
        await adapter.add_sketch_dimension(
            f"{base}.start", "origin", "horizontal_distance", ROD_LEN
        ),
    )
    cap.record("CapZ", '"RodLen"')
    check(
        "back cap radius",
        await adapter.add_sketch_dimension(arc, None, "radial", CAP_R),
    )
    cap.record(
        "CapR",
        '("RodDia" / 2 * "RodDia" / 2 + "CapSag" * "CapSag") / (2 * "CapSag")',
    )
    await ensure_fully_defined(adapter, "back cap sketch")
    check("exit_sketch back cap", await adapter.exit_sketch())
    name_last_feature(adapter, "BackCapProfile")
    drive_jobs += cap.apply(adapter, "BackCapProfile")
    check(
        "revolve back cap",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "BackCap")
    expected += V_CAP
    await volume_check(adapter, "back cap", expected, 0.03 * V_CAP)

    # U36 pin hole: a diametral cross-hole along X at the lever's
    # mid-engagement, sketched on the Right Plane (normal X; sketch u = -z) --
    # the plane the side view looks at, with the crown -- and cut mid-plane
    # twice the rod diameter deep.  (ThroughAll + both_directions cut only ONE
    # side on the farm, r7: the adapter falls back to single-sided ThroughAll
    # when the install has no swEndCondThroughAllBoth.)  The origin sits on
    # the flat front end face, so the circle's axial anchor IS the front-end
    # station the print carries.  Its mirror station (z -4) lies outside the rod, so a wrong side
    # cuts nothing and the volume gate fails loud.
    v_hole = _pin_hole_removed()
    pin_hole = SketchDims()
    check("create_sketch pin hole", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        -ROD_PIN_HOLE_FROM_END,
        0.0,
        PIN_HOLE_DIA / 2.0,
        "pin hole",
        dims=pin_hole,
        names=("PinHoleZ", "PinHoleY", "PinHoleDia"),
        drives=('"PinHoleFromEnd"', None, '"PinHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin_hole.apply(adapter, "PinHoleProfile")
    cut = await adapter.create_cut_extrude(
        ExtrusionParameters(
            depth=2.0 * ROD_DIA, both_directions=True
        )
    )
    if not cut.is_success:
        raise RuntimeError(f"pin hole cut failed: {cut.error}")
    name_last_feature(adapter, "PinHole")
    expected -= v_hole
    await volume_check(adapter, "pin hole", expected, 0.05 * v_hole)

    # Named centreline axis (Axis1): the assembly's revolute (coaxial to the
    # block's lift-bore axis) and the cam/lever clamps all key off it (PR8).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "rod axis")
    # Named pin-hole axis (along X at the pin station): the MHA-135 pin's
    # coaxial reference in the assembly.
    await name_bore_axis(
        adapter, "Top Plane", 0.0, "Front Plane", ROD_PIN_HOLE_FROM_END, "lever pin"
    )

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven lift rod (equations neutral)", expected, 0.03 * V_CAP
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "RodProfile", "RodDia", *deviations(ROD_DIA_BAND)
    )
    set_dimension_prefix(adapter, "BackCapProfile", "CapR", "SR")
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
