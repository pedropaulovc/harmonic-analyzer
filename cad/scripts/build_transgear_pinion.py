r"""Reproduction script: translational-gearing third gear (book ch. 23).

The tiny steel pinion pinned on the knob shaft just behind the mounted
removable -- the "third gear" of the 4/4 video narration: 12 teeth, meshing
the 120T reducer disc (build_rack_pinion.py) at the same DP 38, the
permanent 1:10 reduction of the paper feed (paper-drive rework E7/E8; the
old 24T DP30 estimate belonged to the refuted disc-meshes-rack topology).
At DP 38 the 12T gear's root sits BELOW a 3/8" bore's wall, so it rides a
turned-down O5 pinion seat on the knob shaft
(build_transgear_knob_shaft.py) -- base circle r 3.88 leaves a 1.38 wall.

Layout: gear axis = Z through the origin, disc z = 0..4 mm.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_pinion.py
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
from transgear_pinion_spec import (
    BORE_DIA_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    GEAR_DATA,
)

PART_NAME = "transgear-pinion"
MATERIAL = "Plain Carbon Steel"  # ch. 23 photos: steel (unlike the brass wheels)

TEETH = 12  # 4/4 video narration: the third gear has 12 teeth (med)
DP = 38.0  # meshes the 120T reducer disc at its DP (med)
FACE_WIDTH = 4.0  # mm, thin pinion behind the removable (low)
BORE_DIAMETER = 5.0  # rides the knob shaft's turned-down pinion seat (derived)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): face width and bore diameter carry the
    # load-bearing mm suffix (INCH document; the equation manager reads bare
    # numbers in document units, so an unsuffixed length blows the part up 25.4x).
    # FaceWidth is the cut-bore depth knob (a feature parameter, not a driven
    # sketch dim). TEETH stays a module constant -- the gear blank/gap/pattern is
    # built by build_fixed_gear with literal numerics, off this self-naming path.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")

    drive_jobs: list[tuple[str, str]] = []

    volume = await build_fixed_gear(adapter, TEETH, FACE_WIDTH, dp=DP)

    # On-axis bore (centre 0,0): define_circle emits only the diameter dim, so
    # only the "Dia" slot is recorded -- the X/Z names are ignored.
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
        "driven transgear pinion (equations neutral)",
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
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Gear Data": GEAR_DATA, "Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
