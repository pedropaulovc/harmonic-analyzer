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

    uv run python cad\scripts\build_pd_guide_lock.py
"""

from __future__ import annotations

import math
import sys

from _appearance import PANEL_BLACK, apply_color, apply_material
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, add_line_chain, ensure_fully_defined
from _sketch_chains import define_rectilinear_chain
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _hole_spec import blind_cut_dia_mm
from _holes import wizard_holes
from pd_guide_lock_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HOLE_LOCATION_BAND,
    HOLE_LOCATION_DIMENSIONS,
    HOLE_SPEC,
    HOLE_XY,
    ISOMETRIC_VIEW_NOTE,
    LOCK_HEIGHT,
    LOCK_HEIGHT_BAND,
    LOCK_THICK,
    LOCK_WIDTH,
)
from vn_guide_lock_screw_spec import SHANK_DIA as LOCK_SCREW_SHANK_DIA

PART_NAME = "pd-guide-lock"
MATERIAL = "Plain Carbon Steel"

# LOCK_WIDTH/LOCK_HEIGHT/LOCK_THICK/HOLE_XY live in pd_guide_lock_spec.py (the
# dimensional contract shared with draw_pd_guide_lock.py; re-exported here for
# build_pd_paper_drive_assembly). LOCK_HEIGHT is sized by the BOTTOM station: its
# rail sits 7 below the bar (open channel), so reaching the bar band takes
# 5 (rail) + 7 (channel) + the overlap behind the bar. The 2026-09-02 user
# re-read of ch22 p.54 shows a LOW lock: 5 rail + 7 channel + 3 bar overlap
# (the 2026-07 plate reached a 7 overlap = 19), plus R9-59's 1.0 lip past the
# rail's outer edge that gives the screw holes their edge ligament. R9-61
# brought the spacer-side edge in by 0.35 so the set, skewed plate clears the
# floating pivot spacer: the bottom station overlaps the bar 2.65 (2.15 at
# the -0.50 height band). The top rail sits ON the bar, so the same plate
# overlaps the bar by 9.65 there. (2026-07-07 field report: a 12-tall plate
# topped out AT the bar's bottom edge and retained nothing at the bottom
# stations.)
# Stock 91255A108 button head shanks (MHA-VN-046, rulings R9-31, R9-48) pass
# through the lock plates before threading into the guide's rear-face #4-40
# through taps. The part-owned 1/8 drill (R9-49) carries both printed hole
# positions over the screw majors (vn_guide_lock_screw_spec.LOCK_SET_OFFSET).
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)
if HOLE_DIA < LOCK_SCREW_SHANK_DIA:
    raise AssertionError("stock guide-lock screw shank does not clear the guide lock")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units). (The old
    # HoleDia knob is gone: the screw holes are now a native Hole Wizard feature
    # whose diameter comes from the fractional drill table, not a driven dim.)
    await set_global(adapter, "LockWidth", f"{LOCK_WIDTH}mm")
    await set_global(adapter, "LockHeight", f"{LOCK_HEIGHT}mm")
    await set_global(adapter, "LockThick", f"{LOCK_THICK}mm")
    await set_global(adapter, "LockHoleX1", f"{HOLE_XY[0][0]}mm")
    await set_global(adapter, "LockHoleX2", f"{HOLE_XY[1][0]}mm")
    await set_global(adapter, "LockHoleY", f"{HOLE_XY[0][1]}mm")

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
        adapter,
        lines,
        rect,
        label="lock outline",
        dims=outline,
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

    # Screw holes on the guide-side band: ONE native Hole Wizard 1/8 drill
    # feature (2 through-all instances) drilled from the front face (z=0), while
    # the plate is still a plain prismatic slab. Positions are the guide layout,
    # dimensioned from the plate's corner (the outline's origin); the second
    # hole's Y repeats the first's and stays off the print.
    hole_dia = HOLE_DIA
    if HOLE_XY[0][1] != HOLE_XY[1][1]:
        raise AssertionError("the guide-lock screw holes must share one Y station")
    holes = wizard_holes(
        adapter,
        HOLE_SPEC,
        [[x, y, 0.0] for x, y in HOLE_XY],
        (0.0, 0.0, -1.0),
        "guide-lock screw holes (1/8 drill)",
        name="ScrewHoles",
        placement_dims=[
            (("Hole1X", '"LockHoleX1"'), ("Hole1Y", '"LockHoleY"')),
            (("Hole2X", '"LockHoleX2"'), ("Hole2Y", '"LockHoleY"')),
        ],
    )
    drive_jobs += holes.placement_drive_jobs
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

    # Manufacturing drawing support: the height's and the hole coordinates'
    # explicit bands and every printed dimension's places live on the model
    # (policy rule 2; the paper-drive lock-station sweep and the screw set
    # window read the same constants), then mark exactly the print's
    # dimensions (the drawing recipe imports the marked set and must find
    # every one of these), and stamp the make-critical title-block properties.
    set_dimension_bilateral_tolerance(
        adapter, "LockProfile", "Height", *deviations(LOCK_HEIGHT_BAND)
    )
    for dimension_name in sorted(HOLE_LOCATION_DIMENSIONS):
        set_dimension_symmetric_tolerance(
            adapter, "ScrewHoles", dimension_name, HOLE_LOCATION_BAND
        )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
