r"""Reproduction script: alignment pinion drum (book ch. 25).

The long brass pinion used to set the machine to sines or cosines: with
the cone set swung clear, a lever engages this drum with the cylinder
train so turning it "moves all the cylinder gears as one" (p. 66). The
user-authoritative 32 teeth are cut at the SAME diametral pitch as the
cylinder gears they must mesh with -- the train DP from machine.yaml
(49.82 since the OD-62.2 re-anchor; ch25's book-era DP 30 predates that
rescale and is not the mating train pitch) -- and the drum is long enough
to span all 20 stations at once.
PR7 (review item 14): ONLY the drum is brass -- the integral
Ø6.35 stubs are retired for a separate thicker STEEL arbor
(build_pinion_arbor.py, Ø8) pressed through the drum's new through-bore;
the arbor rides the swing brackets' top bores and carries its integral turned
grip head plus the separate MHA-058 crossrod. The knurled end collars are simplified
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

from _common import (
    SketchDims,
    _early_bound,
    _read_member,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    feature_name_by_type,
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
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _gear import build_fixed_gear
from _part_pmi import author_part_pmi
from alignment_pinion_spec import (
    ARBOR_BORE_BAND,
    BORE_DIA,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FACE_WIDTH,
    GEAR_DATA,
    ISOMETRIC_VIEW_NOTE,
    OUTSIDE_DIA,
    SURFACE_FINISHES,
    TEETH,
)

PART_NAME = "alignment-pinion"
MATERIAL = "Brass"  # p.67: brass drum, same finish as the cylinder train

# The back face (machine z +68.75 before the mechanism shift) covers the whole
# j = 19 gear face (ends +68.47) with 0.28 to spare: ruling (c) bonded the
# drum 0.3 aft and the fit-up stack (#854) put it 0.25 further aft.  The
# released +68.2 shaved that face (Appendix C). The retired cone-knob
# post no longer caps the free back reach. The brass drum's bore matches the
# separate MHA-102 steel arbor.

BORE_R = BORE_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing: this
    # is an INCH document and the equation manager reads bare values in inches.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "OutsideDia", f"{OUTSIDE_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    v_gear = await build_fixed_gear(
        adapter, TEETH, FACE_WIDTH, dp=DIAMETRAL_PITCH
    )
    blank_name = feature_name_by_type(adapter, "Extrusion")
    if not blank_name:
        raise RuntimeError("alignment-pinion gear blank extrusion is missing")
    blank = _early_bound(
        _early_bound(adapter.currentModel, "IPartDoc").FeatureByName(blank_name),
        "IFeature",
    )
    raw_profile = _read_member(blank, "GetFirstSubFeature")
    if raw_profile is None:
        raise RuntimeError("alignment-pinion gear blank profile is missing")
    profile = _early_bound(raw_profile, "IFeature")
    blank.Name = "GearBlank"
    profile.Name = "GearBlankProfile"
    if str(blank.Name) != "GearBlank" or str(profile.Name) != "GearBlankProfile":
        raise RuntimeError("alignment-pinion gear blank feature names did not persist")
    drive_jobs += [
        (name_dimensions(adapter, "GearBlank", ["FaceWidth"])[0], '"FaceWidth"'),
        (
            name_dimensions(adapter, "GearBlankProfile", ["OutsideDia"])[0],
            '"OutsideDia"',
        ),
    ]

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
    set_dimension_bilateral_tolerance(
        adapter,
        "ArborBoreProfile",
        "ArborBoreDia",
        *deviations(ARBOR_BORE_BAND),
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Mark the native blank, face and matched bore controls, then stamp the
    # title-block and gear-data properties consumed by the drawing.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Gear Data": GEAR_DATA,
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
