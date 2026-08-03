r"""Lever-wire endpoint/yoke solver -- the DRAWING-FREE nominal module.

PURE DATA + math, no SolidWorks/COM imports and no drawing-contract imports.
``build_lever_wire`` consumes these to build the wire; ``build_magnifying_wheel``
(the yoke point) and ``build_magnifier_assembly`` (the endpoint anchors) import
from HERE -- not from ``build_lever_wire`` -- so the lever-wire DRAWING notes
(``lever_wire_spec``, imported only by the build script) stay out of the wheel
part recipe and the magnifier assembly helper closure. A sheet-note edit
therefore rebuilds only the lever-wire part + its drawing, never the wheel or
the assembly (codex #360: the old ``from build_lever_wire import ...`` edges
pulled the spec into both closures).

The derivation (see the inline comments, moved verbatim from
``build_lever_wire``): the wire runs from the output fixture's hook to the
XY-tangent point on the magnifying wheel's hub, ducking behind the rim into the
hub's back groove band; the YokePlane offset linearizes the inextensible-wire
coupling at the rest pose.
"""

from __future__ import annotations

import math

WIRE_DIA = 0.8  # hair-thin in the photos; renderable stand-in (low)
CLEARANCE = 0.25  # surface stand-off (interference-gate margin convention)

# --- endpoint anchors (magnifier frame; asserted by build_magnifier_assembly)
#
# DEPTH RE-ANCHOR (2026-07-04, ch30 p.4): the side view shows the whole output
# line -- this wire, the wheel, the rim wire, the pen rod -- as ONE plumb
# vertical at the machine front. The old lever depth (z -85) hung the hook 50
# behind the wheel plane, an ~8 deg lean the photo refutes. A PERFECTLY planar
# wire is impossible (the rim ring z -142.9..-150.9 blocks every straight
# in-band approach, and the hub pokes only 1.0 past the rim per side), so the
# real wire leans SLIGHTLY, ducking behind the rim's back face into the hub's
# back groove band. Solving the clearance system (>= 0.25 surface everywhere;
# rim back-face bound at radius 43.35, axle-flange bound inside radius 17.9,
# spoke fronts at -144.9) gives the hook/hub-end pair below: a 10 mm z drop
# over the ~353 run = 1.6 deg, visually plumb.
CLAMP_X = 150.0  # sliding clamp / vertical rod / fixture line
# The wire TIES through the fixture's cross hole and hangs beside the vertical
# rod, just under the collar's bottom face: wire r + 0.25 below it in y, and
# off the rod axis in -z by rod r 2.5 + wire r 0.4 + 0.25 = 3.15 (the front
# face of the rod). So HOOK_Z = VROD_Z - 3.15 with VROD_Z = -134.8
# (LEVER_ROD_Z -128.3 -- depth window RE-SOLVED 2026-08-02 for the one-piece
# top-frame casting (front rail z -93..-131, band y 999.7..1036.2): the
# thumb-screw head top now stays at 998.7, >= 0.25 (actual 1.0) below the
# casting underside 999.7 (#4-40 shortened 12 -> 11), so the rail imposes NO
# depth bound -- pushing the head band past the rail outer face -131 would
# instead need <= -136.25, beyond the rim-duck floor. Remaining window: the
# front column surface -124.7 forces the rod deeper than -127.95, while the
# wire's rim-duck feasibility caps the hook at ~-137.96 => rod >= -128.31).
HOOK_Y = 915.05  # FIXTURE_Y0 915.7 - wire r 0.4 - 0.25 (under the collar bottom)
HOOK_Z = -137.95
WHEEL_X = 53.0  # magnifying-wheel centre
WHEEL_BAR_Y = 575.7  # ch30 p002 re-anchor (was 565.0)
HUB_DIA = 20.0  # ch. 21 annotated (build_magnifying_wheel.HUB_DIA)
# Hub-end Z: in the hub's back groove band, between the rim-duck bound
# (z >= -142.25 while the run is radially inside the rim ring) and the
# axle-flange bound (<= -142.55 wherever radius < 17.9).
HUB_END_Z = -142.77

# XY tangent from the hook to the hub circle inflated by wire r + clearance,
# on the west (hook) side: the wire grazes the groove and the wrap is implied.
# (-acos picks the tangent whose contact point faces the hook at machine +x;
# the pre-#151 mirrored frame used +acos for the reflected tangent.)
_R_EFF = HUB_DIA / 2.0 + WIRE_DIA / 2.0 + CLEARANCE
_VX, _VY = CLAMP_X - WHEEL_X, HOOK_Y - WHEEL_BAR_Y  # hub centre -> hook (2D)
_THETA = math.atan2(_VY, _VX) - math.acos(_R_EFF / math.hypot(_VX, _VY))

WIRE_START = (CLAMP_X, HOOK_Y, HOOK_Z)  # hook end
WIRE_END = (
    WHEEL_X + _R_EFF * math.cos(_THETA),
    WHEEL_BAR_Y + _R_EFF * math.sin(_THETA),
    HUB_END_Z,
)  # hub end = the PART ORIGIN (local +Y runs hub -> hook)
WIRE_LEN = round(math.dist(WIRE_START, WIRE_END), 3)

# --- WIRE-1 yoke (the coupling mate's geometry) -------------------------------
# The wheel-side yoke point: on the hub PITCH circle (groove radius + wire
# radius -- where the wire centreline rides) at the SAME tangency azimuth, in
# the wheel's mid-plane (machine z -146.9). Its XY radial offset from the wire
# end is perpendicular to the wire axis by tangency, so only the z step feeds
# the YokePlane offset below.
WHEEL_MID_Z = -146.9  # wheel mid-plane (build_magnifier_assembly.WHEEL_MID_Z)
YOKE_PITCH_R = HUB_DIA / 2.0 + WIRE_DIA / 2.0  # 10.4: wire-centreline pitch
YOKE_POINT = (
    WHEEL_X + YOKE_PITCH_R * math.cos(_THETA),
    WHEEL_BAR_Y + YOKE_PITCH_R * math.sin(_THETA),
    WHEEL_MID_Z,
)
# YokePlane: parallel to the part's Top plane (perpendicular to the wire axis)
# through YOKE_POINT. Signed offset along local +Y (= the hub->hook direction).
_Y_LOCAL = [(s - e) / WIRE_LEN for s, e in zip(WIRE_START, WIRE_END, strict=True)]
YOKE_PLANE_OFFSET = round(
    sum((q - e) * y for q, e, y in zip(YOKE_POINT, WIRE_END, _Y_LOCAL, strict=True)), 4
)
