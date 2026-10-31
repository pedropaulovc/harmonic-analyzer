r"""Reproduction script: pinion lift rod (book ch. 25).

The second Ø6.35 rod of the swing rig, running through the pivot
blocks' LOW west bores, parallel to (and 4.51 below) the strap torque
shaft. Turning it by the engage lever (build_dt_pinion_lever.py, clamped
on its front end) spins the two eccentric cam collars pinned to it
(build_dt_pinion_cam.py, PR8); their rising ODs lift the straps' follower
pins resting on them from above and swing the drum east into mesh
(page001_img01). PR5's integral radial cam pins are RETIRED -- the
photo shows plain rod + separate set-pinned collars, and the collar
mechanism replaced the crossed-pin lift.

Layout: rod axis Z, z 0..ROD_LEN, one revolved half-profile crowned at its
back end. U36: the MHA-DT-30 pin hole crosses it along local X, 4.0 in from
the flat front end (the lever hub's mid-engagement), match-drilled at assembly.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_pinion_lift_rod.py
"""

from __future__ import annotations

import math
import sys

from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _drawing_prefix import set_dimension_prefix
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _document_units import apply_package_model_units
from _part_properties import part_drawing_unit
from dt_pinion_lever_geometry import PIN_HOLE_DIA, ROD_PIN_HOLE_FROM_END
from dt_pinion_lift_rod_spec import (
    CAP_R,
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    ROD_DIA,
    ROD_DIA_BAND,
    ROD_LEN,
    SURFACE_FINISHES,
    UNIT,
)

PART_NAME = "dt-pinion-lift-rod"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.68)

# ROD_DIA rides the block bores, same stock as the torque shaft (derived).
# ROD_LEN (pinion_rig_layout): back end FLUSH with the back block's outer
# face (crowned below); the front end reaches just far enough south of the
# front block for the lever's clamp hub.
# CAP_SAG is the back-end crown sagitta (the p.69 dome; the front end hides
# under the lever hub's own domed cap). All three live in
# dt_pinion_lift_rod_spec.py, the dimensional contract the drawing shares.

ROD_R = ROD_DIA / 2.0
V_CAP = math.pi * CAP_SAG**2 * (3.0 * CAP_R - CAP_SAG) / 3.0  # 19.7

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
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations): the rod diameter, body length and
    # crown sagitta -- RodDia/RodLen drive the marked drawing dims, CapSag the
    # crown and the overall. The mm suffix is load-bearing -- this is an INCH
    # document and the equation manager reads BARE numbers in document units
    # (an unsuffixed 6.35 = 6.35 in).
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "RodLen", f"{ROD_LEN}mm")
    await set_global(adapter, "CapSag", f"{CAP_SAG}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    await set_global(adapter, "PinHoleFromEnd", f"{ROD_PIN_HOLE_FROM_END}mm")

    # The rod is one half-profile revolved about its axis, as it sits in the
    # lathe (drawing-guidelines.md rule 11 (turned parts read like the lathe);
    # machinist review r1 of the ENFORCE gate, #1013): the diameter, the body
    # length, the crown's SR and the overall all import into the side view.
    # It is sketched on the Right Plane (sketch u = -z, v along y) -- the
    # plane the side view looks at: the flat front end face on the origin, the
    # OD to the crown rim at the body length, the rim -> apex crown arc (the
    # minor CCW lobe: rim at ~139 deg, apex at 180 deg about its on-axis
    # centre) and the axis back to the origin, over an axis centerline the
    # diameter doubles from.
    from solidworks_mcp.adapters.base import RevolveParameters

    u_rim, u_apex = -ROD_LEN, -(ROD_LEN + CAP_SAG)
    u_centre = -(ROD_LEN + CAP_SAG - CAP_R)
    rod = SketchDims()
    check("create_sketch rod", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "rod axis centerline", await adapter.add_centerline(0.0, 0.0, u_apex, 0.0)
    )
    front = check("rod front end", await adapter.add_line(0.0, 0.0, 0.0, ROD_R))
    outline = check("rod outline", await adapter.add_line(0.0, ROD_R, u_rim, ROD_R))
    arc = check(
        "rod crown arc",
        await adapter.add_arc(u_centre, 0.0, u_rim, ROD_R, u_apex, 0.0),
    )
    close = check("rod close on axis", await adapter.add_line(u_apex, 0.0, 0.0, 0.0))
    set_sketch_direct_db(adapter, False)
    check(
        "rod front end vertical",
        await adapter.add_sketch_constraint(front, None, "vertical"),
    )
    check(
        "rod outline horizontal",
        await adapter.add_sketch_constraint(outline, None, "horizontal"),
    )
    check(
        "rod close horizontal",
        await adapter.add_sketch_constraint(close, None, "horizontal"),
    )
    await anchor_point_to_origin(adapter, f"{front}.start", 0.0, 0.0, "rod front end")
    await add_diametric_linear_dimension(
        adapter, axis, outline, (u_rim / 2.0, ROD_R + 4.0), "RodDia"
    )
    rod.record("RodDia", '"RodDia"')
    await dimension_between(
        adapter,
        f"{outline}.start",
        f"{outline}.end",
        "horizontal_distance",
        ROD_LEN,
        "rod body length",
    )
    rod.record("RodBody", '"RodLen"')
    await dimension_between(
        adapter,
        f"{close}.start",
        "origin",
        "horizontal_distance",
        ROD_LEN + CAP_SAG,
        "rod overall length",
    )
    rod.record("RodOverall", '"RodLen" + "CapSag"')
    check(
        "rod crown radius",
        await adapter.add_sketch_dimension(arc, None, "radial", CAP_R),
    )
    rod.record(
        "CapR",
        '("RodDia" / 2 * "RodDia" / 2 + "CapSag" * "CapSag") / (2 * "CapSag")',
    )
    await ensure_fully_defined(adapter, "rod sketch")
    check("exit_sketch rod", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs = rod.apply(adapter, "RodProfile")
    check("revolve rod", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Rod")
    expected = V_ROD + V_CAP
    await volume_check(adapter, "rod with crown", expected, 0.03 * V_CAP)

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
    # Named pin-hole axis (along X at the pin station): the MHA-DT-30 pin's
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
        adapter, "RodProfile", "RodDia", *deviations(ROD_DIA_BAND), display_unit=UNIT
    )
    set_dimension_prefix(adapter, "RodProfile", "CapR", "SR")
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
