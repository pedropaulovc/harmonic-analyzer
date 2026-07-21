r"""Reproduction script: magnifying lever rod (book ch. 20, pp. 46-49).

The round brass rod affixed to the summing lever that magnifies its sweep
up to 4x. Plain rod with domed (hemispherical) ends, clearly visible in
the p.47 close-up. The sliding clamp block, vertical rod, thumb screw and
output fixture are separate parts (build_magnifying_*.py).

Dimensions: cad/DIMENSIONS.md "Chapter 20" — Ø6 photo-scaled (low).
M6.4 revision: the M2 "310 from the 4x constraint" length is REFUTED by
the calibrated ch. 30 front view (p1): the rod spans x ~ -200..-35 at
y ~982, i.e. ~165 long. Magnification comes from the ratio of the clamp
radius (vertical-rod position along this rod, measured from the bracket
collar near the summing-lever plate) to the summing lever's own ratio --
the p.46/p.48 insets show the CLAMP sliding, not a 310 rod.

Layout: rod axis along +X from the origin (tip of the pivot-end dome at
x=0), profile revolved 360 deg about a centerline on the axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_magnifying_lever.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    anchor_point_to_origin,
    apply_material,
    check,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from magnifying_lever_geom import KNIFE_LOCAL_X, KNIFE_LOCAL_Y, ROD_DIA, ROD_LENGTH
from magnifying_lever_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    ISO_VIEW_NOTE,
)

PART_NAME = "magnifying-lever"
MATERIAL = "Brass"  # see _common.apply_material docstring

R = ROD_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the rod length and diameter. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 165 = 165 in, blowing
    # the part up 25.4x).
    await set_global(adapter, "RodLength", f"{ROD_LENGTH}mm")
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, ROD_LENGTH, 0.0),
    )
    # Half-profile: top line, two quarter-arc dome caps, closing axis line.
    top = check(
        "add_line top",
        await adapter.add_line(R, R, ROD_LENGTH - R, R),
    )
    cap_right = check(
        "add_arc right dome",
        await adapter.add_arc(ROD_LENGTH - R, 0.0, ROD_LENGTH, 0.0, ROD_LENGTH - R, R),
    )
    axis_line = check(
        "add_line axis",
        await adapter.add_line(ROD_LENGTH, 0.0, 0.0, 0.0),
    )
    cap_left = check(
        "add_arc left dome",
        await adapter.add_arc(R, 0.0, R, R, 0.0, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    # 14-unknown half-profile: origin corner anchored, both dome centres
    # anchored on the axis, ONE radial dim (the left dome's radius is
    # already forced by its anchored centre + the anchored origin end --
    # dimensioning it too over-defines), the top edge horizontal with its
    # start vertically aligned over the left centre. The centerline
    # merged into the two axis corners, so it carries no constraints.
    check(
        "anchor origin corner",
        await adapter.add_sketch_constraint(
            f"{axis_line}.end", "origin", "coincident"
        ),
    )
    check(
        "axis line horizontal",
        await adapter.add_sketch_constraint(axis_line, None, "horizontal"),
    )
    # Record each manual display dim into SketchDims as it is created (creation
    # order): the left dome centre is on the axis (x = R, one horizontal dim),
    # then the right dome centre (x = L - R, one horizontal dim), then the right
    # dome radius. The origin-corner anchor is a coincident relation (no dim) and
    # the horizontal / vertical-points constraints carry no dims either -- three
    # display dims total.
    await anchor_point_to_origin(
        adapter, f"{cap_left}.center", R, 0.0, "left dome centre"
    )
    profile.record("LeftDomeCentre", '"RodDia" / 2')
    await anchor_point_to_origin(
        adapter, f"{cap_right}.center", ROD_LENGTH - R, 0.0, "right dome centre"
    )
    profile.record("RightDomeCentre", '"RodLength" - "RodDia" / 2')
    check(
        "right dome radius",
        await adapter.add_sketch_dimension(cap_right, None, "radial", R),
    )
    profile.record("DomeRadius", '"RodDia" / 2')
    check(
        "top horizontal",
        await adapter.add_sketch_constraint(top, None, "horizontal"),
    )
    check(
        "top start over left centre",
        await adapter.add_sketch_constraint(
            f"{top}.start", f"{cap_left}.center", "vertical_points"
        ),
    )
    await ensure_fully_defined(adapter, "rod profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += profile.apply(adapter, "RodProfile")

    check(
        "revolve rod",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Rod")

    # Cylindrical body (length L - 2R, radius R) plus a full sphere from the two
    # hemispherical end domes: V = pi R^2 (L - 2R) + 4/3 pi R^3.
    v_rod = math.pi * R * R * (ROD_LENGTH - 2.0 * R) + 4.0 / 3.0 * math.pi * R**3
    await volume_check(adapter, "rod", v_rod, 0.005 * v_rod)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven rod (equations neutral)", v_rod, 0.005 * v_rod)

    # Named rod axis (local X through the origin = the revolve axis); the
    # bracket collar is a loose guide around it (Ø6.2 over Ø6), not a mate.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "rod axis")

    # KnifeAxis (Axis2): the knife-edge pivot line, local Z through
    # (KNIFE_LOCAL_X, KNIFE_LOCAL_Y) -- see the module-level block. The line is
    # outside the rod body (the physical rod attaches to the summing bar 50 mm
    # past its own domed end; the attachment is not modeled), which is fine for
    # a reference axis: the assembly pivots the lever about it.
    await name_bore_axis(adapter, "Right Plane", KNIFE_LOCAL_X,
                         "Top Plane", KNIFE_LOCAL_Y, "knife axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions (the
    # drawing recipe imports the marked set and must find every one of these),
    # and stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
            "Iso View Note": ISO_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
