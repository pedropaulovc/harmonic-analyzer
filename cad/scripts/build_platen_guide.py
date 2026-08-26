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
to preserve the machine-space rail envelope. Four blind #4-40 receivers enter
from the rear face at the two proportional lock stations.

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
    DRILL_POINT_H,
    HoleSpec,
    blind_cut_dia_mm,
    blind_hole_volume_mm3,
    wizard_holes,
)
from build_fillister_screw import SHANK_LEN as FILLISTER_SHANK_LEN
from build_platen import CBORE_DEPTH as PLATEN_CBORE_DEPTH, PLATE_THICKNESS
from build_guide_lock import LOCK_THICK

PART_NAME = "platen-guide"
MATERIAL = "Plain Carbon Steel"

GUIDE_LENGTH = 269.64  # = resized platen width (ch30-p002 Pose Studio)
GUIDE_HEIGHT = 5.0
GUIDE_DEPTH = 10.0  # 1.0 past the 9-deep bar so the lock plates clear it
LOCK_STATION_X = (80.892, 188.748)  # 30% / 70%; inboard of the east column clamp
LOCK_SCREW_DX = 7.0  # 2 screws per lock flank its centre

HOLE_X = tuple(s + d for s in LOCK_STATION_X for d in (-LOCK_SCREW_DX, LOCK_SCREW_DX))

# The front row receives the ten guide screws after each shank passes through
# the platen material left below its stock-head counterbore. The rear row
# receives the eight lock screws after each shank passes through a 2-mm lock
# plate. Both are #4-40 bottoming taps with positive clearance between the
# screw tip and cylindrical blind-hole bottom.
SCREW_STATION_X = (26.964, 80.892, 134.82, 188.748, 242.676)
GUIDE_SCREW_PASSAGE = PLATE_THICKNESS - PLATEN_CBORE_DEPTH
GUIDE_SCREW_THREAD_ENGAGEMENT = FILLISTER_SHANK_LEN - GUIDE_SCREW_PASSAGE
SCREW_HOLE_DEPTH = 5.52
GUIDE_SCREW_BOTTOM_CLEARANCE = SCREW_HOLE_DEPTH - GUIDE_SCREW_THREAD_ENGAGEMENT

LOCK_SCREW_PASSAGE = LOCK_THICK
LOCK_SCREW_THREAD_ENGAGEMENT = FILLISTER_SHANK_LEN - LOCK_SCREW_PASSAGE
LOCK_SCREW_BOTTOM_CLEARANCE = 0.25
LOCK_SCREW_HOLE_DEPTH = LOCK_SCREW_THREAD_ENGAGEMENT + LOCK_SCREW_BOTTOM_CLEARANCE
_TAP_DRILL_DIA = blind_cut_dia_mm(HoleSpec("tapped_bottoming", "#4-40"))
_DRILL_POINT_REACH = (_TAP_DRILL_DIA / 2.0) * DRILL_POINT_H
_MIN_OPPOSED_RECEIVER_C2C = min(
    abs(lock_x - guide_x) for lock_x in HOLE_X for guide_x in SCREW_STATION_X
)

if min(GUIDE_SCREW_THREAD_ENGAGEMENT, LOCK_SCREW_THREAD_ENGAGEMENT) <= 0.0:
    raise AssertionError("fillister screw stack has no #4-40 thread engagement")
if max(SCREW_HOLE_DEPTH, LOCK_SCREW_HOLE_DEPTH) + _DRILL_POINT_REACH >= GUIDE_DEPTH:
    raise AssertionError("fillister receiver drill point breaks through the platen guide")
if _MIN_OPPOSED_RECEIVER_C2C < _TAP_DRILL_DIA + 0.2:
    raise AssertionError("front and rear #4-40 guide receivers intersect")

DRAWING_NOTES = "HOLE POSITION PER FCF."


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
    # Both hole families are native #4-40 bottoming taps; their diameters come
    # from the ANSI-inch table rather than equation-driven sketch dimensions.

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

    # Lock-screw receivers: ONE native Hole Wizard #4-40 BOTTOMING-TAPPED
    # blind feature (4 points) from the guide's REAR face (local z=-10,
    # outward normal -Z). The stock 6.35-mm shanks pass through the 2-mm lock
    # plates, engage 4.35 mm here, and retain 0.25 mm bottom clearance.
    lock_spec = HoleSpec(
        "tapped_bottoming", "#4-40", end="blind", depth_mm=LOCK_SCREW_HOLE_DEPTH,
        overrides_mm={"ThreadDepth": LOCK_SCREW_THREAD_ENGAGEMENT},
    )
    wizard_holes(
        adapter,
        lock_spec,
        [[x, GUIDE_HEIGHT / 2.0, -GUIDE_DEPTH] for x in HOLE_X],
        (0.0, 0.0, -1.0),
        "lock-screw tapped receivers (#4-40)", name="LockHoles",
    )
    v_holes = len(HOLE_X) * blind_hole_volume_mm3(
        blind_cut_dia_mm(lock_spec), LOCK_SCREW_HOLE_DEPTH
    )
    await volume_check(adapter, "guide with lock receivers", v_rail - v_holes, 0.05 * v_holes)

    # Fastening-screw receivers: ONE native Hole Wizard #4-40 BOTTOMING-TAPPED
    # blind feature (5 points) from the front face. The deeper stock-head
    # counterbore leaves 1.0822 mm of platen passage, so the 6.35-mm shank
    # engages 5.2678 mm here with positive bottom clearance.
    screw_spec = HoleSpec(
        "tapped_bottoming", "#4-40", end="blind", depth_mm=SCREW_HOLE_DEPTH,
        overrides_mm={"ThreadDepth": GUIDE_SCREW_THREAD_ENGAGEMENT},
    )
    wizard_holes(
        adapter, screw_spec,
        [[x, GUIDE_HEIGHT / 2.0, 0.0] for x in SCREW_STATION_X],
        (0.0, 0.0, 1.0),
        "fastening-screw tapped receivers (#4-40)", name="ScrewHoles",
    )
    v_screws = len(SCREW_STATION_X) * blind_hole_volume_mm3(
        blind_cut_dia_mm(screw_spec), SCREW_HOLE_DEPTH
    )
    v_final = v_rail - v_holes - v_screws
    # Native bottoming-tap profiles differ slightly from the ideal
    # cylinder-plus-118-degree point. This still catches a missing station.
    await volume_check(adapter, "guide with screw receivers", v_final, 0.05 * (v_holes + v_screws))

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
