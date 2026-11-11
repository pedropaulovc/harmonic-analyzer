"""Print-worst free play of the 16T:64T crank mesh, sampled in 3D (#2481, #2562).

``crank_mesh_stack`` checks the pair in closed form, one plane at a time. This
module samples the 64T's tooth spaces as cut -- the cutter's normal-section
form swept along a straight line inclined beta, pivoting about the crossing
station -- against the straight 16T on the real crossed axes (FRAME_DY apart,
crossing in plan PLAN_CROSSING_TO_MIDFACE south of mid-face). The gear is held;
the pinion's free rotation is the least angular clearance one way plus the
least the other way over every sampled flank point, every engaged space and
the whole face. The minimum through one pitch is the backlash, as arc on the
16T's operating pitch circle.

Two tooth models, because the answer depends on the flank by about 0.011 mm
(#2481 v3): ``ideal`` (cut-count involutes, the closed form's teeth) and
``stock`` (the cutters' own finite forms, ``StockFormProfile``).

``print_worst_mm`` is the gate: the closing centre (``CENTRE_RANGE_MM``'s low
end), the thickest printed teeth on both gears with either tip, the tooth
line at either end of its printed band and nominal, the crossing station at
either end of its printed band and nominal, and the crank axis tilted either
way in the tooth-line plane by the post's crank-bore angularity and both
journal clearances (``AXIS_TILT_DEG``), which the stack books only as centre
terms. ``test_crank_mesh_free_play`` holds it at ``MARGIN_MM`` or more in both
models, and holds ``dt_crank_drive_gear_spec.MESH_THINNING_MM`` at the least
step that does so.

Offline only: no build script imports this module, so it keys no COM leaf.
Run from the worktree root for the report: uv run --frozen python
cad/scripts/crank_mesh_free_play.py (about a minute).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

import crank_mesh_stack as stack
import dt_crank_drive_gear_spec as gear64
import dt_crank_pinion_spec as pinion
from _printed_tolerance import printed_band_mm
from cone_line import COS_I, SIN_I
from stock_form_cutter import StockFormProfile

FORMS = ("stock", "ideal")
# Daylight the print-worst corner keeps in both tooth models: about three
# times the two models' 0.011 mm disagreement (#2481 v3). The ruled 0.15 mm
# thinning is the least 0.01 step that leaves it.
MARGIN_MM = 0.030

FACE = gear64.FACE_WIDTH
BETA = math.radians(gear64.TOOTH_INCLINATION_DEG)
ALPHA = math.radians(gear64.CUTTER_PRESSURE_ANGLE_DEG)
GROW = stack.EQUIVALENT_RADIUS_GROWTH_64
R64, R16 = stack.R64, stack.R16
TAN_I = SIN_I / COS_I
CLOSING = stack.FRAME_C2C - stack.CENTRE_RANGE_MM[0]
CROSSING_ROW = printed_band_mm(gear64.TOOTH_SPACE_CROSSING_PLACES, unit=gear64.UNIT)
# Axis tilts the stack books only as centre terms; each can lie in the
# tooth-line plane, where a tilt acts as a tooth-angle error.
AXIS_TILT_TERMS_DEG = {
    "post crank-bore angularity": stack.POST_ANGLE_DEG,
    "crank journal clearance over its span": math.degrees(
        stack.CRANK_RUNNING[1] / stack.CRANK_BEARING_LENGTH
    ),
    "cone journal clearance over its span": math.degrees(
        stack.CONE_RUNNING[1] / stack.CONE_BEARING_LENGTH
    ),
}
AXIS_TILT_DEG = sum(AXIS_TILT_TERMS_DEG.values())


def _involute(angle):
    return np.tan(angle) - angle


@dataclass(frozen=True)
class Case:
    forms: str = "stock"
    line: str = "straight"  # "screw": the retired helix through the same crossing section
    delta_deg: float = 0.0  # 64T tooth-angle error
    crossing: float = gear64.TOOTH_SPACE_CROSSING  # from the south face
    extra_c: float = 0.0  # centre opened beyond the closing corner
    shift_north: float = 0.0  # 64T moved north on its axis
    tilt_deg: float = 0.0  # crank axis turned in the tooth-line plane (about the line of centres)


_SECTIONS: dict[tuple, tuple[np.ndarray, np.ndarray, float]] = {}
_PINIONS: dict[tuple, tuple[np.ndarray, np.ndarray, float]] = {}


def _pinion_flank(profile: StockFormProfile, forms: str):
    """(radius, tooth half-angle) along the 16T flank, and its tip radius."""
    key = (forms, profile.blank_radius_mm, profile.radial_translation_mm)
    if key in _PINIONS:
        return _PINIONS[key]
    tip = profile.blank_radius_mm
    if forms == "ideal":
        base = R16 * math.cos(ALPHA)
        r = np.linspace(base, tip, 800)
        half = profile.pitch_tooth_thickness_mm / (2 * R16) + _involute(ALPHA) - _involute(np.arccos(base / r))
    else:
        template = profile.template
        xy = [
            profile.radial_point(float(v), 1)
            for v in np.linspace(template.root_radius_mm, template.base_radius_mm, 60, endpoint=False)
        ]
        xy += [
            profile.flank_point(float(v), 1)
            for v in np.linspace(profile.flank_parameter_min, template.flank_parameter_max, 800)
        ]
        xy = np.array(xy)
        r = np.hypot(xy[:, 0], xy[:, 1])
        half = math.pi / profile.teeth - np.arctan2(xy[:, 1], xy[:, 0])
    _PINIONS[key] = (r, half, tip)
    return _PINIONS[key]


def _gear_section(profile: StockFormProfile, forms: str, samples: int = 240):
    """Normal-section 64T flank (X radial from the real axis, Y >= 0) and tip radius."""
    key = (forms, profile.blank_radius_mm, profile.radial_translation_mm)
    if key in _SECTIONS:
        return _SECTIONS[key]
    tip = profile.blank_radius_mm
    if forms == "ideal":
        virtual = R64 + GROW
        base = virtual * math.cos(ALPHA)
        rho = np.linspace(max(base, profile.root_radius_max_mm + GROW), tip + 0.05 + GROW, samples)
        half = (
            (math.pi * gear64.NORMAL_MODULE_MM - profile.pitch_tooth_thickness_mm * math.cos(BETA))
            / (2 * virtual)
            + _involute(np.arccos(base / rho))
            - _involute(ALPHA)
        )
        x, y = rho * np.cos(half) - GROW, rho * np.sin(half)
    else:
        form = StockFormProfile(
            gear64.TEETH, gear64.CUTTER_TEMPLATE, tip, profile.radial_translation_mm, 0.0
        )
        xy = np.array([
            form.flank_point(float(v), 1)
            for v in np.linspace(form.flank_parameter_min, form.flank_parameter_max, samples)
        ])
        x, y = xy[:, 0], xy[:, 1]
    _SECTIONS[key] = (x, y, tip)
    return _SECTIONS[key]


def free_play(case: Case, pin: StockFormProfile, gear: StockFormProfile, stations=None,
              n_phase: int = 33) -> float:
    """Least free circular backlash (mm on the 16T's operating pitch circle)
    of one printed corner pair over the face stations (default: 25 across the
    whole face), through one 64T pitch of mesh."""
    zs = np.linspace(0.0, FACE, 25) if stations is None else np.atleast_1d(np.asarray(stations, float))
    beta = BETA + math.radians(case.delta_deg)
    gx, gy, tip_g = _gear_section(gear, case.forms)
    r_grid, half_grid, tip_p = _pinion_flank(pin, case.forms)
    z_cross = FACE / 2.0 - stack.PLAN_CROSSING_TO_MIDFACE - case.shift_north  # plan crossing, from the south face
    x_mid = -(FACE / 2.0 - z_cross) * TAN_I
    c_mid = math.hypot(x_mid, stack.FRAME_DY)
    move = case.extra_c - CLOSING
    a0 = np.array([z_cross * TAN_I, stack.FRAME_DY, 0.0]) + np.array([x_mid, stack.FRAME_DY, 0.0]) / c_mid * move
    e3 = np.array([-SIN_I, 0.0, COS_I])  # crank axis; right-hand teeth put it this way round
    if case.tilt_deg:
        a0 = a0 + e3 * (FACE / 2.0) / COS_I  # pivot: the axis point abreast of mid-face
        k, t = np.array([x_mid, stack.FRAME_DY, 0.0]) / c_mid, math.radians(case.tilt_deg)
        e3 = e3 * math.cos(t) + np.cross(k, e3) * math.sin(t) + k * (k @ e3) * (1 - math.cos(t))
    to_gear = np.array([0.0, 0.0, FACE / 2.0]) - a0
    e1 = to_gear - (to_gear @ e3) * e3
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(e3, e1)
    mesh_az = math.atan2(stack.FRAME_DY, x_mid)
    pitch_g, pitch_p = 2 * math.pi / gear64.TEETH, 2 * math.pi / pinion.TEETH
    rw_p = (c_mid + move + GROW) * R16 / (R16 + R64 + GROW)
    js = np.arange(-3, 4)
    k0 = 3
    i_pitch = int(np.argmin(np.abs(np.hypot(gx, gy / math.cos(beta)) - R64)))
    zz = zs[None, :, None]

    def polar(side: int, theta: float):
        az = mesh_az + theta + js[:, None, None] * pitch_g
        rad = gx[None, None, :] + 0 * zz
        if case.line == "straight":
            tan = side * gy[None, None, :] / math.cos(beta) + (zz - case.crossing) * math.tan(beta)
        else:
            tan = side * gy[None, None, :] / math.cos(BETA) + 0 * zz
            az = az + (zz - case.crossing) * math.tan(beta) / R64
        px, py = rad * np.cos(az) - tan * np.sin(az), rad * np.sin(az) + tan * np.cos(az)
        q = np.stack([px - a0[0], py - a0[1], zz - a0[2] + 0 * px], axis=-1)
        q1, q2 = q @ e1, q @ e2
        return np.hypot(q1, q2), np.arctan2(q2, q1), np.hypot(rad, tan) <= tip_g + 1e-9

    best = math.inf
    mid = len(zs) // 2
    for theta in np.linspace(0.0, pitch_g, n_phase, endpoint=False):
        data = {s: polar(s, theta) for s in (1, -1)}
        c0 = 0.5 * (data[1][1][k0, mid, i_pitch] + data[-1][1][k0, mid, i_pitch])
        c1 = 0.5 * (data[1][1][k0 + 1, mid, i_pitch] + data[-1][1][k0 + 1, mid, i_pitch])
        centres = c0 + (1.0 if c1 > c0 else -1.0) * js * pitch_p
        total = 0.0
        for direction in (1, -1):
            per_station = np.full(len(zs), np.inf)
            for s in (1, -1):
                r, ang, inside = data[s]
                rel = (ang - centres[:, None, None]) * direction
                if np.median(rel[k0]) <= 0:
                    continue  # the flank the tooth leaves, turning this way
                clear = np.where(inside & (r <= tip_p), rel - np.interp(r, r_grid, half_grid), np.inf)
                per_station = np.minimum(per_station, clear.min(axis=(0, 2)))
            total += float(per_station.min())
        best = min(best, total * rw_p)
    return best


def governing_pairs(gear_corners=None):
    """The thickest printed teeth on both gears, either tip: the free play
    falls as either tooth thickens, so these four of the sixteen corner pairs
    govern (all sixteen were swept on #2481 v3)."""
    gears = [profile for _, profile in (gear_corners or gear64.STOCK_PROFILE_CORNERS)]
    pins = [profile for _, profile in pinion.STOCK_PROFILE_CORNERS]

    def thickest(profiles):
        top = max(p.pitch_tooth_thickness_mm for p in profiles)
        return [p for p in profiles if p.pitch_tooth_thickness_mm == top]

    return [(a, b) for a in thickest(pins) for b in thickest(gears)]


def print_worst_mm(forms: str, gear_corners=None) -> float:
    """Least free play at the print limits (module docstring), one tooth model."""
    band = gear64.TOOTH_INCLINATION_TOLERANCE_DEG
    crossing = gear64.TOOTH_SPACE_CROSSING
    return min(
        free_play(Case(forms=forms, delta_deg=d, crossing=c, tilt_deg=t), a, b)
        for d in (-band, 0.0, band)
        for c in (crossing - CROSSING_ROW, crossing, crossing + CROSSING_ROW)
        for t in (-AXIS_TILT_DEG, AXIS_TILT_DEG)
        for a, b in governing_pairs(gear_corners)
    )


def straight_tooth_lean_3d(station_mm: float) -> float:
    """Backlash the straight tooth's lean takes at a face station (mm north
    of mid-face), sampled in 3D: the 64T slid to the axes' common
    perpendicular at that station's real centre, ideal involutes, every corner
    pair; the screw form's free play less the straight form's, less the
    pitch-circle thickening. Regenerates test_standard_mesh_checks'
    STRAIGHT_TOOTH_LEAN_3D_MM."""
    z = FACE / 2.0 + station_mm
    w0 = stack.PLAN_CROSSING_TO_MIDFACE
    extra = stack.centre_at_station(station_mm) - math.hypot(stack.FRAME_DY, station_mm * TAN_I)
    pairs = [(a, b) for _, a in pinion.STOCK_PROFILE_CORNERS for _, b in gear64.STOCK_PROFILE_CORNERS]

    def worst(line: str) -> float:
        case = Case(forms="ideal", line=line, shift_north=-w0, extra_c=extra)
        return min(free_play(case, a, b, [z], n_phase=97) for a, b in pairs)

    return worst("screw") - worst("straight") - stack.straight_tooth_thickening(station_mm)


if __name__ == "__main__":
    print(f"axis tilt {AXIS_TILT_DEG:.3f} deg: "
          + ", ".join(f"{k} {v:.3f}" for k, v in AXIS_TILT_TERMS_DEG.items()))
    print(f"64T mesh thinning {gear64.MESH_THINNING_MM:.3f} mm normal; margin {MARGIN_MM:.3f} mm")
    for thinning in (0.0, gear64.MESH_THINNING_MM - gear64.MESH_THINNING_STEP_MM, gear64.MESH_THINNING_MM):
        corners = gear64.profile_corners(gear64.tooth_band(thinning))
        print(f"  thinning {thinning:.3f}: print-worst "
              + ", ".join(f"{f} {print_worst_mm(f, corners):+.4f}" for f in FORMS))
    print("straight-tooth lean, 3D, south face to north face: "
          + ", ".join(f"{straight_tooth_lean_3d(s):.4f}" for s in stack.FACE_STATIONS_MM))
