r"""Reproduction script: platen guide rail (book ch. 22, pp. 54-55; 2 used).

One of the two black guide rails screwed across the FULL width of the platen
back, above and below the bright wear band where the support bar slides --
the platen HANGS on the bar by these. Each is fastened by a row of 5 screws
whose heads show on the platen front (ch22 front photo; counterbored flush so
the paper lies flat, shanks threading into the rail) and carries 2 lock
plates (build_guide_lock.py) that bridge behind the bar so the platen cannot
fall off. 10 deep so the lock plates clear the 9-deep bar.

Layout: length along +X, height along +Y from the origin corner, depth
extruded -Z so native Front looks directly at the hole-entry face. The
assembly seats local z 0 on the platen back and rotates the part 180 about Y
to preserve the machine-space rail envelope. The 4 lock
screw holes run through along Z at the two proportional lock stations.

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
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
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

GUIDE_LENGTH = 269.64  # = resized platen width (ch30-p002 Pose Studio)
GUIDE_HEIGHT = 5.0
GUIDE_DEPTH = 10.0  # 1.0 past the 9-deep bar so the lock plates clear it
LOCK_STATION_X = (80.892, 188.748)  # 30% / 70%; inboard of the east column clamp
LOCK_SCREW_DX = 7.0  # 2 screws per lock flank its centre

HOLE_X = tuple(s + d for s in LOCK_STATION_X for d in (-LOCK_SCREW_DX, LOCK_SCREW_DX))

# Blind holes on the FRONT face (mid-height) where the row of 5 fastening
# screws threads in: the platen counterbores its heads (build_platen), so the
# fillister shanks reach 2.4 past the platen back into the rail. These become
# #4-40 bottoming-tapped Hole Wizard holes (tap drill Ø2.261; was plain Ø3.0).
# Stations = the platen's GUIDE_HOLE_X (pinned by an assert in the assembly
# module). The lock-screw LockHoles above become #4 clearance (the fillister
# lock screws pass through) -- memory/fastener-policy-us-customary.
SCREW_STATION_X = (26.964, 80.892, 134.82, 188.748, 242.676)
SCREW_HOLE_DEPTH = 4.0

# Part-specific process facts only (drawing-simplicity-policy.md rule 6):
# the hole table carries every station and wizard callout.
DRAWING_NOTES = "10 X 5 BAR STOCK FACES OK AS RECEIVED; TAP FROM THE FACE SHOWN."


def _apply_drawing_properties(adapter) -> None:
    apply_drawing_properties(
        adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES}
    )


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
        await adapter.create_extrusion(
            ExtrusionParameters(depth=GUIDE_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Guide")
    depth_dim = name_dimensions(adapter, "Guide", ["Depth"])
    drive_jobs += [(depth_dim[0], '"GuideDepth"')]
    v_rail = GUIDE_LENGTH * GUIDE_HEIGHT * GUIDE_DEPTH
    await volume_check(adapter, "guide rail", v_rail, 0.005 * v_rail)

    # Lock-screw holes: ONE native Hole Wizard #4 clearance feature (4 points)
    # through along Z at the mid-height line, from the native Front face
    # (local z 0, outward normal +Z) -- the fillister lock screws pass through.
    lock_dia = CLEARANCE_MM[("#4", "normal")]
    wizard_holes(
        adapter,
        HoleSpec("clearance", "#4"),
        [[x, GUIDE_HEIGHT / 2.0, 0.0] for x in HOLE_X],
        (0.0, 0.0, 1.0),
        "lock-screw holes (#4 clearance)", name="LockHoles",
    )
    v_holes = len(HOLE_X) * math.pi * (lock_dia / 2.0) ** 2 * GUIDE_DEPTH
    await volume_check(adapter, "guide with holes", v_rail - v_holes, 0.02 * v_holes)

    # Fastening-screw holes: ONE native Hole Wizard #4-40 BOTTOMING-TAPPED blind
    # feature (5 points) from the front face (outward normal +Z) -- the platen
    # guide screws thread INTO these. A wizard blind hole ends in a 118° drill
    # point, so the analytic expectation is blind_hole_volume_mm3.
    screw_spec = HoleSpec(
        "tapped_bottoming", "#4-40", end="blind", depth_mm=SCREW_HOLE_DEPTH,
        overrides_mm={"ThreadDepth": 2.4},
    )
    wizard_holes(
        adapter, screw_spec,
        [[x, GUIDE_HEIGHT / 2.0, 0.0] for x in SCREW_STATION_X],
        (0.0, 0.0, 1.0),
        "fastening-screw tapped holes (#4-40)", name="ScrewHoles",
    )
    v_screws = len(SCREW_STATION_X) * blind_hole_volume_mm3(
        blind_cut_dia_mm(screw_spec), SCREW_HOLE_DEPTH
    )
    v_final = v_rail - v_holes - v_screws
    # The short bottoming-tap table profile differs slightly from the ideal
    # cylinder-plus-118-degree point (about 0.54 mm^3 per hole on SW 2026).
    # Keep the gate tight enough to catch a missing/extra station while covering
    # that native table/profile variation.
    await volume_check(adapter, "guide with screw holes", v_final, 0.05 * v_screws)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven guide (equations neutral)", v_final, 0.02 * v_holes
    )

    clear_dimensions_for_drawing(adapter)
    mark_dimensions_for_drawing(adapter, "GuideProfile", {"Length", "Height"})
    mark_dimensions_for_drawing(adapter, "Guide", {"Depth"})

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    _apply_drawing_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
