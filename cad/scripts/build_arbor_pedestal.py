r"""Reproduction script: cylinder-arbor pedestal (book ch. 13 / video 4).

Black tapered bearing post that clamps the south end of the stationary
cylinder arbor. The gears spin freely on the arbor (dimensions.yaml
ch. 13 "M6.2 keyway refutation"), so the post only holds the arbor
still. Still `t00393` / keyframe `v4_pinion_008` (engineerguy video 4)
show its true shape -- NOT the old plain green block: a black japanned
casting, a low rectangular foot flange carrying a thin strap that
tapers up to a semicircular dome around the arbor clamp bore
(base:top width ~1.2 in the frame, scaled off the 120T gear OD 62.2).

Layout: foot flange standing on the Top plane, centred at the origin
in plan (X width x Z depth); tapered strap up +Y, FLUSH with the
foot's +Z (machine-north) face so the flange extends -Z only -- the
casting is an L in side view, not an upside-down T (PR7 review item;
v4_pinion_008 shows the strap rising from one end of the foot with the
hold-down screw on the exposed flange). Dome + bore along Z at
y = BORE_HEIGHT; a O3.2 fillister-screw hole drops through the flange.
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
    IN,
    PANEL_BLACK,
    SketchDims,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
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
    DRAWING_NOTES,
    FOOT_DEPTH,
    FOOT_HEIGHT,
    FOOT_WIDTH,
    SCREW_CLEARANCE_DIA,
    SCREW_THREAD,
    STRAP_T,
    SURFACE_FINISHES,
    TOP_RADIUS,
)
from _holes import DIAMETER_TOLERANCE_MM, HoleSpec, wizard_holes

PART_NAME = "arbor-pedestal"
MATERIAL = "Gray Cast Iron"  # black japanned casting (t00393)

# Geometry comes from arbor_pedestal_spec — the drawing's single source of the
# marked dimensions — so a spec correction rebuilds the SLDPRT from the same
# values the print annotates (foot envelope, strap, dome, journal bore).
#
# STRAP_T: band local z (FOOT_DEPTH/2 - STRAP_T)..(FOOT_DEPTH/2) = -2..+8.
# Keeps the arbor's 7.5 engagement from the north face; the -Z flange carries
# the screw. Foot-screw shank O2.9 pass-through (build_foot_screw, the flange
# hold-down; its 8.0 shank reaches 3.0 into the base past this 5.0 flange):
# #4 clearance NORMAL fit (Ø3.264 = 0.1285 in, the seat wizard-table value).
SCREW_HOLE_SPEC = HoleSpec("clearance", SCREW_THREAD)
SCREW_HOLE_DIA = SCREW_CLEARANCE_DIA  # 3.264, the seat-proven cut (see the
# spec's pin rationale); the post-create assert below keeps model, note and
# drive-train assembly's foot-screw clearance assert (build_drive_train_assembly)
SCREW_Z = -5.0  # hole centre on the exposed flange, local z (machine -95.5)

BORE_RADIUS = BORE_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): foot extents, strap thickness, dome
    # radius, bore diameter + drive-height station. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 54 = 54 in). FootHeight and
    # StrapThickness feed extrude DEPTHS (feature parameters, not sketch dims),
    # so they carry no drive job; they stay declared knobs like the exemplars.
    await set_global(adapter, "FootWidth", f"{FOOT_WIDTH}mm")
    await set_global(adapter, "FootDepth", f"{FOOT_DEPTH}mm")
    await set_global(adapter, "FootHeight", f"{FOOT_HEIGHT}mm")
    await set_global(adapter, "StrapThickness", f"{STRAP_T}mm")
    await set_global(adapter, "TopRadius", f"{TOP_RADIUS}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHeight", f"{BORE_HEIGHT}mm")
    await set_global(adapter, "ScrewZ", f"{-SCREW_Z}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Foot flange on the Top plane (sketch y = global -Z): an origin-centred
    # rectangle, width along X x depth along Z, extruded up.
    foot = SketchDims()
    check("create_sketch foot", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, FOOT_WIDTH / 2.0, FOOT_DEPTH / 2.0, "foot", dims=foot,
        name_width="Width", drive_width='"FootWidth"',
        name_depth="Depth", drive_depth='"FootDepth"',
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

    # Tapered strap: an isosceles trapezoid on the Front plane, root buried in
    # the foot (bottom edge on the Top plane, y 0), flanks narrowing FootWidth
    # -> 2 x TopRadius at the bore height, mid-plane extruded StrapThickness.
    # Fully defined by: both horizontals, both width dims, the root corner
    # anchored to the origin (on-axis y 0 -> one h-dist dim), the rise dim and
    # the top corner's h-dist -- 8 coordinate constraints for 4 free vertices,
    # no redundancy (the flanks' endpoints merged at creation carry none).
    half_root = FOOT_WIDTH / 2.0
    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    bottom = check(
        "strap bottom",
        await adapter.add_line(-half_root, 0.0, half_root, 0.0),
    )
    check(
        "strap flank right",
        await adapter.add_line(half_root, 0.0, TOP_RADIUS, BORE_HEIGHT),
    )
    top = check(
        "strap top",
        await adapter.add_line(TOP_RADIUS, BORE_HEIGHT, -TOP_RADIUS, BORE_HEIGHT),
    )
    check(
        "strap flank left",
        await adapter.add_line(-TOP_RADIUS, BORE_HEIGHT, -half_root, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    for ent in (bottom, top):
        check("strap horizontal", await adapter.add_sketch_constraint(ent, None, "horizontal"))
    check(
        "dimension strap root width",
        await adapter.add_sketch_dimension(bottom, None, "linear", FOOT_WIDTH),
    )
    strap.record("StrapRootWidth", '"FootWidth"')
    await anchor_point_to_origin(
        adapter, f"{bottom}.start", -half_root, 0.0, "strap root corner"
    )
    strap.record("RootCornerX", '"FootWidth" / 2')
    check(
        "dimension strap top width",
        await adapter.add_sketch_dimension(top, None, "linear", 2.0 * TOP_RADIUS),
    )
    strap.record("StrapTopWidth", '"TopRadius" * 2')
    check(
        "dimension strap rise",
        await adapter.add_sketch_dimension(
            f"{top}.start", f"{bottom}.end", "vertical_distance", BORE_HEIGHT
        ),
    )
    strap.record("StrapRise", '"BoreHeight"')
    check(
        "dimension top corner x",
        await adapter.add_sketch_dimension(
            f"{top}.start", "origin", "horizontal_distance", TOP_RADIUS
        ),
    )
    strap.record("TopCornerX", '"TopRadius"')
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapProfile")
    drive_jobs += strap.apply(adapter, "StrapProfile")
    # L, not T: the strap band hugs the foot's +Z face (local z -2..+8), so
    # the extrude starts at an offset instead of straddling the mid-plane.
    extrude_at_offset(adapter, STRAP_T, FOOT_DEPTH / 2.0 - STRAP_T)
    name_last_feature(adapter, "Strap")
    a_trap = (FOOT_WIDTH + 2.0 * TOP_RADIUS) / 2.0 * BORE_HEIGHT
    w_at_foot_top = FOOT_WIDTH - (FOOT_WIDTH - 2.0 * TOP_RADIUS) * FOOT_HEIGHT / BORE_HEIGHT
    a_overlap = (FOOT_WIDTH + w_at_foot_top) / 2.0 * FOOT_HEIGHT
    v_strap = (a_trap - a_overlap) * STRAP_T
    volume = await volume_check(adapter, "strap", volume + v_strap, 0.005 * v_strap)

    # Dome: a full circle boss centred on the bore station; its upper half
    # stands proud of the trapezoid top (the round head in t00393), its lower
    # half is contained by the flanks (half-width sqrt(R^2 - dy^2) <= R <=
    # trapezoid half-width below the top edge), so the union adds exactly a
    # half disc. On-axis in X (x 0): centre-height dim + diameter only.
    dome = SketchDims()
    check("create_sketch dome", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_HEIGHT, TOP_RADIUS, "dome", dims=dome,
        names=("DomeX", "DomeCy", "DomeDia"),
        drives=(None, '"BoreHeight"', '"TopRadius" * 2'),
    )
    await ensure_fully_defined(adapter, "dome sketch")
    check("exit_sketch dome", await adapter.exit_sketch())
    name_last_feature(adapter, "DomeProfile")
    drive_jobs += dome.apply(adapter, "DomeProfile")
    extrude_at_offset(adapter, STRAP_T, FOOT_DEPTH / 2.0 - STRAP_T)
    name_last_feature(adapter, "Dome")
    v_dome = math.pi * TOP_RADIUS**2 / 2.0 * STRAP_T
    volume = await volume_check(adapter, "dome", volume + v_dome, 0.005 * v_dome)

    # Arbor clamp bore along Z at the drive height, through the strap. On-axis
    # in X (x 0): only the bore-height centre dim + the diameter are display
    # dims, so the "X" slot is ignored.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_HEIGHT, BORE_RADIUS, "bore", dims=bore,
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
            # Mid-plane TOTAL about the Front sketch plane: the strap band now
            # sits offset (-2..+8), so the cut spans generously past it.
            ExtrusionParameters(depth=2.0 * FOOT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * BORE_RADIUS**2 * STRAP_T
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Flange hold-down screw hole (PR7): ONE native Hole Wizard #4 clearance
    # feature (through-all along Y) through the exposed -Z flange at (x 0,
    # z SCREW_Z), drilled from the foot bottom (y=0) -- the fillister screw
    # bolts the casting to the base. The foot bottom is a clean rectangle (the
    # strap/dome/bore are all above it), so find_planar_face resolves cleanly.
    screw_cut = wizard_holes(
        adapter, SCREW_HOLE_SPEC,
        [[0.0, 0.0, SCREW_Z]],
        (0.0, -1.0, 0.0), "flange hold-down hole (#4 clearance)", name="ScrewHole",
        placement_dims=[((None, None), ("ScrewZ", '"ScrewZ"'))],
    )
    # Same constant wizard_holes corrects against, so this can never demand a
    # precision the wizard declines to deliver (the dead band -- see _holes).
    if abs(screw_cut.hole_dia_mm - SCREW_CLEARANCE_DIA) > DIAMETER_TOLERANCE_MM:
        raise RuntimeError(
            f"flange hold-down hole cut Ø{screw_cut.hole_dia_mm:.4f} != spec "
            f"SCREW_CLEARANCE_DIA Ø{SCREW_CLEARANCE_DIA} -- wizard_holes should "
            f"have forced it to within {DIAMETER_TOLERANCE_MM} mm, so either the "
            "spec pin no longer matches _holes.CLEARANCE_MM or the override "
            "write was rejected; dump the table with "
            "diagnostics/diag_hole_wizard_tables.py before touching the pin"
        )
    drive_jobs += screw_cut.placement_drive_jobs
    v_hole = math.pi * (SCREW_CLEARANCE_DIA / 2.0) ** 2 * FOOT_HEIGHT
    volume = await volume_check(adapter, "screw hole", volume - v_hole, 0.02 * v_hole)
    v_final = volume

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pedestal (equations neutral)", v_final, 0.01 * v_bore)
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND)
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
