r"""Reproduction script: crank-drive gear (book ch. 12, p. 20).

The dark steel gear at the cone set's large end, annotated "This gear
engages the crank" (p. 20): together with a pinion on the crankshaft
(`build_dt_crank_pinion.py`) it implements the book-stated 4:1 crank-to-cone
reduction (p. 16). The 64T:16T pair uses standard normal 24DP PA20 teeth.
The crank bore's configured height closes the mesh at the physical 64T
centre without moving the 48DP cone stack or its face/seat datums.

CROSSED-MESH CUT: the 64T rides the cone shaft while the straight 16T
spins about machine z. Its teeth are STRAIGHT, inclined to its axis by the
cone incline, right hand (owner ruling 2026-11-10 on #2332, option A,
superseding the true helix): each tooth space is the finite normal-24DP PA20
stock #2/55T form, cut as a straight prism along the tooth line, its centre
plane crossing the axis TOOTH_SPACE_CROSSING north of the south face
(straight_gash). Actual crossed-mesh engineering acceptance remains separate
from this CAD gate (crank_mesh_stack).

Dimensions: cad/config/dimensions.yaml ch12 crank-drive gear row +
Appendix C #9.

ATTACHMENT (owner decision C1 keyed, 2026-11-09, PR #1992): the 64T slides
onto MHA-DT-04's round land 1 and is driven by the MHA-DT-VN-71 1/16 square
key in the land's keyseat, through one broached keyway on local +X (the clock
the retired D-flat held). The round bore band is the gear-seat fit of that
land; the keyway's width and T come from cone_land_key. Its south bore entry
has a 45° chamfer on the round edge, clear of the collar's root; the bearing
annulus remains intact. Its south face butts against the MHA-DT-04 thrust
collar; the north face touches T120 in the solid cone-gear stack. The 64T
has no tooth-to-key clock requirement.

Layout: gear axis = Z through the origin, disc z = 0..FACE_WIDTH with the
SOUTH (collar) face at z = 0; a tooth is centred on +X on the pitch circle at
mid-face (the assembly's phase math references the mid-face azimuth).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_crank_drive_gear.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import _feature_by_name, name_last_feature
from _part_checks import report_mass_properties
from _part_properties import part_drawing_unit
from _paths import IN
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, blank_sketch, ensure_fully_defined, set_sketch_direct_db
from _sketch_circle import define_circle
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import (
    _set_tolerance_precision,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _simplified_part import save_simplified_part
from _gear import volume_check
from _straight_gash_gear import build_straight_gash_gear
from _part_pmi import author_part_pmi
from gear_face_band import GEAR_FACE_WIDTH_BAND
from dt_crank_drive_gear_notes import GEAR_DATA
from dt_crank_drive_gear_spec import (
    BORE_DIA_BAND,
    BORE_SOUTH_CHAMFER,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FACE_WIDTH,
    KEYWAY_T,
    KEYWAY_T_BAND,
    KEYWAY_WIDTH,
    KEYWAY_WIDTH_BAND,
    NATIVE_FLANK_BOUND_MM,
    OUTSIDE_DIA,
    OUTSIDE_DIA_TOLERANCE_MM,
    SURFACE_FINISHES,
    TEETH,
    TOOTH_SPACE,
    TOOTH_SPACE_FORM,
    UNIT,
)

_TOL_LIMIT = 3  # swTolType_e.swTolLIMIT


def _slot_in_disc_area(rho: float, half_width: float, top_x: float) -> float:
    """Area of the keyway slot {|y| <= half_width, 0 <= x <= top_x} inside a
    circle of radius ``rho`` about the axis, in mm² (exact)."""

    def chord_band(y: float) -> float:
        # Integral of sqrt(rho² - t²) for t in [-y, y].
        return y * math.sqrt(rho * rho - y * y) + rho * rho * math.asin(y / rho)

    if rho <= top_x:
        return chord_band(half_width)
    y_top = math.sqrt(rho * rho - top_x * top_x)
    if y_top >= half_width:
        return 2.0 * half_width * top_x
    return 2.0 * y_top * top_x + chord_band(half_width) - chord_band(y_top)


def _keyed_bore_area(radius: float, half_width: float, top_x: float) -> float:
    """Round bore plus the keyway's area outside it, in mm² (exact)."""
    outside = 2.0 * half_width * top_x - _slot_in_disc_area(radius, half_width, top_x)
    return math.pi * radius * radius + outside


def _bore_south_chamfer_volume(
    radius: float, half_width: float, top_x: float, leg: float
) -> float:
    """45° chamfer on the round south edge, less what the keyway already
    removed: at depth z the annulus radius..radius+leg-z outside the slot,
    Simpson quadrature in z of that exact cross-section."""

    def area_added(offset: float) -> float:
        grown = radius + offset
        annulus = math.pi * (grown * grown - radius * radius)
        in_slot = _slot_in_disc_area(grown, half_width, top_x) - _slot_in_disc_area(
            radius, half_width, top_x
        )
        return annulus - in_slot

    steps = 64
    dz = leg / steps
    total = 0.0
    for index in range(steps + 1):
        weight = 1 if index in (0, steps) else 4 if index % 2 else 2
        total += weight * area_added(leg - index * dz)
    return dz * total / 3.0


def _set_keyway_t_limits(adapter) -> None:
    """Print KeywayT as stacked limits, .4065 over .3995: the envelope of
    cone_land_key.KEYWAY_T_BAND (#2519; T MAX and the web unchanged).  As
    +/-.0035 the band read as a converted value, not an inch step (v49
    machinist review, 2 of 2 runs); the cone gear's _set_keyway_t_limits
    answered the same finding on MHA-DT-03."""
    lower, upper = deviations(KEYWAY_T_BAND)
    display, dimension = _named_dimension(adapter, "BoreProfile", "KeywayT")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = _TOL_LIMIT
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"KeywayT: SetValues rejected the limits {lower}/{upper} mm")
    if int(tolerance.Type) != _TOL_LIMIT:
        raise RuntimeError("KeywayT: LIMIT tolerance type did not persist")
    observed = (
        float(tolerance.GetMinValue()) * 1000.0,
        float(tolerance.GetMaxValue()) * 1000.0,
    )
    if any(abs(o - e) > 1e-6 for o, e in zip(observed, (lower, upper))):
        raise RuntimeError(
            f"KeywayT: limits read back {observed} mm, expected {(lower, upper)}"
        )
    _set_tolerance_precision(
        display,
        (lower, upper),
        display_unit=UNIT,
        label="KeywayT",
        places=DRAWING_PRECISION["BoreProfile"]["KeywayT"],
    )
    _telemetry.success(f"KeywayT: LIMIT {lower:+g}/{upper:+g} mm")


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
# The assembly's coaxial and gear mates select the bore axis by this name.
BORE_AXIS = "BoreAxis"

# The 64T seats on MHA-DT-04's keyed land 1.
BORE_DIAMETER = 0.375 * IN




async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # This INCH document needs explicit mm suffixes in its editable globals.
    # The face width, round bore, keyway and entry chamfer dimensions are
    # equation-driven after the full feature tree exists.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")
    await set_global(adapter, "KeywayWidth", f"{KEYWAY_WIDTH}mm")
    await set_global(adapter, "KeywayT", f"{KEYWAY_T}mm")
    await set_global(adapter, "BoreSouthChamferSize", f"{BORE_SOUTH_CHAMFER}mm")

    drive_jobs: list[tuple[str, str]] = []

    # The shared helper cuts one straight stock-form tooth space through the
    # full-tip blank, gates its volume and native flanks, then patterns it.
    disc = await build_straight_gash_gear(
        adapter, TOOTH_SPACE_FORM, TOOTH_SPACE, TEETH, flank_bound_mm=NATIVE_FLANK_BOUND_MM
    )
    volume = disc.volume

    # The shared stock-form helper leaves the base under adapter default names.
    # Name it here: the face width is a size
    # the turner sets, so it prints as a NATIVE model dimension
    # (drawing-simplicity-policy.md `How the repository implements the guidelines`), which means it must be named,
    # driven, marked and given its decimal places like any other. Driving it is
    # also the guard on the default name: a rename that resolved the wrong
    # feature would move the blank and the equation-neutral volume gate below
    # would fail loud instead of printing the depth of something else.
    _feature_by_name(adapter, "Boss-Extrude1").Name = "GearBlank"
    _telemetry.success("feature 'Boss-Extrude1' -> 'GearBlank'")
    drive_jobs += [
        (name_dimensions(adapter, "GearBlank", ["FaceWidth"])[0], '"FaceWidth"')
    ]

    # Cut one keyed bore through the finished teeth: the bore's major arc
    # through local -X, closed on +X by the keyway's two sides and top. A
    # construction witness from the far (-X) arc wall, on the axis, to the
    # keyway top's midpoint owns the native T measurement (KeywayT, ANSI
    # B17.1), as the retired D-bore's across-flat witness did, and centres
    # the keyway on +X; the top's length is KeywayWidth.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    radius = BORE_DIAMETER / 2.0
    half_width = KEYWAY_WIDTH / 2.0
    top_x = KEYWAY_T - radius
    side_x = math.sqrt(radius * radius - half_width * half_width)
    set_sketch_direct_db(adapter, True)
    arc = check(
        "keyed bore major arc",
        await adapter.add_arc(0.0, 0.0, side_x, half_width, side_x, -half_width),
    )
    lower_side = check(
        "keyway lower side",
        await adapter.add_line(side_x, -half_width, top_x, -half_width),
    )
    top = check(
        "keyway top", await adapter.add_line(top_x, -half_width, top_x, half_width)
    )
    upper_side = check(
        "keyway upper side",
        await adapter.add_line(top_x, half_width, side_x, half_width),
    )
    t_witness = check(
        "keyway T witness", await adapter.add_line(-radius, 0.0, top_x, 0.0)
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, t_witness)
    for label, first, second, relation in (
        ("bore arc centre", f"{arc}.center", "origin", "coincident"),
        ("keyway lower junction", f"{lower_side}.start", f"{arc}.end", "coincident"),
        ("keyway lower corner", f"{top}.start", f"{lower_side}.end", "coincident"),
        ("keyway upper corner", f"{upper_side}.start", f"{top}.end", "coincident"),
        ("keyway upper junction", f"{upper_side}.end", f"{arc}.start", "coincident"),
        ("vertical keyway top", top, None, "vertical"),
        ("horizontal keyway lower side", lower_side, None, "horizontal"),
        ("horizontal keyway upper side", upper_side, None, "horizontal"),
        ("horizontal T witness", t_witness, None, "horizontal"),
        ("witness on bore arc", f"{t_witness}.start", arc, "coincident"),
        ("witness on bore centre", f"{t_witness}.start", "origin", "horizontal_points"),
        ("witness at keyway top midpoint", f"{t_witness}.end", top, "midpoint"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    check(
        "bore diameter", await adapter.add_sketch_dimension(
            arc, None, "diameter", BORE_DIAMETER
        ),
    )
    bore.record("BoreDia", '"BoreDia"')
    check(
        "keyway width", await adapter.add_sketch_dimension(
            f"{top}.start", f"{top}.end", "vertical_distance", KEYWAY_WIDTH,
        ),
    )
    bore.record("KeywayWidth", '"KeywayWidth"')
    check(
        "keyway T", await adapter.add_sketch_dimension(
            f"{t_witness}.start", f"{t_witness}.end",
            "horizontal_distance", KEYWAY_T,
        ),
    )
    bore.record("KeywayT", '"KeywayT"')
    await ensure_fully_defined(adapter, "keyed bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    _verify_named_dimension(adapter, "BoreDia@BoreProfile", BORE_DIAMETER)
    _verify_named_dimension(adapter, "KeywayWidth@BoreProfile", KEYWAY_WIDTH)
    _verify_named_dimension(adapter, "KeywayT@BoreProfile", KEYWAY_T)
    check(
        "cut keyed bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 2.0)),
    )
    name_last_feature(adapter, "Bore")
    v_bore = _keyed_bore_area(radius, half_width, top_x) * FACE_WIDTH
    expected = volume - v_bore
    await volume_check(adapter, "keyed bore", expected, 0.01 * v_bore)

    # The south (z=0) round bore edge only, picked on -X away from the
    # keyway; the chamfer's cone runs out against the keyway's sides, which
    # break through it on +X. It clears MHA-DT-04's collar root so the south
    # face seats flat. The north rim stays square against T120.
    check(
        "chamfer south bore entry",
        await adapter.add_chamfer(BORE_SOUTH_CHAMFER, [[-radius, 0.0, 0.0]]),
    )
    name_last_feature(adapter, "BoreSouthChamfer")
    chamfer_dim = name_dimensions(
        adapter, "BoreSouthChamfer", ["BoreSouthChamferSize"]
    )[0]
    _verify_named_dimension(adapter, chamfer_dim, BORE_SOUTH_CHAMFER)
    drive_jobs.append((chamfer_dim, '"BoreSouthChamferSize"'))
    v_chamfer = _bore_south_chamfer_volume(radius, half_width, top_x, BORE_SOUTH_CHAMFER)
    expected -= v_chamfer
    await volume_check(adapter, "south bore chamfer", expected, 0.03 * v_chamfer + 0.15)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train). Renamed BoreAxis: the tooth cut
    # creates its own reference axes first, so the default AxisN ordinal the
    # assembly used to quote (Axis2) now names the tooth space's pivot (farm
    # run 20261110T211638308Z: '64T coaxial' landed 36.75 mm off).
    bore_axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "bore axis"
    )
    _feature_by_name(adapter, bore_axis).Name = BORE_AXIS
    _telemetry.success(f"feature {bore_axis!r} -> {BORE_AXIS!r}")

    # Apply the deferred drive equations after the whole model + a rebuild exist,
    # then re-check: each equation evaluates to the as-built value, so the
    # geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    face_lower, face_upper = deviations(GEAR_FACE_WIDTH_BAND)
    if face_lower != -face_upper:
        raise AssertionError("the 64T face-width band must be symmetric")
    # The bands are millimetres; UNIT prints them in inches. The face width's
    # authored band prints at its nominal's four places, ±.0010 (machinist
    # review); the spec's FACE_WIDTH_BAND is its limits about the model.
    set_dimension_symmetric_tolerance(
        adapter, "GearBlank", "FaceWidth", face_upper,
        places=DRAWING_PRECISION["GearBlank"]["FaceWidth"], display_unit=UNIT,
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND), display_unit=UNIT
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "KeywayWidth", *deviations(KEYWAY_WIDTH_BAND),
        display_unit=UNIT,
    )
    _set_keyway_t_limits(adapter)
    await volume_check(
        adapter, "driven crank-drive gear (equations neutral)",
        expected, 0.03 * v_chamfer + 0.15,
    )

    # The actual blank circle, as a REFERENCE sketch. The OD is the first size
    # the turner sets and the print must carry it as a model dimension, not as
    # text in the data block (drawing-simplicity-policy.md `How the repository implements the guidelines`'s "model it, even if that takes a hidden reference
    # sketch whose one driving dimension IS the value"); this sketch owns its
    # band and callout whatever recipe cuts the teeth. Construction geometry:
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
        adapter,
        "OutsideDiaReference",
        "OutsideDia",
        OUTSIDE_DIA_TOLERANCE_MM,
        display_unit=UNIT,
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
    apply_drawing_properties(adapter, PART_NAME, {"Gear Data": GEAR_DATA})
    # The reference sketch owns printed dimensions but no geometry: hide it so
    # no assembly instance renders it (#880).  The drawing shows it per view
    # through _drawing_hidden_sketches to import those dimensions.
    blank_sketch(adapter, "OutsideDiaReference")
    return await save_simplified_part(adapter, PART_NAME, disc.tooth_features)


if __name__ == "__main__":
    sys.exit(run_build(build))
