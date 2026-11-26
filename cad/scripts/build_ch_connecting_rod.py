r"""Reproduction script: connecting rod (book ch. 13 pp. 22-25 / ch. 14 p. 29; 20 used).

Black rod machined from 1/4 x 2 1018 cold-finished flat, converting each cam's
rotation into the rocker arm's see-saw: a full ring (strap) riding the
eccentric cam (cast integral with each cylinder gear), a flat shank, and a
U-shaped FORK (clevis; the Y-shaped upper end of the ch14 fan photo) whose two
tines straddle the rocker arm's strap and carry the pressed pivot pin
(MHA-SH-VN-58 RodPin, sh_vn_pivot_pin_rod_spec) through the arm's rod-pin hole near its
rod-side tip. The centre distance follows the actual phased cam centre and the
level rocker's pin, including the common raised drive-axis height. The ch14
end views show the 0-crank tip row level (cos-mode home = top of stroke, cam
lobe UP); the rod length closes that link without moving the rocker bank.

The rod is FLAT: ring and fork share one mid-plane, which is the cam
plane and the arm plane (rocker_bank_layout.ARM_MID_DZ = CAM_MID_DZ), so the
arm runs centred in the fork slot. Ring and shank keep the original's
proportions (owner ruling 2026-11-18, #3114): the ring .170 +/-.002 thick, a
sliding fit between the two tooth discs of its cam slot, which locates the
rod along the bank; the shank .13, its near face .05 from the fork's datum
face (two-place sizes, so its mid-plane stands .005 off the ring's toward
that face), stepped in on both faces so the ring alone meets the discs. The
fork is .39 wide with a full-round crown on the
pin; its two .067 +/-.002 tines straddle a .106 +/-.002 slot (Main ruling
2026-10, option b): each inter-arm gap holds one tine of each neighbouring
rod, so tines, slot and the ring's faces are model bands located from one
finished fork face (#982), and the rocker arm, floating on its shaft, follows
the fork. The pin is pressed into a
hole reamed through both tines and dressed flush (user ruling 2026-10-09, PR
#1292 review F1, reversing the #746 reconstruction choice of peening it into
countersinks): the photos show two rod cheeks round each rocker, not the
original fastener.

Dimensions: cad/config/dimensions.yaml "Chapter 13" rod rows - centre distance
derived (high), ring bore derived from the cam OD + confirmed on the p.25
overlay (med), fork proportions photo-scaled vs the 16 mm arm-depth callout
and sized to the joint budget (sh_vn_pivot_pin_rod_spec), everything else
photo-scaled (low).

Layout: ring centre at the origin, shank rising +Y to the fork; ring and
fork centred on the Front plane (z = 0). Build order matters: the ring
disc, the shank (its foot buried in the ring's wall) and the fork are bossed
first, the slot is cut through the fork, the inside corners are rounded (the
shank's two corners onto the fork's step bossed in as the 1/8 in end mill
leaves them), then the bore and the pin hole.

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
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_precision import apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import set_dimension_bilateral_tolerance, set_dimension_symmetric_tolerance
from _fit_deviations import deviations
from _milled_corner_limit import (
    corner_r_limits,
    line_circle_fillet_area,
    runout_fillet_area,
    runout_rise,
)
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from ch_connecting_rod_notes import ISOMETRIC_VIEW_NOTE
from ch_connecting_rod_notes import DIMENSION_PREFIXES, SHANK_CORNER_R
from ch_connecting_rod_notes import DRAWING_DIMENSIONS, DRAWING_NOTES, DRAWING_PRECISION
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
    PIN_HOLE_DIA,
    RING_BORE_DIA,
    RING_BORE_DIA_BAND,
    RING_FACE_BAND,
    RING_FACE_NEAR,
    RING_OUTER_RADIUS,
    RING_THICKNESS,
    RING_THICKNESS_BAND,
    RING_WALL,
    SHANK_FACE_NEAR,
    SHANK_THICKNESS,
    SHANK_WIDTH,
    SURFACE_FINISHES,
    TINE_BAND,
    TINE_THICKNESS,
    UNIT,
)

PART_NAME = "ch-connecting-rod"
# AISI 1018 CF flat, 1/4 x 2 (the registry row's material_specification);
# SOLIDWORKS's library carries it as Plain Carbon Steel -- see
# _appearance.apply_material.
MATERIAL = "Plain Carbon Steel"

# Cam ring centre -> rocker pin: the
# pin rides the arm's rod-pin hole 133.067 out from the pivot, solved plumb
# over the cam lobe at the drive train's 1.5 deg lock; the lobe is cut on the
# tooth space so it stands UP at the cos-mode home (#749; shared drive height
# plus the eccentricity; the Ry180 axial flip preserves local +Y;
# ch30 photos + GT rocker-corner triangulation put the arm's rod-side end over
# the drum). Solved so the rocker rests LEVEL (arm tilt 0 -- the ch14 end views
# show the 0-crank tip row flat at the TOP of the stroke); the rod leans
# channel_kinematics.ROD_LEAN_DEG (0.082). Supersedes 144.75, the same closure at the
# pre-ROM-fit lobe-down phase and -7.82 deg tilt. build_ch_channel_assembly
# imports this as ROD_C2C (imported, NOT copied). Nominal geometry lives in
# ch_connecting_rod_spec so the part, channel and drawing move as one recipe.
# The fork (the "Y" upper end of the ch14 fan photo, read as two cheeks round
# each rocker): a U-shaped clevis whose tines straddle the rocker strap and
# hold the pressed pivot pin. Its proportions live in ch_connecting_rod_spec;
# the slot cut runs out SLOT_RUNOUT above the crown so the crown alone shapes
# the tine tops.
SLOT_RUNOUT = 1.0  # unprinted
# The shank's near-face reference runs this far down the shank from the fork
# root, so its ordinate prints below the fork in its side detail.
SHANK_FACE_REF_RUN = 2.0  # unprinted
# The shank's foot stands in the middle of the ring's wall: inside the ring
# disc, which is the thicker, so the foot leaves no edge on either ring face.
SHANK_FOOT_Y = RING_OUTER_RADIUS - RING_WALL / 2.0  # unprinted
if math.hypot(SHANK_WIDTH / 2.0, SHANK_FOOT_Y) >= RING_OUTER_RADIUS:
    raise AssertionError("the shank's foot must stand inside the ring disc")
# The shank's two faces in its Right-plane sketch (sketch x = model -Z, the
# fork's datum face at +FORK_THICKNESS / 2): the near face SHANK_FACE_NEAR in
# from the datum face, the far face the shank's thickness beyond it. The two
# are two-place sizes, so the shank is not centred on the rod's mid-plane
# (ch_connecting_rod_spec).
SHANK_NEAR_X = FORK_THICKNESS / 2.0 - SHANK_FACE_NEAR
SHANK_FAR_X = SHANK_NEAR_X - SHANK_THICKNESS
# (near, far) how far each ring face stands over its shank face (#3114): the
# shank lies inside the ring on both sides, which boss_volume relies on. The
# two corners where a shank face meets the ring's OD wall stay sharp in the
# model, inside the title block's INSIDE CORNERS R.040 MAX like the other
# title-block corners: the near step is shallower than the modelled corner radius,
# so a fillet has no seat there, and the far step would seat one only at
# nominal (the printed bands take it down to .001).
RING_STEPS = (
    RING_THICKNESS / 2.0 - SHANK_NEAR_X,
    SHANK_FAR_X + RING_THICKNESS / 2.0,
)
if min(RING_STEPS) <= 0.0:
    raise AssertionError("each shank face must lie inside its ring face (boss_volume)")
# The rocker pivot pin hole is a reamed press hole; its size and band live in
# ch_connecting_rod_spec.
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > any local thickness or width
# How far RingFaceReference's line on the fork's datum face runs up that face
# from its root step: unprinted, well inside the fork's height.
DATUM_FACE_REF_RUN = 2.0

FORK_BOSS_LENGTH = FORK_TOP_Y - FORK_BASE_Y  # crown top -> root step (.71)
SLOT_DEPTH = FORK_TOP_Y - FORK_CROTCH_Y  # crown top -> slot floor (.58)
SLOT_CUT_HEIGHT = SLOT_DEPTH + SLOT_RUNOUT

# The shank's four Q9 corners (ch_connecting_rod_notes.SHANK_CORNER_R) and
# the printed R.065's band (.060-.070). The fork's step beside the shank is
# narrower than the least radius the print allows, so the 1/8 in cutter that
# rounds the corner, tangent to the flank, runs through the step's outer
# corner and leaves no step face: the step corners are bossed in as that
# cutter leaves them (StepCorners), not filleted.
SHANK_CORNER_R_LIMITS = corner_r_limits(unit=UNIT)
FORK_STEP = (FORK_WIDTH - SHANK_WIDTH) / 2.0  # .035
if FORK_STEP >= SHANK_CORNER_R_LIMITS[0]:
    raise AssertionError("the fork's step seats a full fillet at the least corner radius")
# The step corners' plane: the shank's mid-thickness, in model z (the shank
# is not centred on the rod's mid-plane).
SHANK_MID_Z = -(SHANK_NEAR_X + SHANK_FAR_X) / 2.0


def _circle_cap_area(radius: float, half_width: float) -> float:
    """Area under y = sqrt(R^2 - x^2) for |x| <= half_width."""
    return half_width * math.sqrt(radius**2 - half_width**2) + radius**2 * math.asin(
        half_width / radius
    )


def fork_outline_area(from_y: float) -> float:
    """Front-plane area of the fork outline (the root rectangle plus the crown
    semicircle on the pin) at and above ``from_y`` (FORK_BASE_Y..pin)."""
    return FORK_WIDTH * (CENTER_DISTANCE - from_y) + math.pi * FORK_CROWN_RADIUS**2 / 2.0


def ring_volume() -> float:
    """The ring disc before its bore."""
    return math.pi * RING_OUTER_RADIUS**2 * RING_THICKNESS


def shank_volume() -> float:
    """The shank's run from the ring's OD to the fork root. Its foot inside
    the ring adds nothing: the shank lies inside both ring faces."""
    shank_area = SHANK_WIDTH * FORK_BASE_Y - _circle_cap_area(
        RING_OUTER_RADIUS, SHANK_WIDTH / 2.0
    )
    return shank_area * SHANK_THICKNESS


def boss_volume() -> float:
    """Ring disc, shank and fork boss before any cut."""
    return (
        ring_volume()
        + shank_volume()
        + fork_outline_area(FORK_BASE_Y) * FORK_THICKNESS
    )


def slot_volume() -> float:
    """The slot runs through the fork's width above the crotch."""
    return fork_outline_area(FORK_CROTCH_Y) * FORK_SLOT_WIDTH


def strap_bore_volume() -> float:
    """The bore runs through the ring's thickness (the shank's foot stands
    in the ring's wall, clear of it)."""
    return math.pi * (RING_BORE_DIA / 2.0) ** 2 * RING_THICKNESS


def pin_hole_volume() -> float:
    """The reamed hole crosses the slot, so it only cuts the two tines."""
    return math.pi * (PIN_HOLE_DIA / 2.0) ** 2 * (FORK_THICKNESS - FORK_SLOT_WIDTH)


def _fillet_area(radius: float, opening: float) -> float:
    """Section area a radius adds in a straight concave corner whose walls
    meet at ``opening`` radians across the air."""
    return radius**2 * (1.0 / math.tan(opening / 2.0) - (math.pi - opening) / 2.0)


def inside_corner_volume() -> float:
    """The title-block inside corners' fillets: the slot floor's two corners
    across the fork's width, and the two ledges where the shank's faces meet
    the fork's root step, across the shank's width. Each ledge fillet ends
    flush with the flanks' planes, which the step corners' boss (outside
    the ledges' fillets, inside the shank's faces) then extends."""
    square = _fillet_area(INSIDE_CORNER_R, math.pi / 2.0)
    return square * (2.0 * FORK_WIDTH + 2.0 * SHANK_WIDTH)


def shank_corner_volume() -> float:
    """ShankCorners: the shank's two flanks onto the ring's OD, through the
    shank's thickness (the ring is the thicker, so each fillet ends flat on
    a shank face)."""
    return (
        2.0
        * line_circle_fillet_area(SHANK_CORNER_R, RING_OUTER_RADIUS, SHANK_WIDTH / 2.0)
        * SHANK_THICKNESS
    )


def step_corner_volume() -> float:
    """StepCorners: the shank's two flanks onto the fork's step, through the
    shank's thickness."""
    return 2.0 * runout_fillet_area(SHANK_CORNER_R, FORK_STEP) * SHANK_THICKNESS


def finished_volume() -> float:
    return (
        boss_volume()
        - slot_volume()
        + inside_corner_volume()
        + shank_corner_volume()
        + step_corner_volume()
        - strap_bore_volume()
        - pin_hole_volume()
    )


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations) for every module constant; derived spans
    # (ring outer radius, the shank's foot and root heights, the two near-face
    # ordinates) are equations of those primitives, so a knob edit keeps the
    # strap-to-pin geometry consistent. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 127 = 127 in,
    # blowing the part up 25.4x).
    set_global(adapter, "CenterDistance", f"{CENTER_DISTANCE}mm")
    set_global(adapter, "RingBoreDia", f"{RING_BORE_DIA}mm")
    set_global(adapter, "RingWall", f"{RING_WALL}mm")
    set_global(adapter, "RingThickness", f"{RING_THICKNESS}mm")
    set_global(adapter, "ShankWidth", f"{SHANK_WIDTH}mm")
    set_global(adapter, "ShankThickness", f"{SHANK_THICKNESS}mm")
    set_global(adapter, "ForkWidth", f"{FORK_WIDTH}mm")
    set_global(adapter, "ForkTine", f"{TINE_THICKNESS}mm")
    set_global(adapter, "ForkSlotWidth", f"{FORK_SLOT_WIDTH}mm")
    set_global(adapter, "ForkThickness", '2 * "ForkTine" + "ForkSlotWidth"')
    set_global(adapter, "ForkCrotchBelowPin", f"{FORK_CROTCH_BELOW_PIN}mm")
    set_global(adapter, "ForkBaseBelowPin", f"{FORK_BASE_BELOW_PIN}mm")
    set_global(adapter, "SlotRunout", f"{SLOT_RUNOUT}mm")
    set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    set_global(adapter, "InsideCornerR", f"{INSIDE_CORNER_R}mm")
    set_global(adapter, "CornerR", f"{SHANK_CORNER_R}mm")
    set_global(adapter, "RingOuterRadius", '"RingBoreDia" / 2 + "RingWall"')
    set_global(adapter, "ForkBaseY", '"CenterDistance" - "ForkBaseBelowPin"')
    set_global(
        adapter, "RingFaceNear", '("ForkThickness" - "RingThickness") / 2'
    )
    set_global(adapter, "ShankFaceNear", f"{SHANK_FACE_NEAR}mm")
    set_global(adapter, "ShankFootY", '"RingOuterRadius" - "RingWall" / 2')

    # Each sketch records its dim names + drive equations into a per-sketch
    # SketchDims in helper emission order; the drives are collected and applied in
    # one deferred batch at the end (every target resolves against the finished
    # model).
    drive_jobs: list[tuple[str, str]] = []

    # Ring: a full disc on the Front plane, extruded mid-plane to the ring's
    # thickness (#3114: .170, the sliding fit in the cam slot). On-origin
    # circle: the diameter is its one dimension.
    ring_sd = SketchDims()
    check("create_sketch ring", adapter.create_sketch("Front"))
    define_circle(
        adapter, 0.0, 0.0, RING_OUTER_RADIUS, "ring OD", dims=ring_sd,
        names=(None, None, "RingOuterDia"),
        drives=(None, None, '2 * "RingOuterRadius"'),
    )
    ensure_fully_defined(adapter, "ring sketch")
    check("exit_sketch ring", adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    drive_jobs += ring_sd.apply(adapter, "RingProfile")
    check(
        "extrude ring",
        adapter.create_extrusion(
            ExtrusionParameters(depth=RING_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Ring")
    # The ring's thickness prints at the ring in the side view (#982 review
    # r1): named so its band and the drawing select it by name.
    ring_thick_dim = name_dimensions(adapter, "Ring", ["RingThick"])
    drive_jobs.append((ring_thick_dim[0], '"RingThickness"'))

    # Shank: its side section on the Right plane (sketch x = model -Z), a
    # rectangle the shank's thickness wide from its foot in the ring's wall
    # up to the fork's root step, extruded mid-plane to the shank's width. Its
    # near face stands SHANK_FACE_NEAR in from the fork's datum face, so the
    # rectangle is not centred on the sketch origin. The shank lies inside the
    # ring on both faces, so the foot is buried in the disc and no flank runs
    # across a ring face (two coplanar bosses left such seams, #982 review
    # r2). Sketched from the side so the thickness is a sketch dimension on
    # the root line, whose ends the fork's side detail shows; the width is the
    # extrusion's depth. Dim EMISSION ORDER: thickness, root height, near
    # face z, foot height. 8 DOF (four corners) = 4 relations + 4 dims.
    shank_sd = SketchDims()
    check("create_sketch shank", adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    shank_root, shank_far, shank_foot, shank_near = add_line_chain(
        adapter,
        [
            (SHANK_NEAR_X, FORK_BASE_Y),
            (SHANK_FAR_X, FORK_BASE_Y),
            (SHANK_FAR_X, SHANK_FOOT_Y),
            (SHANK_NEAR_X, SHANK_FOOT_Y),
        ],
    )
    set_sketch_direct_db(adapter, False)
    for label, line, relation in (
        ("root", shank_root, "horizontal"),
        ("far face", shank_far, "vertical"),
        ("foot", shank_foot, "horizontal"),
        ("near face", shank_near, "vertical"),
    ):
        check(f"shank {label}", adapter.add_sketch_constraint(line, None, relation))
    check(
        "shank thickness",
        adapter.add_sketch_dimension(shank_root, None, "linear", SHANK_THICKNESS),
    )
    shank_sd.record("ShankThick", '"ShankThickness"')
    dimension_between(
        adapter, f"{shank_root}.start", "origin", "vertical_distance", FORK_BASE_Y,
        "shank root height",
    )
    shank_sd.record("ShankRootY", '"ForkBaseY"')
    dimension_between(
        adapter, f"{shank_root}.start", "origin", "horizontal_distance",
        SHANK_NEAR_X, "shank near face z",
    )
    shank_sd.record("ShankFaceZ", '"ForkThickness" / 2 - "ShankFaceNear"')
    dimension_between(
        adapter, f"{shank_foot}.start", "origin", "vertical_distance", SHANK_FOOT_Y,
        "shank foot height",
    )
    shank_sd.record("ShankFootY", '"ShankFootY"')
    ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank_sd.apply(adapter, "ShankProfile")
    check(
        "extrude shank",
        adapter.create_extrusion(
            ExtrusionParameters(depth=SHANK_WIDTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Shank")
    # The shank's width prints across its flanks in the front view: named so
    # the precision and the drawing select it by name.
    shank_width_dim = name_dimensions(adapter, "Shank", ["ShankWidthDim"])
    drive_jobs.append((shank_width_dim[0], '"ShankWidth"'))
    v_expected = ring_volume() + shank_volume()
    volume_check(adapter, "ring and shank bosses", v_expected, 0.002 * v_expected)

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
    check("create_sketch fork", adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    fw = FORK_WIDTH / 2.0
    fork_root = check(
        "fork root",
        adapter.add_line(-fw, FORK_BASE_Y, fw, FORK_BASE_Y),
    )
    fork_side_r = check(
        "fork side right",
        adapter.add_line(fw, FORK_BASE_Y, fw, CENTER_DISTANCE),
    )
    fork_crown = check(
        "fork crown",
        adapter.add_arc(
            0.0, CENTER_DISTANCE, fw, CENTER_DISTANCE, -fw, CENTER_DISTANCE
        ),
    )
    fork_side_l = check(
        "fork side left",
        adapter.add_line(-fw, CENTER_DISTANCE, -fw, FORK_BASE_Y),
    )
    set_sketch_direct_db(adapter, False)
    for ent, relation in (
        (fork_root, "horizontal"),
        (fork_side_r, "vertical"),
        (fork_side_l, "vertical"),
    ):
        check(f"fork {relation}", adapter.add_sketch_constraint(ent, None, relation))
    check(
        "dimension fork width",
        adapter.add_sketch_dimension(fork_root, None, "linear", FORK_WIDTH),
    )
    fork_sd.record("ForkWidthDim", '"ForkWidth"')
    check(
        "dimension fork crown radius",
        adapter.add_sketch_dimension(fork_crown, None, "radial", fw),
    )
    fork_sd.record("ForkCrownR", '"ForkWidth" / 2')
    anchor_point_to_origin(
        adapter, f"{fork_crown}.center", 0.0, CENTER_DISTANCE, "fork crown centre"
    )
    fork_sd.record("ForkPinY", '"CenterDistance"')
    dimension_between(
        adapter,
        f"{fork_side_r}.start",
        f"{fork_side_r}.end",
        "vertical_distance",
        FORK_BASE_BELOW_PIN,
        "fork side length",
    )
    fork_sd.record("ForkSideLength", '"ForkBaseBelowPin"')
    dimension_between(
        adapter, f"{fork_side_r}.start", "origin", "horizontal_distance", fw,
        "fork side x",
    )
    fork_sd.record("ForkSideX", '"ForkWidth" / 2')
    ensure_fully_defined(adapter, "fork sketch")
    check("exit_sketch fork", adapter.exit_sketch())
    name_last_feature(adapter, "ForkProfile")
    drive_jobs += fork_sd.apply(adapter, "ForkProfile")
    check(
        "extrude fork",
        adapter.create_extrusion(
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
    volume_check(adapter, "ring, shank and fork bosses", v_expected, 0.002 * v_expected)

    # Fork slot: a Right-plane rectangle (sketch x = model -Z) centred on the
    # rod mid-plane, from the crotch up past the crown, cut through the fork's
    # width. Every side-view location runs from ONE finished face, the fork's
    # outer face at sketch +x (model -Z; the left face in the side view): a
    # construction line on that face, from the fork's root step to its crown
    # top, carries the boss length and the slot depth from the crown top, the
    # near tine (face to slot wall) and the near-face ordinate of the shank.
    # A short construction line on the shank's near face runs down the shank
    # from the root step, so its ordinate prints below the fork. The ring's
    # near face is located from the same datum face in its own sketch
    # (RingFaceReference, below), because the side view prints it and the
    # fork's detail prints these. Every reference is driven by the same knobs
    # as the solid features, so it always lies on the modelled face. Dim
    # EMISSION ORDER: face x and root height (general anchor, TWO dims), boss
    # length, slot width, cut height, near tine, slot depth, then the shank
    # face's ordinate and its run.
    # 16 DOF = face line: vertical + 2 anchor dims + boss length; rectangle:
    # four relations + 4 dims; the shank-face line: vertical + level with the
    # face line's root end + ordinate + run.
    slot_sd = SketchDims()
    check("create_sketch fork slot", adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    face_x = FORK_THICKNESS / 2.0
    face_ref = check(
        "fork face reference",
        adapter.add_centerline(face_x, FORK_BASE_Y, face_x, FORK_TOP_Y),
    )
    sh = FORK_SLOT_WIDTH / 2.0
    slot_rect = [
        (-sh, FORK_CROTCH_Y),
        (sh, FORK_CROTCH_Y),
        (sh, FORK_CROTCH_Y + SLOT_CUT_HEIGHT),
        (-sh, FORK_CROTCH_Y + SLOT_CUT_HEIGHT),
    ]
    slot = add_line_chain(adapter, slot_rect)
    shank_face = check(
        "shank face reference",
        adapter.add_centerline(
            SHANK_NEAR_X,
            FORK_BASE_Y,
            SHANK_NEAR_X,
            FORK_BASE_Y - SHANK_FACE_REF_RUN,
        ),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "fork face reference vertical",
        adapter.add_sketch_constraint(face_ref, None, "vertical"),
    )
    anchor_point_to_origin(
        adapter, f"{face_ref}.start", face_x, FORK_BASE_Y, "fork face reference"
    )
    slot_sd.record("ForkFaceX", '"ForkThickness" / 2')
    slot_sd.record("ForkRootY", '"ForkBaseY"')
    dimension_between(
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
            adapter.add_sketch_constraint(line, None, direction),
        )
    dimension_between(
        adapter, f"{slot[0]}.start", f"{slot[0]}.end", "horizontal_distance",
        FORK_SLOT_WIDTH, "slot width",
    )
    slot_sd.record("SlotWidth", '"ForkSlotWidth"')
    dimension_between(
        adapter, f"{slot[1]}.start", f"{slot[1]}.end", "vertical_distance",
        SLOT_CUT_HEIGHT, "slot cut height",
    )
    slot_sd.record(
        "SlotCutHeight", '"ForkWidth" / 2 + "ForkCrotchBelowPin" + "SlotRunout"'
    )
    # The near tine: the datum face to the slot's near wall, at the tine top.
    dimension_between(
        adapter, f"{face_ref}.end", f"{slot[0]}.end", "horizontal_distance",
        TINE_THICKNESS, "near tine",
    )
    slot_sd.record("TineNear", '"ForkTine"')
    dimension_between(
        adapter, f"{slot[0]}.start", f"{face_ref}.end", "vertical_distance",
        SLOT_DEPTH, "slot depth",
    )
    slot_sd.record("SlotDepth", '"ForkWidth" / 2 + "ForkCrotchBelowPin"')
    check(
        "ShankFaceNear reference vertical",
        adapter.add_sketch_constraint(shank_face, None, "vertical"),
    )
    check(
        "ShankFaceNear reference level with the fork root",
        adapter.add_sketch_constraint(
            f"{shank_face}.start", f"{face_ref}.start", "horizontal_points"
        ),
    )
    dimension_between(
        adapter, f"{face_ref}.start", f"{shank_face}.end", "horizontal_distance",
        SHANK_FACE_NEAR, "ShankFaceNear",
    )
    slot_sd.record("ShankFaceNear", '"ShankFaceNear"')
    dimension_between(
        adapter, f"{shank_face}.start", f"{shank_face}.end", "vertical_distance",
        SHANK_FACE_REF_RUN, "ShankFaceNear reference run",
    )
    slot_sd.record("ShankFaceNearRun")
    ensure_fully_defined(adapter, "fork slot sketch")
    check("exit_sketch fork slot", adapter.exit_sketch())
    name_last_feature(adapter, "ForkSlotProfile")
    drive_jobs += slot_sd.apply(adapter, "ForkSlotProfile")
    check(
        "cut fork slot",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ForkSlot")
    v_expected -= slot_volume()
    volume_check(adapter, "fork slot", v_expected, 0.01 * slot_volume() + 0.05)

    # Every other inside corner an R of this size can seat in gets the one
    # modelled radius, inside the title block's INSIDE CORNERS R.040 MAX,
    # which governs it on the print (ch_connecting_rod_spec): the two ledges
    # where the shank's faces meet the fork's root step, and the slot floor's
    # two corners. Each ledge fillet ends flush with the flanks' planes. The
    # two corners where a shank face meets the ring's OD stay sharp
    # (RING_STEPS). Points are model coordinates: model z is the Right-plane
    # sketch's -x.
    corner_edges = [
        [0.0, FORK_BASE_Y, -SHANK_NEAR_X],
        [0.0, FORK_BASE_Y, -SHANK_FAR_X],
        [0.0, FORK_CROTCH_Y, FORK_SLOT_WIDTH / 2.0],
        [0.0, FORK_CROTCH_Y, -FORK_SLOT_WIDTH / 2.0],
    ]
    check(
        "fillet inside corners",
        adapter.add_fillet(INSIDE_CORNER_R, corner_edges, propagate=False),
    )
    name_last_feature(adapter, "InsideCorners")
    corner_dim = name_dimensions(adapter, "InsideCorners", ["InsideCornerR"])
    drive_jobs.append((corner_dim[0], '"InsideCornerR"'))
    v_corners = inside_corner_volume()
    v_expected += v_corners
    volume_check(adapter, "inside corner fillets", v_expected, 0.1 * v_corners + 0.05)

    # ShankCorners: the shank's two flanks onto the ring's OD at the 1/8 in
    # end mill's R.065 (owner ruling 2026-11-23, tool audit Q9;
    # ch_connecting_rod_notes), through the shank's thickness. The right-hand
    # edge first: the printed 4X R.065 lands its leader there (FRONT_KEEP).
    # z = 0 lies on both edges, between the shank's two faces.
    shank_x = SHANK_WIDTH / 2.0
    junction_y = math.sqrt(RING_OUTER_RADIUS**2 - shank_x**2)
    check(
        "fillet shank corners",
        adapter.add_fillet(
            SHANK_CORNER_R,
            [[shank_x, junction_y, 0.0], [-shank_x, junction_y, 0.0]],
            propagate=False,
        ),
    )
    name_last_feature(adapter, "ShankCorners")
    shank_corner_dim = name_dimensions(adapter, "ShankCorners", ["ShankCornerR"])
    drive_jobs.append((shank_corner_dim[0], '"CornerR"'))
    v_corners = shank_corner_volume()
    v_expected += v_corners
    volume_check(adapter, "shank corner fillets", v_expected, 0.1 * v_corners + 0.05)

    # StepCorners: the shank's two flanks onto the fork's step at the same
    # radius. The step is narrower than the radius (FORK_STEP), so the 1/8 in
    # cutter, tangent to the flank, passes through the step's outer corner
    # (cam.py's outline): its arc runs from the flank straight onto that
    # corner and no step face is left, which a fillet cannot model. Each
    # corner is a region bossed through the shank's thickness: the flank from
    # the arc's tangent point up to the step, the step out to its outer
    # corner, and the arc back, its radius driven by the "CornerR" global
    # that ShankCorners carries. The regions are sketched on a plane at the
    # shank's mid-thickness (SHANK_MID_Z) and bossed mid-plane to the
    # shank's thickness, so their faces lie in the shank's; the ledge fillets
    # above stop at the flanks' planes, outside them. The sketch is mirror-
    # symmetric about the rod's axis. Dim EMISSION ORDER per region (right,
    # then left): the inside corner's x and y (general anchor, TWO dims), the
    # step's width, the arc's radius. 14 DOF = per region: flank vertical,
    # step horizontal, arc tangent to the flank + 4 dims.
    check(
        "create_plane ShankMidPlane",
        adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=SHANK_MID_Z
            )
        ),
    )
    name_last_feature(adapter, "ShankMidPlane")
    (shank_mid_dim,) = name_dimensions(adapter, "ShankMidPlane", ["ShankMidZ"])
    drive_jobs.append(
        (shank_mid_dim, '"ForkThickness" / 2 - "ShankFaceNear" - "ShankThickness" / 2')
    )
    step_sd = SketchDims()
    check("create_sketch step corners", adapter.create_sketch("ShankMidPlane"))
    tangent_y = FORK_BASE_Y - runout_rise(SHANK_CORNER_R, FORK_STEP)
    regions = []
    set_sketch_direct_db(adapter, True)
    for side, label, suffix in ((1.0, "right", "R"), (-1.0, "left", "L")):
        inside = (side * shank_x, FORK_BASE_Y)
        outer = (side * fw, FORK_BASE_Y)
        tangent = (side * shank_x, tangent_y)
        centre = (side * (shank_x + SHANK_CORNER_R), tangent_y)
        # add_arc runs anticlockwise start -> end.
        if side > 0.0:
            flank, step = add_line_chain(adapter, [tangent, inside, outer], close=False)
            arc = check(
                f"step corner {label} arc", adapter.add_arc(*centre, *outer, *tangent)
            )
            corner = f"{flank}.end"
        else:
            step, flank = add_line_chain(adapter, [outer, inside, tangent], close=False)
            arc = check(
                f"step corner {label} arc", adapter.add_arc(*centre, *tangent, *outer)
            )
            corner = f"{step}.end"
        regions.append((side, label, suffix, flank, step, arc, corner))
    set_sketch_direct_db(adapter, False)
    for side, label, suffix, flank, step, arc, corner in regions:
        for line, relation in ((flank, "vertical"), (step, "horizontal")):
            check(
                f"step corner {label} {relation}",
                adapter.add_sketch_constraint(line, None, relation),
            )
        check(
            f"step corner {label} arc tangent to the flank",
            adapter.add_sketch_constraint(arc, flank, "tangent"),
        )
        anchor_point_to_origin(
            adapter, corner, side * shank_x, FORK_BASE_Y, f"step corner {label}"
        )
        step_sd.record(f"StepCornerX{suffix}", '"ShankWidth" / 2')
        step_sd.record(f"StepCornerY{suffix}", '"ForkBaseY"')
        dimension_between(
            adapter, f"{step}.start", f"{step}.end", "horizontal_distance",
            FORK_STEP, f"step corner {label} step",
        )
        step_sd.record(f"StepWidth{suffix}", '("ForkWidth" - "ShankWidth") / 2')
        check(
            f"dimension step corner {label} radius",
            adapter.add_sketch_dimension(arc, None, "radial", SHANK_CORNER_R),
        )
        step_sd.record(f"StepCornerR{suffix}", '"CornerR"')
    ensure_fully_defined(adapter, "step corners sketch")
    check("exit_sketch step corners", adapter.exit_sketch())
    name_last_feature(adapter, "StepCornersProfile")
    drive_jobs += step_sd.apply(adapter, "StepCornersProfile")
    check(
        "extrude step corners",
        adapter.create_extrusion(
            ExtrusionParameters(depth=SHANK_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "StepCorners")
    (step_thick_dim,) = name_dimensions(adapter, "StepCorners", ["StepCornersThick"])
    drive_jobs.append((step_thick_dim, '"ShankThickness"'))
    blank_reference_geometry(adapter, (("ShankMidPlane", "PLANE"),))
    v_corners = step_corner_volume()
    v_expected += v_corners
    volume_check(adapter, "step corner bosses", v_expected, 0.1 * v_corners + 0.05)

    # Strap bore - rides the eccentric cam. On-axis circle: diameter only.
    bore_sd = SketchDims()
    check("create_sketch bore", adapter.create_sketch("Front"))
    define_circle(
        adapter, 0.0, 0.0, RING_BORE_DIA / 2.0, "strap bore", dims=bore_sd,
        names=("StrapBoreCx", "StrapBoreCz", "StrapBoreDia"),
        drives=(None, None, '"RingBoreDia"'),
    )
    ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", adapter.exit_sketch())
    name_last_feature(adapter, "StrapBoreProfile")
    drive_jobs += bore_sd.apply(adapter, "StrapBoreProfile")
    check(
        "cut strap bore",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "StrapBore")
    v_expected -= strap_bore_volume()
    volume_check(adapter, "strap bore", v_expected, 0.002 * v_expected)

    # Pivot pin hole on the rod axis, reamed through both tines (the slot
    # between them is air). The pin RUNS in the arm's #47 hole and is PRESSED
    # here, its ends dressed flush (sh_vn_pivot_pin_rod_spec). No countersink: the
    # hole runs straight through each tine, so the pin bears on the whole tine.
    pin_hole = SketchDims()
    check("create_sketch rocker pin hole", adapter.create_sketch("Front"))
    define_circle(
        adapter,
        0.0,
        CENTER_DISTANCE,
        PIN_HOLE_DIA / 2.0,
        "rocker pin hole",
        dims=pin_hole,
        names=(None, "PinHoleY", "PinHoleDia"),
        drives=(None, '"CenterDistance"', '"PinHoleDia"'),
    )
    ensure_fully_defined(adapter, "rocker pin hole sketch")
    check("exit_sketch rocker pin hole", adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin_hole.apply(adapter, "PinHoleProfile")
    check(
        "cut rocker pin hole",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinHole")
    v_pin = pin_hole_volume()
    v_expected -= v_pin
    v_built = volume_check(
        adapter, "pin hole through both tines", v_expected, 0.03 * v_pin + 0.05
    )

    # RingFaceReference: the ring's near face from the fork's datum face, in
    # a sketch of its own on the Right plane (sketch x = model -Z) that no
    # feature consumes. The side view prints this one ordinate at the ring and
    # imports this sketch alone; the fork's detail imports ForkSlotProfile
    # alone. Two construction lines, each lying on a face's edge in the side
    # view: one on the datum face, running up it from the fork's root step,
    # and one on the ring's near face, running down the ring's wall to the
    # ring's bottom. The ordinate runs from the datum line's root end to the
    # ring line's bottom end, so one witness drops from the fork's root corner
    # and the other from the ring's bottom corner. Dim EMISSION ORDER: datum
    # face x and root height (general anchor, TWO dims), the datum line's run,
    # the ring face's ordinate, its bottom end's depth below the bore axis and
    # its run. 8 DOF = two lines, each vertical + 3 dims.
    ring_ref = SketchDims()
    check("create_sketch ring face reference", adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    datum_face = check(
        "datum face reference",
        adapter.add_centerline(
            face_x, FORK_BASE_Y, face_x, FORK_BASE_Y + DATUM_FACE_REF_RUN
        ),
    )
    ring_face = check(
        "ring face reference",
        adapter.add_centerline(
            RING_THICKNESS / 2.0,
            RING_WALL - RING_OUTER_RADIUS,
            RING_THICKNESS / 2.0,
            -RING_OUTER_RADIUS,
        ),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "datum face reference vertical",
        adapter.add_sketch_constraint(datum_face, None, "vertical"),
    )
    anchor_point_to_origin(
        adapter, f"{datum_face}.start", face_x, FORK_BASE_Y, "datum face reference"
    )
    ring_ref.record("DatumFaceX", '"ForkThickness" / 2')
    ring_ref.record("DatumRootY", '"ForkBaseY"')
    dimension_between(
        adapter, f"{datum_face}.start", f"{datum_face}.end", "vertical_distance",
        DATUM_FACE_REF_RUN, "datum face reference run",
    )
    ring_ref.record("DatumFaceRun")
    check(
        "RingFaceNear reference vertical",
        adapter.add_sketch_constraint(ring_face, None, "vertical"),
    )
    dimension_between(
        adapter, f"{datum_face}.start", f"{ring_face}.end", "horizontal_distance",
        RING_FACE_NEAR, "RingFaceNear",
    )
    ring_ref.record("RingFaceNear", '"RingFaceNear"')
    dimension_between(
        adapter, f"{ring_face}.end", "origin", "vertical_distance",
        RING_OUTER_RADIUS, "RingFaceNear reference bottom",
    )
    ring_ref.record("RingFaceNearBottom", '"RingOuterRadius"')
    dimension_between(
        adapter, f"{ring_face}.start", f"{ring_face}.end", "vertical_distance",
        RING_WALL, "RingFaceNear reference run",
    )
    ring_ref.record("RingFaceNearRun", '"RingWall"')
    ensure_fully_defined(adapter, "ring face reference sketch")
    check("exit_sketch ring face reference", adapter.exit_sketch())
    name_last_feature(adapter, "RingFaceReference")
    drive_jobs += ring_ref.apply(adapter, "RingFaceReference")

    # Named bore axes for assembly mates (view-independent name selection):
    # Axis1 = strap bore on the cam (origin), Axis2 = pivot pin bore (0, CD).
    name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "strap bore")
    name_bore_axis(
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
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(
        adapter, "driven connecting rod (equations neutral)", v_built, 0.001 * v_built
    )
    # Saved shown, the reference lines would print in every assembly render
    # (#880); the drawing shows the sketch in its side view to import its
    # ordinate (_drawing_hidden_sketches).
    blank_reference_sketches(adapter, ("RingFaceReference",))
    # The bands are millimetres; UNIT prints them in inches.
    set_dimension_bilateral_tolerance(
        adapter,
        "StrapBoreProfile",
        "StrapBoreDia",
        *deviations(RING_BORE_DIA_BAND),
        display_unit=UNIT,
    )
    # The fork straddles the rocker strap inside one station pitch (Main
    # ruling 2026-10, option b), and the ring slides in its cam slot and
    # carries the fork, and the arm with it, along the bank (#3114,
    # test_channel_axial_budget): the near tine, the slot and the ring's near
    # face print natively, located from the fork's datum face, and the ring's
    # thickness at the ring, each band symmetric so it prints +/-. The fork
    # over the tines is a reference (two tines and the slot set it). The
    # shank's near face and thickness carry no model band: they print at
    # two places and take the title block's .XX
    # (ch_connecting_rod_spec.SHANK_FACE_BAND, SHANK_THICKNESS_BAND).
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
        adapter, "RingFaceReference", "RingFaceNear", face_upper, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "Ring", "RingThick", thick_upper, display_unit=UNIT
    )
    # The reamed press hole prints the .0775 reamer's size and no band (owner
    # ruling 2026-11-24, fit audit question 3): the pin is its gauge (note 1).
    # Its four places come from DRAWING_PRECISION.
    apply_drawing_precision(adapter, DRAWING_PRECISION)

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The one printed shank corner stands for all four (4X R.065).
    for (feature_name, dimension_name), prefix in DIMENSION_PREFIXES.items():
        set_dimension_prefix(adapter, feature_name, dimension_name, prefix)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "Manufacturing Notes": DRAWING_NOTES,
        },
    )
    artefacts = save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number", "Material Specification", "Finish", "Quantity",
            "Isometric View Note", "Manufacturing Notes",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
