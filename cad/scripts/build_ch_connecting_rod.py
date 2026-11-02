r"""Reproduction script: connecting rod (book ch. 13 pp. 22-25 / ch. 14 p. 29; 20 used).

Black rod machined from 1018 low-carbon steel plate, converting each cam's
rotation into the rocker arm's see-saw: a full ring (strap) riding the
eccentric cam (cast integral with each cylinder gear), a thin flat shank, and a
U-shaped FORK (clevis; the Y-shaped upper end of the ch14 fan photo) whose two
tines straddle the rocker arm's strap and carry the pressed pivot pin
(MHA-CH-10, ch_rod_pivot_pin_spec) through the arm's rod-pin hole near its
rod-side tip. The centre distance follows the actual phased cam centre and the
level rocker's pin, including the common raised drive-axis height. The ch14
end views show the 0-crank tip row level (cos-mode home = top of stroke, cam
lobe UP); the rod length closes that link without moving the rocker bank.

The rod is FLAT: ring, shank and fork share one mid-plane, which is the cam
plane and the arm plane (rocker_bank_layout.ARM_MID_DZ = CAM_MID_DZ), so the
arm runs centred in the fork slot. The fork is .39 wide with a full-round
crown on the pin; its two .067 +/-.002 tines straddle a .106 +/-.002 slot
(Main ruling 2026-10, option b): each inter-arm gap holds one tine of each
neighbouring rod, so tines, slot and the ring/shank faces are model bands
located from one finished fork face (#982). The pin is pressed into a
hole reamed through both tines and dressed flush (user ruling 2026-10-09, PR
#1292 review F1, reversing the #746 reconstruction choice of peening it into
countersinks): the photos show two rod cheeks round each rocker, not the
original fastener.

Dimensions: cad/config/dimensions.yaml "Chapter 13" rod rows - centre distance
derived (high), ring bore derived from the cam OD + confirmed on the p.25
overlay (med), fork proportions photo-scaled vs the 16 mm arm-depth callout
and sized to the joint budget (ch_rod_pivot_pin_spec), everything else
photo-scaled (low).

Layout: ring centre at the origin, shank rising +Y to the fork; thicknesses
extruded mid-plane in Z. Build order matters: the plate (ring and shank, one
outline) and the fork are bossed first, the slot is cut through the fork,
then the bore.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_connecting_rod.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_properties import part_drawing_unit
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_precision import apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import set_dimension_bilateral_tolerance, set_dimension_symmetric_tolerance
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from ch_connecting_rod_notes import ISOMETRIC_VIEW_NOTE
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
    FORK_TOP_Y,
    FORK_WIDTH,
    INSIDE_CORNER_R,
    PIN_HOLE_BAND,
    PIN_HOLE_DIA,
    RING_BORE_DIA,
    RING_BORE_DIA_BAND,
    RING_FACE_BAND,
    RING_FACE_NEAR,
    RING_OUTER_RADIUS,
    RING_THICKNESS,
    RING_THICKNESS_BAND,
    RING_WALL,
    SHANK_THICKNESS,
    SHANK_WIDTH,
    SURFACE_FINISHES,
    TINE_BAND,
    TINE_THICKNESS,
    UNIT,
)

PART_NAME = "ch-connecting-rod"
# AISI 1018 plate (the registry row's material_specification); SOLIDWORKS's
# library carries it as Plain Carbon Steel -- see _appearance.apply_material.
MATERIAL = "Plain Carbon Steel"

# Cam ring centre -> rocker pin, VERTICAL rod: the
# pin rides the arm's rod-pin hole 133.067 out from the pivot -- directly
# above the phased cam LOBE (shared drive height plus the eccentricity
# rotated by the configured tooth phase),
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
# hold the pressed pivot pin. Its proportions live in ch_connecting_rod_spec;
# the slot cut runs out SLOT_RUNOUT above the crown so the crown alone shapes
# the tine tops.
SLOT_RUNOUT = 1.0  # unprinted
# The ring/shank near-face reference runs this far down the shank from the
# fork root, so its ordinate prints below the fork in its side detail.
RING_FACE_REF_RUN = 2.0  # unprinted
# The rocker pivot pin hole is a reamed press hole; its size and band live in
# ch_connecting_rod_spec.
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > any local thickness or width

FORK_BOSS_LENGTH = FORK_TOP_Y - FORK_BASE_Y  # crown top -> root step (.71)
SLOT_DEPTH = FORK_TOP_Y - FORK_CROTCH_Y  # crown top -> slot floor (.58)
SLOT_CUT_HEIGHT = SLOT_DEPTH + SLOT_RUNOUT


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
    """Plate (ring disc and shank, one outline) + fork boss before any cut:
    the shank counts only its run from the ring OD to the fork root."""
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
    """The reamed hole crosses the slot, so it only cuts the two tines."""
    return math.pi * (PIN_HOLE_DIA / 2.0) ** 2 * (FORK_THICKNESS - FORK_SLOT_WIDTH)


def _fillet_area(radius: float, opening: float) -> float:
    """Section area a radius adds in a straight concave corner whose walls
    meet at ``opening`` radians across the air."""
    return radius**2 * (1.0 / math.tan(opening / 2.0) - (math.pi - opening) / 2.0)


# The shank's flank meets the ring's OD at its tangent's angle: the air
# between them opens past square by the flank's angle on the circle.
SHANK_RING_OPENING = math.pi / 2.0 + math.asin(SHANK_WIDTH / 2.0 / RING_OUTER_RADIUS)


def inside_corner_volume() -> float:
    """The inside-corner fillets: the slot floor's two corners across the
    fork's width, the root step's loop round the shank's end (two corners
    across its width, two through its thickness), and the shank's two
    flanks onto the ring through the plate. The loop's four meeting corners
    add only an R^3 sliver, inside the gate's allowance."""
    square = _fillet_area(INSIDE_CORNER_R, math.pi / 2.0)
    straight = 2.0 * FORK_WIDTH + 2.0 * SHANK_WIDTH + 2.0 * SHANK_THICKNESS
    ring = _fillet_area(INSIDE_CORNER_R, SHANK_RING_OPENING) * 2.0 * SHANK_THICKNESS
    return square * straight + ring


def finished_volume() -> float:
    return (
        boss_volume()
        - slot_volume()
        + inside_corner_volume()
        - strap_bore_volume()
        - pin_hole_volume()
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

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
    await set_global(adapter, "ForkTine", f"{TINE_THICKNESS}mm")
    await set_global(adapter, "ForkSlotWidth", f"{FORK_SLOT_WIDTH}mm")
    await set_global(adapter, "ForkThickness", '2 * "ForkTine" + "ForkSlotWidth"')
    await set_global(adapter, "ForkCrotchBelowPin", f"{FORK_CROTCH_BELOW_PIN}mm")
    await set_global(adapter, "ForkBaseBelowPin", f"{FORK_BASE_BELOW_PIN}mm")
    await set_global(adapter, "SlotRunout", f"{SLOT_RUNOUT}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    await set_global(adapter, "InsideCornerR", f"{INSIDE_CORNER_R}mm")
    await set_global(adapter, "RingOuterRadius", '"RingBoreDia" / 2 + "RingWall"')
    await set_global(adapter, "ForkBaseY", '"CenterDistance" - "ForkBaseBelowPin"')
    await set_global(
        adapter, "RingFaceNear", '("ForkThickness" - "RingThickness") / 2'
    )

    # Each sketch records its dim names + drive equations into a per-sketch
    # SketchDims in helper emission order; the drives are collected and applied in
    # one deferred batch at the end (every target resolves against the finished
    # model).
    drive_jobs: list[tuple[str, str]] = []

    # Plate: the ring disc and the shank as ONE closed outline extruded once
    # -- the ring OD's major arc from the shank's left flank round the bottom
    # to its right flank, the flanks up to the fork's root step, and the root
    # line. Two coplanar bosses (a disc, then a shank dipping into it) left
    # the shank's flanks as seams across the ring's faces in the front view
    # (#982 review r2), reading as a step the side view does not show. Dim
    # EMISSION ORDER: ring OD, shank width, root height, right flank x; the
    # arc centre is a coincident relation. 9 DOF (arc 5, the root's two
    # corners 4) = 3 relations + 4 dims + the centre's 2, the flanks' feet
    # held to the arc's ends by coincident relations.
    plate = SketchDims()
    check("create_sketch plate", await adapter.create_sketch("Front"))
    shank_x = SHANK_WIDTH / 2.0
    junction_y = math.sqrt(RING_OUTER_RADIUS**2 - shank_x**2)
    set_sketch_direct_db(adapter, True)
    ring_arc = check(
        "ring OD major arc",
        await adapter.add_arc(0.0, 0.0, -shank_x, junction_y, shank_x, junction_y),
    )
    flank_r, root, flank_l = await add_line_chain(
        adapter,
        [
            (shank_x, junction_y),
            (shank_x, FORK_BASE_Y),
            (-shank_x, FORK_BASE_Y),
            (-shank_x, junction_y),
        ],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    for label, first, second, relation in (
        ("ring centre", f"{ring_arc}.center", "origin", "coincident"),
        ("right flank foot", f"{flank_r}.start", f"{ring_arc}.end", "coincident"),
        ("left flank foot", f"{flank_l}.end", f"{ring_arc}.start", "coincident"),
        ("right flank", flank_r, None, "vertical"),
        ("left flank", flank_l, None, "vertical"),
        ("shank root", root, None, "horizontal"),
    ):
        check(f"plate {label}", await adapter.add_sketch_constraint(first, second, relation))
    check(
        "ring outer diameter",
        await adapter.add_sketch_dimension(
            ring_arc, None, "diameter", 2.0 * RING_OUTER_RADIUS
        ),
    )
    plate.record("RingOuterDia", '2 * "RingOuterRadius"')
    check(
        "shank width",
        await adapter.add_sketch_dimension(root, None, "linear", SHANK_WIDTH),
    )
    plate.record("ShankWidthDim", '"ShankWidth"')
    await dimension_between(
        adapter, f"{root}.start", "origin", "vertical_distance", FORK_BASE_Y,
        "shank root height",
    )
    plate.record("ShankRootY", '"ForkBaseY"')
    await dimension_between(
        adapter, f"{flank_r}.start", "origin", "horizontal_distance", shank_x,
        "shank right flank x",
    )
    plate.record("ShankSideX", '"ShankWidth" / 2')
    await ensure_fully_defined(adapter, "plate sketch")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += plate.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Plate")
    # The plate's thickness prints at the ring in the side view (#982 review
    # r1): named so its band and the drawing select it by name.
    ring_thick_dim = name_dimensions(adapter, "Plate", ["RingThick"])
    drive_jobs.append((ring_thick_dim[0], '"RingThickness"'))

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
    # The fork thickness prints as a reference at three places (two tines and
    # the slot own its limits): named so the precision and the drawing select
    # it by name.
    fork_thickness_dim = name_dimensions(adapter, "ForkBoss", ["ForkThick"])
    drive_jobs.append((fork_thickness_dim[0], '"ForkThickness"'))
    v_expected = boss_volume()
    await volume_check(adapter, "ring, shank and fork bosses", v_expected, 0.002 * v_expected)

    # Fork slot: a Right-plane rectangle (sketch x = model -Z) centred on the
    # rod mid-plane, from the crotch up past the crown, cut through the fork's
    # width. Every side-view location runs from ONE finished face, the fork's
    # outer face at sketch +x (model -Z; the left face in the side view): a
    # construction line on that face, from the fork's root step to its crown
    # top, carries the boss length and the slot depth from the crown top, the
    # near tine (face to slot wall) and the plate's near-face ordinate. A
    # short construction line on the plate's near face runs down the shank
    # from the root step, so that ordinate prints below the fork; the plate's
    # thickness prints at the ring (RingThick@Plate). Every reference is
    # driven by the same knobs as the solid features, so it always lies on the
    # modelled face. Dim EMISSION ORDER: face x and root height (general
    # anchor, TWO dims), boss length, slot width, cut height, near tine, slot
    # depth, then the near face's ordinate and its run.
    # 16 DOF = face line: vertical + 2 anchor dims + boss length; rectangle:
    # four relations + 4 dims; the near-face line: vertical + level with the
    # face line's root end + ordinate + run.
    slot_sd = SketchDims()
    check("create_sketch fork slot", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    face_x = FORK_THICKNESS / 2.0
    face_ref = check(
        "fork face reference",
        await adapter.add_centerline(face_x, FORK_BASE_Y, face_x, FORK_TOP_Y),
    )
    sh = FORK_SLOT_WIDTH / 2.0
    slot_rect = [
        (-sh, FORK_CROTCH_Y),
        (sh, FORK_CROTCH_Y),
        (sh, FORK_CROTCH_Y + SLOT_CUT_HEIGHT),
        (-sh, FORK_CROTCH_Y + SLOT_CUT_HEIGHT),
    ]
    slot = await add_line_chain(adapter, slot_rect)
    ring_face = check(
        "ring face reference",
        await adapter.add_centerline(
            RING_THICKNESS / 2.0,
            FORK_BASE_Y,
            RING_THICKNESS / 2.0,
            FORK_BASE_Y - RING_FACE_REF_RUN,
        ),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "fork face reference vertical",
        await adapter.add_sketch_constraint(face_ref, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{face_ref}.start", face_x, FORK_BASE_Y, "fork face reference"
    )
    slot_sd.record("ForkFaceX", '"ForkThickness" / 2')
    slot_sd.record("ForkRootY", '"ForkBaseY"')
    await dimension_between(
        adapter,
        f"{face_ref}.start",
        f"{face_ref}.end",
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
    # The near tine: the datum face to the slot's near wall, at the tine top.
    await dimension_between(
        adapter, f"{face_ref}.end", f"{slot[0]}.end", "horizontal_distance",
        TINE_THICKNESS, "near tine",
    )
    slot_sd.record("TineNear", '"ForkTine"')
    await dimension_between(
        adapter, f"{slot[0]}.start", f"{face_ref}.end", "vertical_distance",
        SLOT_DEPTH, "slot depth",
    )
    slot_sd.record("SlotDepth", '"ForkWidth" / 2 + "ForkCrotchBelowPin"')
    check(
        "RingFaceNear reference vertical",
        await adapter.add_sketch_constraint(ring_face, None, "vertical"),
    )
    check(
        "RingFaceNear reference level with the fork root",
        await adapter.add_sketch_constraint(
            f"{ring_face}.start", f"{face_ref}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter, f"{face_ref}.start", f"{ring_face}.end", "horizontal_distance",
        RING_FACE_NEAR, "RingFaceNear",
    )
    slot_sd.record("RingFaceNear", '"RingFaceNear"')
    await dimension_between(
        adapter, f"{ring_face}.start", f"{ring_face}.end", "vertical_distance",
        RING_FACE_REF_RUN, "RingFaceNear reference run",
    )
    slot_sd.record("RingFaceNearRun")
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

    # Every inside corner gets the one modelled radius, inside the title
    # block's INSIDE CORNERS R1.0 MAX, which governs it on the print
    # (ch_connecting_rod_spec): the shank's two flanks onto the ring, the
    # root step's loop round the shank's end (the flanks' corners, then the
    # plate faces'), and the slot floor's two corners.
    shank_x = SHANK_WIDTH / 2.0
    junction_y = math.sqrt(RING_OUTER_RADIUS**2 - shank_x**2)
    plate_z = SHANK_THICKNESS / 2.0
    corner_edges = [
        [shank_x, junction_y, 0.0],
        [-shank_x, junction_y, 0.0],
        [shank_x, FORK_BASE_Y, 0.0],
        [-shank_x, FORK_BASE_Y, 0.0],
        [0.0, FORK_BASE_Y, plate_z],
        [0.0, FORK_BASE_Y, -plate_z],
        [0.0, FORK_CROTCH_Y, FORK_SLOT_WIDTH / 2.0],
        [0.0, FORK_CROTCH_Y, -FORK_SLOT_WIDTH / 2.0],
    ]
    check(
        "fillet inside corners",
        await adapter.add_fillet(INSIDE_CORNER_R, corner_edges, propagate=False),
    )
    name_last_feature(adapter, "InsideCorners")
    corner_dim = name_dimensions(adapter, "InsideCorners", ["InsideCornerR"])
    drive_jobs.append((corner_dim[0], '"InsideCornerR"'))
    v_corners = inside_corner_volume()
    v_expected += v_corners
    await volume_check(adapter, "inside corner fillets", v_expected, 0.1 * v_corners + 0.05)

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

    # Pivot pin hole on the rod axis, reamed through both tines (the slot
    # between them is air). The pin RUNS in the arm's #47 hole and is PRESSED
    # here, its ends dressed flush (ch_rod_pivot_pin_spec). No countersink: the
    # hole runs straight through each tine, so the pin bears on the whole tine.
    pin_hole = SketchDims()
    check("create_sketch rocker pin hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        CENTER_DISTANCE,
        PIN_HOLE_DIA / 2.0,
        "rocker pin hole",
        dims=pin_hole,
        names=(None, "PinHoleY", "PinHoleDia"),
        drives=(None, '"CenterDistance"', '"PinHoleDia"'),
    )
    await ensure_fully_defined(adapter, "rocker pin hole sketch")
    check("exit_sketch rocker pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin_hole.apply(adapter, "PinHoleProfile")
    check(
        "cut rocker pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinHole")
    v_pin = pin_hole_volume()
    v_expected -= v_pin
    v_built = await volume_check(
        adapter, "pin hole through both tines", v_expected, 0.03 * v_pin + 0.05
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
    # The bands are millimetres; UNIT prints them in inches.
    set_dimension_bilateral_tolerance(
        adapter,
        "StrapBoreProfile",
        "StrapBoreDia",
        *deviations(RING_BORE_DIA_BAND),
        display_unit=UNIT,
    )
    # The fork straddles the rocker strap inside one station pitch (Main
    # ruling 2026-10, option b), and the ring must ride its cam slot while the
    # fork rides the arm (test_channel_axial_budget): the near tine, the slot
    # and the plate's near face print natively, located from the fork's datum
    # face, and the plate's thickness at the ring, each band symmetric so it
    # prints +/-. The fork over the tines is a reference (two tines and the
    # slot set it).
    tine_lower, tine_upper = deviations(TINE_BAND)
    slot_lower, slot_upper = deviations(FORK_SLOT_BAND)
    face_lower, face_upper = deviations(RING_FACE_BAND)
    thick_lower, thick_upper = deviations(RING_THICKNESS_BAND)
    if (tine_lower, slot_lower, face_lower, thick_lower) != (
        -tine_upper, -slot_upper, -face_upper, -thick_upper
    ):
        raise AssertionError("the fork side-view bands must be symmetric")
    set_dimension_symmetric_tolerance(
        adapter, "ForkSlotProfile", "TineNear", tine_upper, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "ForkSlotProfile", "SlotWidth", slot_upper, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "ForkSlotProfile", "RingFaceNear", face_upper, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "Plate", "RingThick", thick_upper, display_unit=UNIT
    )
    # The reamed press hole's band rides natively on its diameter; the front
    # view imports the .077 nominal at four places (DRAWING_PRECISION), its
    # +.0009/+.0005 at the same four.
    set_dimension_bilateral_tolerance(
        adapter,
        "PinHoleProfile",
        "PinHoleDia",
        *deviations(PIN_HOLE_BAND),
        display_unit=UNIT,
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
        {"Isometric View Note": ISOMETRIC_VIEW_NOTE},
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number", "Material Specification", "Finish", "Quantity",
            "Isometric View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
