r"""Reproduction script: crank-drive gear (book ch. 12, p. 20).

The dark steel gear at the cone set's large end, annotated "This gear
engages the crank" (p. 20): together with a pinion on the crankshaft
(`build_crank_pinion.py`) it implements the book-stated 4:1 crank-to-cone
reduction (p. 16). Tooth-count/DP split per the Appendix C #9 estimate,
re-anchored on the 62.2 cylinder OD: DP 26.57, 64T (pitch r 30.59 = the
cone T120's, restoring the p.20 "same OD as the 120T" read), mating a
16T pinion. The 4:1 ratio itself is book-stated and fixed; the split is
ratified by the p.18/p.19/p.20 photos (2026-07-14 rederive: pitch ~1.9x
coarser than the train beside the 120T, pinion OD ~0.72x the O24 green
column).

CROSSED-MESH CUT (2026-07-14 rederive, "crank-pinion and crank-drive gear
are not meshing"): the 64T rides the cone shaft, inclined 12.52 deg IN
PLAN, while its 16T pinion spins about machine z (ch30 GT pins the crank
axle at the pedestal's x at BOTH ends -- a cone-parallel crankshaft would
land 22 mm east at the arm, 20+ sigma off; the planar crank->paper chain
corroborates). The pair is therefore a CROSSED-axis mesh, and straight
uniform teeth geometrically cannot engage at depth across it (flank
misregistration +-1.08 mm across the face vs <=0.70 available clearance
-- the old build backed the crank off until the tips cleared entirely,
the user-flagged air gap). The book photos (ch12 p.18/p.19) show the
real pair deeply engaged, so the real 64T must carry the accommodation
the crossing demands; this script cuts it as a true swept helix -- the
tooth gaps advance (z - face/2)*tan(incline)/R_pitch across the face
(equivalently: gear helix angle = shaft angle, pinion straight = a
textbook crossed-helical pair) -- plus transverse tooth thinning (config)
that also absorbs the cos(incline) normal-pitch shrink, and a deepened root floor (the mating
16T's tips need real dedendum). Study: crossed_mesh_study (analytic,
2026-07-14); arbitrated against the live interference gate.

Dimensions: cad/config/dimensions.yaml ch12 crank-drive gear row +
Appendix C #9.

Layout: gear axis = Z through the origin, disc z = 0..10 mm; the helix
twist is symmetric about the mid-face plane z = 5 (the assembly's phase
math references the mid-face azimuth).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_drive_gear.py
"""

from __future__ import annotations

import math
import sys

import _config
from _common import (
    IN,
    SketchDims,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _gear import build_fixed_gear, volume_check
from crank_drive_gear_spec import DRAWING_DIMENSIONS, DRAWING_NOTES, GEAR_DATA

PART_NAME = "crank-drive-gear"
MATERIAL = "Plain Carbon Steel"  # p.20: dark gear, distinct from the brass train

TEETH = 64  # Appendix C #9 estimate, photo-ratified 2026-07-14 (see docstring)
DP = _config.machine("gear_train", "crank_drive_diametral_pitch")  # cad/config/machine/gear_train.yaml
PA_DEG = 14.5
FACE_WIDTH = 10.0  # mm, p.20 -- wider than the 7 mm cone faces (low)
# M6.7: seated perpendicular on the cone shaft's 3/8" pivot journal
# like the cone gears (true cone, p.20).
BORE_DIAMETER = 0.375 * IN  # snug on the 3/8" journal

# Crossed-mesh accommodation (module docstring): helix angle == the cone
# plan incline, DERIVED from the same config the assembly derives it from
# (radius step per 6 teeth vs the drum seat pitch) -- never a free literal,
# so the gear and the drive-train geometry cannot drift apart. Positive
# sign: the gap azimuth advances CCW (about local +z) toward the gear's
# +z face, which the assembly places toward machine +z (the analytic
# study's zero-collision hand; the mirrored hand collides 28 mm^3).
_DP_TRAIN = _config.machine("gear_train", "diametral_pitch")
_RADIUS_STEP = 3.0 * 25.4 / _DP_TRAIN
_SEAT_NOMINAL = _config.machine("cone_incline", "drum_seat_nominal_mm")
_Z_PITCH = _SEAT_NOMINAL * math.cos(math.asin(_RADIUS_STEP / _SEAT_NOMINAL))
HELIX_DEG = math.degrees(math.asin(_RADIUS_STEP / _Z_PITCH))  # 12.5182
BACKLASH_MM = _config.machine("gear_train", "crank_drive_backlash_mm")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in document
    # units (an unsuffixed 9.525 would be read as 9.525 inches). FaceWidth is the
    # blank/bore extrude DEPTH (a feature parameter, not a sketch dim), so it is
    # an editable knob but nothing in drive_jobs drives it; BoreDia drives the
    # shaft-bore diameter. The toothed-disc geometry (teeth/DP) is authored by the
    # shared _gear helper with literal-numeric curve expressions, so it has no
    # sketch dim to drive here.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")

    drive_jobs: list[tuple[str, str]] = []

    volume = await build_fixed_gear(
        adapter, TEETH, FACE_WIDTH, dp=DP, pa_deg=PA_DEG,
        helix_deg=HELIX_DEG,
        backlash_mm=BACKLASH_MM, root_relief=True,
    )

    # Shaft bore (on-axis circle at the origin: only the diameter is a dim, so
    # define_circle records just that -- the centre X/Z slots are ignored).
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIAMETER / 2.0, "bore", dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 2.0)),
    )
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * (BORE_DIAMETER / 2.0) ** 2 * FACE_WIDTH
    expected = volume - v_bore
    await volume_check(adapter, "bore", expected, 0.01 * v_bore)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "bore axis")

    # Apply the deferred drive equations after the whole model + a rebuild exist,
    # then re-check: each equation evaluates to the as-built value, so the
    # geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven crank-drive gear (equations neutral)", expected, 0.01 * v_bore)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Mark the bore as the single manufacturing model dimension and stamp the
    # title-block + gear-data properties the curated drawing reads.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Gear Data": GEAR_DATA, "Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
