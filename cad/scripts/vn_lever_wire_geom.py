r"""Lever-wire endpoint/yoke solver -- the DRAWING-FREE nominal module.

PURE DATA + math, no SolidWorks/COM imports and no drawing-contract imports.
``build_lever_wire`` consumes these to build the wire; ``build_magnifying_wheel``
(the yoke point) and ``build_magnifier_assembly`` (the endpoint anchors) import
from HERE -- not from ``build_lever_wire`` -- so the lever-wire DRAWING notes
(``lever_wire_spec``, imported only by the build script) stay out of the wheel
part recipe and the magnifier assembly helper closure. A sheet-note edit
therefore rebuilds only the lever-wire part + its drawing, never the wheel or
the assembly (codex #360: the old ``from build_vn_lever_wire import ...`` edges
pulled the spec into both closures).

The derivation: the wire runs from the output fixture's hook to the XY-tangent
point on the brass drum (``mg_wheel_drum_geom``) pressed on the wheel's
front spigot; the wire part's Top plane (through the drum end, normal to the
wire) carrying the drum-pitch yoke point linearizes the inextensible-wire coupling
at the rest pose. The run is a straight rest-pose line (no wrap modelling).
"""

from __future__ import annotations

import math

from _mcmaster_9666k56 import DIA_MAX as _STOCK_DIA_MAX, DIA_MIN as _STOCK_DIA_MIN
from mg_magnifying_wheel_geom import (
    DRUM_MID_Z as _DRUM_MID_LOCAL_Z,
    HUB_DIA as _BOSS_DIA,
    HUB_FRONT_Z as _SPIGOT_FRONT_LOCAL_Z,
    HUB_STEP_Z as _BOSS_FRONT_LOCAL_Z,
    RIM_AXIAL as _RIM_AXIAL,
    RIM_INNER_DIA as _RIM_INNER_DIA,
    RIM_OUTER_DIA as _RIM_OUTER_DIA,
    SPOKE_AXIAL as _SPOKE_AXIAL,
)
from mg_wheel_drum_geom import DRUM_OD, DRUM_WIRE_R, LEVER_WIRE_DIA
from mg_output_fixture_geom import (
    FIXTURE_AXIS_Y,
    HOOK_OFFSET_X,
    HOOK_TARGET_Z,
    WIRE_DIA,
    WIRE_CLEARANCE as CLEARANCE,
)
from paper_drive_geom import PEN_Z_MID

assert math.isclose(WIRE_DIA, LEVER_WIRE_DIA, abs_tol=1e-12), (
    "fixture groove and wheel drum must carry the same lever wire diameter"
)

# Ø0.8 design nominal: inside the purchased 9666K56 0.031 +/-0.001 in band.
if not _STOCK_DIA_MIN <= WIRE_DIA <= _STOCK_DIA_MAX:
    raise AssertionError("lever wire Ø must lie in the 9666K56 catalogue band")

# --- endpoint anchors (magnifier frame; asserted by build_mg_magnifier_assembly)
#
# DEPTH RE-ANCHOR (option A1, #1559, ch30 p.4): the side view shows the whole
# output line -- the lever, its thumb screw, the vertical rod, this wire, the
# wheel, the rim wire, the pen rod -- as ONE plumb plane at the machine front.
# The magnifying group sits in the drum's wire lane (DRUM_END_Z), so the hook
# and the drum end share one depth and the wire runs straight down that plane,
# clearing the rim, spokes and boss only in XY (``run_gaps``).
CLAMP_X = 150.0  # sliding clamp / vertical rod / fixture line
# The wire wraps the output fixture's turned spigot groove and leaves it at
# screw-axis height, in the rod's own plane. The fixture yaws about the vertical
# rod to put the hook there while moving it toward the bracket. Geometry and
# yaw share one drawing-free owner with the fixture part build.
HOOK_X = CLAMP_X + HOOK_OFFSET_X
HOOK_Y = FIXTURE_AXIS_Y
HOOK_Z = HOOK_TARGET_Z
WHEEL_X = 53.0  # magnifying-wheel centre
WHEEL_BAR_Y = 575.7  # ch30 p002 re-anchor (was 565.0)
# Wheel mid-plane = the pen-rod line (mg_wheel_group asserts the stack closes
# on it; build_mg_magnifier_assembly places the wheel there).
WHEEL_MID_Z = PEN_Z_MID
DRUM_DIA = DRUM_OD
# Drum-end Z: the drum's axial middle, so the tangency sits mid-lane.
DRUM_END_Z = round(WHEEL_MID_Z + _DRUM_MID_LOCAL_Z, 6)
# Option A1: the hook lies in the drum lane, so the run has no depth fleet.
assert math.isclose(HOOK_Z, DRUM_END_Z, abs_tol=1e-9), (
    f"lever-wire hook depth {HOOK_Z} left the drum lane {DRUM_END_Z}"
)

# XY tangent from the hook to the drum circle inflated by wire r + clearance.
# +acos picks the tangent on the drum's right seen from the front (~2:25):
# the wire wraps clockwise from there, down the drum's side to TIE 1 at
# 6 o'clock (mg_magnifying_wheel_geom).
_R_EFF = DRUM_DIA / 2.0 + WIRE_DIA / 2.0 + CLEARANCE  # 10.1


def tangent_theta(hook_x: float, hook_y: float) -> float:
    """Machine-XY azimuth (rad, from +x about the wheel centre) of the drum
    tangent point the straight run from the hook touches."""
    vx, vy = hook_x - WHEEL_X, hook_y - WHEEL_BAR_Y
    return math.atan2(vy, vx) + math.acos(_R_EFF / math.hypot(vx, vy))


def tangent_end(hook_x: float, hook_y: float) -> tuple[float, float, float]:
    """The drum end of the straight run from a hook at (hook_x, hook_y)."""
    theta = tangent_theta(hook_x, hook_y)
    return (
        WHEEL_X + _R_EFF * math.cos(theta),
        WHEEL_BAR_Y + _R_EFF * math.sin(theta),
        DRUM_END_Z,
    )


_THETA = tangent_theta(HOOK_X, HOOK_Y)
# Front-view clock angle of the tangency (CCW from 3 o'clock; machine +x is
# the front view's left).
TANGENT_CLOCK_DEG = 180.0 - math.degrees(_THETA)

WIRE_START = (HOOK_X, HOOK_Y, HOOK_Z)  # groove front tangent, hook end
WIRE_END = tangent_end(HOOK_X, HOOK_Y)  # drum end = the PART ORIGIN
WIRE_LEN = round(math.dist(WIRE_START, WIRE_END), 3)


def run_gaps(
    start: tuple[float, float, float], end: tuple[float, float, float], n: int = 4001
) -> dict[str, float]:
    """Surface gaps from a straight run to the wheel's pen-side faces it passes:
    the rim ring, the spokes and the Ø25 boss (each where the run is radially
    over it, wire r + clearance widened), and the drum lane's two ends at the
    drum end. Positive = clear."""
    face = {
        "rim": WHEEL_MID_Z - _RIM_AXIAL / 2.0,
        "spokes": WHEEL_MID_Z - _SPOKE_AXIAL / 2.0,
        "boss": WHEEL_MID_Z + _BOSS_FRONT_LOCAL_Z,
    }
    band = {
        "rim": (_RIM_INNER_DIA / 2.0, _RIM_OUTER_DIA / 2.0),
        "spokes": (_BOSS_DIA / 2.0, _RIM_INNER_DIA / 2.0),
        "boss": (0.0, _BOSS_DIA / 2.0),
    }
    margin = WIRE_DIA / 2.0 + CLEARANCE
    gaps = {key: math.inf for key in face}
    for i in range(n):
        t = i / (n - 1)
        p = [s + t * (e - s) for s, e in zip(start, end, strict=True)]
        radial = math.hypot(p[0] - WHEEL_X, p[1] - WHEEL_BAR_Y)
        for key, (r_in, r_out) in band.items():
            if r_in - margin <= radial <= r_out + margin:
                gaps[key] = min(gaps[key], face[key] - p[2] - WIRE_DIA / 2.0)
    gaps["drum_back"] = WHEEL_MID_Z + _BOSS_FRONT_LOCAL_Z - end[2] - WIRE_DIA / 2.0
    gaps["drum_front"] = end[2] - (WHEEL_MID_Z + _SPIGOT_FRONT_LOCAL_Z) - WIRE_DIA / 2.0
    return gaps


RUN_GAPS = run_gaps(WIRE_START, WIRE_END)
for _key, _gap in RUN_GAPS.items():
    if _gap < CLEARANCE:
        raise AssertionError(f"lever wire run: {_key} gap {_gap:.3f} < {CLEARANCE}")

# --- WIRE-1 yoke (the coupling mate's geometry) -------------------------------
# The wheel-side yoke point: on the drum PITCH circle (drum radius + wire
# radius -- where the wire centreline rides) at the SAME tangency azimuth, in
# the wheel's mid-plane (the wheel part's Front plane).
YOKE_PITCH_R = DRUM_WIRE_R  # 9.85: wire-centreline pitch
YOKE_POINT = (
    WHEEL_X + YOKE_PITCH_R * math.cos(_THETA),
    WHEEL_BAR_Y + YOKE_PITCH_R * math.sin(_THETA),
    WHEEL_MID_Z,
)
# The coupling plane is the wire part's own Top plane (through the drum end,
# perpendicular to the wire axis). Option A1 makes the run coplanar with the
# drum lane, so the yoke point has no z step from the wire end, and its XY
# offset is radial -- perpendicular to the wire by tangency. Its signed distance
# along the wire axis is therefore zero: the yoke point lies ON Top.
_Y_LOCAL = [(s - e) / WIRE_LEN for s, e in zip(WIRE_START, WIRE_END, strict=True)]
_YOKE_AXIAL = sum(
    (q - e) * y for q, e, y in zip(YOKE_POINT, WIRE_END, _Y_LOCAL, strict=True)
)
if abs(_YOKE_AXIAL) >= 1e-9:
    raise AssertionError(
        f"WIRE-1 yoke point sits {_YOKE_AXIAL:.3e} off the lever wire's Top plane"
    )
