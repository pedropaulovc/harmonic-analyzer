r"""Reproduction script: latch-hook bracket (MHA-170; ch. 23; 1 used).

A 1.5 steel sheet bent into an L (``latch_hook_bracket_geometry``): the base
lies on the support bar's back face under two #4-40 bracket screws
(MHA-171), and the flap stands rearward at the base's +X end with the latch
hook strip (MHA-127) riveted to its inside face.

Layout (part frame = machine axes, origin at the L's outer corner):

* ``BracketProfile``: the L section on the Top Plane (sketch y = model -Z),
  extruded +Y by the width (``Bracket``);
* ``InsideBend`` / ``OutsideBend``: the bend, concentric R0.75 / R2.25;
* ``ScrewHoleProfile`` on the Front Plane (the base's underside, z = 0), cut
  +Z through the base (``ScrewHoles``);
* ``RivetHoleProfile`` on the Right Plane (the flap's outer face, x = 0),
  cut -X through the flap (``RivetHoles``).

The assembly places the part by translation to
``latch_hook_bracket_geometry.MACHINE_ORIGIN``: Front Plane on the bar's back
face, Right Plane at machine x 60.0, Top Plane at machine y 299.2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_latch_hook_bracket.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    bbox_extent_check,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from latch_hook_bracket_geometry import (
    BASE_LENGTH,
    FLAP_HEIGHT,
    INSIDE_BEND_R,
    OUTSIDE_BEND_R,
    RIVET_HOLE_DIA,
    RIVET_YZ,
    SCREW_HOLE_DIA,
    SCREW_HOLE_X,
    SCREW_HOLE_Y,
    SHEET_T,
    WIDTH,
)
from latch_hook_bracket_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HOLE_BAND,
    ISOMETRIC_VIEW_NOTE,
    POSITION_DIMENSIONS,
    POSITION_TOL,
    WIDTH_TOL,
)

PART_NAME = "latch-hook-bracket"
MATERIAL = "Plain Carbon Steel"  # low-carbon steel sheet (the registry row names it)
DRAWING_PROPERTIES = {
    "Manufacturing Notes": DRAWING_NOTES,
    "Isometric View Note": ISOMETRIC_VIEW_NOTE,
}

_SECTION = BASE_LENGTH * SHEET_T + (FLAP_HEIGHT - SHEET_T) * SHEET_T
_FILLET_AREA = 1.0 - math.pi / 4.0  # per r^2: a 90-degree fillet's section
V_L = _SECTION * WIDTH
V_BENT = V_L + _FILLET_AREA * (INSIDE_BEND_R**2 - OUTSIDE_BEND_R**2) * WIDTH
V_SCREW_HOLES = 2.0 * math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * SHEET_T
V_RIVET_HOLES = 2.0 * math.pi * (RIVET_HOLE_DIA / 2.0) ** 2 * SHEET_T
V_FINAL = V_BENT - V_SCREW_HOLES - V_RIVET_HOLES

# The L section in Top-Plane sketch coordinates (x, -z), from the base's -X
# underside corner round to the base's top: segment 0 prints the base length,
# 1 the flap height, 2 the flap's thickness, 3 the flap's inside height; the
# last horizontal and vertical close the chain.  Vertex 1 is the origin.
_L_POINTS = [
    (-BASE_LENGTH, 0.0),
    (0.0, 0.0),
    (0.0, -FLAP_HEIGHT),
    (-SHEET_T, -FLAP_HEIGHT),
    (-SHEET_T, -SHEET_T),
    (-BASE_LENGTH, -SHEET_T),
]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "BaseLength", f"{BASE_LENGTH}mm")
    await set_global(adapter, "FlapHeight", f"{FLAP_HEIGHT}mm")
    await set_global(adapter, "SheetT", f"{SHEET_T}mm")
    await set_global(adapter, "Width", f"{WIDTH}mm")
    await set_global(adapter, "InsideBendR", f"{INSIDE_BEND_R}mm")
    await set_global(adapter, "ScrewHoleX1", f"{-SCREW_HOLE_X[0]}mm")
    await set_global(adapter, "ScrewHoleX2", f"{-SCREW_HOLE_X[1]}mm")
    await set_global(adapter, "ScrewHoleY", f"{SCREW_HOLE_Y}mm")
    await set_global(adapter, "ScrewHoleDia", f"{SCREW_HOLE_DIA}mm")
    await set_global(adapter, "RivetY", f"{RIVET_YZ[0][0]}mm")
    await set_global(adapter, "RivetZ1", f"{RIVET_YZ[0][1]}mm")
    await set_global(adapter, "RivetZ2", f"{RIVET_YZ[1][1]}mm")
    await set_global(adapter, "RivetDia", f"{RIVET_HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # The formed L: one Top-plane section extruded +Y by the width.
    profile = SketchDims()
    check("create_sketch bracket profile", await adapter.create_sketch("Top"))
    lines = await add_line_chain(adapter, _L_POINTS)
    await define_rectilinear_chain(
        adapter,
        lines,
        _L_POINTS,
        anchor=1,
        label="bracket L",
        dims=profile,
        names=["BaseLength", "FlapHeight", "FlapT", "FlapInside"],
        drives=[
            '"BaseLength"',
            '"FlapHeight"',
            '"SheetT"',
            '"FlapHeight" - "SheetT"',
        ],
    )
    await ensure_fully_defined(adapter, "bracket profile")
    check("exit_sketch bracket profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BracketProfile")
    drive_jobs += profile.apply(adapter, "BracketProfile")
    check(
        "extrude bracket",
        await adapter.create_extrusion(ExtrusionParameters(depth=WIDTH)),
    )
    name_last_feature(adapter, "Bracket")
    width_dim = name_dimensions(adapter, "Bracket", ["Width"])
    drive_jobs.append((width_dim[0], '"Width"'))
    await volume_check(adapter, "sharp L", V_L, 0.005 * V_L)
    await bbox_extent_check(adapter, "base length", "x", BASE_LENGTH)
    await bbox_extent_check(adapter, "width", "y", WIDTH)
    await bbox_extent_check(adapter, "flap height", "z", FLAP_HEIGHT)

    # The bend: inside R0.75 in the re-entrant corner, outside R2.25 on the
    # outer corner, both about one centre (x, z) = (-2.25, 2.25).
    check(
        "fillet inside bend",
        await adapter.add_fillet(INSIDE_BEND_R, [[-SHEET_T, WIDTH / 2.0, SHEET_T]]),
    )
    name_last_feature(adapter, "InsideBend")
    inside = name_dimensions(adapter, "InsideBend", ["InsideBendR"])
    drive_jobs.append((inside[0], '"InsideBendR"'))
    check(
        "fillet outside bend",
        await adapter.add_fillet(OUTSIDE_BEND_R, [[0.0, WIDTH / 2.0, 0.0]]),
    )
    name_last_feature(adapter, "OutsideBend")
    outside = name_dimensions(adapter, "OutsideBend", ["OutsideBendR"])
    drive_jobs.append((outside[0], '"InsideBendR" + "SheetT"'))
    await volume_check(adapter, "bent L", V_BENT, 0.005 * V_L)

    # Screw holes, drilled through the base after bending: a Front-plane
    # sketch (sketch x = X, y = Y) cut +Z through the sheet.  Both holes'
    # X run from the flap's outer face (the origin); the second hole's Y and
    # size ride the same globals and print once under "2X".
    screws = SketchDims()
    check("create_sketch screw holes", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        SCREW_HOLE_X[0],
        SCREW_HOLE_Y,
        SCREW_HOLE_DIA / 2.0,
        "far screw hole",
        dims=screws,
        names=("ScrewX1", "ScrewY", "ScrewDia"),
        drives=('"ScrewHoleX1"', '"ScrewHoleY"', '"ScrewHoleDia"'),
    )
    await define_circle(
        adapter,
        SCREW_HOLE_X[1],
        SCREW_HOLE_Y,
        SCREW_HOLE_DIA / 2.0,
        "near screw hole",
        dims=screws,
        names=("ScrewX2", "ScrewY2", "ScrewDia2"),
        drives=('"ScrewHoleX2"', '"ScrewHoleY"', '"ScrewHoleDia"'),
    )
    await ensure_fully_defined(adapter, "screw hole sketch")
    check("exit_sketch screw holes", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewHoleProfile")
    drive_jobs += screws.apply(adapter, "ScrewHoleProfile")
    check(
        "cut screw holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SHEET_T, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "ScrewHoles")
    await volume_check(
        adapter, "screw holes", V_BENT - V_SCREW_HOLES, 0.02 * V_SCREW_HOLES
    )

    # Rivet holes through the flap: a Right-plane sketch (sketch x = -Z,
    # y = Y) cut -X through the sheet, at the hook's nominal rivet
    # positions.  The shop match-drills them through the set hook at
    # assembly (R9-15), so only their size is marked for the sheet.
    rivets = SketchDims()
    check("create_sketch rivet holes", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        -RIVET_YZ[0][1],
        RIVET_YZ[0][0],
        RIVET_HOLE_DIA / 2.0,
        "lower rivet hole",
        dims=rivets,
        names=("RivetZ1", "RivetY", "RivetDia"),
        drives=('"RivetZ1"', '"RivetY"', '"RivetDia"'),
    )
    await define_circle(
        adapter,
        -RIVET_YZ[1][1],
        RIVET_YZ[1][0],
        RIVET_HOLE_DIA / 2.0,
        "upper rivet hole",
        dims=rivets,
        names=("RivetZ2", "RivetY2", "RivetDia2"),
        drives=('"RivetZ2"', '"RivetY"', '"RivetDia"'),
    )
    await ensure_fully_defined(adapter, "rivet hole sketch")
    check("exit_sketch rivet holes", await adapter.exit_sketch())
    name_last_feature(adapter, "RivetHoleProfile")
    drive_jobs += rivets.apply(adapter, "RivetHoleProfile")
    check(
        "cut rivet holes",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=SHEET_T)),
    )
    name_last_feature(adapter, "RivetHoles")
    await volume_check(adapter, "rivet holes", V_FINAL, 0.02 * V_RIVET_HOLES)

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven bracket (equations neutral)", V_FINAL, 0.005 * V_FINAL
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # Drilled after bending, never under size.
    set_dimension_bilateral_tolerance(
        adapter, "ScrewHoleProfile", "ScrewDia", *deviations(HOLE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "RivetHoleProfile", "RivetDia", *deviations(HOLE_BAND)
    )
    # Hole positions from the formed datums.
    for feature_name, dimension_names in POSITION_DIMENSIONS.items():
        for dimension_name in dimension_names:
            set_dimension_symmetric_tolerance(
                adapter, feature_name, dimension_name, POSITION_TOL
            )
    # The base inside the bar's lock-free band, and the screw holes' y-edge
    # ligament: an explicit band on the width.
    set_dimension_symmetric_tolerance(adapter, "Bracket", "Width", WIDTH_TOL)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(adapter, PART_NAME, DRAWING_PROPERTIES)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
