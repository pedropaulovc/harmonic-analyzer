r"""Reproduction script: platen guide rail (book ch. 22, pp. 54-55; 2 used).

One of the two black guide rails screwed across the FULL width of the platen
back, above and below the bright wear band where the support bar slides --
the platen HANGS on the bar by these. Each is fastened by a row of 5 screws
whose heads show on the platen front (ch22 front photo; counterbored flush so
the paper lies flat, shanks threading into the rail) and carries 2 lock
plates (build_pd_guide_lock.py) that bridge behind the bar so the platen cannot
fall off. 10 deep so the lock plates clear the 9-deep bar.

Layout: length along +X, height along +Y from the origin corner, depth
extruded -Z so native Front looks directly at the hole-entry face. The
assembly seats local z 0 on the platen back and rotates the part 180 about Y
to preserve the machine-space rail envelope. Five #4-40 guide-screw receivers
tapped THROUGH from the front face (R9-64) and four lock-screw receivers
tapped THROUGH from the rear face at the two proportional lock stations
(R9-48).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_platen_guide.py
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
)
from _fit_deviations import deviations
from _hole_spec import THREAD_MAJOR_MM, blind_cut_dia_mm
from _holes import wizard_holes
from _part_pmi import author_part_pmi
from _printed_tolerance import printed_deviations
from vn_fillister_screw_spec import SHANK_LEN as FILLISTER_SHANK_LEN
from vn_guide_lock_screw_spec import SHANK_LEN as LOCK_SCREW_SHANK_LEN
from vn_guide_lock_screw_spec import TAP_MOUTH_BREAK, TIP_REACH_MAX
from pd_platen_spec import CBORE_DEPTH as PLATEN_CBORE_DEPTH, PLATE_THICKNESS
from pd_guide_lock_spec import LOCK_THICK
from pd_platen_guide_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    GEOMETRIC_TOLERANCES_MM,
    GUIDE_DEPTH_BAND,
    GUIDE_DEPTH_PLACES,
    LOCK_GAP_FIT,
    LOCK_TAP_SPEC,
    SURFACE_FINISHES,
    TAPPED_HOLE_SPEC,
)
from pd_support_bar_spec import BAR_DEPTH, BAR_DEPTH_BAND

PART_NAME = "pd-platen-guide"
MATERIAL = "Plain Carbon Steel"

GUIDE_LENGTH = 269.64  # = resized platen width (ch30-p002 Pose Studio)
GUIDE_HEIGHT = 5.0
GUIDE_DEPTH = 10.0  # 1.0 past the 9-deep bar so the lock plates clear it
LOCK_STATION_X = (80.892, 188.748)  # 30% / 70%; inboard of the east column clamp
LOCK_SCREW_DX = 7.0  # 2 screws per lock flank its centre

HOLE_X = tuple(s + d for s in LOCK_STATION_X for d in (-LOCK_SCREW_DX, LOCK_SCREW_DX))

# The front row receives the ten guide screws (MHA-VN-006 fillisters) after each
# shank passes through the platen material left below its stock-head
# counterbore; the rear row receives the eight lock screws (MHA-VN-046 button
# heads, rulings R9-31, R9-48) after each shank passes through a 2-mm lock
# plate. Both are #4-40 tapped through (R9-64, R9-48), the tips stopping
# inside the rail.
SCREW_STATION_X = (26.964, 80.892, 134.82, 188.748, 242.676)
GUIDE_SCREW_PASSAGE = PLATE_THICKNESS - PLATEN_CBORE_DEPTH
# The stock 1/4 in shank (length band +0) is the screw's reach into the rail:
# all of it engages full thread.
GUIDE_SCREW_THREAD_ENGAGEMENT = FILLISTER_SHANK_LEN - GUIDE_SCREW_PASSAGE

LOCK_SCREW_PASSAGE = LOCK_THICK
LOCK_SCREW_THREAD_ENGAGEMENT = LOCK_SCREW_SHANK_LEN - LOCK_SCREW_PASSAGE
if TAPPED_HOLE_SPEC.end != "through_all" or TAPPED_HOLE_SPEC.overrides_mm:
    raise AssertionError("platen-guide front receivers must be tapped through")
_MIN_OPPOSED_RECEIVER_C2C = min(
    abs(lock_x - guide_x) for lock_x in HOLE_X for guide_x in SCREW_STATION_X
)
_GUIDE_DEPTH_DEV = printed_deviations(
    GUIDE_DEPTH, GUIDE_DEPTH_PLACES, deviations(GUIDE_DEPTH_BAND)
)
# The lock seats' shallowest depth: the printed band's floor, or a seat faced
# to the fitted lock gap (R9-47) on the thinnest bar. The front taps at the
# lock stations exit under the seats.
LOCK_SEAT_DEPTH_MIN = min(
    GUIDE_DEPTH + _GUIDE_DEPTH_DEV[0], BAR_DEPTH - BAR_DEPTH_BAND + LOCK_GAP_FIT[0]
)
# R9-48: the longest lock screw under the thinnest plate stops this far inside
# the rail's platen-mating face at the shallowest seat.
LOCK_SCREW_TIP_INSIDE_MIN = LOCK_SEAT_DEPTH_MIN - TIP_REACH_MAX
# R9-64: the guide screw's tip stops this far inside the rail's rear face at
# the shallowest seat. With the receiver tapped through, that face is the far
# end of the hole, so this is the screw's clearance to it (the assembly's
# bottom-clearance check reads it under that name).
GUIDE_SCREW_TIP_INSIDE_MIN = LOCK_SEAT_DEPTH_MIN - GUIDE_SCREW_THREAD_ENGAGEMENT
GUIDE_SCREW_BOTTOM_CLEARANCE = GUIDE_SCREW_TIP_INSIDE_MIN
# Each row's through taps exit the opposite face beside the other row's taps:
# the least wall between the two thread majors, each at its printed position
# and with its mouth broken at the title block's row.
_POSITION_RADIAL = float(GEOMETRIC_TOLERANCES_MM["guide hole-pattern position"]) / 2.0
LOCK_TAP_EXIT_WALL_MIN = (
    _MIN_OPPOSED_RECEIVER_C2C
    - 2.0 * _POSITION_RADIAL
    - THREAD_MAJOR_MM[LOCK_TAP_SPEC.size]
    - 2.0 * TAP_MOUTH_BREAK
)
RECEIVER_WALL_FLOOR = 1.5

if min(GUIDE_SCREW_THREAD_ENGAGEMENT, LOCK_SCREW_THREAD_ENGAGEMENT) <= 0.0:
    raise AssertionError("platen-guide screw stack has no #4-40 thread engagement")
if GUIDE_SCREW_TIP_INSIDE_MIN <= 0.0:
    raise AssertionError(
        "MHA-VN-006 guide screw tip in the MHA-PD-011 platen guide: stands "
        f"{-GUIDE_SCREW_TIP_INSIDE_MIN:.3f} out of the rear face"
    )
if LOCK_SCREW_TIP_INSIDE_MIN <= 0.0:
    raise AssertionError(
        "MHA-VN-046 guide-lock screw tip in the MHA-PD-011 platen guide: stands "
        f"{-LOCK_SCREW_TIP_INSIDE_MIN:.3f} out of the platen-mating face"
    )
if LOCK_TAP_EXIT_WALL_MIN < RECEIVER_WALL_FLOOR:
    raise AssertionError(
        "MHA-PD-011 platen guide through tap beside the other row's tap: wall "
        f"{LOCK_TAP_EXIT_WALL_MIN:.3f} < {RECEIVER_WALL_FLOOR}"
    )
# R9-47: the as-made lock gap (shallowest rail on the deepest bar) never
# falls under the fitted window's max, so facing the seats always cuts.
if GUIDE_DEPTH + _GUIDE_DEPTH_DEV[0] - (BAR_DEPTH + BAR_DEPTH_BAND) < LOCK_GAP_FIT[1]:
    raise AssertionError(
        "MHA-PD-011 platen guide on the support bar: as-made lock gap under the "
        f"fitted max {LOCK_GAP_FIT[1]:.2f}"
    )

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"


def _apply_drawing_properties(adapter) -> None:
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units).
    await set_global(adapter, "GuideLength", f"{GUIDE_LENGTH}mm")
    await set_global(adapter, "GuideHeight", f"{GUIDE_HEIGHT}mm")
    await set_global(adapter, "GuideDepth", f"{GUIDE_DEPTH}mm")
    # Both hole families are native #4-40 taps (front bottoming, rear through);
    # their diameters come from the ANSI-inch table rather than
    # equation-driven sketch dimensions.

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
        adapter,
        lines,
        rect,
        label="guide outline",
        dims=outline,
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

    # Lock-screw receivers: ONE native Hole Wizard #4-40 tapped THROUGH
    # feature (4 points) from the guide's REAR face (local z=-10, outward
    # normal -Z). The stock 9.525-mm shanks pass through the 2-mm lock plates
    # and stop inside the rail (R9-48).
    lock_spec = LOCK_TAP_SPEC
    wizard_holes(
        adapter,
        lock_spec,
        [[x, GUIDE_HEIGHT / 2.0, -GUIDE_DEPTH] for x in HOLE_X],
        (0.0, 0.0, -1.0),
        f"lock-screw tapped receivers ({lock_spec.size})",
        name="LockHoles",
    )
    v_holes = (
        len(HOLE_X) * math.pi * (blind_cut_dia_mm(lock_spec) / 2.0) ** 2 * GUIDE_DEPTH
    )
    await volume_check(
        adapter, "guide with lock receivers", v_rail - v_holes, 0.05 * v_holes
    )

    # Fastening-screw receivers: ONE native Hole Wizard #4-40 tapped THROUGH
    # feature (5 points) from the front face (R9-64). The deeper stock-head
    # counterbore leaves 1.0822 mm of platen passage, so the 6.35-mm shank
    # engages 5.2678 mm of full thread and stops inside the rail.
    screw_spec = TAPPED_HOLE_SPEC
    wizard_holes(
        adapter,
        screw_spec,
        [[x, GUIDE_HEIGHT / 2.0, 0.0] for x in SCREW_STATION_X],
        (0.0, 0.0, 1.0),
        f"fastening-screw tapped receivers ({screw_spec.size})",
        name="ScrewHoles",
    )
    v_screws = (
        len(SCREW_STATION_X)
        * math.pi
        * (blind_cut_dia_mm(screw_spec) / 2.0) ** 2
        * GUIDE_DEPTH
    )
    v_final = v_rail - v_holes - v_screws
    await volume_check(
        adapter, "guide with screw receivers", v_final, 0.05 * (v_holes + v_screws)
    )

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven guide (equations neutral)", v_final, 0.02 * v_holes
    )

    # The depth's one-sided band is the paper-drive lock-station sweep's
    # (pd_platen_guide_spec), native on the model so the sheet prints it; every
    # printed dimension's places are authored here too (policy rule 2).
    set_dimension_bilateral_tolerance(
        adapter, "Guide", "Depth", *deviations(GUIDE_DEPTH_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    _apply_drawing_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
