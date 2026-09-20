r"""Reproduction script: crank-drive gear (book ch. 12, p. 20).

The dark steel gear at the cone set's large end, annotated "This gear
engages the crank" (p. 20): together with a pinion on the crankshaft
(`build_crank_pinion.py`) it implements the book-stated 4:1 crank-to-cone
reduction (p. 16). The 64T:16T count split preserves that stated ratio;
DP 25.731104 is fixed by the recentered 64T station against the unchanged
cone-pivot-post-v2 crank axis at the checked 0.25-mm mesh slack. This
supersedes the intermediate DP24.74 rear-shifted layout.

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
import _telemetry
import cone_gear_shaft_spec
from _common import (
    IN,
    SketchDims,
    _early_bound,
    _feature_by_name,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _gear import build_fixed_gear, volume_check
from _part_pmi import author_part_pmi
from crank_drive_gear_notes import DRAWING_NOTES, GEAR_DATA
from crank_drive_gear_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    OUTSIDE_DIA,
    SURFACE_FINISHES,
)


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch circle as construction geometry.

    ``ConstructionGeometry`` is declared on the base ISketchSegment, not the
    derived ISketchArc the entity registry binds -- rebind before the set.
    Construction, not BLANKED: a blanked sketch's dimensions never reach
    ``InsertModelAnnotations3``, while construction geometry imports its
    dimensions normally and is never drawn in a view (build_harmonic_base's
    two reference sketches proved both halves live).
    """
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _verify_named_dimension(adapter, full_name: str, expected_mm: float) -> None:
    """Prove a renamed dimension is the one the recipe meant.

    ``name_dimensions`` renames by CREATION ORDER, so a feature that emits more
    than one display dimension can hand the name to the wrong value in silence.
    Cheap to check, and the failure it catches would otherwise surface as a
    wrong number on a released sheet.
    """
    raw = adapter.currentModel.Parameter(full_name)
    if raw is None:
        raise RuntimeError(f"no dimension named {full_name}")
    actual_mm = float(_early_bound(raw, "IDimension").SystemValue) * 1000.0
    if abs(actual_mm - expected_mm) > 1e-6:
        raise RuntimeError(
            f"{full_name} measures {actual_mm:g} mm, expected {expected_mm:g} mm"
        )


PART_NAME = "crank-drive-gear"
MATERIAL = "Plain Carbon Steel"  # p.20: dark gear, distinct from the brass train

TEETH = 64  # Appendix C #9 estimate, photo-ratified 2026-07-14 (see docstring)
DP = _config.machine("gear_train", "crank_drive_diametral_pitch")  # cad/config/machine/gear_train.yaml
PA_DEG = 14.5
FACE_WIDTH = 8.0  # mm, p.20 photo-proportioned (low).  Symmetric narrowing
# retains the rederived centre/mesh axes and clears the fixed v2 post boss.
# M6.7: seated perpendicular on the cone shaft's 3/8" pivot journal
# like the cone gears (true cone, p.20).
BORE_DIAMETER = 0.375 * IN  # snug on the 3/8" journal

# Crossed-mesh accommodation (module docstring): the tooth inclination is the
# exact-solid result for the recentered 64T station and is shared through the
# gear-train config. Positive
# sign: the gap azimuth advances CCW (about local +z) toward the gear's
# +z face, which the assembly places toward machine +z (the analytic
# study's zero-collision hand; the mirrored hand collides 28 mm^3).
HELIX_DEG = _config.machine("gear_train", "crank_drive_helix_deg")
BACKLASH_MM = _config.machine("gear_train", "crank_drive_backlash_mm")

# The bore over the cone gear shaft is this part's ONE critical fit, and a slip
# fit exists only if the size limits on BOTH mating features are narrower than
# the clearance band it claims (cad/docs/tolerance-policy.md step 6b). So the
# band is DERIVED -- never a per-part number -- from the named fit class and the
# shaft land's own published limits: bore_min = shaft_max + clearance_min,
# bore_max = shaft_min + clearance_max. Move either input and this moves with
# it. It lives in the BUILD script, not in the shared spec: reading a fit class
# in crank_drive_gear_spec would put tolerances.yaml in the import closure of
# every assembly that imports OUTSIDE_DIA from it (test_dodo_recipe's
# fine-grained-config contract), and only the part needs the limits.
_CLEARANCE_MIN, _CLEARANCE_MAX = _config.fit("shaft_in_bushing")[
    "diametral_clearance_mm"
]
_LAND_UPPER, _LAND_LOWER = cone_gear_shaft_spec.SECTION_DIA_BAND
BORE_DIA_BAND = (  # (upper, lower) deviations
    round(_LAND_LOWER + _CLEARANCE_MAX, 3),
    round(_LAND_UPPER + _CLEARANCE_MIN, 3),
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in document
    # units (an unsuffixed 9.525 would be read as 9.525 inches). FaceWidth is the
    # blank/bore extrude DEPTH and BoreDia the shaft-bore diameter; both are
    # printed dimensions, so both are knobs AND both are driven below. The
    # toothed-disc geometry (teeth/DP/helix) is authored by the shared _gear
    # helper with literal-numeric curve expressions, so it has no sketch dim to
    # drive here -- which is why the tip circle needs the reference sketch
    # further down.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")

    drive_jobs: list[tuple[str, str]] = []

    volume = await build_fixed_gear(
        adapter, TEETH, FACE_WIDTH, dp=DP, pa_deg=PA_DEG,
        helix_deg=HELIX_DEG,
        backlash_mm=BACKLASH_MM, root_relief=True,
    )

    # build_fixed_gear is shared by five recipes, so it leaves the blank under
    # the adapter's default names. Name the boss here: the face width is a size
    # the turner sets, so it prints as a NATIVE model dimension
    # (drawing-simplicity-policy.md rules 1-2), which means it must be named,
    # driven, marked and given its decimal places like any other. Driving it is
    # also the guard on the default name: a rename that resolved the wrong
    # feature would move the blank and the equation-neutral volume gate below
    # would fail loud instead of printing the depth of something else.
    _feature_by_name(adapter, "Boss-Extrude1").Name = "GearBlank"
    _telemetry.success("feature 'Boss-Extrude1' -> 'GearBlank'")
    drive_jobs += [
        (name_dimensions(adapter, "GearBlank", ["FaceWidth"])[0], '"FaceWidth"')
    ]

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
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND)
    )
    await volume_check(adapter, "driven crank-drive gear (equations neutral)", expected, 0.01 * v_bore)

    # The tip circle, as a REFERENCE sketch. The helix recipe grows the teeth
    # off a ROOT cylinder blank (_gear.build_fixed_gear), so no solid feature
    # owns the outside diameter -- yet the OD is the first size the turner sets
    # and the print must carry it as a model dimension, not as text in the data
    # block (policy rule 2's "model it, even if that takes a hidden reference
    # sketch whose one driving dimension IS the value"). Construction geometry:
    # its dimension imports onto the sheet, the circle itself is never drawn.
    check("create_sketch tip reference", await adapter.create_sketch("Front"))
    tip_ref = await define_circle(
        adapter, 0.0, 0.0, OUTSIDE_DIA / 2.0, "tip circle reference"
    )
    _as_construction(adapter, tip_ref)
    await ensure_fully_defined(adapter, "tip circle reference sketch")
    check("exit_sketch tip reference", await adapter.exit_sketch())
    name_last_feature(adapter, "OutsideDiaReference")
    name_dimensions(adapter, "OutsideDiaReference", ["OutsideDia"])
    _verify_named_dimension(adapter, "OutsideDia@OutsideDiaReference", OUTSIDE_DIA)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Mark this part's three manufacturing dimensions, author the decimal places
    # they print with (policy rule 2: the model owns both the band and its
    # spelling -- the drawing only reads them back), and stamp the title-block +
    # gear-data properties the curated drawing reads.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Gear Data": GEAR_DATA, "Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
