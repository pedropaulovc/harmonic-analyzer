r"""Reproduction script: magnifier subassembly (book ch. 20-21).

The amplification stage: the magnifying lever takes the summing lever's tiny
motion and the magnifying wheel multiplies it again (via the wire to the pen),
in machine coordinates (assembly origin = base origin; the output side is -Z).

* magnifying-bracket -- the fitting that AFFIXES the lever rod to the pivoted
  summing bar, so it RIDES the lever (locked, like the clamp chain), its collar
  carrying the rod with a press fit alone (#1570) at every rock angle. The
  lever EXTENDS FROM the pivoted summing bar and pivots WITH it about the
  knife-edge ridge line (engineerguy video 2/4 + 4/4; tip arc ~6 mm), so its
  one DOF is the rock about that Z line; the clamp + thumb screw + vertical rod
  + output-fixture ride the lever as one rigid body at the set magnification
  radius -- the radius from the KNIFE EDGE is what the sliding clamp adjusts
  (<=4x) -- and the output fixture is where WIRE 1 to the wheel's drum hooks.
* wheel-bar (HALF-width, clamped at ONE column with a free end past the pen
  hanger) + its two-piece column clamp (front/back arcs + two clamp screws --
  the platen support bar's clamp, ch30 p005).
* wheel-axle -- a plain pin pressed in the bar's reamed bore (structure) --
  carrying the stack back washer, magnifying-wheel (spins on the pin,
  revolute), front washer, nut and locknut (stations: mg_wheel_group). The
  brass wheel-drum is pressed on the wheel's front spigot and rides it. The
  wheel rim drives the pen rod via WIRE 2 (pn-pen.SLDASM).
  Its two assembly settings, the press gauge and the endshake, are model
  dimensions of a blanked construction chain (mg_magnifier_assembly_spec)
  that the MHA-MG-00 sheet prints; a second blanked chain carries the lever
  group's clamp station and fixture drop. The named explode the MHA-MG-00
  exploded sheets show (MG_MAGNIFIER_EXPLODED) is authored here too
  (_mg_magnifier_explode).
* lever-wire -- WIRE 1's straight rest-pose run from the output fixture's
  spigot groove (in the rod's plane) down to the drum tangent. It ARTICULATES like the real wire: a
  ball joint at the hook (HookPoint on the wire coincident to the fixture's
  HookAnchorPoint) plus a 0.25 stand-off tangency to the drum,
  so the hook end follows the lever while the drum end hugs the drum (its two
  residual DOF, swing + spin, are freed operational DOF). Its Top plane
  carries the WIRE-1 COUPLING mate: the wheel's WireYokePoint held coincident
  to it ties the wheel's spin to the wire's travel along its own axis (the
  linearized inextensible-wire constraint), so with every freed DOF genuinely
  free, dragging the lever swings the clamp/rod/fixture group, the wire
  pivots at the hook staying on the drum, and the wheel turns: a working
  kinematic chain, pivoted where the book pivots it.

Cross-subassembly fits (checked at the top level): the column-clamp arcs ride
the O25.4 column (fr-frame.SLDASM); the pen-hanger (pn-pen.SLDASM) clamps the
wheel-bar, and the wheel rim -> pen-rod wire couples this sub to the pen.

Documented simplifications (Appendix C): both thumb screws are modeled
backed-out with their tips tangent to the rods they clamp (seated screws would
overlap them). The output fixture has the photographed hex body, grooved
spigot and axial screw; the wires are straight rest-pose runs only (lever-wire
here, pen-wire in pn-pen.SLDASM). Groove wraps, tie-offs and compliance are not
modeled, and the kinematic couplings stay Motion-study mates
(cad/docs/motion-policy.md).

Fix-all strategy (M6.2): every structural component inserted at its exact final
transform and fixed; the lever + bracket + wheel + wire are left free and
constrained by mates; transforms asserted by read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 20-21.

Assembly render artifacts are produced by the shared save_assembly_and_images
path, using its standard reproducible views.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_magnifier_assembly.py
"""

from __future__ import annotations

import math
import sys

import mg_magnifier_assembly_spec as stack_spec
from _check import check
from _com import _early_bound, _read_member
from _custom_properties import apply_custom_properties
from _dimensions import drive_dimension, set_global
from _session import run_build
from _drawing_marks import DRAWN_BY, mark_dimensions_for_drawing
from _drawing_precision import apply_drawing_precision, _named_dimension
from _drawing_tolerances import (
    set_dimension_symmetric_tolerance,
    _set_tolerance_precision,
)
from _feature_tree import name_last_feature
from _assembly_named_views import name_standard_views
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _assembly import (
    activate_assembly_contract,
    angle_driver,
    assembly_title_properties,
    author_in_drawing_configurations,
    assert_component_placed,
    assert_free_dof_necessity,
    check_no_interference,
    coincident_mate,
    component_named_ref,
    component_origin,
    distance_driver,
    lock_mate,
    named_ref,
    place_component,
    reset_dof_manifest,
    remap_front_to_machine_front,
    save_assembly_and_images,
    write_dof_manifest,
    world_point,
)
from _assembly_patterns import (
    assert_pattern_targets,
    linear_component_pattern,
    PatternDirection,
)
from _interference_contracts import allowed_interference_pairs
from _mg_magnifier_explode import create_mg_magnifier_explode
from _transforms import (
    IDENTITY,
    ROT_X_NEG90,
    ROT_Y_180,
    ROT_Y_POS90,
    compose_rows,
    euler_from_rows,
    rot_z_rows,
    rows_from_euler,
)
from _cone_axis_constants import FRAME_FRONT_COLUMN_Z, SUMMING_Z
from sm_summing_lever_spec import PLATE_L
from mg_wheel_bar_geom import WHEEL_BAR_Y
from magnifying_bracket_joint_layout import (
    BRACKET_ORIGIN,
    SCREW_POSITIONS,
    SEAT_PLANE_Z,
)

ASM_NAME = "mg-magnifier"
BRACKET_SCREW_POSITIONS = SCREW_POSITIONS
BRACKET_SCREW_ROWS = ROT_X_NEG90

# --- machine anchors ---------------------------------------------------------
# ch30 p002 front-view re-anchor (2026-07-17): the wheel
# + bar + column clamps sit 10.7 higher than the old 565.0 -- the photo shows
# the rim clearing the platen box top, which 565.0 left overlapped
COLUMN_X = 197.0  # the WEST column (machine +x is west; the crank side -x is east)
COLUMN_Z = FRAME_FRONT_COLUMN_Z
# Depth chain -- the SAME two-piece clamp seat as the platen support bar
# (paper-drive PR #196 E2): the front arc's front face (-129.4) carries the
# bar's back face; the bar's front face lands on the shared -138.9 plane, so
# the wheel/axle/wire/pen line is untouched by the clamp swap.
from _clamp_arc import EAR_HOLE_Z as CLAMP_EAR_DX  # noqa: E402
from _column_clamp_interface import (  # noqa: E402
    ARC_DEPTH as ARC_FRONT_DEPTH,
    BAR_DEPTH as WHEEL_BAR_DEPTH,
)
from mg_wheel_bar_geom import (  # noqa: E402
    BAR_FRONT_Z as WHEEL_BAR_FRONT_Z,
    CLAMP_HOLE_X as BAR_CLAMP_HOLE_LOCAL_X,
    WHEEL_BAR_X0,
)

BAR_BACK_Z = COLUMN_Z - ARC_FRONT_DEPTH  # -129.4
BAR_FRONT_Z = BAR_BACK_Z - WHEEL_BAR_DEPTH  # -138.9: bar front = platen-back plane
BAR_Z = (BAR_FRONT_Z + BAR_BACK_Z) / 2.0  # -134.15 bar centre
# The wheel stack (mg_wheel_group) and the axle's gauge read the bar's front
# face from mg_wheel_bar_geom: it must be the clamp chain's.
assert math.isclose(BAR_FRONT_Z, WHEEL_BAR_FRONT_Z, abs_tol=1e-9), (
    "wheel-bar front face drifted from mg_wheel_bar_geom.BAR_FRONT_Z"
)

# --- magnifying group --------------------------------------------------------
# Rod at the plate centreline (979.7 -- the whole summing chain dropped 10.3
# with the one-piece top-frame casting, crossbar underside 1010 -> 999.7) so it
# stays coplanar with the coefficients plate; the bracket flange butts the
# plate front face. The clamp + vertical rod ride with it (CLAMP_POS and
# VROD_TOP_Y derive from LEVER_ROD_Y).
LEVER_ROD_Y = 979.7
# DEPTH (option A1, #1559): the ch30 p.4 side view is a TRUE PLUMB PLANE -- the
# lever rod, the clamp's thumb screw, the vertical rod, the fixture's wire hook
# and the drum's wire lane all lie in one plane, so WIRE 1 runs straight down
# it with no depth lean. LEVER_ROD_Z is therefore the drum lane
# (mg_vn_lever_wire_geom.DRUM_END_Z, asserted below). It stays a module-level
# literal: web/scripts/native_identity_source.py reads LEVER_ROD_Y,
# LEVER_ROD_Z and VROD_TOP_Y from this file by AST. The one-piece top-frame
# casting's front rail imposes no depth bound (the exact-stock thumb-screw
# reach, asserted below, keeps its head under the rail), and the Ø6 lever's
# clearance to the front column surface (-124.7) is now ~45.8 -- trivially
# large. The drum route's rim/spoke/boss clearance is proved in XY by
# mg_vn_lever_wire_geom.RUN_GAPS; the bracket arm reaches back to the unchanged
# plate flange (magnifying_bracket_joint_layout).
LEVER_ROD_Z = -173.51
from mg_vn_lever_wire_geom import DRUM_END_Z as LEVER_WIRE_DRUM_Z  # noqa: E402

assert math.isclose(LEVER_ROD_Z, LEVER_WIRE_DRUM_Z, abs_tol=1e-9), (
    f"magnifying group plane {LEVER_ROD_Z} left the drum wire lane {LEVER_WIRE_DRUM_Z}"
)
LEVER_X0 = 200.0  # lever part origin (rod west dome tip; rod spans +35..+200,
# placed Ry(180) so the part's local +x runs east toward the summing knife)

# Knife-edge pivot (engineerguy video 2/4 + 4/4): the lever rod EXTENDS FROM
# the pivoted summing bar and pivots WITH it about the knife-edge ridge line
# (along Z) -- it does NOT spin in the press-fitted, bonded bracket collar.
# The ridge is the summing sub's knife line; assert the lever part's local
# KnifeAxis lands exactly on it, so a knife move fails loud here.
from mg_lever_press_fit_geom import ROD_DIA as LEVER_ROD_DIA  # noqa: E402
from mg_magnifying_lever_geom import (  # noqa: E402
    CLAMP_LOCAL_X,
    COLLAR_LOCAL_X,
    KNIFE_LOCAL_X,
    KNIFE_LOCAL_Y,
)
from spring_mount_geom import KNIFE, KNIFE_CONTACT_Y  # noqa: E402

# The lever is placed Ry(180) (local +x -> machine -x), so the knife lands at
# LEVER_X0 - KNIFE_LOCAL_X.
assert math.isclose(LEVER_X0 - KNIFE_LOCAL_X, KNIFE[0], abs_tol=1e-9), (
    "magnifying-lever KnifeAxis x drifted from the summing knife line"
)
assert math.isclose(LEVER_ROD_Y + KNIFE_LOCAL_Y, KNIFE_CONTACT_Y, abs_tol=1e-9), (
    "magnifying-lever KnifeAxis y drifted from the knife-edge contact ridge"
)
from _mcmaster_91882a221 import (  # noqa: E402
    HEAD_STACK_LEN as THUMB_HEAD_STACK_LEN,
    SHANK_LEN as THUMB_SHANK_LEN,
)

TOP_FRAME_RAIL_UNDERSIDE_Y = 999.7
_MIN_THUMB_RAIL_CLEARANCE = 0.25
THUMB_SCREW_TIP_Y = LEVER_ROD_Y + LEVER_ROD_DIA / 2.0
THUMB_SCREW_OUTER_FACE_Y = THUMB_SCREW_TIP_Y + THUMB_SHANK_LEN + THUMB_HEAD_STACK_LEN
THUMB_SCREW_RAIL_CLEARANCE = TOP_FRAME_RAIL_UNDERSIDE_Y - THUMB_SCREW_OUTER_FACE_Y
assert THUMB_SCREW_RAIL_CLEARANCE >= _MIN_THUMB_RAIL_CLEARANCE, (
    f"thumb-screw head clears the top-frame rail by only "
    f"{THUMB_SCREW_RAIL_CLEARANCE:.4f} mm"
)
# Sliding clamp default position (p.46/48 insets) and the bracket collar, both
# derived from the lever-local stations error_budget.py reads for the
# magnification range (Ry(180): machine x = LEVER_X0 - local x).
CLAMP_X = LEVER_X0 - CLAMP_LOCAL_X  # 150
BRACKET_X = LEVER_X0 - COLLAR_LOCAL_X  # 40
assert math.isclose(SEAT_PLANE_Z, SUMMING_Z - PLATE_L / 2.0, abs_tol=1e-9), (
    "magnifying-bracket seat drifted from the summing-lever front face"
)
assert all(
    math.isclose(actual, expected, abs_tol=1e-9)
    for actual, expected in zip(
        BRACKET_ORIGIN, (BRACKET_X, LEVER_ROD_Y, LEVER_ROD_Z), strict=True
    )
), "magnifying-bracket joint origin drifted from its live placement"
# The bracket part imports COLLAR_HALF_LEN from mg_magnifying_lever_geom (which
# reads output.magnifier_collar_half_len_mm), so the collar length has ONE read
# point and there is no copy left here to assert equal.
# The clamp (#1559) is a vertical length of 7/16 hex: placed UNROTATED (hex
# axis = machine +Y, lever bore along X through the corners), its bottom-face
# origin LEVER_BORE_Y under the lever axis. The vertical rod screws into the
# clamp's bottom-face #4-40 tap on the same axis and seats on its shoulder; its
# thread tip sits SHOULDER_X above that face. mg_rod_clamp_joint's import-time
# worst-case asserts (engagement, tap depth) gate this assembly.
import mg_rod_clamp_joint  # noqa: E402, F401
from mg_magnifying_clamp_geom import LEVER_BORE_Y as CLAMP_BORE_Y  # noqa: E402
from mg_magnifying_vertical_rod_geom import SHOULDER_X as VROD_SHOULDER_X  # noqa: E402

CLAMP_POS = (CLAMP_X, LEVER_ROD_Y - CLAMP_BORE_Y, LEVER_ROD_Z)
VROD_Z = LEVER_ROD_Z  # coaxial with the clamp and its thumb screw
# Thread tip: the shoulder seats on the clamp's bottom face. A literal for the
# same AST reader as LEVER_ROD_Z, asserted against its derivation.
VROD_TOP_Y = 967.55
assert math.isclose(
    VROD_TOP_Y, LEVER_ROD_Y - CLAMP_BORE_Y + VROD_SHOULDER_X, abs_tol=1e-9
), "vertical-rod thread tip drifted from the clamp's bottom face + SHOULDER_X"
from mg_output_fixture_geom import (  # noqa: E402
    FIXTURE_AXIS_Y,
    FIXTURE_YAW_DEG,
    HOOK_LOCAL,
    SPIGOT_FACE_X,
    VROD_Z as FIXTURE_VROD_Z,
)
from mg_magnifying_vertical_rod_geom import ROD_DIA as VROD_DIA  # noqa: E402

assert math.isclose(
    VROD_Z, FIXTURE_VROD_Z, rel_tol=0.0, abs_tol=1e-9
), f"fixture vertical-rod Z datum {FIXTURE_VROD_Z} drifted from clamp datum {VROD_Z}"

# Local +X runs through the spigot toward the bracket, slightly back (+Z);
# local +Z is the machine-front groove tangent. No chirality shim is applied.
FIXTURE_ROWS = rows_from_euler([0.0, 180.0 + FIXTURE_YAW_DEG, 0.0])
FIXTURE_POSITION = (CLAMP_X, FIXTURE_AXIS_Y, VROD_Z)
assert all(
    math.isclose(actual, expected, abs_tol=1e-9)
    for actual, expected in (
        (stack_spec.LEVER_TIP_X, LEVER_X0),
        (stack_spec.LEVER_AXIS_Y, LEVER_ROD_Y),
        (stack_spec.CLAMP_CENTRE_X, CLAMP_X),
        (stack_spec.FIXTURE_AXIS_Y, FIXTURE_POSITION[1]),
    )
), "mg_magnifier_assembly_spec's lever settings drifted from the placed lever group"
FIXTURE_SCREW_ROWS = compose_rows(ROT_Y_180, FIXTURE_ROWS)
FIXTURE_SCREW_TIP_X = VROD_DIA / 2.0
FIXTURE_SCREW_COLLAR_X = FIXTURE_SCREW_TIP_X + THUMB_SHANK_LEN
FIXTURE_SCREW_OUTER_X = FIXTURE_SCREW_COLLAR_X + THUMB_HEAD_STACK_LEN
FIXTURE_SCREW_STANDOFF = FIXTURE_SCREW_COLLAR_X - SPIGOT_FACE_X
FIXTURE_SCREW_POSITION = tuple(
    origin + FIXTURE_SCREW_OUTER_X * FIXTURE_ROWS[0][axis]
    for axis, origin in enumerate(FIXTURE_POSITION)
)
assert FIXTURE_SCREW_STANDOFF > 0.0, "fixture screw collar must stand off the spigot"

# --- wheel -------------------------------------------------------------------
WHEEL_X = 53.0
# Clamp screws flank the column line, closing the stack bar -> front arc ->
# back arc with heads on the bar's front face (ch30 p002 / support-bar idiom).
# (west screw first -- keeps the component instance order of the mirrored-era
# build, so the pose-equivalence diff matches instances by name)
CLAMP_SCREW_X = (COLUMN_X + CLAMP_EAR_DX, COLUMN_X - CLAMP_EAR_DX)
# The bar's clamp holes must land on those screw lines: the bar is placed at
# IDENTITY, so book hole x = centre + local station.
assert sorted(round(WHEEL_BAR_X0 + lx, 6) for lx in BAR_CLAMP_HOLE_LOCAL_X) == sorted(
    round(x, 6) for x in CLAMP_SCREW_X
), "wheel-bar clamp holes drifted off the column clamp-screw lines"
# The axial stack on the pin (bar front face -> spacer -> back washer -> wheel
# hub -> endshake -> front washer -> nut -> locknut) lives in mg_wheel_group,
# asserted there at import (the spacer's length lands the wheel's mid-plane on
# the pen-rod line); machine z = BAR_FRONT_Z - d.
from mg_wheel_group import (  # noqa: E402
    BACK_WASHER_D,
    FRONT_WASHER_D,
    LOCKNUT_D,
    NUT_D,
    SPACER_D,
    WHEEL_MID_Z,
)

assert (stack_spec.AXLE_X, stack_spec.AXLE_Y, stack_spec.BAR_FRONT_Z) == (
    WHEEL_X,
    WHEEL_BAR_Y,
    BAR_FRONT_Z,
), "mg_magnifier_assembly_spec's axle line drifted from the placed axle"
# --- amplification wire 1 (fixture -> drum) ----------------------------------
# Endpoints + length live in build_mg_vn_lever_wire.py (the part's length IS the run);
# re-derive the anchors from THIS script's layout and fail loud on drift, so a
# layout move can never leave a floating wire.
from mg_vn_lever_wire_geom import (  # noqa: E402
    CLEARANCE as WIRE_CLEARANCE,
    DRUM_DIA,
    RUN_GAPS,
    WIRE_DIA as HUB_WIRE_DIA,
    WIRE_END as HUB_WIRE_END,
    WIRE_START as HUB_WIRE_START,
)
from mg_magnifying_wheel_geom import (  # noqa: E402
    DRUM_MID_Z,
    HUB_FRONT_Z,
    HUB_STEP_Z,
)

# The lever wire, the pen wire and the wheel stack all take the wheel plane
# from _recording_geometry.PEN_Z_MID; mg_wheel_group asserts the stack closes on it.
DRUM_Z = WHEEL_MID_Z + DRUM_MID_Z  # drum centre (drum frame mid-plane)

# Transform the model-owned groove front tangent, rather than assuming an
# x-symmetric collar: its nonzero local X must be rotated exactly once.
_HOOK_EXPECTED = tuple(
    origin + sum(HOOK_LOCAL[i] * FIXTURE_ROWS[i][axis] for i in range(3))
    for axis, origin in enumerate(FIXTURE_POSITION)
)
assert all(
    math.isclose(a, b, abs_tol=1e-9)
    for a, b in zip(HUB_WIRE_START, _HOOK_EXPECTED, strict=True)
), f"lever-wire hook {HUB_WIRE_START} drifted from the fixture anchor {_HOOK_EXPECTED}"
# The run grazes the brass drum at the 0.25 stand-off tangent ...
assert math.isclose(
    math.hypot(HUB_WIRE_END[0] - WHEEL_X, HUB_WIRE_END[1] - WHEEL_BAR_Y),
    DRUM_DIA / 2.0 + HUB_WIRE_DIA / 2.0 + WIRE_CLEARANCE,
    abs_tol=1e-9,
), "lever-wire end is not tangent to the drum"
# ... inside the drum's axial span (boss front face .. spigot front end, wire
# r inside each), and the slanted run clears the rim, spokes and boss pen-side
# faces it passes (RUN_GAPS, asserted >= CLEARANCE in mg_vn_lever_wire_geom).
assert (
    WHEEL_MID_Z + HUB_STEP_Z - HUB_WIRE_DIA / 2.0
    > HUB_WIRE_END[2]
    > WHEEL_MID_Z + HUB_FRONT_Z + HUB_WIRE_DIA / 2.0
), "lever-wire end z outside the drum span"
assert min(RUN_GAPS.values()) >= WIRE_CLEARANCE, f"lever-wire run gaps {RUN_GAPS}"


def _lever_wire_rows() -> list[list[float]]:
    """Rotation rows turning the part's +Y (wire axis) onto the HUB->HOOK
    direction (the part origin is the hub end -- its Top plane sits at the
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


def _assert_fixture_hook_anchor(adapter, fixture: str) -> None:
    """Prove the saved part's named point, not just a copied nominal, meets the wire."""
    assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
    component = assembly.GetComponentByName(fixture)
    if component is None:
        raise RuntimeError(f"fixture component missing: {fixture}")
    model = _early_bound(component, "IComponent2").GetModelDoc2()
    if model is None:
        raise RuntimeError(f"fixture part document not loaded: {fixture}")
    feature = _early_bound(model, "IPartDoc").FeatureByName("HookAnchorPoint")
    if feature is None:
        raise RuntimeError("output fixture is missing HookAnchorPoint")
    ref = _early_bound(feature, "IFeature").GetSpecificFeature2()
    if ref is None:
        raise RuntimeError("HookAnchorPoint is not native reference geometry")
    point = _early_bound(ref, "IRefPoint").GetRefPoint()
    if point is None:
        raise RuntimeError("HookAnchorPoint has no native point")
    local = [
        float(value) * 1000.0
        for value in _read_member(_early_bound(point, "IMathPoint"), "ArrayData")
    ]
    actual = world_point(adapter, fixture, local)
    if not all(
        math.isclose(a, b, abs_tol=1e-3)
        for a, b in zip(actual, HUB_WIRE_START, strict=True)
    ):
        raise RuntimeError(
            f"HookAnchorPoint {actual} != WIRE_START {HUB_WIRE_START} mm"
        )


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
_STANDOFF_R = DRUM_DIA / 2.0 + HUB_WIRE_DIA / 2.0 + WIRE_CLEARANCE  # 10.1
_WIRE_SPIN_ANGLE = math.degrees(math.acos(min(1.0, abs(_HW_ROWS[2][0]))))


async def _author_axle_stack_reference(adapter) -> None:
    """The press gauge and the endshake as model dimensions: no solid or pose
    edits, one construction chain on the axle centreline through the bar front
    face, the shank step, the wheel's spigot face and the front washer
    (mg_magnifier_assembly_spec), dimensioned from globals, banded,
    marked for the drawing and blanked (the ms ClampedSetting pattern).
    On the Right plane, sketch x is machine -z and sketch y is machine y."""
    spec = stack_spec
    for name, value in (
        ("AxleBarFrontFace", -spec.BAR_FRONT_Z),
        ("AxleAxisY", spec.AXLE_Y),
        ("AxlePressGauge", spec.PRESS_GAUGE),
        ("HubFrontStation", spec.HUB_FRONT_D),
        ("WheelEndshake", spec.ENDSHAKE),
    ):
        await set_global(adapter, name, f"{value}mm")
    xs = [-spec.BAR_FRONT_Z + d for d in spec.CHAIN_D]
    y = spec.AXLE_Y
    dims = SketchDims()
    check("create axle stack sketch", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    legs = [
        check(f"axle stack leg {index}", await adapter.add_line(x0, y, x1, y))
        for index, (x0, x1) in enumerate(zip(xs, xs[1:]))
    ]
    set_sketch_direct_db(adapter, False)
    for index, leg in enumerate(legs):
        segment = _early_bound(adapter._sketch_entities[leg], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"axle stack leg {index} is not construction")
        check(
            f"axle stack leg {index} horizontal",
            await adapter.add_sketch_constraint(leg, None, "horizontal"),
        )
    for index, (leg, after) in enumerate(zip(legs, legs[1:])):
        check(
            f"axle stack leg {index} chained",
            await adapter.add_sketch_constraint(
                f"{leg}.end", f"{after}.start", "coincident"
            ),
        )
    await anchor_point_to_origin(
        adapter, f"{legs[0]}.start", xs[0], y, "bar front face"
    )
    dims.record("StackFaceX", '"AxleBarFrontFace"')
    dims.record("StackAxisY", '"AxleAxisY"')
    for leg, length, (name, drive) in zip(
        legs,
        (x1 - x0 for x0, x1 in zip(xs, xs[1:])),
        (
            (spec.PRESS_GAUGE_DIMENSION, '"AxlePressGauge"'),
            ("StepToHubFront", '"HubFrontStation" - "AxlePressGauge"'),
            (spec.ENDSHAKE_DIMENSION, '"WheelEndshake"'),
        ),
        strict=True,
    ):
        await dimension_between(
            adapter, f"{leg}.start", f"{leg}.end", "horizontal_distance", length, name
        )
        dims.record(name, drive)
    await ensure_fully_defined(adapter, "axle stack")
    check("exit axle stack sketch", await adapter.exit_sketch())
    name_last_feature(adapter, spec.FEATURE)
    for name, expression in dims.apply(adapter, spec.FEATURE):
        await drive_dimension(adapter, name, expression)
    for name, band in spec.DIMENSION_TOLERANCES.items():
        set_dimension_symmetric_tolerance(adapter, spec.FEATURE, name, band)
        display, _ = _named_dimension(adapter, spec.FEATURE, name)
        _set_tolerance_precision(
            display,
            (-band, band),
            label=f"axle stack {name}",
            places=spec.TOLERANCE_PRECISION,
        )
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    mark_dimensions_for_drawing(adapter, spec.FEATURE, set(spec.DIMENSION_TOLERANCES))
    # Blanked so no view of this assembly or of the top assembly renders the
    # chain; the MHA-MG-00 detail shows it in that view only.
    blank_sketch(adapter, spec.FEATURE)
    feature = _early_bound(
        _early_bound(adapter.currentModel, "IAssemblyDoc").FeatureByName(spec.FEATURE),
        "IFeature",
    )
    if int(feature.Visible) != 1:  # swVisibilityStateHide
        raise RuntimeError(f"{spec.FEATURE} still visible after BlankSketch")


async def _author_lever_setting_reference(adapter) -> None:
    """The clamp station and the fixture drop as model dimensions: one
    construction chain on the Front plane (sketch x, y = machine x, y) from
    the lever rod's west tip along its axis to the clamp centre, then down the
    vertical-rod line to the output fixture's axis (mg_magnifier_assembly_spec
    LEVER_FEATURE). Dimensioned from globals, marked for the drawing and
    blanked, as the axle stack chain is; no tolerance band: the title block's
    general tolerance governs these operator settings."""
    spec = stack_spec
    for name, value in (
        ("LeverTipX", spec.LEVER_TIP_X),
        ("LeverAxisY", spec.LEVER_AXIS_Y),
        ("LeverClampStation", spec.CLAMP_STATION),
        ("LeverFixtureDrop", spec.FIXTURE_DROP),
    ):
        await set_global(adapter, name, f"{value}mm")
    points = (
        (spec.LEVER_TIP_X, spec.LEVER_AXIS_Y),
        (spec.CLAMP_CENTRE_X, spec.LEVER_AXIS_Y),
        (spec.CLAMP_CENTRE_X, spec.FIXTURE_AXIS_Y),
    )
    dims = SketchDims()
    check("create lever settings sketch", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    legs = [
        check(f"lever settings leg {index}", await adapter.add_line(*p0, *p1))
        for index, (p0, p1) in enumerate(zip(points, points[1:]))
    ]
    set_sketch_direct_db(adapter, False)
    for index, (leg, relation) in enumerate(zip(legs, ("horizontal", "vertical"))):
        segment = _early_bound(adapter._sketch_entities[leg], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"lever settings leg {index} is not construction")
        check(
            f"lever settings leg {index} {relation}",
            await adapter.add_sketch_constraint(leg, None, relation),
        )
    check(
        "lever settings legs chained",
        await adapter.add_sketch_constraint(
            f"{legs[0]}.end", f"{legs[1]}.start", "coincident"
        ),
    )
    await anchor_point_to_origin(adapter, f"{legs[0]}.start", *points[0], "lever tip")
    dims.record("LeverTipX", '"LeverTipX"')
    dims.record("LeverAxisY", '"LeverAxisY"')
    await dimension_between(
        adapter,
        f"{legs[0]}.start",
        f"{legs[0]}.end",
        "horizontal_distance",
        spec.CLAMP_STATION,
        spec.CLAMP_STATION_DIMENSION,
    )
    dims.record(spec.CLAMP_STATION_DIMENSION, '"LeverClampStation"')
    await dimension_between(
        adapter,
        f"{legs[1]}.start",
        f"{legs[1]}.end",
        "vertical_distance",
        spec.FIXTURE_DROP,
        spec.FIXTURE_DROP_DIMENSION,
    )
    dims.record(spec.FIXTURE_DROP_DIMENSION, '"LeverFixtureDrop"')
    await ensure_fully_defined(adapter, "lever settings")
    check("exit lever settings sketch", await adapter.exit_sketch())
    name_last_feature(adapter, spec.LEVER_FEATURE)
    for name, expression in dims.apply(adapter, spec.LEVER_FEATURE):
        await drive_dimension(adapter, name, expression)
    apply_drawing_precision(adapter, spec.LEVER_DRAWING_PRECISION)
    mark_dimensions_for_drawing(
        adapter, spec.LEVER_FEATURE, spec.LEVER_DRAWING_DIMENSIONS[spec.LEVER_FEATURE]
    )
    blank_sketch(adapter, spec.LEVER_FEATURE)
    feature = _early_bound(
        _early_bound(adapter.currentModel, "IAssemblyDoc").FeatureByName(
            spec.LEVER_FEATURE
        ),
        "IFeature",
    )
    if int(feature.Visible) != 1:  # swVisibilityStateHide
        raise RuntimeError(f"{spec.LEVER_FEATURE} still visible after BlankSketch")


async def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
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
        "mg-wheel-bar",
        [WHEEL_BAR_X0, WHEEL_BAR_Y, BAR_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
    )
    # Two-piece clamp at the west column -- the SAME black arcs as the platen
    # support bar (ch30 p005 / paper-drive PR #196 E2): the front arc's face
    # carries the bar's back face, the back arc closes on the column, and two
    # clamp screws (heads on the bar's front face, ch30 p002) close the stack
    # bar -> front arc -> back arc. Ry(+90): the arcs' local +X faces machine -Z.
    for arc in ("sh-column-clamp-front", "sh-column-clamp-back"):
        await place_component(
            adapter,
            arc,
            [COLUMN_X, WHEEL_BAR_Y, COLUMN_Z],
            [0.0, 90.0, 0.0],
            ROT_Y_POS90,
            label=f"{arc} (wheel x{COLUMN_X:.0f})",
        )
    # One physically mated seed plus a native component pattern.  Seed at the
    # lower-X hole so PatternAxisX FORWARD lands the generated instance on the
    # second Hole Wizard station; both stations derive from the same bar
    # constants. The exact rigid pose is held by one lock mate.
    seed_x, patterned_x = sorted(CLAMP_SCREW_X)
    seed_target = [seed_x, WHEEL_BAR_Y, BAR_FRONT_Z]
    clamp_seed = await place_component(
        adapter,
        "mg-vn-clamp-screw",
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
    ml = await place_component(
        adapter,
        "mg-magnifying-lever",
        [LEVER_X0, LEVER_ROD_Y, LEVER_ROD_Z],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
        ground=False,
    )
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
    await distance_driver(
        adapter,
        named_ref(f"Axis2@{ml}", "AXIS"),
        named_ref("Right Plane", "PLANE"),
        abs(KNIFE[0]),
        label="mag-lever knife line across",
        verify=(ml, ml_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Axis2@{ml}", "AXIS"),
        named_ref("Top Plane", "PLANE"),
        KNIFE_CONTACT_Y,
        label="mag-lever knife line height",
        verify=(ml, ml_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{ml}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        abs(LEVER_ROD_Z),
        label="mag-lever depth",
        verify=(ml, ml_o),
    )
    await angle_driver(
        adapter,
        named_ref(f"Top Plane@{ml}", "PLANE"),
        named_ref("Top Plane", "PLANE"),
        0.0,
        label="mag-lever rock PARK driver (freed in default build)",
        verify=(ml, ml_o),
        free_dof_key="lever_rock",
    )
    # The bracket affixes the lever to the rocking summing bar, not the frame.
    # Its collar is press-fitted and bonded to MHA-MG-03 (mg_lever_press_fit_geom),
    # so it is locked to the lever and stays concentric through the rock.
    # Grounding this moving fitting would constrain the mechanism incorrectly.
    bracket = await place_component(
        adapter,
        "mg-magnifying-bracket",
        list(BRACKET_ORIGIN),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{bracket}", "PLANE"),
        named_ref(f"Front Plane@{ml}", "PLANE"),
        label="mag-bracket locked to lever",
    )
    # Stock shank is -Y: Rx(-90) points it +Z into the lever's front taps.
    # Heads bear on the flange's front face; both ride the knife-edge rock.
    for index, position in enumerate(BRACKET_SCREW_POSITIONS, start=1):
        screw = await place_component(
            adapter,
            "mg-vn-magnifying-bracket-screw",
            list(position),
            [-90.0, 0.0, 0.0],
            BRACKET_SCREW_ROWS,
            ground=False,
            label=f"magnifying-bracket screw {index}",
        )
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{screw}", "PLANE"),
            named_ref(f"Front Plane@{bracket}", "PLANE"),
            label=f"magnifying-bracket screw {index} locked to bracket",
        )
        assert_component_placed(adapter, screw, list(position), BRACKET_SCREW_ROWS)
    # The clamp + vertical rod + output fixture + thumb screw are clamped to the
    # lever at the set magnification radius (the thumb screw pinches the lever
    # in the clamp; the rod is screwed home on its shoulder): they ride the
    # lever as one rigid body. The output fixture is where WIRE 1 to the wheel
    # drum hooks -- its (mostly vertical) travel as the lever rotates is what
    # drives the magnifying wheel in the Motion study, so these must move WITH
    # the lever, not stay fixed. Lock each to the lever.
    # Unrotated: the clamp's hex axis is already machine +Y and its lever bore
    # already runs along X through the corners.
    clamp = await place_component(
        adapter,
        "mg-magnifying-clamp",
        list(CLAMP_POS),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{clamp}", "PLANE"),
        named_ref(f"Front Plane@{ml}", "PLANE"),
        label="mag-clamp locked to lever",
    )
    # Backed-out thumb screw: the shank tip stays tangent to the lever top (a
    # seated screw would overlap the lever it pinches -- see module docstring).
    # Exact 91882A221 reach comes from the wrapper's stock shank and head-stack
    # constants. The wrapper preserves its outer-head-face local origin, so the
    # target below is that face after placing the tip at THUMB_SCREW_TIP_Y.
    # THUMB_SCREW_RAIL_CLEARANCE proves the head clears the full-depth front
    # rail while the clamp's #4-40 tap band (block top +9.0 down to the bore
    # top +3.1: 5.9 of thread) stays fully engaged. It enters the top face on
    # the hex axis, coaxial with the vertical rod below. Rz(-90) points the
    # shank down the hex axis; the extra Ry(180) turns its head features to
    # the machine hand ([180, 0, -90] is the same rotation's Euler form).
    _rz90_ry180 = compose_rows(rot_z_rows(-90.0), ROT_Y_180)
    tscrew = await place_component(
        adapter,
        "mg-vn-thumb-screw",
        [CLAMP_X, THUMB_SCREW_OUTER_FACE_Y, LEVER_ROD_Z],
        [180.0, 0.0, -90.0],
        _rz90_ry180,
        ground=False,
        label="thumb-screw (clamp)",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{tscrew}", "PLANE"),
        named_ref(f"Front Plane@{clamp}", "PLANE"),
        label="thumb-screw locked to clamp",
    )
    vrod = await place_component(
        adapter,
        "mg-magnifying-vertical-rod",
        [CLAMP_X, VROD_TOP_Y, VROD_Z],
        [180.0, 0.0, -90.0],
        _rz90_ry180,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{vrod}", "PLANE"),
        named_ref(f"Front Plane@{clamp}", "PLANE"),
        label="vertical-rod locked to clamp",
    )
    fixture = await place_component(
        adapter,
        "mg-output-fixture",
        list(FIXTURE_POSITION),
        euler_from_rows(FIXTURE_ROWS),
        FIXTURE_ROWS,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{fixture}", "PLANE"),
        named_ref(f"Front Plane@{vrod}", "PLANE"),
        label="output-fixture locked to vertical-rod",
    )
    assert_component_placed(adapter, fixture, list(FIXTURE_POSITION), FIXTURE_ROWS)
    fixture_screw = await place_component(
        adapter,
        "mg-vn-thumb-screw",
        list(FIXTURE_SCREW_POSITION),
        euler_from_rows(FIXTURE_SCREW_ROWS),
        FIXTURE_SCREW_ROWS,
        ground=False,
        label="thumb-screw (output fixture)",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{fixture_screw}", "PLANE"),
        named_ref(f"Front Plane@{fixture}", "PLANE"),
        label="output-fixture thumb-screw locked to fixture",
    )
    assert_component_placed(
        adapter, fixture_screw, list(FIXTURE_SCREW_POSITION), FIXTURE_SCREW_ROWS
    )

    # --- magnifying wheel ----------------------------------------------------
    # Rx(-90): the pin's +Y axis points -Z (pressed to its gauge from the bar
    # front face, the origin; back end about flush). The pin is structure
    # (fixed, pressed in the bar's reamed bore); the wheel spins on its shank
    # (revolute).
    ax = await place_component(
        adapter,
        "mg-wheel-axle",
        [WHEEL_X, WHEEL_BAR_Y, BAR_FRONT_Z],
        [-90.0, 0.0, 0.0],
        ROT_X_NEG90,
    )

    async def _stack_part(stem: str, d: float, lock_label: str) -> str:
        """A spacer/washer/nut on the pin at stack station d (mg_wheel_group):
        the part's local +Z axis (z 0..thickness, Front Plane at z 0) turned
        onto machine -Z by Ry(180), its back face at z BAR_FRONT_Z - d, locked
        to the pin (the same lock the old single nut used)."""
        target = [WHEEL_X, WHEEL_BAR_Y, BAR_FRONT_Z - d]
        comp = await place_component(
            adapter,
            stem,
            target,
            [0.0, 180.0, 0.0],
            ROT_Y_180,
            ground=False,
            label=f"{stem} d{d:.4g}",
        )
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{comp}", "PLANE"),
            named_ref(f"Front Plane@{ax}", "PLANE"),
            label=lock_label,
        )
        assert_component_placed(adapter, comp, target, ROT_Y_180)
        return comp

    await _stack_part(
        "mg-wheel-axle-spacer",
        SPACER_D,
        "wheel-axle spacer locked to the axle",
    )
    await _stack_part(
        "mg-vn-wheel-axle-back-washer",
        BACK_WASHER_D,
        "wheel back washer locked to the axle",
    )
    wh = await place_component(
        adapter,
        "mg-magnifying-wheel",
        [WHEEL_X, WHEEL_BAR_Y, WHEEL_MID_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    wh_o = component_origin(adapter, wh)
    # Revolute: radial coincident (wheel axis Z || axle stud Z) + axial
    # distance(Front, |z|); the spin -- the old angle(Right, 0) rock snapshot --
    # is now pinned by the WIRE-1 yoke below, coupling it to the lever.
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{wh}", "AXIS"),
        named_ref(f"Axis1@{ax}", "AXIS"),
        label="magnifying-wheel pivot",
        verify=(wh, wh_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{wh}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        abs(wh_o[2]),
        label="magnifying-wheel axial",
        verify=(wh, wh_o),
    )
    # Brass drum pressed on the wheel's front spigot: rides the wheel.
    drum_target = [WHEEL_X, WHEEL_BAR_Y, DRUM_Z]
    drum = await place_component(
        adapter,
        "mg-wheel-drum",
        drum_target,
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{drum}", "PLANE"),
        named_ref(f"Front Plane@{wh}", "PLANE"),
        label="wheel drum locked to the wheel",
    )
    # Front washer, nut and locknut close the stack at the set endshake.
    await _stack_part(
        "mg-vn-wheel-axle-front-washer",
        FRONT_WASHER_D,
        "wheel front washer locked to the axle",
    )
    await _stack_part("mg-vn-wheel-axle-nut", NUT_D, "wheel-axle nut locked to the axle")
    await _stack_part(
        "mg-vn-wheel-axle-nut", LOCKNUT_D, "wheel-axle locknut locked to the axle"
    )
    # --- amplification wire 1 (fixture -> drum) ------------------------------
    # The straight rest-pose run leaves the fixture's spigot-groove front
    # tangent and grazes the brass drum's tangent; wraps are implied. Part
    # origin = the DRUM end, +Y toward the hook.
    hw = await place_component(
        adapter,
        "mg-vn-lever-wire",
        list(HUB_WIRE_END),
        euler_from_rows(_HW_ROWS),
        _HW_ROWS,
        ground=False,
    )
    hw_o = component_origin(adapter, hw)
    # The wire ARTICULATES instead of riding the lever group rigidly (a locked
    # wire's hub tip would sweep a ~10 mm lateral arc off the hub even over
    # the real ~1.6 deg knife rock -- user-flagged): a BALL JOINT at the hook
    # (the wire's HookPoint coincident to the fixture's HookAnchorPoint) plus
    # the 0.25 axis-axis stand-off to the drum (the offset tangency the
    # rest geometry is built at), so the hook end follows the lever while the
    # drum end hugs the drum; the tip only creeps along its own axis (the
    # unmodeled wrap's pay-in/pay-out). Ref POINTs select via GetCorresponding
    # -- they do not resolve through name@comp strings.
    await coincident_mate(
        adapter,
        component_named_ref(hw, "HookPoint", "POINT"),
        component_named_ref(fixture, "HookAnchorPoint", "POINT"),
        label="lever-wire hook ball joint",
        verify=(hw, hw_o),
    )
    _assert_fixture_hook_anchor(adapter, fixture)
    await distance_driver(
        adapter,
        component_named_ref(hw, "Axis1", "AXIS"),
        component_named_ref(wh, "Axis1", "AXIS"),
        _STANDOFF_R,
        label="lever-wire hub stand-off tangency",
        verify=(hw, hw_o),
    )
    # The wire's two residual DOF (swing across the tangency family + spin
    # about its own axis) are freed operational DOF: each drive spec is
    # recorded into the DOF manifest, never authored. SWING pins the HUB-end
    # point's depth (the swing sweeps the hub end front-back on the tangency
    # family; the lever arm is the whole wire, so the driver has first-order
    # authority everywhere -- unlike the rest plane-plane angle, 0.74 deg = a
    # Jacobian extremum that authored satisfied but pinned NOTHING;
    # closure-replay catch 2026-07-05).
    await distance_driver(
        adapter,
        component_named_ref(hw, "HubPoint", "POINT"),
        named_ref("Front Plane", "PLANE"),
        HUB_WIRE_END[2],  # SIGNED (hub z<0):
        # distance_driver abs()es the mate value but needs the sign to seed the
        # side; the recorded spec then carries the right flip so the transient
        # replay is flip-free (was abs() -> far-side error-47 add + recovery)
        label="lever-wire swing PARK driver (hub depth, freed in default build)",
        verify=(hw, hw_o),
        free_dof_key="wire_swing",
    )
    await angle_driver(
        adapter,
        named_ref(f"Front Plane@{hw}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        _WIRE_SPIN_ANGLE,
        label="lever-wire spin PARK driver (freed in default build)",
        verify=(hw, hw_o),
        free_dof_key="wire_spin",
    )

    # WIRE-1 coupling (replaces the old wheel rock snapshot): the wheel's
    # WireYokePoint (drum pitch circle @ the wire tangency) held coincident to
    # the lever-wire's Top plane (perpendicular to the wire axis, through the
    # drum end; the coplanar A1 route puts the yoke point on it -- asserted in
    # mg_vn_lever_wire_geom). The wheel's
    # spin -- its one remaining DOF -- is thereby tied to the lever group's
    # travel along the wire: the linearized inextensible-wire constraint, sign
    # and ratio from geometry (build_mg_vn_lever_wire docstring). With every freed
    # DOF genuinely free, dragging the lever turns the wheel. The mate is
    # residual-free at the rest pose, so the wheel must NOT move when it
    # solves -- asserted right after.
    # component_named_ref, not a name@comp string: a reference POINT does not
    # resolve through SelectByID2 string selection -- the GetCorresponding path
    # is how the Motion study selects its rim RefPoint too.
    await coincident_mate(
        adapter,
        component_named_ref(wh, "WireYokePoint", "POINT"),
        named_ref(f"Top Plane@{hw}", "PLANE"),
        label="WIRE1 yoke fixture->wheel",
        verify=(wh, wh_o),
    )
    assert_component_placed(adapter, wh, [WHEEL_X, WHEEL_BAR_Y, WHEEL_MID_Z], IDENTITY)
    assert_component_placed(adapter, drum, drum_target, IDENTITY)

    # Certify the AS-BUILT model. THREE freed operational DOF: the lever's
    # knife rock + the wire's swing/spin (all recorded into the DOF manifest
    # above, never authored); the yoke-coupled wheel must also read
    # under-constrained WITH them, else the coupling died -- and so must the
    # lock-mated bracket (a regression to grounded would re-create the collar
    # clipping this rework fixed).
    assert_free_dof_necessity(
        adapter,
        3,
        required_stems=(
            "mg-magnifying-lever",
            "mg-magnifying-wheel",
            "mg-vn-lever-wire",
            "mg-magnifying-bracket",
        ),
    )
    write_dof_manifest(ASM_NAME)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
    )
    await _author_axle_stack_reference(adapter)
    await _author_lever_setting_reference(adapter)
    # Title-block identity for the assembly drawing (draw_mg_magnifier_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry;
    # released component drawing (the BOM has no material/finish columns).
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # Both drawing configurations own the explode: the exploded sheets'
    # views at 1:2 reference Default Simplified.
    author_in_drawing_configurations(
        adapter,
        ASM_NAME,
        lambda configuration: create_mg_magnifier_explode(adapter, configuration),
    )
    # Keep the fitter projections independent of the saved machine-front views.
    # Only cameras change: +Y remains up and the physical front remains -Z.
    name_standard_views(
        adapter, views=stack_spec.DRAWING_STANDARD_VIEWS, label=ASM_NAME
    )
    remap_front_to_machine_front(adapter)
    artefacts = await save_assembly_and_images(adapter, ASM_NAME)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
