r"""Reproduction script: platen guide lock plate (book ch. 22, pp. 54-55; 4 used).

One of the four small black plates screwed to the backs of the two platen
guide rails (2 per rail), bridging BEHIND the support bar so the hanging
platen cannot fall off it: the plate overlaps the guide on one long edge
(the 2 screw holes) and cantilevers past the bar's back face on the other.

Layout: width along +X, height along +Y from the origin corner, thickness
extruded +Z; the y = 0 edge is the guide-side edge (screw holes 2.5 above
it). Bottom-rail copies mount as authored and bridge UP across the open
channel onto the bar band; top-rail copies are flipped Rz180 by the assembly
and hang DOWN over the bar.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_guide_lock.py
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
from _holes import HoleSpec, blind_cut_dia_mm, wizard_holes
from guide_lock_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    HOLE_XY,
    ISOMETRIC_VIEW_NOTE,
    LOCK_HEIGHT,
    LOCK_THICK,
    LOCK_WIDTH,
)
from build_fillister_screw import SHANK_DIA as FILLISTER_SHANK_DIA

PART_NAME = "guide-lock"
MATERIAL = "Plain Carbon Steel"

# LOCK_WIDTH/LOCK_HEIGHT/LOCK_THICK/HOLE_XY live in guide_lock_spec.py (the
# dimensional contract shared with draw_guide_lock.py; re-exported here for
# build_paper_drive_assembly). LOCK_HEIGHT is sized by the BOTTOM station: its
# rail sits 7 below the bar (open channel), so reaching a 7 overlap behind the
# bar band takes 5 (rail) + 7 (channel) + 7 (bar) = 19. The top rail sits ON
# the bar, so the same plate overlaps the bar by 14 there -- and the two rows
# still clear each other by 1.0 in y (2026-07-07 field report: a 12-tall plate
# topped out AT the bar's bottom edge and retained nothing at the bottom
# stations).
# Stock 90114A511 shanks pass through the lock plates before threading into the
# guide's rear-face #4-40 receivers. The #4 CLOSE clearance is the existing
# placement interface and still leaves positive diametral clearance.
HOLE_SPEC = HoleSpec("clearance", "#4", fit="close")
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)
if HOLE_DIA < FILLISTER_SHANK_DIA:
    raise AssertionError("stock fillister shank does not clear the guide lock")

async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units). (The old
    # HoleDia knob is gone: the screw holes are now a native Hole Wizard feature
    # whose diameter comes from the #4 clearance table, not a driven dim.)
    await set_global(adapter, "LockWidth", f"{LOCK_WIDTH}mm")
    await set_global(adapter, "LockHeight", f"{LOCK_HEIGHT}mm")
    await set_global(adapter, "LockThick", f"{LOCK_THICK}mm")

    drive_jobs: list[tuple[str, str]] = []

    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    rect = [
        (0.0, 0.0),
        (LOCK_WIDTH, 0.0),
        (LOCK_WIDTH, LOCK_HEIGHT),
        (0.0, LOCK_HEIGHT),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="lock outline", dims=outline,
        names=["Width", "Height"],
        drives=['"LockWidth"', '"LockHeight"'],
    )
    await ensure_fully_defined(adapter, "lock outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "LockProfile")
    drive_jobs += outline.apply(adapter, "LockProfile")
    check(
        "extrude lock",
        await adapter.create_extrusion(ExtrusionParameters(depth=LOCK_THICK)),
    )
    name_last_feature(adapter, "Lock")
    depth_dim = name_dimensions(adapter, "Lock", ["Depth"])
    drive_jobs += [(depth_dim[0], '"LockThick"')]
    v_plate = LOCK_WIDTH * LOCK_HEIGHT * LOCK_THICK
    await volume_check(adapter, "lock plate", v_plate, 0.005 * v_plate)

    # Screw holes on the guide-side band: ONE native Hole Wizard #4 clearance
    # feature (2 through-all instances) drilled from the front face (z=0), while
    # the plate is still a plain prismatic slab. Positions are the guide layout.
    hole_dia = HOLE_DIA
    wizard_holes(
        adapter,
        HOLE_SPEC,
        [[x, y, 0.0] for x, y in HOLE_XY],
        (0.0, 0.0, -1.0),
        "guide-lock screw holes (#4 clearance)",
        name="ScrewHoles",
    )
    v_holes = len(HOLE_XY) * math.pi * (hole_dia / 2.0) ** 2 * LOCK_THICK
    v_final = v_plate - v_holes
    await volume_check(adapter, "lock with holes", v_final, 0.005 * v_plate)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven lock (equations neutral)", v_final, 0.005 * v_plate
    )

    # Manufacturing drawing support: mark exactly the print's dimensions (the
    # drawing recipe imports the marked set and must find every one of these),
    # and stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
