r"""Reproduction script: connecting rod (book ch. 13 pp. 22-25 / ch. 14 p. 29; 20 used).

Black rough-finished rod converting each cam's rotation into the rocker
arm's see-saw: a full ring (strap) riding the Ø30.6 eccentric cam (cast
integral with each cylinder gear), a thin flat shank, and a rounded
flat-topped BLOCK head (the bright square tops of the ch14 end views) pinned (Ø2)
to the rocker arm's rod-pin hole near the arm's rod-side tip. Centre
distance 163.10103: the rod hangs PLUMB with the arm LEVEL after the fixed-post
photos show every rod dropping vertically from the arm tip onto its cam,
the ch14 end views show the 0-crank tip row dead level (cos-mode home =
top of stroke, cam lobe UP), so the pin (127.37 out from the mid-seesaw
pivot) sits directly above the phased lobe centre at machine
(-54.474, 99.155) and the rod length closes that vertical link. The head
is 15 tall (top-to-shoulder), 5 wide, flat top 2.4 above the pin, the 8
shank stepping IN to it (2026-09-02: the ch14 p.28 end views show a narrow
bright square top on every rod, ~3x taller than wide, and ch15 p.33 shows
the blocks hanging below the bar feet). It is 2.9 thick -- the most the
arm-to-arm gap it hangs in allows -- beside the arm inside the 7.06 pitch; the M2 "thick stepped tip
blocks" read of p.29 was amplitude-bar feet, not these rods.

Dimensions: cad/DIMENSIONS.md "Chapter 13 - Connecting rods" - centre
distance derived (high), ring bore derived from the cam OD + confirmed on
the p.25 overlay (med), head proportions photo-scaled vs the 16 mm callout
(med), everything else photo-scaled (low).

Layout: ring centre at the origin, shank rising +Y to the head;
thicknesses extruded mid-plane in Z. Build order matters: ring disc,
shank and head are bossed first, then the bore is cut so the strap
opening also trims the shank sliver that dips into it.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_connecting_rod.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _holes import HoleSpec, wizard_holes
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from connecting_rod_notes import DRAWING_NOTES, ISOMETRIC_VIEW_NOTE
from connecting_rod_notes import DRAWING_DIMENSIONS
from connecting_rod_spec import (
    CENTER_DISTANCE,
    HEAD_CROWN_ABOVE_PIN,
    HEAD_HEIGHT,
    HEAD_THICKNESS,
    HEAD_WIDTH,
    RING_BORE_DIA,
    RING_BORE_DIA_BAND,
    RING_THICKNESS,
    RING_WALL,
    SHANK_THICKNESS,
    SHANK_WIDTH,
    SURFACE_FINISHES,
)

import _telemetry

PART_NAME = "connecting-rod"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

# Cam ring centre -> rocker pin, VERTICAL rod: the
# pin rides the arm's rod-pin hole 133.067 out from the pivot -- directly
# above the phased cam LOBE (installed machine centre (-60.167, 99.155) =
# drum (-60.394, 90.518) + ECC 8.64 rotated by the +1.5 deg tooth phase,
# lobe UP at the cos-mode home; the Ry180 axial flip preserves local +Y;
# ch30 photos + GT rocker-corner triangulation put the arm's rod-side end over
# the drum). Solved so the rocker rests LEVEL (arm tilt 0 -- the ch14 end views
# show the 0-crank tip row flat at the TOP of the stroke) with the rod plumb
# (rod tilt 0 by construction). Supersedes 144.75, the same closure at the
# pre-ROM-fit lobe-down phase and -7.82 deg tilt. build_channel_assembly
# imports this as ROD_C2C (imported, NOT copied). Nominal geometry lives in
# connecting_rod_spec so the part, channel and drawing move as one recipe.
# Block head: flat top, vertical cheeks, angled shoulders stepping the 8
# shank IN to the 5 block (2026-09-02 end-view re-derive). The pin sits HIGH
# in the head / LOW in the arm (top only 2.4 above the pin), so the block
# hangs ~12.6 below the pin beside the arm tip.
HEAD_SHOULDER_RISE = 1.2  # shoulder step height (width 8 -> 5)
# rocker-arm rod-end pin hole (ch14): was Ø2.0 drill, now #47 (Ø1.994) native
# Hole Wizard feature; diameter is imported from connecting_rod_spec.
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > any local thickness

RING_OUTER_RADIUS = RING_BORE_DIA / 2.0 + RING_WALL  # 20.4
SHANK_START_Y = RING_BORE_DIA / 2.0 - 0.5  # overlaps the strap annulus
HEAD_TOP_Y = CENTER_DISTANCE + HEAD_CROWN_ABOVE_PIN
HEAD_START_Y = HEAD_TOP_Y - HEAD_HEIGHT
SHOULDER_TOP_Y = HEAD_START_Y + HEAD_SHOULDER_RISE


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations) for every module constant; derived spans
    # (ring outer radius, the shank/block start heights) are equations of those
    # primitives, so a knob edit keeps the strap-to-pin geometry consistent. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 127 = 127 in,
    # blowing the part up 25.4x).
    await set_global(adapter, "CenterDistance", f"{CENTER_DISTANCE}mm")
    await set_global(adapter, "RingBoreDia", f"{RING_BORE_DIA}mm")
    await set_global(adapter, "RingWall", f"{RING_WALL}mm")
    await set_global(adapter, "RingThickness", f"{RING_THICKNESS}mm")
    await set_global(adapter, "ShankWidth", f"{SHANK_WIDTH}mm")
    await set_global(adapter, "ShankThickness", f"{SHANK_THICKNESS}mm")
    await set_global(adapter, "HeadWidth", f"{HEAD_WIDTH}mm")
    await set_global(adapter, "HeadHeight", f"{HEAD_HEIGHT}mm")
    await set_global(adapter, "HeadCrownAbovePin", f"{HEAD_CROWN_ABOVE_PIN}mm")
    await set_global(adapter, "HeadShoulderRise", f"{HEAD_SHOULDER_RISE}mm")
    await set_global(adapter, "HeadThickness", f"{HEAD_THICKNESS}mm")
    # (The old PinHoleDia knob is gone: the rocker pin hole is now a native Hole
    # Wizard #47 feature whose diameter comes from the drill standard.)
    await set_global(adapter, "RingOuterRadius", '"RingBoreDia" / 2 + "RingWall"')
    await set_global(adapter, "ShankStartY", '"RingBoreDia" / 2 - 0.5mm')
    await set_global(
        adapter, "HeadStartY",
        '"CenterDistance" + "HeadCrownAbovePin" - "HeadHeight"',
    )
    await set_global(
        adapter, "HeadTopY",
        '"CenterDistance" + "HeadCrownAbovePin"',
    )

    # Each sketch records its dim names + drive equations into a per-sketch
    # SketchDims in helper emission order; the drives are collected and applied in
    # one deferred batch at the end (every target resolves against the finished
    # model).
    drive_jobs: list[tuple[str, str]] = []

    # Ring disc (bore is cut last so it also trims the shank sliver). On-axis
    # circle: only the diameter is a dim (centre is a coincident relation).
    ring_disc = SketchDims()
    check("create_sketch ring disc", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, RING_OUTER_RADIUS, "ring outer", dims=ring_disc,
        names=("RingCx", "RingCz", "RingOuterDia"),
        drives=(None, None, '2 * "RingOuterRadius"'),
    )
    await ensure_fully_defined(adapter, "ring disc sketch")
    check("exit_sketch ring disc", await adapter.exit_sketch())
    name_last_feature(adapter, "RingDiscProfile")
    drive_jobs += ring_disc.apply(adapter, "RingDiscProfile")
    check(
        "extrude ring disc",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RingDisc")

    # Shank: flat bar from the strap up to the head's shoulder root. Rectilinear
    # chain emits width, length, then the corner anchor (x, z) -- the corner sits
    # at (-ShankWidth/2, ShankStartY); the anchor X dim is the unsigned half-width.
    shank_sd = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    shank_rect = [
        (-SHANK_WIDTH / 2.0, SHANK_START_Y),
        (SHANK_WIDTH / 2.0, SHANK_START_Y),
        (SHANK_WIDTH / 2.0, HEAD_START_Y),
        (-SHANK_WIDTH / 2.0, HEAD_START_Y),
    ]
    shank = await add_line_chain(adapter, shank_rect)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter, shank, shank_rect, label="shank", dims=shank_sd,
        names=["ShankWidthDim", "ShankLength", "ShankCornerX", "ShankCornerZ"],
        drives=['"ShankWidth"', '"HeadStartY" - "ShankStartY"',
                '"ShankWidth" / 2', '"ShankStartY"'],
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank_sd.apply(adapter, "ShankProfile")
    check(
        "extrude shank",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SHANK_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Shank")

    # Block head, pinned beside the rocker arm at assembly: angled shoulders
    # step the 8 shank IN to the 5-wide cheeks, vertical cheeks, and a FLAT
    # top (2026-09-02: the ch14 end views' bright square tops).
    # Dim EMISSION ORDER (each recorded as its display dim is created): shoulder
    # width (= ShankWidth), the shoulder-root corner anchor (X half-width, then
    # Z = HeadStartY), the top's height, the two shoulder rises, the two cheek
    # half-width offsets. Bottom horizontal + cheek verticals + top horizontal
    # are RELATIONS, not dims -- exactly 12 coordinate constraints for the 6
    # free vertices, no redundancy.
    head_sd = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    hw, sw = HEAD_WIDTH / 2.0, SHANK_WIDTH / 2.0
    head_bottom = check(
        "head bottom",
        await adapter.add_line(-sw, HEAD_START_Y, sw, HEAD_START_Y),
    )
    head_sh_r = check(
        "head shoulder right",
        await adapter.add_line(sw, HEAD_START_Y, hw, SHOULDER_TOP_Y),
    )
    head_cheek_r = check(
        "head cheek right",
        await adapter.add_line(hw, SHOULDER_TOP_Y, hw, HEAD_TOP_Y),
    )
    head_top = check(
        "head top",
        await adapter.add_line(hw, HEAD_TOP_Y, -hw, HEAD_TOP_Y),
    )
    head_cheek_l = check(
        "head cheek left",
        await adapter.add_line(-hw, HEAD_TOP_Y, -hw, SHOULDER_TOP_Y),
    )
    check(
        "head shoulder left",
        await adapter.add_line(-hw, SHOULDER_TOP_Y, -sw, HEAD_START_Y),
    )
    set_sketch_direct_db(adapter, False)
    for ent, relation in (
        (head_bottom, "horizontal"),
        (head_cheek_r, "vertical"),
        (head_cheek_l, "vertical"),
        (head_top, "horizontal"),
    ):
        check(f"head {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check(
        "dimension head bottom width",
        await adapter.add_sketch_dimension(head_bottom, None, "linear", SHANK_WIDTH),
    )
    head_sd.record("HeadBottomWidth", '"ShankWidth"')
    await anchor_point_to_origin(
        adapter, f"{head_bottom}.start", -sw, HEAD_START_Y, "head shoulder root"
    )
    head_sd.record("HeadAnchorX", '"ShankWidth" / 2')
    head_sd.record("HeadAnchorZ", '"HeadStartY"')
    check(
        "dimension head top height",
        await adapter.add_sketch_dimension(
            f"{head_top}.start", "origin", "vertical_distance", HEAD_TOP_Y
        ),
    )
    head_sd.record("HeadTopYDim", '"HeadTopY"')
    check(
        "dimension shoulder rise right",
        await adapter.add_sketch_dimension(
            f"{head_sh_r}.end", f"{head_bottom}.end", "vertical_distance",
            HEAD_SHOULDER_RISE,
        ),
    )
    head_sd.record("HeadShoulderRiseR", '"HeadShoulderRise"')
    check(
        "dimension shoulder rise left",
        await adapter.add_sketch_dimension(
            f"{head_cheek_l}.end", f"{head_bottom}.start", "vertical_distance",
            HEAD_SHOULDER_RISE,
        ),
    )
    head_sd.record("HeadShoulderRiseL", '"HeadShoulderRise"')
    check(
        "dimension cheek right x",
        await adapter.add_sketch_dimension(
            f"{head_cheek_r}.start", "origin", "horizontal_distance", hw
        ),
    )
    head_sd.record("HeadCheekRX", '"HeadWidth" / 2')
    check(
        "dimension cheek left x",
        await adapter.add_sketch_dimension(
            f"{head_cheek_l}.start", "origin", "horizontal_distance", hw
        ),
    )
    head_sd.record("HeadCheekLX", '"HeadWidth" / 2')
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head_sd.apply(adapter, "HeadProfile")
    check(
        "extrude head",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HEAD_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Head")
    res = await adapter.get_mass_properties()
    _telemetry.info(f"volume after bosses: {res.data.volume:.1f} mm^3")
    # disc ~3922 + shank ~2467 + head ~226 (shoulder trapezoid 7.8 + block
    # 69.0 = 76.8 mm^2 x 2.9) - overlap; Phase 3 rebuild confirms

    # Strap bore - rides the eccentric cam. On-axis circle: diameter only.
    bore_sd = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, RING_BORE_DIA / 2.0, "strap bore", dims=bore_sd,
        names=("StrapBoreCx", "StrapBoreCz", "StrapBoreDia"),
        drives=(None, None, '"RingBoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapBoreProfile")
    drive_jobs += bore_sd.apply(adapter, "StrapBoreProfile")
    check(
        "cut strap bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "StrapBore")

    # Rocker pin hole through the head (high in the crown, 2.4 below the crown
    # top): was a plain Ø2.0 cut, now a native Hole Wizard #47 number drill
    # (Ø1.994) at (0, CENTER_DISTANCE) drilled +Z through the 2.5 mm head
    # (memory/fastener-policy-us-customary). Through-all is geometrically
    # identical to the old mid-plane both-directions cut.
    pin_cut = wizard_holes(
        adapter,
        HoleSpec("drilled_number", "#47"),
        [[0.0, CENTER_DISTANCE, HEAD_THICKNESS / 2.0]],
        (0.0, 0.0, 1.0),
        "rocker pin hole (#47)",
        name="PinHole",
        placement_dims=[((None, None), ("PinCz", '"CenterDistance"'))],
    )
    drive_jobs += pin_cut.placement_drive_jobs
    res = await adapter.get_mass_properties()
    v_built = float(res.data.volume)
    _telemetry.info(f"volume after cuts: {v_built:.1f} mm^3")
    # bore now -2234 (r 15.4 x 3) - sliver - pin; Phase 3 rebuild confirms

    # Named bore axes for assembly mates (view-independent name selection):
    # Axis1 = strap bore on the cam (origin), Axis2 = rocker pin bore (0, 147.67).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "strap bore")
    await name_bore_axis(
        adapter,
        "Right Plane",
        0.0,
        "Top Plane",
        CENTER_DISTANCE,
        "rod pin bore",
        drive_b='"CenterDistance"',
        drive_jobs=drive_jobs,
    )

    # Apply the deferred drive equations after the whole model + a rebuild exists,
    # so every target resolves. Each equation evaluates to the as-built value (the
    # rod's volume has no tidy closed form, so the neutrality gate asserts the
    # post-drive volume equals the captured as-built volume): geometry must not
    # move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven connecting rod (equations neutral)", v_built, 0.001 * v_built
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "StrapBoreProfile",
        "StrapBoreDia",
        *deviations(RING_BORE_DIA_BAND),
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number", "Material Specification", "Finish", "Quantity",
            "Manufacturing Notes", "Isometric View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
