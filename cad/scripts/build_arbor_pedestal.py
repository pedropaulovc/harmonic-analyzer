r"""Reproduction script: cylinder-arbor pedestal (book ch. 13 / video 4).

Black tapered bearing post that clamps one end of the stationary
cylinder arbor (two per machine; the north one is the same casting turned
180 about Y). The gears spin freely on the arbor (dimensions.yaml
ch. 13 "M6.2 keyway refutation"), so the post only holds the arbor
still. Still `t00393` / keyframe `v4_pinion_008` (engineerguy video 4)
show its true shape -- NOT the old plain green block: a black-finished
ferrous pedestal, likely steel plate but equally machinable from gray iron,
with a low rectangular foot flange carrying a thin strap that tapers up to a
semicircular dome around the arbor clamp bore

Layout: foot flange standing on the Top plane, centred on X in plan
(X width x Z depth); tapered strap up +Y, FLUSH with the foot's +Z
(inner) face so the flange extends -Z only -- the casting is an L in side
view, not an upside-down T (PR7 review item; v4_pinion_008 shows the strap
rising from one end of the foot with the hold-down screw on the exposed
flange). The strap band keeps local z -2..+8 about the origin; U34c grew
the foot OUTBOARD only, to an 18 ledge (local z -20..-2) centred on one
#8 close-clearance hole (ch12 p.18 img09). Dome + bore along Z at
y = BORE_HEIGHT.
The strap profile is a trapezoid + a full circle boss (its upper half
proud of the trapezoid = the dome) -- no arcs, only proven primitives
(see build_connecting_rod's head for the anchored-polygon pattern).

Dimensions: cad/config/dimensions.yaml ch. 13 "Drive supports".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_arbor_pedestal.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    _read_member,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
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
from _part_pmi import author_part_pmi
from arbor_pedestal_spec import (
    BORE_DIA,
    BORE_DIA_BAND,
    BORE_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FOOT_DEPTH,
    FOOT_HEIGHT,
    FOOT_NEAR_Z,
    FOOT_WIDTH,
    REFERENCE_SKETCHES,
    SCREW_HOLE_DIA,
    SCREW_HOLE_SPEC,
    SCREW_Z,
    SET_SCREW_HOLE_SPEC,
    SET_SCREW_Z,
    STRAP_INNER_Z,
    STRAP_ROOT_Z,
    STRAP_T,
    SURFACE_FINISHES,
    TAPER_TANGENT_X,
    TAPER_TANGENT_Y,
    TOP_RADIUS,
)
from _hole_spec import blind_cut_dia_mm
from _visibility import blank_reference_geometry
from _holes import (
    DIAMETER_TOLERANCE_MM,
    cross_hole_volume_mm3,
    wizard_hole_on_cylinder,
    wizard_holes,
)
import _telemetry

PART_NAME = "arbor-pedestal"
MATERIAL = "Plain Carbon Steel"  # photo-likely steel; gray iron remains permitted
CAD_APPEARANCE = (0.28, 0.28, 0.30)  # neutral charcoal keeps drawing edges legible

# Geometry comes from arbor_pedestal_spec — the drawing's single source of the
# marked dimensions — so a spec correction rebuilds the SLDPRT from the same
# values the print annotates (foot envelope, strap, dome, journal bore).
#
# STRAP_T: band local z STRAP_ROOT_Z..STRAP_INNER_Z = -2..+8, unchanged by
# U34c. The -Z ledge carries a #8 close-clearance hole for the MHA-143
# #8-32 x 3/4 fillister (McMaster 90280A197); the base seat under it is
# transfer-punched through this hole at assembly.
# SCREW_Z (spec): hole centre on the ledge, local z -11.
# SET_SCREW_Z (spec): the #4-40 apex tap for the MHA-147 set screw (#743),
# radial through the crown at the strap's mid-depth, local z +3.

BORE_RADIUS = BORE_DIA / 2.0

# The five drawing-reference lines (arbor_pedestal_spec.REFERENCE_SKETCHES):
# (sketch, plane, dimension, start, end, orientation, value, drives). Points
# are sketch coordinates -- the Top plane's sketch y is machine -Z, the Front
# plane's is machine +Y. Every line lies on the part outline, so the view
# that shows its sketch prints no extra line, and each starts on a FEATURE
# (policy rule 7): the far face / strap root for the depths, the west side
# face for the lateral locations. ``drives`` binds, in creation order, the
# value dimension and then the start point's origin anchors (two for a
# general point, one for a point on a sketch axis) to the part's globals, so
# a global edit moves the line with the geometry it restates.
REFERENCE_LINES = (
    (
        "StrapDepthReference",
        "Top",
        "StrapDepth",
        (FOOT_WIDTH / 2.0, -STRAP_ROOT_Z),
        (FOOT_WIDTH / 2.0, -STRAP_INNER_Z),
        "vertical",
        STRAP_T,
        ('"StrapThickness"', '"FootWidth" / 2', '"StrapThickness" - "StrapInnerZ"'),
    ),
    (
        "HoldDownReference",
        "Top",
        "HoldDownLocation",
        (-FOOT_WIDTH / 2.0, -STRAP_INNER_Z),
        (-FOOT_WIDTH / 2.0, -SCREW_Z),
        "vertical",
        STRAP_INNER_Z - SCREW_Z,
        ('"StrapInnerZ" + "ScrewZ"', '"FootWidth" / 2', '"StrapInnerZ"'),
    ),
    (
        "HoleLateralReference",
        "Top",
        "HoleLateral",
        (-FOOT_WIDTH / 2.0, -FOOT_NEAR_Z),
        (0.0, -FOOT_NEAR_Z),
        "horizontal",
        FOOT_WIDTH / 2.0,
        ('"FootWidth" / 2', '"FootWidth" / 2', '"FootDepth" - "StrapInnerZ"'),
    ),
    (
        "BoreLateralReference",
        "Front",
        "BoreLateral",
        (-FOOT_WIDTH / 2.0, 0.0),
        (0.0, 0.0),
        "horizontal",
        FOOT_WIDTH / 2.0,
        ('"FootWidth" / 2', '"FootWidth" / 2'),
    ),
    (
        "SetScrewReference",
        "Top",
        "SetScrewLocation",
        (FOOT_WIDTH / 2.0, -STRAP_INNER_Z),
        (FOOT_WIDTH / 2.0, -SET_SCREW_Z),
        "vertical",
        STRAP_INNER_Z - SET_SCREW_Z,
        ('"StrapInnerZ" - "SetScrewZ"', '"FootWidth" / 2', '"StrapInnerZ"'),
    ),
)
if tuple(row[0] for row in REFERENCE_LINES) != REFERENCE_SKETCHES:
    raise AssertionError("REFERENCE_LINES and REFERENCE_SKETCHES disagree")


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry.

    ``ConstructionGeometry`` is declared on the base ISketchSegment, not the
    derived ISketchLine the entity registry binds -- rebind before the set.
    """
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _reference_line(
    adapter, sketch, plane, dimension, start, end, orientation, value, drives
) -> list[tuple[str, str]]:
    """One hidden-reference sketch: a construction line whose driving
    dimension IS ``value``; returns its deferred drive jobs."""
    check(f"create_sketch {sketch}", await adapter.create_sketch(plane))
    # Direct-to-DB: the line lies on an outline station and runs along a
    # sketch axis direction, so creation-time inference would snap in the
    # relations added below and over-define the sketch.
    set_sketch_direct_db(adapter, True)
    line = check(f"{sketch} line", await adapter.add_line(*start, *end))
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, line)
    check(
        f"{sketch} {orientation}",
        await adapter.add_sketch_constraint(line, None, orientation),
    )
    await dimension_between(
        adapter, f"{line}.start", f"{line}.end", f"{orientation}_distance", value, sketch
    )
    await anchor_point_to_origin(adapter, f"{line}.start", *start, sketch)
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    names = [dimension, *(f"{dimension}Anchor{i}" for i in range(1, len(drives)))]
    full = name_dimensions(adapter, sketch, names)
    measured = float(
        _early_bound(adapter.currentModel.Parameter(full[0]), "IDimension").SystemValue
    ) * 1000.0
    if abs(measured - value) > 1e-6:
        raise RuntimeError(f"{full[0]} measures {measured:g} mm, expected {value:g} mm")
    return list(zip(full, drives, strict=True))


@_telemetry.traced("appearance.hide_reference_sketches")
def _hide_reference_sketches(adapter) -> None:
    """Blank the drawing-reference sketches and prove each one reads hidden."""
    for name in REFERENCE_SKETCHES:
        blank_sketch(adapter, name)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    shown = {
        name: visible
        for name in REFERENCE_SKETCHES
        # swVisibilityState_e: 1 hidden
        if (visible := int(_read_member(part.FeatureByName(name), "Visible"))) != 1
    }
    if shown:
        raise RuntimeError(f"reference sketches still visible after blanking: {shown}")
    _telemetry.event(
        "part.reference_sketches_hidden",
        sketches=", ".join(REFERENCE_SKETCHES),
        count=len(REFERENCE_SKETCHES),
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): foot extents, strap thickness, dome
    # radius, bore diameter + drive-height station. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 54 = 54 in). FootHeight and
    # StrapThickness feed extrude DEPTHS (feature parameters, not sketch dims),
    # so they carry no drive job; they stay declared knobs like the exemplars.
    await set_global(adapter, "FootWidth", f"{FOOT_WIDTH}mm")
    await set_global(adapter, "FootDepth", f"{FOOT_DEPTH}mm")
    await set_global(adapter, "StrapInnerZ", f"{STRAP_INNER_Z}mm")
    await set_global(adapter, "FootHeight", f"{FOOT_HEIGHT}mm")
    await set_global(adapter, "StrapThickness", f"{STRAP_T}mm")
    await set_global(adapter, "TopRadius", f"{TOP_RADIUS}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHeight", f"{BORE_HEIGHT}mm")
    await set_global(adapter, "TangentX", f"{TAPER_TANGENT_X}mm")
    await set_global(adapter, "TangentY", f"{TAPER_TANGENT_Y}mm")
    await set_global(adapter, "ScrewZ", f"{-SCREW_Z}mm")
    await set_global(adapter, "SetScrewZ", f"{SET_SCREW_Z}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Foot flange on the Top plane (sketch y = global -Z): X-centred, its far
    # edge on the strap inner face (z +8) and running 28 outboard to z -20, so
    # the rectangle is anchored at its inner-west corner rather than centred.
    foot = SketchDims()
    check("create_sketch foot", await adapter.create_sketch("Top"))
    half_width = FOOT_WIDTH / 2.0
    foot_points = [
        (-half_width, -STRAP_INNER_Z),
        (half_width, -STRAP_INNER_Z),
        (half_width, -FOOT_NEAR_Z),
        (-half_width, -FOOT_NEAR_Z),
    ]
    foot_lines = await add_line_chain(adapter, foot_points)
    await define_rectilinear_chain(
        adapter,
        foot_lines,
        foot_points,
        label="foot",
        dims=foot,
        names=["Width", "Depth", "FootWest", "FootInner"],
        drives=['"FootWidth"', '"FootDepth"', '"FootWidth" / 2', '"StrapInnerZ"'],
    )
    await ensure_fully_defined(adapter, "foot sketch")
    check("exit_sketch foot", await adapter.exit_sketch())
    name_last_feature(adapter, "FootProfile")
    drive_jobs += foot.apply(adapter, "FootProfile")
    check(
        "extrude foot",
        await adapter.create_extrusion(ExtrusionParameters(depth=FOOT_HEIGHT)),
    )
    name_last_feature(adapter, "Foot")
    # Name the extrude DEPTH so the foot flange height is a markable drawing dim.
    foot_ht_dim = name_dimensions(adapter, "Foot", ["FootHt"])
    drive_jobs += [(foot_ht_dim[0], '"FootHeight"')]
    v_foot = FOOT_WIDTH * FOOT_DEPTH * FOOT_HEIGHT
    volume = await volume_check(adapter, "foot", v_foot, 0.005 * v_foot)

    # True tangent strap: the sides start flush with the 24 mm foot and meet
    # the concentric R10 crown without a tolerance-sized step or visual kink.
    half_root = FOOT_WIDTH / 2.0
    half_tangent = TAPER_TANGENT_X
    tangent_y = TAPER_TANGENT_Y
    strap_rise = tangent_y - FOOT_HEIGHT
    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    bottom = check(
        "strap bottom",
        await adapter.add_line(-half_root, FOOT_HEIGHT, half_root, FOOT_HEIGHT),
    )
    check(
        "strap flank right",
        await adapter.add_line(half_root, FOOT_HEIGHT, half_tangent, tangent_y),
    )
    top = check(
        "strap tangent chord",
        await adapter.add_line(half_tangent, tangent_y, -half_tangent, tangent_y),
    )
    check(
        "strap flank left",
        await adapter.add_line(-half_tangent, tangent_y, -half_root, FOOT_HEIGHT),
    )
    set_sketch_direct_db(adapter, False)
    for ent in (bottom, top):
        check(
            "strap horizontal",
            await adapter.add_sketch_constraint(ent, None, "horizontal"),
        )
    check(
        "dimension strap root width",
        await adapter.add_sketch_dimension(bottom, None, "linear", FOOT_WIDTH),
    )
    strap.record("StrapRootWidth", '"FootWidth"')
    await anchor_point_to_origin(
        adapter, f"{bottom}.start", -half_root, FOOT_HEIGHT, "strap root corner"
    )
    strap.record("RootCornerX", '"FootWidth" / 2')
    strap.record("RootCornerY", '"FootHeight"')
    check(
        "dimension strap tangent chord",
        await adapter.add_sketch_dimension(top, None, "linear", 2.0 * half_tangent),
    )
    strap.record("StrapTangentChord", '"TangentX" * 2')
    check(
        "dimension strap rise",
        await adapter.add_sketch_dimension(
            f"{top}.start", f"{bottom}.end", "vertical_distance", strap_rise
        ),
    )
    strap.record("StrapRise", '"TangentY" - "FootHeight"')
    check(
        "dimension tangent point x",
        await adapter.add_sketch_dimension(
            f"{top}.start", "origin", "horizontal_distance", half_tangent
        ),
    )
    strap.record("TangentX", '"TangentX"')
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapProfile")
    drive_jobs += strap.apply(adapter, "StrapProfile")
    # L, not T: the strap band hugs the foot's +Z face (local z -2..+8), so
    # the extrude starts at an offset instead of straddling the mid-plane.
    extrude_at_offset(adapter, STRAP_T, STRAP_ROOT_Z)
    name_last_feature(adapter, "Strap")
    a_strap = (FOOT_WIDTH + 2.0 * half_tangent) / 2.0 * strap_rise
    v_strap = a_strap * STRAP_T
    volume = await volume_check(adapter, "strap", volume + v_strap, 0.005 * v_strap)

    # Dome: a full circle boss centred on the bore station. The tangent strap
    # already contains the circle below its tangent chord, so the union adds
    # only the circular cap above that chord.
    dome = SketchDims()
    check("create_sketch dome", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        BORE_HEIGHT,
        TOP_RADIUS,
        "dome",
        dims=dome,
        names=("DomeX", "DomeCy", "DomeDia"),
        drives=(None, '"BoreHeight"', '"TopRadius" * 2'),
    )
    await ensure_fully_defined(adapter, "dome sketch")
    check("exit_sketch dome", await adapter.exit_sketch())
    name_last_feature(adapter, "DomeProfile")
    drive_jobs += dome.apply(adapter, "DomeProfile")
    extrude_at_offset(adapter, STRAP_T, STRAP_ROOT_Z)
    name_last_feature(adapter, "Dome")
    chord_offset = tangent_y - BORE_HEIGHT
    cap_area = TOP_RADIUS**2 * math.acos(chord_offset / TOP_RADIUS) - (
        chord_offset * math.sqrt(TOP_RADIUS**2 - chord_offset**2)
    )
    v_dome = cap_area * STRAP_T
    volume = await volume_check(adapter, "dome", volume + v_dome, 0.005 * v_dome)

    # Arbor clamp bore along Z at the drive height, through the strap. On-axis
    # in X (x 0): only the bore-height centre dim + the diameter are display
    # dims, so the "X" slot is ignored.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        BORE_HEIGHT,
        BORE_RADIUS,
        "bore",
        dims=bore,
        names=("BoreX", "BoreHeight", "BoreDia"),
        drives=(None, '"BoreHeight"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            # Mid-plane TOTAL about the Front sketch plane: the strap band
            # sits offset (-2..+8), so the cut spans generously past it.
            ExtrusionParameters(depth=2.0 * FOOT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * BORE_RADIUS**2 * STRAP_T
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Flange hold-down screw hole (U34c): ONE native Hole Wizard #8 close
    # clearance feature (through-all along Y) through the exposed -Z ledge at
    # (x 0, z SCREW_Z), drilled from the foot bottom (y=0) -- the MHA-143
    # fillister bolts the casting to the base. The foot bottom is a clean rectangle (the
    # strap/dome/bore are all above it), so find_planar_face resolves cleanly.
    screw_cut = wizard_holes(
        adapter,
        SCREW_HOLE_SPEC,
        [[0.0, 0.0, SCREW_Z]],
        (0.0, -1.0, 0.0),
        "flange hold-down hole (#8 close clearance)",
        name="ScrewHole",
        placement_dims=[((None, None), ("ScrewZ", '"ScrewZ"'))],
    )
    # Same constant wizard_holes corrects against, so this can never demand a
    # precision the wizard declines to deliver (the dead band -- see _holes).
    if abs(screw_cut.hole_dia_mm - SCREW_HOLE_DIA) > DIAMETER_TOLERANCE_MM:
        raise RuntimeError(
            f"flange hold-down hole cut Ø{screw_cut.hole_dia_mm:.4f} != "
            f"part-owned spec Ø{SCREW_HOLE_DIA}; wizard_holes should have forced "
            f"it to within {DIAMETER_TOLERANCE_MM} mm"
        )
    drive_jobs += screw_cut.placement_drive_jobs
    v_hole = math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * FOOT_HEIGHT
    volume = await volume_check(adapter, "screw hole", volume - v_hole, 0.02 * v_hole)

    # Apex set-screw tap (#743, user ruling Q3): ONE native #4-40 tapped hole
    # drilled radially down through the crown at the strap's mid-depth and
    # stopped at the next surface -- the arbor bore -- so it never runs on
    # into the strap below. The station plane carries the axial position;
    # Right Plane clocks it to the apex.
    check(
        "create_plane SetScrewStationPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=SET_SCREW_Z
            )
        ),
    )
    name_last_feature(adapter, "SetScrewStationPlane")
    station_dim = name_dimensions(adapter, "SetScrewStationPlane", ["SetScrewZ"])
    drive_jobs += [(station_dim[0], '"SetScrewZ"')]
    wizard_hole_on_cylinder(
        adapter,
        SET_SCREW_HOLE_SPEC,
        [0.0, BORE_HEIGHT + TOP_RADIUS, SET_SCREW_Z],
        "apex set-screw tap (#4-40)",
        name="SetScrewTap",
        point_planes=("SetScrewStationPlane", "Right Plane"),
    )
    blank_reference_geometry(adapter, (("SetScrewStationPlane", "PLANE"),))
    # The tap drill removes the crown wall between the crown and the bore:
    # half of each perpendicular cross-hole volume, crown minus bore.
    tap_dia = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC)
    v_tap = (
        cross_hole_volume_mm3(tap_dia, 2.0 * TOP_RADIUS)
        - cross_hole_volume_mm3(tap_dia, BORE_DIA)
    ) / 2.0
    volume = await volume_check(adapter, "apex set-screw tap", volume - v_tap, 0.03 * v_tap)
    v_final = volume

    for row in REFERENCE_LINES:
        drive_jobs += await _reference_line(adapter, *row)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pedestal (equations neutral)", v_final, 0.01 * v_bore
    )
    _hide_reference_sketches(adapter)
    # Decimal places are the tolerance statement, so the PART carries them
    # (policy rule 2); the drawing reads them back instead of rewriting them.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND)
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CAD_APPEARANCE)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
