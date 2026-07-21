r"""Reproduction script: magnifier subassembly (book ch. 20-21).

The amplification stage: the magnifying lever takes the summing lever's tiny
motion and the magnifying wheel multiplies it again (via the wire to the pen),
in machine coordinates (assembly origin = base origin; the output side is -Z).

* magnifying-bracket -- the fitting that AFFIXES the lever rod to the pivoted
  summing bar, so it RIDES the lever (locked, like the clamp chain), its collar
  carrying the rod (Ø6.2 over Ø6) concentrically at every rock angle. The
  lever EXTENDS FROM the pivoted summing bar and pivots WITH it about the
  knife-edge ridge line (engineerguy video 2/4 + 4/4; tip arc ~6 mm), so its
  one DOF is the rock about that Z line; the clamp + thumb screw + vertical rod
  + output-fixture ride the lever as one rigid body at the set magnification
  radius -- the radius from the KNIFE EDGE is what the sliding clamp adjusts
  (<=4x) -- and the output fixture is where WIRE 1 to the wheel hub hooks.
* wheel-bar (HALF-width, clamped at ONE column with a free end past the pen
  hanger) + its two-piece column clamp (front/back arcs + two clamp screws --
  the platen support bar's clamp, ch30 p005).
* wheel-axle (structure) carrying the magnifying-wheel, which spins on its stud
  (revolute); the wheel rim drives the pen rod via WIRE 2 (pen.SLDASM).
* lever-wire -- WIRE 1's straight rest-pose run from the output fixture's cross
  hole down to the hub-groove tangent. It ARTICULATES like the real wire: a
  ball joint at the hook (HookPoint on the wire coincident to the fixture's
  HookAnchorPoint) plus a 0.25 face-face stand-off tangency to the hub drum,
  so the hook end follows the lever while the hub end hugs the groove (its two
  residual DOF, swing + spin, are freed operational DOF). Its YokePlane
  carries the WIRE-1 COUPLING mate: the wheel's WireYokePoint held coincident
  to it ties the wheel's spin to the wire's travel along its own axis (the
  linearized inextensible-wire constraint), so with every freed DOF genuinely
  free, dragging the lever swings the clamp/rod/fixture group, the wire
  pivots at the hook staying on the hub, and the wheel turns: a working
  kinematic chain, pivoted where the book pivots it.

Cross-subassembly fits (checked at the top level): the column-clamp arcs ride
the O25.4 column (frame.SLDASM); the pen-hanger (pen.SLDASM) clamps the
wheel-bar, and the wheel rim -> pen-rod wire couples this sub to the pen.

Documented simplifications (Appendix C): the magnifying clamp's thumb screw is
modeled backed-out (the tip is tangent to the lever rod -- a seated screw would
overlap it); the output fixture's clamp screw is omitted (its cross hole doubles
as the wire hook); the wires are modeled as straight rest-pose rods only
(lever-wire here, pen-wire in pen.SLDASM) -- hub/rim wraps, hooks and compliance
are not, and the kinematic couplings stay Motion-study mates
(docs/motion-policy.md), so each run stands 0.25 off its wheel surface.

Fix-all strategy (M6.2): every structural component inserted at its exact final
transform and fixed; the lever + bracket + wheel + wire are left free and
constrained by mates; transforms asserted by read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 20-21.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_magnifier_assembly.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    apply_custom_properties,
    apply_summary_info,
    check,
    part_properties,
    run_build,
)
from _drawing_marks import DRAWN_BY
from _assembly import (
    angle_driver,
    assert_component_placed,
    assert_free_dof_necessity,
    assert_pattern_targets,
    check_no_interference,
    coincident_mate,
    component_named_ref,
    component_origin,
    distance_driver,
    linear_component_pattern,
    lock_mate,
    named_ref,
    PatternDirection,
    place_component,
    reset_dof_manifest,
    save_assembly_and_images,
    write_dof_manifest,
)
from _transforms import (
    IDENTITY,
    ROT_X_NEG90,
    ROT_Y_180,
    ROT_Y_POS90,
    compose_rows,
    euler_from_rows,
    rot_z_rows,
)

ASM_NAME = "magnifier"

# --- machine anchors ---------------------------------------------------------
WHEEL_BAR_Y = 575.7  # ch30 p002 front-view re-anchor (2026-07-17): the wheel
# + bar + column clamps sit 10.7 higher than the old 565.0 -- the photo shows
# the rim clearing the platen box top, which 565.0 left overlapped
COLUMN_X = 197.0  # the WEST column (machine +x is west; the crank side -x is east)
COLUMN_Z = -112.0
# Depth chain -- the SAME two-piece clamp seat as the platen support bar
# (paper-drive PR #196 E2): the front arc's front face (-129.9) carries the
# bar's back face; the bar's front face lands on the shared -138.9 plane, so
# the wheel/axle/wire/pen line is untouched by the clamp swap.
from _clamp_arc import EAR_HOLE_Z as CLAMP_EAR_DX  # noqa: E402
from column_clamp_front_geom import ARC_DEPTH as ARC_FRONT_DEPTH  # noqa: E402
from wheel_bar_geom import (  # noqa: E402
    BAR_DEPTH as WHEEL_BAR_DEPTH,
    CLAMP_HOLE_X as BAR_CLAMP_HOLE_LOCAL_X,
)

BAR_BACK_Z = COLUMN_Z - ARC_FRONT_DEPTH  # -129.9
BAR_FRONT_Z = BAR_BACK_Z - WHEEL_BAR_DEPTH  # -138.9: bar front = platen-back plane
BAR_Z = (BAR_FRONT_Z + BAR_BACK_Z) / 2.0  # -134.4 bar centre

# --- magnifying group --------------------------------------------------------
# Rod at the plate centreline (990) so it is coplanar with the coefficients plate
# (raised from 985); the bracket flange butts the plate front face. The clamp +
# vertical rod ride up with it (CLAMP_POS and VROD_TOP_Y derive from LEVER_ROD_Y).
LEVER_ROD_Y = 990.0
# DEPTH RE-ANCHOR (2026-07-04): the ch30 p.4 side view shows the whole output
# line (fixture wire, wheel, rim wire, pen rod) as ONE plumb vertical at the
# machine front -- the old z -85 (M6.4, low) hung the wire hook 50 behind the
# wheel plane, an ~8 deg lean the photo refutes. -128.3 is the ONLY window:
# the thumb-screw head (top y 1010, pokes above the top-frame ring bottom
# 999.7) must clear the ring's front rail z -101..-123 (=> <= -128.25), the
# lever rod must clear the front column surface -124.7 (=> <= -127.95), and
# the lever-wire's rim-duck route caps the hook at ~-137.96 (=> >= -128.31).
# VROD_Z = -134.8 (clamp's 6.5 skew bore); wire hook -137.95; the bracket arm
# reaches back to the unchanged plate flange (build_magnifying_bracket).
LEVER_ROD_Z = -128.3
LEVER_X0 = 200.0  # lever part origin (rod west dome tip; rod spans +35..+200,
# placed Ry(180) so the part's local +x runs east toward the summing knife)

# Knife-edge pivot (engineerguy video 2/4 + 4/4): the lever rod EXTENDS FROM
# the pivoted summing bar and pivots WITH it about the knife-edge ridge line
# (along Z) -- it does NOT spin in the bracket collar (a loose Ø6.2/Ø6 guide).
# The ridge is the summing sub's knife line; assert the lever part's local
# KnifeAxis lands exactly on it, so a knife move fails loud here.
from magnifying_lever_geom import KNIFE_LOCAL_X, KNIFE_LOCAL_Y  # noqa: E402
from build_summing_assembly import KNIFE, KNIFE_CONTACT_Y  # noqa: E402

# The lever is placed Ry(180) (local +x -> machine -x), so the knife lands at
# LEVER_X0 - KNIFE_LOCAL_X.
assert math.isclose(LEVER_X0 - KNIFE_LOCAL_X, KNIFE[0], abs_tol=1e-9), \
    "magnifying-lever KnifeAxis x drifted from the summing knife line"
assert math.isclose(LEVER_ROD_Y + KNIFE_LOCAL_Y, KNIFE_CONTACT_Y, abs_tol=1e-9), \
    "magnifying-lever KnifeAxis y drifted from the knife-edge contact ridge"
CLAMP_X = 150.0  # sliding clamp default position (p.46/48 insets)
from magnifying_clamp_geom import (  # noqa: E402
    BLOCK_DEPTH as CLAMP_DEPTH,
    LEVER_BORE_Y as CLAMP_BORE_Y,
    ROD_BORE_X as CLAMP_ROD_DX,
)

CLAMP_POS = (
    CLAMP_X - CLAMP_DEPTH / 2.0,  # local z 0..12 -> machine x (Ry+90)
    LEVER_ROD_Y - CLAMP_BORE_Y,
    LEVER_ROD_Z,
)
VROD_Z = LEVER_ROD_Z - CLAMP_ROD_DX  # -134.8 (local +x -> machine -z)
VROD_TOP_Y = LEVER_ROD_Y + 5.0  # dome inside the clamp's rod bore (rides the rod)
FIXTURE_Y0 = 926.0  # collar y 926..934 on the vertical rod

# --- wheel -------------------------------------------------------------------
WHEEL_X = 53.0
WHEEL_BAR_X0 = 109.0  # wheel-bar centre: span -8 .. +226 (29 past the west column)
# Clamp screws flank the column line, closing the stack bar -> front arc ->
# back arc with heads on the bar's front face (ch30 p002 / support-bar idiom).
# (west screw first -- keeps the component instance order of the mirrored-era
# build, so the pose-equivalence diff matches instances by name)
CLAMP_SCREW_X = (COLUMN_X + CLAMP_EAR_DX, COLUMN_X - CLAMP_EAR_DX)
# The bar's clamp holes must land on those screw lines: the bar is placed at
# IDENTITY, so book hole x = centre + local station.
assert sorted(
    round(WHEEL_BAR_X0 + lx, 6) for lx in BAR_CLAMP_HOLE_LOCAL_X
) == sorted(round(x, 6) for x in CLAMP_SCREW_X), \
    "wheel-bar clamp holes drifted off the column clamp-screw lines"
from build_wheel_axle import FLANGE_LEN, STUD_LEN  # noqa: E402

WHEEL_MID_Z = BAR_FRONT_Z - FLANGE_LEN - (STUD_LEN - 4.0) / 2.0  # -146.9:
# the 10-wide hub sits flush between the flange face and the tip collar

# --- amplification wire 1 (fixture -> hub) -----------------------------------
# Endpoints + length live in build_lever_wire.py (the part's length IS the run);
# re-derive the anchors from THIS script's layout and fail loud on drift, so a
# layout move can never leave a floating wire.
from lever_wire_geom import (  # noqa: E402
    CLEARANCE as WIRE_CLEARANCE,
    WIRE_DIA as HUB_WIRE_DIA,
    WIRE_END as HUB_WIRE_END,
    WIRE_START as HUB_WIRE_START,
)
from magnifying_wheel_geom import HUB_DIA, SPOKE_AXIAL  # noqa: E402

# Hook = tied through the cross hole, hanging under the collar's bottom face
# (wire r + 0.25) on the front face of the vertical rod (Ø5 rod r 2.5 +
# wire r + 0.25).
_HOOK_EXPECTED = (
    CLAMP_X,
    FIXTURE_Y0 - (HUB_WIRE_DIA / 2.0 + WIRE_CLEARANCE),
    VROD_Z - (2.5 + HUB_WIRE_DIA / 2.0 + WIRE_CLEARANCE),
)
assert all(
    math.isclose(a, b, abs_tol=1e-9)
    for a, b in zip(HUB_WIRE_START, _HOOK_EXPECTED, strict=True)
), f"lever-wire hook {HUB_WIRE_START} drifted from the fixture anchor {_HOOK_EXPECTED}"
# The run grazes the hub groove at the 0.25 stand-off tangent ...
assert math.isclose(
    math.hypot(HUB_WIRE_END[0] - WHEEL_X, HUB_WIRE_END[1] - WHEEL_BAR_Y),
    HUB_DIA / 2.0 + HUB_WIRE_DIA / 2.0 + WIRE_CLEARANCE,
    abs_tol=1e-9,
), "lever-wire end is not tangent to the hub groove"
# ... inside the clear axial lane between the axle flange back face and the
# spoke front faces (else the slanted run clips the flange or a spoke).
assert (
    BAR_FRONT_Z - FLANGE_LEN
    > HUB_WIRE_END[2]
    > WHEEL_MID_Z + SPOKE_AXIAL / 2.0 + HUB_WIRE_DIA / 2.0
), "lever-wire end z outside the flange..spoke clear lane"


def _lever_wire_rows() -> list[list[float]]:
    """Rotation rows turning the part's +Y (wire axis) onto the HUB->HOOK
    direction (the part origin is the hub end -- its Top/YokePlane sit at the
    tangency); X' is the horizontal perpendicular, Z' = X' x Y' (proper)."""
    delta = [s - e for s, e in zip(HUB_WIRE_START, HUB_WIRE_END, strict=True)]
    length = math.hypot(*delta)
    d = [v / length for v in delta]
    n = math.hypot(d[0], d[1])
    x = [d[1] / n, -d[0] / n, 0.0]
    z = [
        x[1] * d[2] - x[2] * d[1],
        x[2] * d[0] - x[0] * d[2],
        x[0] * d[1] - x[1] * d[0],
    ]
    return [x, d, z]


# Wire articulation geometry (ball joint + hub stand-off, see build()). The
# stand-off is an AXIS-AXIS distance (wire centreline Axis1 <-> wheel Axis1 at
# the offset-tangency radius): skew lines have ONE minimal distance, so there
# is no far-side flip, and name selection survives solver motion -- a
# point-picked FACE self-destructs the moment flip-recovery moves the wire
# (caught live: "Failed to select mate entity 1 (FACE at ...)" on re-add).
# Free-DOF drive formulations, re-derived after BOTH original plane-plane
# angle drivers turned out Jacobian-singular (closure-replay catch, 2026-07-05):
# the SWING angle sat at 0.74 deg -- an angle to a fixed plane is a CONE
# of orientations, and that close to the apex it pins nothing -- and the SPIN
# angle (Right@wire vs Right, 13.4 deg) had its gradient PERPENDICULAR to the
# spin DOF: the wire's Right normal is built horizontal, so spinning about
# the near-vertical wire axis tips it out-of-plane first-order and the
# in-plane angle is stationary. Both authored satisfied; neither pinned.
# Now: SWING pins the hub-end point's depth (distance -- lever arm = the
# whole wire); SPIN pins angle(Front@wire, RIGHT plane): that normal is
# ~vertical, so the spin gradient is ~parallel to the wire axis
# (sensitivity ~0.97, exactly the direction the other rows leave free) and
# the rest value ~89.8 deg is far from the 0/180 cone apex.
_HW_ROWS = _lever_wire_rows()
_STANDOFF_R = HUB_DIA / 2.0 + HUB_WIRE_DIA / 2.0 + WIRE_CLEARANCE  # 10.65
_WIRE_SPIN_ANGLE = math.degrees(math.acos(min(1.0, abs(_HW_ROWS[2][0]))))


async def build(adapter) -> dict[str, str]:
    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())

    # --- wheel bar + clamp ---------------------------------------------------
    # FIRST so the auto-fixed assembly seed is structure, not the mated lever
    # (the bracket -- the old first insert -- now RIDES the lever, see below).
    # Magnifying-wheel bar: HALF-width (every ch30 plate shows it clamped
    # at ONE column with a free end just past the pen hanger -- M6.8
    # 8-view pass). Span -8..+192 covers the axle (+53) and the hanger
    # strap top (+3..+19).
    wheel_bar = await place_component(
        adapter,
        "wheel-bar",
        [WHEEL_BAR_X0, WHEEL_BAR_Y, BAR_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
    )
    # Two-piece clamp at the west column -- the SAME black arcs as the platen
    # support bar (ch30 p005 / paper-drive PR #196 E2): the front arc's face
    # carries the bar's back face, the back arc closes on the column, and two
    # clamp screws (heads on the bar's front face, ch30 p002) close the stack
    # bar -> front arc -> back arc. Ry(+90): the arcs' local +X faces machine -Z.
    for arc in ("column-clamp-front", "column-clamp-back"):
        await place_component(adapter, arc, [COLUMN_X, WHEEL_BAR_Y, COLUMN_Z],
                              [0.0, 90.0, 0.0], ROT_Y_POS90,
                              label=f"{arc} (wheel x{COLUMN_X:.0f})")
    # One physically mated seed plus a native component pattern.  Seed at the
    # lower-X hole so PatternAxisX FORWARD lands the generated instance on the
    # second Hole Wizard station; both stations derive from the same bar
    # constants. The exact rigid pose is held by one lock mate.
    seed_x, patterned_x = sorted(CLAMP_SCREW_X)
    seed_target = [seed_x, WHEEL_BAR_Y, BAR_FRONT_Z]
    clamp_seed = await place_component(
        adapter,
        "clamp-screw",
        seed_target,
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label=f"clamp-screw seed (wheel x{seed_x:+.1f})",
    )
    await lock_mate(
        adapter,
        named_ref(f"Right Plane@{clamp_seed}", "PLANE"),
        named_ref(f"Right Plane@{wheel_bar}", "PLANE"),
        label="wheel clamp-screw seed fixed to bar",
    )
    assert_component_placed(adapter, clamp_seed, seed_target, IDENTITY)
    clamp_instances = await linear_component_pattern(
        adapter,
        [clamp_seed],
        axis="x",
        spacing_mm=patterned_x - seed_x,
        instances=2,
        direction=PatternDirection.REVERSE,
        label="wheel clamp-screw pattern",
    )
    assert_pattern_targets(
        adapter,
        clamp_instances,
        [[patterned_x, WHEEL_BAR_Y, BAR_FRONT_Z]],
        IDENTITY,
        "wheel clamp-screw pattern",
    )

    # --- magnifying group ----------------------------------------------------
    # The lever pivots about the summing bar's knife-edge ridge (see the
    # knife-pivot block above); the rock drive spec uses the Top-plane angle
    # (Y-normal, mirror-invariant -> no flip).
    ml = await place_component(adapter, "magnifying-lever",
                               [LEVER_X0, LEVER_ROD_Y, LEVER_ROD_Z],
                               [0.0, 180.0, 0.0], ROT_Y_180, ground=False)
    ml_o = component_origin(adapter, ml)
    # Knife-edge pivot: the lever's KnifeAxis (Axis2, local Z through the
    # summing knife-edge ridge) held by two axis-to-plane distances (the
    # pen-rod idiom -- parallelism + position, no rotational overlap), depth
    # pinned on the Front plane. The one remaining DOF -- the rock about the
    # knife line, the ~6 mm tip arc of video 2/4|4/4 -- is the sub's FREED
    # operational DOF: its drive spec is recorded into the DOF manifest, never
    # authored -- the lever and everything clamped to it swings about the
    # knife line, and the WIRE-1 yoke below turns the wheel with it. Same
    # mechanism as drive-train's crank spin. The bracket collar stays a loose
    # visual guide.
    await distance_driver(adapter, named_ref(f"Axis2@{ml}", "AXIS"),
                          named_ref("Right Plane", "PLANE"), abs(KNIFE[0]),
                          label="mag-lever knife line across", verify=(ml, ml_o))
    await distance_driver(adapter, named_ref(f"Axis2@{ml}", "AXIS"),
                          named_ref("Top Plane", "PLANE"), KNIFE_CONTACT_Y,
                          label="mag-lever knife line height", verify=(ml, ml_o))
    await distance_driver(adapter, named_ref(f"Front Plane@{ml}", "PLANE"),
                          named_ref("Front Plane", "PLANE"), abs(LEVER_ROD_Z),
                          label="mag-lever depth", verify=(ml, ml_o))
    await angle_driver(adapter, named_ref(f"Top Plane@{ml}", "PLANE"),
                       named_ref("Top Plane", "PLANE"), 0.0,
                       label="mag-lever rock PARK driver (freed in default build)",
                       verify=(ml, ml_o), free_dof_key="lever_rock")
    # Bracket: the fitting that AFFIXES the lever rod to the (rocking) summing
    # bar -- it rides the lever, not the frame, so it is LOCKED to the lever
    # like the clamp chain below (grounding it made the free lever rock clip
    # the collar: the rod sweeps ~0.7 mm at the collar over the ~1.6 deg rock,
    # far past the 0.1 radial slack). Its collar stays the rod's snug carrier
    # (Ø6.2 over Ø6), now exactly concentric at every rock angle.
    bracket = await place_component(adapter, "magnifying-bracket",
                                    [40.0, LEVER_ROD_Y, LEVER_ROD_Z],
                                    [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{bracket}", "PLANE"),
                    named_ref(f"Front Plane@{ml}", "PLANE"),
                    label="mag-bracket locked to lever")
    # The clamp + vertical rod + output fixture + thumb screw are clamped to the
    # lever at the set magnification radius (the thumb screw locks the clamp on
    # the rod): they ride the lever as one rigid body. The output fixture is
    # where WIRE 1 to the wheel hub hooks -- its (mostly vertical) travel as the
    # lever rotates is what drives the magnifying wheel in the Motion study, so
    # these must move WITH the lever, not stay fixed. Lock each to the lever.
    # Ry(+90): the clamp's lever bore (local Z) turns onto the rod axis (X).
    clamp = await place_component(adapter, "magnifying-clamp", list(CLAMP_POS),
                                  [0.0, 90.0, 0.0], ROT_Y_POS90, ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{clamp}", "PLANE"),
                    named_ref(f"Front Plane@{ml}", "PLANE"),
                    label="mag-clamp locked to lever")
    # Backed-out thumb screw: shank tip tangent to the rod top (a seated
    # screw would overlap the rod it pinches -- see module docstring). Rz(-90)
    # points the shank down the clamp bore; the extra Ry(180) turns its head
    # features to the machine hand ([180, 0, -90] is the same rotation's Euler
    # form).
    _rz90_ry180 = compose_rows(rot_z_rows(-90.0), ROT_Y_180)
    tscrew = await place_component(adapter, "thumb-screw",
                                   [CLAMP_X, LEVER_ROD_Y + 3.0 + 12.0 + 5.0, LEVER_ROD_Z],
                                   [180.0, 0.0, -90.0], _rz90_ry180, ground=False,
                                   label="thumb-screw (clamp)")
    await lock_mate(adapter, named_ref(f"Front Plane@{tscrew}", "PLANE"),
                    named_ref(f"Front Plane@{clamp}", "PLANE"),
                    label="thumb-screw locked to clamp")
    vrod = await place_component(adapter, "magnifying-vertical-rod",
                                 [CLAMP_X, VROD_TOP_Y, VROD_Z],
                                 [180.0, 0.0, -90.0], _rz90_ry180, ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{vrod}", "PLANE"),
                    named_ref(f"Front Plane@{clamp}", "PLANE"),
                    label="vertical-rod locked to clamp")
    fixture = await place_component(adapter, "output-fixture",
                                    [CLAMP_X, FIXTURE_Y0, VROD_Z],
                                    [0.0, 0.0, 0.0], IDENTITY, ground=False)
    # (the fixture is x-symmetric about its origin, so it stays at IDENTITY)
    await lock_mate(adapter, named_ref(f"Front Plane@{fixture}", "PLANE"),
                    named_ref(f"Front Plane@{vrod}", "PLANE"),
                    label="output-fixture locked to vertical-rod")

    # --- magnifying wheel ----------------------------------------------------
    # Rx(-90): the axle's +Y axis points -Z (flange on the bar front face).
    # The axle is structure (fixed); the wheel spins on its stud (revolute).
    ax = await place_component(adapter, "wheel-axle",
                               [WHEEL_X, WHEEL_BAR_Y, BAR_FRONT_Z],
                               [-90.0, 0.0, 0.0], ROT_X_NEG90)
    wh = await place_component(adapter, "magnifying-wheel",
                               [WHEEL_X, WHEEL_BAR_Y, WHEEL_MID_Z], [0.0, 0.0, 0.0],
                               IDENTITY, ground=False)
    wh_o = component_origin(adapter, wh)
    # Revolute: radial coincident (wheel axis Z || axle stud Z) + axial
    # distance(Front, |z|); the spin -- the old angle(Right, 0) rock snapshot --
    # is now pinned by the WIRE-1 yoke below, coupling it to the lever.
    await coincident_mate(adapter, named_ref(f"Axis1@{wh}", "AXIS"),
                          named_ref(f"Axis1@{ax}", "AXIS"),
                          label="magnifying-wheel pivot", verify=(wh, wh_o))
    await distance_driver(adapter, named_ref(f"Front Plane@{wh}", "PLANE"),
                          named_ref("Front Plane", "PLANE"), abs(wh_o[2]),
                          label="magnifying-wheel axial", verify=(wh, wh_o))
    # --- amplification wire 1 (fixture -> hub) -------------------------------
    # The straight rest-pose run: it hangs from the fixture's cross hole and
    # grazes the hub-groove tangent (the wrap is implied -- module docstring).
    # Locked to the output fixture so it rides the lever group, like the rest
    # of the clamped chain. Part origin = the HUB end, +Y toward the hook.
    hw = await place_component(adapter, "lever-wire", list(HUB_WIRE_END),
                               euler_from_rows(_HW_ROWS), _HW_ROWS, ground=False)
    hw_o = component_origin(adapter, hw)
    # The wire ARTICULATES instead of riding the lever group rigidly (a locked
    # wire's hub tip would sweep a ~10 mm lateral arc off the hub even over
    # the real ~1.6 deg knife rock -- user-flagged): a BALL JOINT at the hook
    # (the wire's HookPoint coincident to the fixture's HookAnchorPoint) plus
    # the 0.25 face-face stand-off to the hub drum (the offset tangency the
    # rest geometry is built at), so the hook end follows the lever while the
    # hub end hugs the groove; the tip only creeps along its own axis (the
    # unmodeled wrap's pay-in/pay-out). Ref POINTs select via GetCorresponding
    # -- they do not resolve through name@comp strings.
    await coincident_mate(adapter, component_named_ref(hw, "HookPoint", "POINT"),
                          component_named_ref(fixture, "HookAnchorPoint", "POINT"),
                          label="lever-wire hook ball joint", verify=(hw, hw_o))
    await distance_driver(
        adapter, component_named_ref(hw, "Axis1", "AXIS"),
        component_named_ref(wh, "Axis1", "AXIS"), _STANDOFF_R,
        label="lever-wire hub stand-off tangency", verify=(hw, hw_o))
    # The wire's two residual DOF (swing across the tangency family + spin
    # about its own axis) are freed operational DOF: each drive spec is
    # recorded into the DOF manifest, never authored. SWING pins the HUB-end
    # point's depth (the swing sweeps the hub end front-back on the tangency
    # family; the lever arm is the whole wire, so the driver has first-order
    # authority everywhere -- unlike the rest plane-plane angle, 0.74 deg = a
    # Jacobian extremum that authored satisfied but pinned NOTHING;
    # closure-replay catch 2026-07-05).
    await distance_driver(
        adapter, component_named_ref(hw, "HubPoint", "POINT"),
        named_ref("Front Plane", "PLANE"), HUB_WIRE_END[2],  # SIGNED (hub z<0):
        # distance_driver abs()es the mate value but needs the sign to seed the
        # side; the recorded spec then carries the right flip so the transient
        # replay is flip-free (was abs() -> far-side error-47 add + recovery)
        label="lever-wire swing PARK driver (hub depth, freed in default build)",
        verify=(hw, hw_o), free_dof_key="wire_swing")
    await angle_driver(adapter, named_ref(f"Front Plane@{hw}", "PLANE"),
                       named_ref("Right Plane", "PLANE"), _WIRE_SPIN_ANGLE,
                       label="lever-wire spin PARK driver (freed in default build)",
                       verify=(hw, hw_o), free_dof_key="wire_spin")

    # WIRE-1 coupling (replaces the old wheel rock snapshot): the wheel's
    # WireYokePoint (hub pitch circle @ the wire tangency) held coincident to
    # the lever-wire's YokePlane (perpendicular to the wire axis). The wheel's
    # spin -- its one remaining DOF -- is thereby tied to the lever group's
    # travel along the wire: the linearized inextensible-wire constraint, sign
    # and ratio from geometry (build_lever_wire docstring). With every freed
    # DOF genuinely free, dragging the lever turns the wheel. The mate is
    # residual-free at the rest pose, so the wheel must NOT move when it
    # solves -- asserted right after.
    # component_named_ref, not a name@comp string: a reference POINT does not
    # resolve through SelectByID2 string selection -- the GetCorresponding path
    # is how the Motion study selects its rim RefPoint too.
    await coincident_mate(adapter, component_named_ref(wh, "WireYokePoint", "POINT"),
                          named_ref(f"YokePlane@{hw}", "PLANE"),
                          label="WIRE1 yoke fixture->wheel", verify=(wh, wh_o))
    assert_component_placed(
        adapter, wh, [WHEEL_X, WHEEL_BAR_Y, WHEEL_MID_Z], IDENTITY)

    # Certify the AS-BUILT model. THREE freed operational DOF: the lever's
    # knife rock + the wire's swing/spin (all recorded into the DOF manifest
    # above, never authored); the yoke-coupled wheel must also read
    # under-constrained WITH them, else the coupling died -- and so must the
    # lock-mated bracket (a regression to grounded would re-create the collar
    # clipping this rework fixed).
    assert_free_dof_necessity(
        adapter, 3,
        required_stems=("magnifying-lever", "magnifying-wheel", "lever-wire",
                        "magnifying-bracket"))
    write_dof_manifest(ASM_NAME)
    check_no_interference(adapter)
    # Title-block identity for the assembly drawing (draw_magnifier_assembly.py):
    # part_properties supplies Title/Generator plus the TOL_* general-tolerance
    # cells finalize_drawing hard-requires; material/finish defer to the parts
    # list (standard assembly-drawing practice).
    apply_custom_properties(
        adapter,
        {
            **part_properties(ASM_NAME),
            # MHA-A## = assembly-drawing ids, beside the parts' MHA-### range
            # (a longer number overflows the DWG. NO. title-block cell).
            "Number": "MHA-A05",
            "Revision": "A",
            "Revision Description": "Initial release",
            "Material": "SEE PARTS LIST",
            "Material Specification": "SEE PARTS LIST",
            "Finish": "SEE PARTS LIST",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The PART cell resolves the document summary Title; "magnifier assembly"
    # (not the bare stem) so the sheet identifies itself as an assembly drawing.
    apply_summary_info(adapter, title=f"{ASM_NAME} assembly")
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
