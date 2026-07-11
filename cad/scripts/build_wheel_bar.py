r"""Reproduction script: magnifying-wheel bar (book ch. 21, pp. 50-51).

The short bar carrying the magnifying-wheel axle and the pen-hanger
strap. M6.8 ch30 8-view pass (user-confirmed): unlike the two full-width
platen rails, this bar spans only ~HALF the frame width -- every plate
shows it clamped at ONE column (the machine +x / west one) with a
free end just past the pen hanger; there is no second clamp on the far
column at this height.

Section 10 tall x 9 deep -- the support-bar stock (the front faces of
both bars share the machine z -138.9 plane; the 9 depth puts the back
face on the front clamp arc's face at -129.9, the same two-piece clamp
seat as build_support_bar.py). 234 long: the clamped end runs 29 past
the west column line (the support-bar idiom -- the clamp-screw stack
bar -> front arc -> back arc needs bar over BOTH ear holes), the free
end just past the hanger. Placed IDENTITY in build_magnifier_assembly at
centre x +109 (machine = local + 109): span -8..+226, covering the wheel
axle (+53) and the pen-hanger strap top with margin.

Holes (all along local Z, the machine front-back axis):
* 2x O4.4 clamp-screw through-holes flanking the column at local
  x 70.5 / 105.5 (the column line crosses the bar at local +88 =
  column +197 - centre +109; ears at +-17.5,
  _clamp_arc.EAR_HOLE_Z): heads on the bar's front face, threading into
  the back arc -- exactly the support-bar stack.
* 1x O3.8 pen-hanger screw hole at local (-114.5, 0) (machine
  (-5.5, 565) = local + 109)
  taking the pen-hanger screw from behind the bar. The hole sits in the
  5-wide strap/bar overlap at the free end (0.6 edge wall to the end
  face -- thin but photo-consistent: the bar end runs "just past" the
  hanger).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_wheel_bar.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_centered_rectangle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _holes import HoleSpec, blind_cut_dia_mm, wizard_holes

PART_NAME = "wheel-bar"
MATERIAL = "Plain Carbon Steel"

BAR_SIDE = 10.0  # tall (Y) (low)
BAR_DEPTH = 9.0  # deep (Z) -- support-bar stock; back face seats on the clamp arc
BAR_LENGTH = 234.0  # clamped end 29 past the west column + free end (photo, med)
SCREW_HOLE_X = -114.5
# Pen-hanger screw passes through: #6 clearance, CLOSE fit (Ø3.912, the wizard
# twin of the old Ø3.8 artefact dim; nearest UNC to the screw).
SCREW_HOLE_SPEC = HoleSpec("clearance", "#6", fit="close")
CLAMP_HOLE_X = (70.5, 105.5)  # local stations flanking the column line at +88
# The O3.9 clamp-screw shanks pass through: #8 clearance (support-bar idiom).
CLAMP_HOLE_SPEC = HoleSpec("clearance", "#8")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the section, the bar length, and the
    # screw holes (diameters + X stations). The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 200 = 200 in). BAR_DEPTH is the extrude
    # DEPTH (a feature parameter, not a sketch dim), so BarDepth is on record
    # for the GUI but the depth itself is static, matching the exemplars.
    # (The old ScrewHoleDia/ScrewHoleX/ClampHoleDia knobs are gone: the holes are
    # now native Hole Wizard features whose diameters come from the clearance
    # tables and whose positions are the literal photo stations.)
    await set_global(adapter, "BarSide", f"{BAR_SIDE}mm")
    await set_global(adapter, "BarDepth", f"{BAR_DEPTH}mm")
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Square bar profile: width along X = length, depth along Z = section,
    # origin-centred. The old add_line_chain + define_rectilinear_chain pair is
    # an origin-centred rectangle, so switch it to define_centered_rectangle
    # (cleaner; emits exactly width, depth, cornerX, cornerZ).
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter, BAR_LENGTH / 2.0, BAR_SIDE / 2.0, "bar", dims=bar,
        name_width="Length", drive_width='"BarLength"',
        name_depth="Side", drive_depth='"BarSide"',
        name_corner=("CornerX", "CornerZ"),
        drive_corner=('"BarLength" / 2', '"BarSide" / 2'),
    )
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BAR_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bar")

    expected = BAR_LENGTH * BAR_SIDE * BAR_DEPTH
    await volume_check(adapter, "bar", expected, 0.005 * expected)

    # All bores drilled through along Z from the bar FRONT face (local
    # z = -BAR_DEPTH/2, the heads' side), while the bar is a plain prism:
    # ONE pen-hanger #6 clearance hole + ONE 2-instance #8 clearance clamp
    # feature (the support-bar stack: heads on the bar front face, shanks
    # through the bar + front arc, threading into the back arc). Positions are
    # the photo layout.
    front_z = -BAR_DEPTH / 2.0
    screw_dia = blind_cut_dia_mm(SCREW_HOLE_SPEC)
    clamp_dia = blind_cut_dia_mm(CLAMP_HOLE_SPEC)
    wizard_holes(
        adapter, SCREW_HOLE_SPEC,
        [[SCREW_HOLE_X, 0.0, front_z]],
        (0.0, 0.0, -1.0), "pen-hanger screw hole (#6 clearance)", name="ScrewHole",
    )
    expected -= math.pi * (screw_dia / 2.0) ** 2 * BAR_DEPTH
    await volume_check(adapter, "bar with screw hole", expected, 1.0)

    wizard_holes(
        adapter, CLAMP_HOLE_SPEC,
        [[x, 0.0, front_z] for x in CLAMP_HOLE_X],
        (0.0, 0.0, -1.0), "clamp-screw clearance holes (#8)", name="ClampHoles",
    )
    expected -= 2.0 * math.pi * (clamp_dia / 2.0) ** 2 * BAR_DEPTH
    await volume_check(adapter, "bar with clamp holes", expected, 1.0)

    # Deferred drive equations after the model + a rebuild exists, then re-check:
    # each equation evaluates to the as-built value, so geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven wheel bar (equations neutral)", expected, 1.0)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
