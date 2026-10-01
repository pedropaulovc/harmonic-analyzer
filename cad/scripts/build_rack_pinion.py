r"""Reproduction script: translational-gearing reducer disc MHA-070 (book ch. 23).

The large thin brass disc gear -- the "fourth gear" of the 4/4 video: 120
teeth (narrated count, CONFIRMED by an FFT ring count on the ch30 p002
front view, ~115-119 peak) at DP 38 (disc OD measures ~82 +-2.5; 120T DP38
gives PD 80.21 / OD 81.55, and the measured rack/disc pitch ratio ~1.27
matches 2.660/2.101). It does NOT touch the rack (the old 96T DP30
"rack-pinion" role is REFUTED -- paper-drive rework E7/E8): it is the fixed
reduction wheel, driven 12:120 by the knob shaft's 12T DP38, slipped on the
pinion sleeve's Ø10 spigot and screwed to the brass hub's flange (MHA-159)
by three #0-80 fillister screws (MHA-161).

Every size is ``rack_pinion_spec``'s; the screw pattern is
``transgear_disc_hub_geometry``'s (the one authority the flange shares).

Layout (part frame): gear axis = Z through the origin; the Front plane is
the disc's FRONT face (z = 0, the flange seat), the body runs z = 0..3 and
+Z is machine rearward.

Features: ``GearBlank`` / ``GearBlankProfile`` (the toothed disc's blank,
renamed so its depth prints as ``FaceWidth``), the tooth gap + pattern,
``BoreProfile`` / ``Bore`` (Ø10 through), ``DiscTaps`` (native Hole Wizard
#0-80 taps through, placed from the rear face on the bolt circle), and
``DiscTapCountersinks`` (the 90° entry countersinks on the front face).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_rack_pinion.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
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
    set_global,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _drawing_simplified import save_simplified_part
from _gear import build_fixed_gear, volume_check
from _holes import wizard_holes
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from rack_pinion_spec import (
    BORE_DEVIATIONS,
    BORE_DIA,
    CSK_LEG,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FACE_WIDTH,
    GEAR_DATA,
    SURFACE_FINISHES,
    TAP_CENTRES,
    TAP_DRILL_DIA,
    TAP_SPEC,
    TAP_TO_BORE_WALL_WORST,
    TEETH,
)
from transgear_disc_hub_geometry import (
    BOLT_CIRCLE_DIA,
    BOLT_CIRCLE_X_FACTOR,
    BOLT_CIRCLE_Y_FACTOR,
)
from transgear_disc_screw_spec import ENGAGEMENT_WORST_D

PART_NAME = "rack-pinion"
MATERIAL = "Brass"  # ch. 23 photos: brass

# The paper-drive assembly reads TEETH, DP and FACE_WIDTH from here
# (test_buildgraph pins that edge).
DP = DIAMETRAL_PITCH
BORE_DIAMETER = BORE_DIA

_R_TAP = TAP_DRILL_DIA / 2.0
V_BORE = math.pi * (BORE_DIAMETER / 2.0) ** 2 * FACE_WIDTH
V_TAPS = len(TAP_CENTRES) * math.pi * _R_TAP**2 * FACE_WIDTH
# One 45-degree countersink ring on each tap-drill mouth.
V_CSKS = len(TAP_CENTRES) * math.pi * CSK_LEG**2 * (_R_TAP + CSK_LEG / 3.0)

# The 0° centre lies on +X (y = 0); the 120° / 240° centres carry both
# coordinates, each driven from the one "BoltCircleDia" global.
_BC_HALF = '"BoltCircleDia" / 2'
_BC_X = f'"BoltCircleDia" * {BOLT_CIRCLE_X_FACTOR!r}'
_BC_Y = f'"BoltCircleDia" * {BOLT_CIRCLE_Y_FACTOR!r}'
TAP_PLACEMENT_DIMS = [
    (("TapX1", _BC_HALF), (None, None)),
    (("TapX2", _BC_X), ("TapY2", _BC_Y)),
    (("TapX3", _BC_X), ("TapY3", _BC_Y)),
]


def _rename_gear_blank(adapter) -> None:
    """Name build_fixed_gear's blank extrude and its sketch so the disc
    thickness prints as the native ``FaceWidth``."""
    blank_name = feature_name_by_type(adapter, "Extrusion")
    if not blank_name:
        raise RuntimeError("rack-pinion gear blank extrusion is missing")
    blank = _early_bound(
        _early_bound(adapter.currentModel, "IPartDoc").FeatureByName(blank_name),
        "IFeature",
    )
    raw_profile = _read_member(blank, "GetFirstSubFeature")
    if raw_profile is None:
        raise RuntimeError("rack-pinion gear blank profile is missing")
    profile = _early_bound(raw_profile, "IFeature")
    blank.Name = "GearBlank"
    profile.Name = "GearBlankProfile"
    if str(blank.Name) != "GearBlank" or str(profile.Name) != "GearBlankProfile":
        raise RuntimeError("rack-pinion gear blank feature names did not persist")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreateAxisParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units. The toothed-disc geometry (teeth/DP) is authored by the
    # shared _gear helper with literal-numeric curve expressions.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")
    await set_global(adapter, "BoltCircleDia", f"{BOLT_CIRCLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    disc = await build_fixed_gear(adapter, TEETH, FACE_WIDTH, dp=DP)
    _rename_gear_blank(adapter)
    drive_jobs += [
        (name_dimensions(adapter, "GearBlank", ["FaceWidth"])[0], '"FaceWidth"')
    ]
    expected = disc.volume

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
    expected -= V_BORE
    await volume_check(adapter, "bore", expected, 0.01 * V_BORE)

    # --- #0-80 taps through, placed from the rear face on the flange's bolt
    # circle; the front mouths countersunk.  The sheet prints no position:
    # the shop transfers each tap from its MHA-159 flange hole at assembly.
    taps = wizard_holes(
        adapter,
        TAP_SPEC,
        [[x, y, FACE_WIDTH] for x, y in TAP_CENTRES],
        (0.0, 0.0, 1.0),
        f"disc taps ({TAP_SPEC.size} through)",
        name="DiscTaps",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=TAP_PLACEMENT_DIMS,
    )
    drive_jobs += taps.placement_drive_jobs
    expected -= V_TAPS
    await volume_check(adapter, "disc with taps", expected, 0.03 * V_TAPS + 0.05)
    check(
        "countersink disc-tap front mouths",
        await adapter.add_chamfer(
            CSK_LEG, [[x + _R_TAP, y, 0.0] for x, y in TAP_CENTRES]
        ),
    )
    name_last_feature(adapter, "DiscTapCountersinks")
    expected -= V_CSKS
    await volume_check(adapter, "disc-tap countersinks", expected, 0.03 * V_CSKS + 0.05)

    # Apply the deferred drive equations after the whole model + a rebuild exist,
    # then re-check: each equation evaluates to the as-built value, so the
    # geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven rack pinion (equations neutral)", expected, 0.01 * V_BORE
    )

    # Construction axis (Top x Right = the Z gear axis through the origin): the
    # paper-drive assembly gear-mates the disc to the third gear and revolute-
    # mates it on the stud. A reference feature -- no volume, geometry unchanged.
    gear_axis = check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    ).name
    # Hidden but still selectable by name for the assembly's mates.
    blank_reference_geometry(adapter, ((gear_axis, "AXIS"),))

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    _telemetry.info(
        f"disc screw engagement {ENGAGEMENT_WORST_D:.2f} D worst;"
        f" tap to bore wall {TAP_TO_BORE_WALL_WORST:.2f} worst"
    )

    # The bore's reamed slip band on the sleeve spigot is the one model band;
    # the other printed places (and so the general-tolerance row each
    # dimension claims) are authored on the model.
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *BORE_DEVIATIONS
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Gear Data": GEAR_DATA, "Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_simplified_part(adapter, PART_NAME, disc.tooth_features)


if __name__ == "__main__":
    sys.exit(run_build(build))
