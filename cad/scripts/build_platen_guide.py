r"""Reproduction script: platen guide rail (book ch. 22, pp. 54-55; 2 used).

One of the two black guide rails screwed across the FULL width of the platen
back, above and below the bright wear band where the support bar slides --
the platen HANGS on the bar by these. Each is fastened by a row of 5 screws
whose heads show on the platen front (ch22 front photo; counterbored flush so
the paper lies flat, shanks threading into the rail) and carries 2 lock
plates (build_guide_lock.py) that bridge behind the bar so the platen cannot
fall off. 10 deep so the lock plates clear the 9-deep bar.

Layout: length along +X, height along +Y from the origin corner, depth
extruded +Z (the assembly seats local z 0 on the platen back). The 4 lock
screw holes run through along Z at the two lock stations (x 60/240 +- 7).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_platen_guide.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_rectilinear_chain,
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
from _holes import (
    CLEARANCE_MM,
    HoleSpec,
    blind_cut_dia_mm,
    blind_hole_volume_mm3,
    wizard_holes,
)

PART_NAME = "platen-guide"
MATERIAL = "Plain Carbon Steel"

GUIDE_LENGTH = 300.0  # = platen width (ch22 back photo: full-width rails)
GUIDE_HEIGHT = 5.0
GUIDE_DEPTH = 10.0  # 1.0 past the 9-deep bar so the lock plates clear it
LOCK_STATION_X = (60.0, 240.0)  # lock-plate centres (2 per guide)
LOCK_SCREW_DX = 7.0  # 2 screws per lock flank its centre

HOLE_X = tuple(s + d for s in LOCK_STATION_X for d in (-LOCK_SCREW_DX, LOCK_SCREW_DX))

# Blind holes on the FRONT face (mid-height) where the row of 5 fastening
# screws threads in: the platen counterbores its heads (build_platen), so the
# fillister shanks reach 2.4 past the platen back into the rail. These become
# #4-40 bottoming-tapped Hole Wizard holes (tap drill Ø2.261; was plain Ø3.0).
# Stations = the platen's GUIDE_HOLE_X (pinned by an assert in the assembly
# module). The lock-screw LockHoles above become #4 clearance (the fillister
# lock screws pass through) -- memory/fastener-policy-us-customary.
SCREW_STATION_X = (30.0, 90.0, 150.0, 210.0, 270.0)
SCREW_HOLE_DEPTH = 3.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units).
    await set_global(adapter, "GuideLength", f"{GUIDE_LENGTH}mm")
    await set_global(adapter, "GuideHeight", f"{GUIDE_HEIGHT}mm")
    await set_global(adapter, "GuideDepth", f"{GUIDE_DEPTH}mm")
    # (The old HoleDia knob is gone: the holes are now native Hole Wizard
    # features whose diameters come from the #4 clearance / #4-40 tap standards.)

    drive_jobs: list[tuple[str, str]] = []

    # Rail outline: corner-at-origin rectangle, length along X, height along Y.
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    rect = [
        (0.0, 0.0),
        (GUIDE_LENGTH, 0.0),
        (GUIDE_LENGTH, GUIDE_HEIGHT),
        (0.0, GUIDE_HEIGHT),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="guide outline", dims=outline,
        names=["Length", "Height"],
        drives=['"GuideLength"', '"GuideHeight"'],
    )
    await ensure_fully_defined(adapter, "guide outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "GuideProfile")
    drive_jobs += outline.apply(adapter, "GuideProfile")
    check(
        "extrude guide",
        await adapter.create_extrusion(ExtrusionParameters(depth=GUIDE_DEPTH)),
    )
    name_last_feature(adapter, "Guide")
    v_rail = GUIDE_LENGTH * GUIDE_HEIGHT * GUIDE_DEPTH
    await volume_check(adapter, "guide rail", v_rail, 0.005 * v_rail)

    # Lock-screw holes: ONE native Hole Wizard #4 clearance feature (4 points)
    # through along Z at the mid-height line, from the front face (local z 0,
    # outward normal -Z) -- the fillister lock screws pass through.
    lock_dia = CLEARANCE_MM[("#4", "normal")]
    wizard_holes(
        adapter,
        HoleSpec("clearance", "#4"),
        [[x, GUIDE_HEIGHT / 2.0, 0.0] for x in HOLE_X],
        (0.0, 0.0, -1.0),
        "lock-screw holes (#4 clearance)", name="LockHoles",
    )
    v_holes = len(HOLE_X) * math.pi * (lock_dia / 2.0) ** 2 * GUIDE_DEPTH
    await volume_check(adapter, "guide with holes", v_rail - v_holes, 0.02 * v_holes)

    # Fastening-screw holes: ONE native Hole Wizard #4-40 BOTTOMING-TAPPED blind
    # feature (5 points) from the front face (outward normal -Z) -- the platen
    # guide screws thread INTO these. A wizard blind hole ends in a 118° drill
    # point, so the analytic expectation is blind_hole_volume_mm3.
    screw_spec = HoleSpec(
        "tapped_bottoming", "#4-40", end="blind", depth_mm=SCREW_HOLE_DEPTH
    )
    wizard_holes(
        adapter, screw_spec,
        [[x, GUIDE_HEIGHT / 2.0, 0.0] for x in SCREW_STATION_X],
        (0.0, 0.0, -1.0),
        "fastening-screw tapped holes (#4-40)", name="ScrewHoles",
    )
    v_screws = len(SCREW_STATION_X) * blind_hole_volume_mm3(
        blind_cut_dia_mm(screw_spec), SCREW_HOLE_DEPTH
    )
    v_final = v_rail - v_holes - v_screws
    await volume_check(adapter, "guide with screw holes", v_final, 0.02 * v_screws)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven guide (equations neutral)", v_final, 0.02 * v_holes
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
