r"""Reproduction script: translational-gearing feed pinion (book ch. 23).

The "fifth gear" of the 4/4 video narration: "Behind and attached to the
fourth gear is the fifth gear. This gear has twelve teeth and engages the
rack." 12T at DP 30 (it MUST match the rack -- the scale anchor of ch. 23),
PD 10.160. Locked coaxially behind the 120T reducer disc on the stud, its
long face bridges from the disc plane back to the rack plane (the wide
long-toothed pinion of p.58/p.62), passing under the platen's bottom edge
to mesh the teeth-down rack. At DP 30 the 12T base circle (r 4.92) sits almost ON a 3/8" bore's
wall, so pinion + disc ride the stud's turned-down O5 front section
(build_transgear_stub.py) -- the O5 bore leaves a 2.4 wall.

Layout: gear axis = Z through the origin, disc z = 0..9.5 mm.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_feed_pinion.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
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
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _gear import build_fixed_gear, volume_check
from _part_pmi import author_part_pmi
from transgear_feed_pinion_spec import (
    BORE_DIA_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    GEAR_DATA,
    SURFACE_FINISHES,
)

PART_NAME = "transgear-feed-pinion"
MATERIAL = "Brass"  # ch. 23 photos: brass like the disc it is pinned to

TEETH = 12  # 4/4 video narration: "this gear has twelve teeth" (med)
DP = 30.0  # meshes the DP30 rack (the ch23 scale anchor)
FACE_WIDTH = 9.5  # bridges the disc plane back to the rack plane (derived)
BORE_DIAMETER = 5.0  # rides the stud's turned-down front seat (derived)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): face width and bore diameter carry the
    # load-bearing mm suffix (INCH document; the equation manager reads bare
    # numbers in document units). FaceWidth is the cut-bore depth knob (a feature
    # parameter, not a driven sketch dim). TEETH/DP stay module constants -- the
    # gear blank/gap/pattern is built by build_fixed_gear with literal numerics.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")

    drive_jobs: list[tuple[str, str]] = []

    volume = await build_fixed_gear(adapter, TEETH, FACE_WIDTH, dp=DP)

    # On-axis bore (centre 0,0): define_circle emits only the diameter dim.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIAMETER / 2.0,
        "bore",
        dims=bore,
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
    await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "driven feed pinion (equations neutral)",
        volume - v_bore,
        0.01 * v_bore,
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Mark the bore as the single manufacturing model dimension and stamp the
    # title-block + gear-data properties the curated drawing reads.
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND)
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Gear Data": GEAR_DATA, "Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
