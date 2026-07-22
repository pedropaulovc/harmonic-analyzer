r"""Reproduction script: alignment pinion drum (book ch. 25).

The long brass pinion used to set the machine to sines or cosines: with
the cone set swung clear, a lever engages this drum with the cylinder
train so turning it "moves all the cylinder gears as one" (p. 66). 42
teeth (counted on the p. 67 plate), cut at the SAME diametral pitch as
the cylinder gears it must mesh with -- the train DP from machine.yaml
(49.82 since the OD-62.2 re-anchor; ch25's book-era DP 30 predates that
rescale and over-sizes the teeth ~66%, burying the drum 5.4 mm into
every cylinder gear) -- and a drum long enough to span all 20 stations
at once. PR7 (review item 14): ONLY the drum is brass -- the integral
Ø6.35 stubs are retired for a separate thicker STEEL arbor
(build_pinion_arbor.py, Ø8) pressed through the drum's new through-bore;
the arbor rides the swing brackets' top bores and carries the turning
handle (build_pinion_handle.py). The knurled end collars are simplified
away.

Layout: axis Z, drum z 0..143.2, Ø8 through-bore on the axis.
The ch30/M6.8 model carries it in the DISENGAGED rest state (p. 68
"gap"), so no tooth-phase seed is needed.

Dimensions: cad/DIMENSIONS.md "Chapter 25"; tooth count from
cad/config/machine/alignment_pinion.yaml.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_alignment_pinion.py
"""

from __future__ import annotations

import math
import sys

import _config
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
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _gear import build_fixed_gear
from alignment_pinion_spec import DRAWING_DIMENSIONS, DRAWING_NOTES, GEAR_DATA
from build_cone_gear import DP  # DP = train diametral_pitch (machine.yaml)

PART_NAME = "alignment-pinion"
MATERIAL = "Brass"  # p.67: brass drum, same finish as the cylinder train

TEETH = _config.machine("alignment_pinion", "teeth")  # ch25 plate count (high)
FACE_WIDTH = 143.2  # DIMENSIONS.md ch25: spans all 20 drum stations, but
# the back face (machine z +68.2) shaves the last 0.28 of the j = 19
# gear face (ends +68.48); documented in Appendix C (derived). (The old
# cone-knob post that once capped the drum + stub at machine z 74 is
# retired; the free back reach now belongs to the separate arbor.)
BORE_DIA = 8.0  # PR7 (review item 14): the integral Ø6.35 stubs are RETIRED
# -- only the drum is brass; the arbor is a separate thicker STEEL shaft
# (build_pinion_arbor.py, Ø8) pressed through this bore. Must match the
# arbor's SHAFT_DIA and the strap's ArborBore.

BORE_R = BORE_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the arbor bore diameter and, as a
    # declared feature-parameter knob, the drum face width. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 8 = 8 in). TEETH stays a
    # module constant -- build_fixed_gear cuts the blank/gap/pattern with
    # literal numerics, off this self-naming path.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    v_gear = await build_fixed_gear(adapter, TEETH, FACE_WIDTH, dp=DP)

    # Arbor through-bore (PR7): the steel Ø8 arbor (build_pinion_arbor.py)
    # presses through -- on-axis circle, mid-plane cut spanning the drum.
    from solidworks_mcp.adapters.base import ExtrusionParameters

    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_R, "arbor bore", dims=bore,
        names=("ArborBoreCx", "ArborBoreCz", "ArborBoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "ArborBoreProfile")
    drive_jobs += bore.apply(adapter, "ArborBoreProfile")
    check(
        "cut arbor bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.5 * FACE_WIDTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ArborBore")
    v_bore = math.pi * BORE_R**2 * FACE_WIDTH
    expected = v_gear - v_bore
    await volume_check(adapter, "arbor bore", expected, 0.02 * v_bore)
    # The gear's central reference axis (Axis1@alignment-pinion, Top∩Right from
    # build_fixed_gear) is the pinion spin/lock axis used by the p2 swing group
    # in build_drive_train -- same convention as the cone gears.

    # Deferred drive equations, then re-check neutrality
    # (each evaluates to the as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven alignment pinion (equations neutral)", expected, 0.02 * v_bore
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Mark the arbor bore as the manufacturing model dimension and stamp the
    # title-block + gear-data properties the curated drawing requires.
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
