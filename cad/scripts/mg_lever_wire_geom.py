r"""Lever-wire endpoint/yoke solver -- the DRAWING-FREE nominal module.

PURE DATA + math, no SolidWorks/COM imports and no drawing-contract imports.
``build_lever_wire`` consumes these to build the wire; ``build_magnifying_wheel``
(the yoke point) and ``build_magnifier_assembly`` (the endpoint anchors) import
from HERE -- not from ``build_lever_wire`` -- so the lever-wire DRAWING notes
(``lever_wire_spec``, imported only by the build script) stay out of the wheel
part recipe and the magnifier assembly helper closure. A sheet-note edit
therefore rebuilds only the lever-wire part + its drawing, never the wheel or
the assembly (codex #360: the old ``from build_mg_lever_wire import ...`` edges
pulled the spec into both closures).

The derivation: the wire runs from the output fixture's hook to the XY-tangent
point on the brass drum (``mg_wheel_drum_geom``) pressed on the wheel's
front spigot; the YokePlane offset linearizes the inextensible-wire coupling
at the rest pose. The run is a straight rest-pose line (no wrap modelling).
"""

from __future__ import annotations

import math

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

WIRE_DIA = LEVER_WIRE_DIA  # hair-thin in the photos; renderable stand-in (low)
CLEARANCE = 0.25  # surface stand-off (interference-gate margin convention)

# --- endpoint anchors (magnifier frame; asserted by build_mg_magnifier_assembly)
#
# DEPTH RE-ANCHOR (2026-07-04, ch30 p.4): the side view shows the whole output
# line -- this wire, the wheel, the rim wire, the pen rod -- as ONE plumb
# vertical at the machine front. The hook hangs just behind the wheel bar's
# front face; the wire drops to the drum on the wheel's pen side, crossing the
# rim's axial band only outside the rim (``run_gaps``): ~17 mm of z over the
# ~350 run = 2.8 deg, visually plumb.
CLAMP_X = 150.0  # sliding clamp / vertical rod / fixture line
# The wire TIES through the fixture's cross hole and hangs beside the vertical
# rod, just under the collar's bottom face: wire r + 0.25 below it in y, and
# off the rod axis in -z by rod r 2.5 + wire r 0.4 + 0.25 = 3.15 (the front
# face of the rod). So HOOK_Z = VROD_Z - 3.15 with VROD_Z = -134.8
# (LEVER_ROD_Z -128.3 -- depth window RE-SOLVED 2026-08-02 for the one-piece
# top-frame casting): build_mg_magnifier_assembly derives and asserts the
# thumb-screw rail clearance from the exact 91882A221 stock reach, so the rail
# imposes NO depth bound.
HOOK_Y = 915.05  # FIXTURE_Y0 915.7 - wire r 0.4 - 0.25 (under the collar bottom)
HOOK_Z = -137.95
WHEEL_X = 53.0  # magnifying-wheel centre
WHEEL_BAR_Y = 575.7  # ch30 p002 re-anchor (was 565.0)
WHEEL_MID_Z = -146.9  # wheel mid-plane (build_mg_magnifier_assembly.WHEEL_MID_Z)
DRUM_DIA = DRUM_OD
# Drum-end Z: the drum's axial middle, so the tangency sits mid-lane.
DRUM_END_Z = round(WHEEL_MID_Z + _DRUM_MID_LOCAL_Z, 6)  # -154.91

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


_THETA = tangent_theta(CLAMP_X, HOOK_Y)
# Front-view clock angle of the tangency (CCW from 3 o'clock; machine +x is
# the front view's left).
TANGENT_CLOCK_DEG = 180.0 - math.degrees(_THETA)  # ~17.7

WIRE_START = (CLAMP_X, HOOK_Y, HOOK_Z)  # hook end
WIRE_END = tangent_end(CLAMP_X, HOOK_Y)  # drum end = the PART ORIGIN
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
# the wheel's mid-plane (the wheel part's Front plane). Its XY radial offset
# from the wire end is perpendicular to the wire axis by tangency, so only the
# z step feeds the YokePlane offset below.
YOKE_PITCH_R = DRUM_WIRE_R  # 9.85: wire-centreline pitch
YOKE_POINT = (
    WHEEL_X + YOKE_PITCH_R * math.cos(_THETA),
    WHEEL_BAR_Y + YOKE_PITCH_R * math.sin(_THETA),
    WHEEL_MID_Z,
)
# YokePlane: parallel to the part's Top plane (perpendicular to the wire axis)
# through YOKE_POINT. Signed offset along local +Y (= the drum->hook direction).
_Y_LOCAL = [(s - e) / WIRE_LEN for s, e in zip(WIRE_START, WIRE_END, strict=True)]
YOKE_PLANE_OFFSET = round(
    sum((q - e) * y for q, e, y in zip(YOKE_POINT, WIRE_END, _Y_LOCAL, strict=True)), 4
)
