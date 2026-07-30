r"""Reproduction script: translational-gearing reducer disc (book ch. 23).

The large thin brass disc gear -- the "fourth gear" of the 4/4 video: 120
teeth (narrated count, CONFIRMED by an FFT ring count on the ch30 p002
front view, ~115-119 peak) at DP 38 (disc OD measures ~82 +-2.5; 120T DP38
gives PD 80.21 / OD 81.55, and the measured rack/disc pitch ratio ~1.27
matches 2.660/2.101). It does NOT touch the rack (the old 96T DP30
"rack-pinion" role is REFUTED -- paper-drive rework E7/E8): it is the fixed
reduction wheel, driven 12:120 by the third gear on the knob shaft
(build_transgear_pinion.py) and locked coaxially to the 12T DP30 feed
pinion (build_transgear_feed_pinion.py) that meshes the rack. ~3 mm disc,
plain 3/8" stud bore.

Layout: gear axis = Z through the origin, disc z = 0..3 mm.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_rack_pinion.py
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
from rack_pinion_spec import BORE_DIA_BAND, DRAWING_DIMENSIONS, DRAWING_NOTES, GEAR_DATA

PART_NAME = "rack-pinion"
MATERIAL = "Brass"  # ch. 23 photos: brass

TEETH = 120  # 4/4 video narration, FFT-confirmed on ch30 p002 (med)
DP = 38.0  # OD ~82 at 120T; pitch-ratio cross-check vs the DP30 rack (med)
FACE_WIDTH = 3.0  # mm, edge-on view v4_transgear_002 (low)
BORE_DIAMETER = 5.0  # shares the stud's O5 front seat with the feed pinion
# (whose 12T DP30 base circle cannot take the 3/8" stud -- see
# build_transgear_feed_pinion.py)


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

    volume = await build_fixed_gear(adapter, TEETH, FACE_WIDTH, dp=DP)

    # Shaft bore (on-axis circle at the origin: only the diameter is a dim, so
    # define_circle records just that -- the centre X/Z slots are ignored).
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
    expected = volume - v_bore
    await volume_check(adapter, "bore", expected, 0.01 * v_bore)

    # Apply the deferred drive equations after the whole model + a rebuild exist,
    # then re-check: each equation evaluates to the as-built value, so the
    # geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven rack pinion (equations neutral)", expected, 0.01 * v_bore
    )

    # Construction axis (Top x Right = the Z gear axis through the origin): the
    # paper-drive assembly gear-mates the disc to the third gear and revolute-
    # mates it on the stud. A reference feature -- no volume, geometry unchanged.
    from solidworks_mcp.adapters.base import CreateAxisParameters  # noqa: E402

    check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
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
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Gear Data": GEAR_DATA, "Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
