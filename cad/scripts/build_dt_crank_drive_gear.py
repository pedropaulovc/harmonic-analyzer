r"""Reproduction script: crank-drive gear (book ch. 12, p. 20).

The dark steel gear at the cone set's large end, annotated "This gear
engages the crank" (p. 20): together with a pinion on the crankshaft
(`build_dt_crank_pinion.py`) it implements the book-stated 4:1 crank-to-cone
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

ATTACHMENT (user ruling 2026-09-28): the 64T slides onto MHA-DT-004's
Sec1 D-flat land with one matching flat, normal to local +X. The round
and across-flat bore bands are derived from that land's two printed
bands. Its south bore entry has a 1.00 x 45° chamfer across the entire
D-profile to swallow the flat mill's runout crescent against the square
shaft collar; the bearing annulus remains intact. Its south face butts
against the MHA-DT-004 thrust collar; the north face touches T120 in the
solid cone-gear stack. The 64T has no tooth-to-flat clock requirement.

Layout: gear axis = Z through the origin, disc z = 0..FACE_WIDTH; the helix
twist is symmetric about the mid-face plane (the assembly's phase math
references the mid-face azimuth).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_crank_drive_gear.py
"""

from __future__ import annotations

import math
import sys

import _config
import _telemetry
from _common import (
    IN,
    SketchDims,
    _early_bound,
    _feature_by_name,
    apply_material,
    blank_sketch,
    check,
    name_bore_axis,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    set_global,
    set_sketch_direct_db,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _simplified_part import save_simplified_part
from _gear import build_fixed_gear, volume_check
from _part_pmi import author_part_pmi
from dt_crank_drive_gear_notes import DRAWING_NOTES, GEAR_DATA
from dt_crank_drive_gear_spec import (
    BORE_AF,
    BORE_AF_BAND,
    BORE_DIA_BAND,
    BORE_SOUTH_CHAMFER,
    BORE_SOUTH_CHAMFER_BAND,
    CUTTER_DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FACE_WIDTH,
    FACE_WIDTH_BAND,
    LONG_ADDENDUM_MM,
    OUTSIDE_DIA,
    OUTSIDE_DIA_TOLERANCE_MM,
    PRESSURE_ANGLE_DEG,
    SURFACE_FINISHES,
)


def _d_bore_area(radius: float, flat_x: float) -> float:
    """Area of a round bore trimmed by its across-flat chord, in mm²."""
    half_chord = math.sqrt(radius * radius - flat_x * flat_x)
    segment = radius * radius * math.acos(flat_x / radius) - flat_x * half_chord
    return math.pi * radius * radius - segment


def _bore_south_chamfer_volume(radius: float, flat_x: float, leg: float) -> float:
    """45° D-rim chamfer removal: offset arc AND flat, integrated axially.

    At depth z the bore grows by leg-z along both walls; Simpson quadrature
    of that exact D cross-section avoids pretending the flat is a full circle.
    """
    base = _d_bore_area(radius, flat_x)
    steps = 16
    dz = leg / steps
    total = 0.0
    for index in range(steps + 1):
        offset = index * dz
        area_added = _d_bore_area(radius + offset, flat_x + offset) - base
        total += (1 if index in (0, steps) else 4 if index % 2 else 2) * area_added
    return dz * total / 3.0


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch segment as construction geometry.

    ``ConstructionGeometry`` lives on ISketchSegment, not the derived
    ISketchArc/ISketchLine bound by the entity registry. A construction
    witness imports its native dimension while staying out of the cut
    profile and the visible drawing geometry.
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


PART_NAME = "dt-crank-drive-gear"
MATERIAL = "Plain Carbon Steel"  # p.20: dark gear, distinct from the brass train

TEETH = 64  # Appendix C #9 estimate, photo-ratified 2026-07-14 (see docstring)
DP = _config.machine("gear_train", "crank_drive_diametral_pitch")  # cad/config/machine/gear_train.yaml
PA_DEG = PRESSURE_ANGLE_DEG  # transverse, from the normal-plane cutter (spec)
# The 64T seats on MHA-DT-004's flatted Sec1 gear land.
BORE_DIAMETER = 0.375 * IN

# Crossed-mesh accommodation (module docstring): the tooth inclination is the
# exact-solid result for the recentered 64T station and is shared through the
# gear-train config. Positive
# sign: the gap azimuth advances CCW (about local +z) toward the gear's
# +z face, which the assembly places toward machine +z (the analytic
# study's zero-collision hand; the mirrored hand collides 28 mm^3).
HELIX_DEG = _config.machine("gear_train", "crank_drive_helix_deg")
BACKLASH_MM = _config.machine("gear_train", "crank_drive_backlash_mm")



async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # This INCH document needs explicit mm suffixes in its editable globals.
    # The face width, round bore, across-flat witness and entry chamfer
    # dimensions are equation-driven after the full feature tree exists.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")
    await set_global(adapter, "BoreAF", f"{BORE_AF}mm")
    await set_global(adapter, "BoreSouthChamferSize", f"{BORE_SOUTH_CHAMFER}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Normal-defined (#906): the transverse DP/PA place the involute, the
    # cutter's DP sets the depth; the blank is turned long (R9-56).
    disc = await build_fixed_gear(
        adapter, TEETH, FACE_WIDTH, dp=DP, pa_deg=PA_DEG,
        helix_deg=HELIX_DEG,
        backlash_mm=BACKLASH_MM, root_relief=True,
        depth_dp=CUTTER_DIAMETRAL_PITCH,
        long_addendum_mm=LONG_ADDENDUM_MM,
    )
    volume = disc.volume

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

    # Cut one D-profile through the finished helix. Its circle arc is the
    # major arc through local -X; the closing chord is perpendicular to +X.
    # A construction witness from the opposite arc wall to the flat owns
    # the native across-flat measurement (BoreAF), independent of BoreDia.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    radius = BORE_DIAMETER / 2.0
    flat_x = BORE_AF - radius
    half_chord = math.sqrt(radius * radius - flat_x * flat_x)
    set_sketch_direct_db(adapter, True)
    arc = check(
        "D-bore major arc",
        await adapter.add_arc(0.0, 0.0, flat_x, half_chord, flat_x, -half_chord),
    )
    flat = check(
        "D-bore flat", await adapter.add_line(flat_x, -half_chord, flat_x, half_chord)
    )
    af_witness = check(
        "D-bore across-flat witness", await adapter.add_line(-radius, 0.0, flat_x, 0.0)
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, af_witness)
    for label, first, second, relation in (
        ("bore arc centre", f"{arc}.center", "origin", "coincident"),
        ("bore lower junction", f"{flat}.start", f"{arc}.end", "coincident"),
        ("bore upper junction", f"{flat}.end", f"{arc}.start", "coincident"),
        ("vertical bore flat", flat, None, "vertical"),
        ("horizontal AF witness", af_witness, None, "horizontal"),
        ("witness on bore arc", f"{af_witness}.start", arc, "coincident"),
        ("witness on bore centre", f"{af_witness}.start", "origin", "horizontal_points"),
        ("witness on bore flat", f"{af_witness}.end", flat, "coincident"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    check(
        "bore diameter", await adapter.add_sketch_dimension(
            arc, None, "diameter", BORE_DIAMETER
        ),
    )
    bore.record("BoreDia", '"BoreDia"')
    check(
        "across-flat size", await adapter.add_sketch_dimension(
            f"{af_witness}.start", f"{af_witness}.end",
            "horizontal_distance", BORE_AF,
        ),
    )
    bore.record("BoreAF", '"BoreAF"')
    await ensure_fully_defined(adapter, "D-bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    _verify_named_dimension(adapter, "BoreDia@BoreProfile", BORE_DIAMETER)
    _verify_named_dimension(adapter, "BoreAF@BoreProfile", BORE_AF)
    check(
        "cut D-bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 2.0)),
    )
    name_last_feature(adapter, "Bore")
    v_bore = _d_bore_area(radius, flat_x) * FACE_WIDTH
    expected = volume - v_bore
    await volume_check(adapter, "D-bore", expected, 0.01 * v_bore)

    # Both south (z=0) bore edges must be selected: the round major arc at
    # -X and the D-flat chord on +X. The north rim stays square against T120.
    # A ≥Ø8 end mill leaves at most MAX_FLAT_CRESCENT (≈0.960 mm at print
    # worst) of horn + axial runout where the shaft flat meets its collar;
    # the minimum 1.00-mm, 45° chamfer swallows it. A single native feature
    # removes both sides of that crescent, not just the easy round arc.
    check(
        "chamfer south D-bore entry",
        await adapter.add_chamfer(
            BORE_SOUTH_CHAMFER,
            [[-radius, 0.0, 0.0], [flat_x, 0.0, 0.0]],
        ),
    )
    name_last_feature(adapter, "BoreSouthChamfer")
    chamfer_dim = name_dimensions(
        adapter, "BoreSouthChamfer", ["BoreSouthChamferSize"]
    )[0]
    _verify_named_dimension(adapter, chamfer_dim, BORE_SOUTH_CHAMFER)
    drive_jobs.append((chamfer_dim, '"BoreSouthChamferSize"'))
    v_chamfer = _bore_south_chamfer_volume(radius, flat_x, BORE_SOUTH_CHAMFER)
    expected -= v_chamfer
    await volume_check(adapter, "south D-bore chamfer", expected, 0.03 * v_chamfer + 0.15)

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
    face_lower, face_upper = deviations(FACE_WIDTH_BAND)
    if face_lower != -face_upper:
        raise AssertionError("the 64T face-width band must be symmetric")
    set_dimension_symmetric_tolerance(
        adapter, "GearBlank", "FaceWidth", face_upper
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreAF", *deviations(BORE_AF_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreSouthChamfer", "BoreSouthChamferSize",
        *deviations(BORE_SOUTH_CHAMFER_BAND),
    )
    await volume_check(
        adapter, "driven crank-drive gear (equations neutral)",
        expected, 0.03 * v_chamfer + 0.15,
    )

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
    # Its own band: the crank-mesh stack's tip-to-root air takes it
    # (dt_crank_drive_gear_spec).
    set_dimension_symmetric_tolerance(
        adapter, "OutsideDiaReference", "OutsideDia", OUTSIDE_DIA_TOLERANCE_MM
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Mark the five manufacturing dimensions, author their model precision
    # and stamp the drawing's title-block and gear-data properties.
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
    # The reference sketch owns printed dimensions but no geometry: hide it so
    # no assembly instance renders it (#880).  The drawing shows it per view
    # through _drawing_hidden_sketches to import those dimensions.
    blank_sketch(adapter, "OutsideDiaReference")
    return await save_simplified_part(adapter, PART_NAME, disc.tooth_features)


if __name__ == "__main__":
    sys.exit(run_build(build))
