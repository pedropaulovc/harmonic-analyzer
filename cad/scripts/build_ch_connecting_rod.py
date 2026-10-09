r"""Reproduction script: connecting rod (book ch. 13 pp. 22-25 / ch. 14 p. 29; 20 used).

Black rod machined from 1018 low-carbon steel plate, converting each cam's
rotation into the rocker arm's see-saw: a full ring (strap) riding the Ø30.6
eccentric cam (cast integral with each cylinder gear), a thin flat shank, and a
U-shaped FORK (clevis; the Y-shaped upper end of the ch14 fan photo) whose two
tines straddle the rocker arm's 2.500 strap and carry the peened pivot pin
(MHA-CH-010, ch_rod_pivot_pin_spec) through the arm's rod-pin hole near its
rod-side tip. Centre distance 163.10103: the rod hangs PLUMB with the arm
LEVEL after the fixed-post photos show every rod dropping vertically from the
arm tip onto its cam, the ch14 end views show the 0-crank tip row dead level
(cos-mode home = top of stroke, cam lobe UP), so the pin (127.37 out from the
mid-seesaw pivot) sits directly above the phased lobe centre at machine
(-54.474, 99.155) and the rod length closes that vertical link.

The rod is FLAT: ring, shank and fork share one mid-plane, which is the cam
plane and the arm plane (rocker_bank_layout.ARM_MID_DZ = CAM_MID_DZ), so the
arm runs centred in the fork slot. The fork is 10 wide with a full-round
crown on the pin, 6.075 +/-0.05 over the tines with a 2.625 +0.127/0 slot
(Main ruling 2026-10, option b): each inter-arm gap holds one tine of each
neighbouring rod, so both are 3-place model bands. Peening the pin into
countersinks on both tine faces is a RECONSTRUCTION choice (issue #746): the
photos show two rod cheeks round each rocker, not the original fastener.

Dimensions: cad/config/dimensions.yaml "Chapter 13" rod rows - centre distance
derived (high), ring bore derived from the cam OD + confirmed on the p.25
overlay (med), fork proportions photo-scaled vs the 16 mm arm-depth callout
and sized to the joint budget (ch_rod_pivot_pin_spec), everything else
photo-scaled (low).

Layout: ring centre at the origin, shank rising +Y to the fork; thicknesses
extruded mid-plane in Z. Build order matters: ring disc, shank and fork are
bossed first, the slot is cut through the fork, then the bore is cut so the
strap opening also trims the shank sliver that dips into it.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_connecting_rod.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    name_dimensions,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _hole_spec import blind_cut_dia_mm
from _holes import wizard_holes
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from ch_connecting_rod_notes import DRAWING_NOTES, ISOMETRIC_VIEW_NOTE
from ch_connecting_rod_notes import DRAWING_DIMENSIONS, DRAWING_PRECISION
from ch_connecting_rod_spec import (
    CENTER_DISTANCE,
    FORK_BASE_BELOW_PIN,
    FORK_BASE_Y,
    FORK_CROTCH_BELOW_PIN,
    FORK_CROTCH_Y,
    FORK_CROWN_RADIUS,
    FORK_SLOT_BAND,
    FORK_SLOT_WIDTH,
    FORK_THICKNESS,
    FORK_THICKNESS_BAND,
    FORK_TOP_Y,
    FORK_WIDTH,
    PIN_HOLE_CSK_DIA,
    PIN_HOLE_SPEC,
    RING_BORE_DIA,
    RING_BORE_DIA_BAND,
    RING_OUTER_RADIUS,
    RING_THICKNESS,
    RING_WALL,
    SHANK_THICKNESS,
    SHANK_WIDTH,
    SURFACE_FINISHES,
)

PART_NAME = "ch-connecting-rod"
# AISI 1018 plate (the registry row's material_specification); SOLIDWORKS's
# library carries it as Plain Carbon Steel -- see _common.apply_material.
MATERIAL = "Plain Carbon Steel"

# Cam ring centre -> rocker pin, VERTICAL rod: the
# pin rides the arm's rod-pin hole 133.067 out from the pivot -- directly
# above the phased cam LOBE (installed machine centre (-60.167, 99.155) =
# drum (-60.394, 90.518) + ECC 8.64 rotated by the +1.5 deg tooth phase,
# lobe UP at the cos-mode home; the Ry180 axial flip preserves local +Y;
# ch30 photos + GT rocker-corner triangulation put the arm's rod-side end over
# the drum). Solved so the rocker rests LEVEL (arm tilt 0 -- the ch14 end views
# show the 0-crank tip row flat at the TOP of the stroke) with the rod plumb
# (rod tilt 0 by construction). Supersedes 144.75, the same closure at the
# pre-ROM-fit lobe-down phase and -7.82 deg tilt. build_ch_channel_assembly
# imports this as ROD_C2C (imported, NOT copied). Nominal geometry lives in
# ch_connecting_rod_spec so the part, channel and drawing move as one recipe.
# The fork (the "Y" upper end of the ch14 fan photo, read as two cheeks round
# each rocker): a U-shaped clevis whose tines straddle the rocker strap and
# retain the peened pivot pin. Its proportions live in ch_connecting_rod_spec;
# the slot cut runs out SLOT_RUNOUT above the crown so the crown alone shapes
# the tine tops.
SLOT_RUNOUT = 1.0  # unprinted
# The rocker pivot pin hole is a native Hole Wizard number-drill feature; its
# identity lives in ch_connecting_rod_spec.
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > any local thickness or width

SHANK_START_Y = RING_BORE_DIA / 2.0 - 0.5  # overlaps the strap annulus
FORK_BOSS_LENGTH = FORK_TOP_Y - FORK_BASE_Y  # crown top -> root step (16.0)
SLOT_DEPTH = FORK_TOP_Y - FORK_CROTCH_Y  # crown top -> slot floor (13.0)
SLOT_CUT_HEIGHT = SLOT_DEPTH + SLOT_RUNOUT
PIN_DRILL_DIA = blind_cut_dia_mm(PIN_HOLE_SPEC)
# 90-degree countersink = an equal-distance chamfer whose leg is the radial
# step from the drill to the countersink diameter.
PIN_CSK_LEG = (PIN_HOLE_CSK_DIA - PIN_DRILL_DIA) / 2.0


def _circle_cap_area(radius: float, half_width: float) -> float:
    """Area under y = sqrt(R^2 - x^2) for |x| <= half_width."""
    return half_width * math.sqrt(radius**2 - half_width**2) + radius**2 * math.asin(
        half_width / radius
    )


def fork_outline_area(from_y: float) -> float:
    """Front-plane area of the fork outline (the root rectangle plus the crown
    semicircle on the pin) at and above ``from_y`` (FORK_BASE_Y..pin)."""
    return FORK_WIDTH * (CENTER_DISTANCE - from_y) + math.pi * FORK_CROWN_RADIUS**2 / 2.0


def boss_volume() -> float:
    """Ring disc + shank + fork boss before any cut. The shank inside the
    ring circle is buried in the thicker disc, so only its run from the ring OD
    to the fork root counts."""
    shank_area = SHANK_WIDTH * FORK_BASE_Y - _circle_cap_area(
        RING_OUTER_RADIUS, SHANK_WIDTH / 2.0
    )
    return (
        math.pi * RING_OUTER_RADIUS**2 * RING_THICKNESS
        + shank_area * SHANK_THICKNESS
        + fork_outline_area(FORK_BASE_Y) * FORK_THICKNESS
    )


def slot_volume() -> float:
    """The slot runs through the fork's width above the crotch."""
    return fork_outline_area(FORK_CROTCH_Y) * FORK_SLOT_WIDTH


def strap_bore_volume() -> float:
    return math.pi * (RING_BORE_DIA / 2.0) ** 2 * RING_THICKNESS


def pin_hole_volume() -> float:
    """The drill crosses the slot, so it only cuts the two tines."""
    return math.pi * (PIN_DRILL_DIA / 2.0) ** 2 * (FORK_THICKNESS - FORK_SLOT_WIDTH)


def pin_countersink_volume() -> float:
    """Two 90-degree chamfer rings on the drill mouths."""
    return 2.0 * math.pi * PIN_CSK_LEG**2 * (PIN_DRILL_DIA / 2.0 + PIN_CSK_LEG / 3.0)


def finished_volume() -> float:
    return (
        boss_volume()
        - slot_volume()
        - strap_bore_volume()
        - pin_hole_volume()
        - pin_countersink_volume()
    )


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
    await set_global(adapter, "ForkWidth", f"{FORK_WIDTH}mm")
    await set_global(adapter, "ForkThickness", f"{FORK_THICKNESS}mm")
    await set_global(adapter, "ForkSlotWidth", f"{FORK_SLOT_WIDTH}mm")
    await set_global(adapter, "ForkCrotchBelowPin", f"{FORK_CROTCH_BELOW_PIN}mm")
    await set_global(adapter, "ForkBaseBelowPin", f"{FORK_BASE_BELOW_PIN}mm")
    await set_global(adapter, "SlotRunout", f"{SLOT_RUNOUT}mm")
    # (The old PinHoleDia knob is gone: the rocker pin hole is now a native Hole
    # Wizard feature whose standard diameter is part-owned.)
    await set_global(adapter, "RingOuterRadius", '"RingBoreDia" / 2 + "RingWall"')
    await set_global(adapter, "ShankStartY", '"RingBoreDia" / 2 - 0.5mm')
    await set_global(adapter, "ForkBaseY", '"CenterDistance" - "ForkBaseBelowPin"')

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

    # Shank: flat bar from the strap up to the fork's root step. Rectilinear
    # chain emits width, length, then the corner anchor (x, z) -- the corner sits
    # at (-ShankWidth/2, ShankStartY); the anchor X dim is the unsigned half-width.
    shank_sd = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    shank_rect = [
        (-SHANK_WIDTH / 2.0, SHANK_START_Y),
        (SHANK_WIDTH / 2.0, SHANK_START_Y),
        (SHANK_WIDTH / 2.0, FORK_BASE_Y),
        (-SHANK_WIDTH / 2.0, FORK_BASE_Y),
    ]
    shank = await add_line_chain(adapter, shank_rect)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter, shank, shank_rect, label="shank", dims=shank_sd,
        names=["ShankWidthDim", "ShankLength", "ShankCornerX", "ShankCornerZ"],
        drives=['"ShankWidth"', '"ForkBaseY" - "ShankStartY"',
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

    # Fork boss: a tombstone outline -- the root step at FORK_BASE_Y, two
    # vertical sides, and a semicircular crown centred on the pin (R =
    # ForkWidth/2, tangent to the sides -- add_arc runs CCW start->end, so
    # right-side-top -> left-side-top bows over the TOP). Because the crown
    # centre sits on the sketch axis with radius = the side half-width, each
    # side-top lands on the crown's equator by construction. Extruded mid-plane
    # to the full fork thickness; the slot cut below splits it into two tines.
    # Dim EMISSION ORDER (each recorded as its display dim is created): root
    # width, crown radius, crown-centre height (x on-axis, so
    # anchor_point_to_origin emits ONE dim), right-side length, right-side x.
    # Root horizontal + side verticals are RELATIONS: 9 DOF (four corners and
    # the centre, less the arc's equal radius) = 3 relations + the on-axis
    # alignment + 5 dims, no redundancy.
    fork_sd = SketchDims()
    check("create_sketch fork", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    fw = FORK_WIDTH / 2.0
    fork_root = check(
        "fork root",
        await adapter.add_line(-fw, FORK_BASE_Y, fw, FORK_BASE_Y),
    )
    fork_side_r = check(
        "fork side right",
        await adapter.add_line(fw, FORK_BASE_Y, fw, CENTER_DISTANCE),
    )
    fork_crown = check(
        "fork crown",
        await adapter.add_arc(
            0.0, CENTER_DISTANCE, fw, CENTER_DISTANCE, -fw, CENTER_DISTANCE
        ),
    )
    fork_side_l = check(
        "fork side left",
        await adapter.add_line(-fw, CENTER_DISTANCE, -fw, FORK_BASE_Y),
    )
    set_sketch_direct_db(adapter, False)
    for ent, relation in (
        (fork_root, "horizontal"),
        (fork_side_r, "vertical"),
        (fork_side_l, "vertical"),
    ):
        check(f"fork {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check(
        "dimension fork width",
        await adapter.add_sketch_dimension(fork_root, None, "linear", FORK_WIDTH),
    )
    fork_sd.record("ForkWidthDim", '"ForkWidth"')
    check(
        "dimension fork crown radius",
        await adapter.add_sketch_dimension(fork_crown, None, "radial", fw),
    )
    fork_sd.record("ForkCrownR", '"ForkWidth" / 2')
    await anchor_point_to_origin(
        adapter, f"{fork_crown}.center", 0.0, CENTER_DISTANCE, "fork crown centre"
    )
    fork_sd.record("ForkPinY", '"CenterDistance"')
    await dimension_between(
        adapter,
        f"{fork_side_r}.start",
        f"{fork_side_r}.end",
        "vertical_distance",
        FORK_BASE_BELOW_PIN,
        "fork side length",
    )
    fork_sd.record("ForkSideLength", '"ForkBaseBelowPin"')
    await dimension_between(
        adapter, f"{fork_side_r}.start", "origin", "horizontal_distance", fw,
        "fork side x",
    )
    fork_sd.record("ForkSideX", '"ForkWidth" / 2')
    await ensure_fully_defined(adapter, "fork sketch")
    check("exit_sketch fork", await adapter.exit_sketch())
    name_last_feature(adapter, "ForkProfile")
    drive_jobs += fork_sd.apply(adapter, "ForkProfile")
    check(
        "extrude fork",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=FORK_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ForkBoss")
    # The fork thickness prints natively at three places (FORK_THICKNESS_BAND):
    # named so the band, the precision and the drawing select it by name.
    fork_thickness_dim = name_dimensions(adapter, "ForkBoss", ["ForkThick"])
    drive_jobs.append((fork_thickness_dim[0], '"ForkThickness"'))
    v_expected = boss_volume()
    await volume_check(adapter, "ring, shank and fork bosses", v_expected, 0.002 * v_expected)

    # Fork slot: a Right-plane rectangle (sketch x = model Z) centred on the rod
    # mid-plane, from the crotch up past the crown, cut through the fork's
    # width. A construction centreline from the fork's root step to its crown
    # top carries the two lengths the side view prints from the crown top --
    # the slot depth (to the crotch) and the boss length (to the root step) --
    # so the print measures from the visible tine tops, never from the origin.
    # The boss length is a driving dimension of that reference line, driven by
    # the same knobs as the fork outline, so it always equals the modelled
    # step. Dim EMISSION ORDER: reference start height (on-axis anchor, ONE
    # dim), boss length, slot width, cut height, slot corner x, slot depth.
    # 12 DOF = reference vertical + on-axis alignment + 2 dims, rectangle's four
    # relations + 4 dims.
    slot_sd = SketchDims()
    check("create_sketch fork slot", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    boss_ref = check(
        "fork boss reference",
        await adapter.add_centerline(0.0, FORK_BASE_Y, 0.0, FORK_TOP_Y),
    )
    sh = FORK_SLOT_WIDTH / 2.0
    slot_rect = [
        (-sh, FORK_CROTCH_Y),
        (sh, FORK_CROTCH_Y),
        (sh, FORK_CROTCH_Y + SLOT_CUT_HEIGHT),
        (-sh, FORK_CROTCH_Y + SLOT_CUT_HEIGHT),
    ]
    slot = await add_line_chain(adapter, slot_rect)
    set_sketch_direct_db(adapter, False)
    check(
        "fork boss reference vertical",
        await adapter.add_sketch_constraint(boss_ref, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{boss_ref}.start", 0.0, FORK_BASE_Y, "fork boss reference"
    )
    slot_sd.record("ForkRootY", '"ForkBaseY"')
    await dimension_between(
        adapter,
        f"{boss_ref}.start",
        f"{boss_ref}.end",
        "vertical_distance",
        FORK_BOSS_LENGTH,
        "fork boss length",
    )
    slot_sd.record("ForkBossLength", '"ForkWidth" / 2 + "ForkBaseBelowPin"')
    for line, (x1, y1), (x2, y2) in zip(
        slot, slot_rect, slot_rect[1:] + slot_rect[:1], strict=True
    ):
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"slot {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    await dimension_between(
        adapter, f"{slot[0]}.start", f"{slot[0]}.end", "horizontal_distance",
        FORK_SLOT_WIDTH, "slot width",
    )
    slot_sd.record("SlotWidth", '"ForkSlotWidth"')
    await dimension_between(
        adapter, f"{slot[1]}.start", f"{slot[1]}.end", "vertical_distance",
        SLOT_CUT_HEIGHT, "slot cut height",
    )
    slot_sd.record(
        "SlotCutHeight", '"ForkWidth" / 2 + "ForkCrotchBelowPin" + "SlotRunout"'
    )
    # Centred: the tines come out equal (the notes' tine-match requirement).
    await dimension_between(
        adapter, f"{slot[0]}.start", "origin", "horizontal_distance", sh,
        "slot corner x",
    )
    slot_sd.record("SlotHalfWidth", '"ForkSlotWidth" / 2')
    await dimension_between(
        adapter, f"{slot[0]}.start", f"{boss_ref}.end", "vertical_distance",
        SLOT_DEPTH, "slot depth",
    )
    slot_sd.record("SlotDepth", '"ForkWidth" / 2 + "ForkCrotchBelowPin"')
    await ensure_fully_defined(adapter, "fork slot sketch")
    check("exit_sketch fork slot", await adapter.exit_sketch())
    name_last_feature(adapter, "ForkSlotProfile")
    drive_jobs += slot_sd.apply(adapter, "ForkSlotProfile")
    check(
        "cut fork slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ForkSlot")
    v_expected -= slot_volume()
    await volume_check(adapter, "fork slot", v_expected, 0.01 * slot_volume() + 0.05)

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
    v_expected -= strap_bore_volume()
    await volume_check(adapter, "strap bore", v_expected, 0.002 * v_expected)

    # Pivot pin hole on the rod axis, drilled +Z from the front tine's outer
    # face through both tines (the slot between them is air). The pin RUNS in
    # the arm's #47 hole and is RETAINED here, peened into the countersinks.
    pin_cut = wizard_holes(
        adapter,
        PIN_HOLE_SPEC,
        [[0.0, CENTER_DISTANCE, FORK_THICKNESS / 2.0]],
        (0.0, 0.0, 1.0),
        "rocker pin hole",
        name="PinHole",
        placement_dims=[((None, None), ("PinCz", '"CenterDistance"'))],
        expect_dia_mm=blind_cut_dia_mm(PIN_HOLE_SPEC),
    )
    drive_jobs += pin_cut.placement_drive_jobs
    v_pin = pin_hole_volume()
    v_expected -= v_pin
    await volume_check(adapter, "pin hole through both tines", v_expected, 0.03 * v_pin + 0.05)
    # 90-degree countersinks on both tine outer faces: the peened pin ends
    # upset into them (ch_rod_pivot_pin_spec). Edge picks sit on the drill
    # mouths' +X rims; the chamfer leg is unprinted (the hole callout carries
    # the countersink diameter).
    pin_r = PIN_DRILL_DIA / 2.0
    check(
        "countersink pin hole mouths",
        await adapter.add_chamfer(
            PIN_CSK_LEG,
            [
                [pin_r, CENTER_DISTANCE, z_face]
                for z_face in (-FORK_THICKNESS / 2.0, FORK_THICKNESS / 2.0)
            ],
        ),
    )
    name_last_feature(adapter, "PinCountersinks")
    v_csk = pin_countersink_volume()
    v_expected -= v_csk
    v_built = await volume_check(
        adapter, "pin-hole countersinks", v_expected, 0.03 * v_csk + 0.05
    )

    # Named bore axes for assembly mates (view-independent name selection):
    # Axis1 = strap bore on the cam (origin), Axis2 = pivot pin bore (0, CD).
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
    # so every target resolves. Each equation evaluates to the as-built value, so
    # the neutrality gate asserts the post-drive volume equals the as-built
    # volume: geometry must not move.
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
    # The fork straddles the rocker strap inside one station pitch, so its
    # outer thickness and slot print natively at three places (Main ruling
    # 2026-10, option b). The fork is centred (mid-plane extrude) and its band
    # symmetric, so it prints +/-; the slot may only come out wide.
    fork_lower, fork_upper = deviations(FORK_THICKNESS_BAND)
    if fork_lower != -fork_upper:
        raise AssertionError("ch_connecting_rod_spec.FORK_THICKNESS_BAND must be symmetric")
    set_dimension_symmetric_tolerance(adapter, "ForkBoss", "ForkThick", fork_upper)
    set_dimension_bilateral_tolerance(
        adapter, "ForkSlotProfile", "SlotWidth", *deviations(FORK_SLOT_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)

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
