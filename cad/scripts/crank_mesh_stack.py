"""Fixed-centre 16T:64T crossed mesh: dimensional stack and standard check.

The 64T's straight teeth are inclined to the cone axis by the cone incline,
right hand, cut with the same normal 24DP PA20 stock cutter as the straight
16T. It is checked as an ordinary crossed pair in the 64T's normal section:
the 64T takes its virtual radius R/cos^2(beta) and its thickness scales by
cos(beta), while the 16T is already in that plane (to within the 0.52 deg
crossing). The centre range is
the closed-form sum of the printed and fitted terms below, each booked at the
end that closes or opens the mesh. Everything is read from part specs and
config. The native assembly interference gate checks the real flanks.

The standard check books the centre at mid-face and the 64T's tooth at the
station where the cutter's centre plane crosses its axis. Because the axes
cross in plan, the centre closes toward the 64T's south face and opens toward
its north face; because the teeth are straight, each tooth space also shifts
sideways off its radial line away from the crossing station, which thickens
the tooth on the pitch circle and raises the root. Off the pitch circle the
same shift leans each flank against the screw form, one flank's way at the
tip and the other's at the root, so the two flanks' contact radii decide what
it costs. ``station_checks`` reports all of it per face station, NOT gated
(the margin it shows awaits an owner ruling, #2481).
"""
from __future__ import annotations

import functools
import math
from dataclasses import dataclass, replace

import numpy as np

import _config
import dt_cone_pivot_post_spec as post
import dt_crank_drive_gear_spec as gear64
import dt_crank_pinion_spec as pinion
import dt_crankshaft_spec as shaft
import dt_cone_gear_shaft_spec as cone_shaft
from cone_line import COS_I, POST_STATION, SIN_I
from cone_stack_end_play import CONE_FLOAT_NORTH
from _cone_axis_constants import GEAR_AXIS_SHIFT
from gear_seat_fit import GEAR_SEAT_CLEARANCE
from standard_mesh_checks import (
    MeshCheck,
    backlash,
    check_mesh,
    interference_margin,
    plane_gear,
    root_clearance,
)

R64 = gear64.PITCH_DIA / 2.0
R16 = pinion.PITCH_DIA / 2.0
FRAME_C2C = R64 + R16 + _config.fit("crank_mesh", "c2c_slack_mm")
FRAME_DY = post.CRANK_BORE_HEIGHT - post.BORE_HEIGHT
FRAME_DX = math.sqrt(FRAME_C2C**2 - FRAME_DY**2)
DC_PER_DY = FRAME_DY / FRAME_C2C
DC_PER_DX = FRAME_DX / FRAME_C2C
if not R64 > R16 > 0 or not FRAME_C2C > FRAME_DY > 0:
    raise AssertionError("fixed-centre mesh geometry needs ordered radii and real axis spacing")
GEAR64_POST_OFFSET = (
    gear64.LAYOUT_CENTRE_STATION + GEAR_AXIS_SHIFT + gear64.CENTRE_SHIFT_NORTH - POST_STATION
)
CRANK_RUNNING = shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM
CONE_RUNNING = cone_shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM
CRANK_BEARING_LENGTH = shaft.JOURNAL_SUPPORT_SPAN_MIN_MM
CONE_BEARING_LENGTH = cone_shaft.JOURNAL_SUPPORT_SPAN_MIN_MM
CRANK_SUPPORT_NORTH_MIN = (
    shaft.SHAFT_LENGTH + shaft.SHAFT_LENGTH_BAND[1]
    - shaft.JOURNAL_INBOARD_STATION - shaft.STATION_ROW
)
_FACE_UPPER = pinion.printed_deviations(
    pinion.FACE_WIDTH, pinion.FACE_WIDTH_PLACES, pinion.FACE_WIDTH_LIMITS, unit=pinion.UNIT
)[1]
PINION_HALF_FACE_MAX = (pinion.FACE_WIDTH + _FACE_UPPER) / 2.0
CRANK_OVERHANG = (
    shaft.SEAT_PINION + pinion.SEAT_GAP_MAX_MM - pinion.SEAT_FEELER_MM
    + PINION_HALF_FACE_MAX - CRANK_SUPPORT_NORTH_MIN
)
CONE_OVERHANG = GEAR64_POST_OFFSET - post.CONE_BOSS_LENGTH / 2.0
MESH_LEVER = post.CRANK_BOSS_NORTH_FACE + pinion.SEAT_GAP_MAX_MM + PINION_HALF_FACE_MAX
POST_ANGLE_DEG = post.CRANK_BORE_ANGLE_LIMIT_DEG
TOOTH_RUNOUT_TIR_MM = gear64.TOOTH_RUNOUT_TIR_MM
TIP_ROOT_BAND_RADIAL = max(pinion.OUTSIDE_DIA_TOLERANCE_MM, gear64.OUTSIDE_DIA_TOLERANCE_MM) / 2.0
SPACING_PRINTED = post.CRANK_ABOVE_CONE + pinion.printed_deviations(
    post.CRANK_ABOVE_CONE,
    post.DRAWING_PRECISION_BY_NAME["CrankAboveCone"],
    (0.0, 0.0),
    unit=shaft.POST_UNIT,
)[0]
if not (CRANK_BEARING_LENGTH > 0 and CRANK_SUPPORT_NORTH_MIN > 0 and CRANK_OVERHANG >= 0):
    raise AssertionError("crankshaft journal must support the 16T mesh plane")
if abs(SPACING_PRINTED - FRAME_DY) >= 0.01:
    raise AssertionError("printed post bore spacing diverges from the mesh reference")


def _float_at_rest(clearance: float, bearing_length: float, overhang: float) -> float:
    """Journal float at the mesh: c/2 plus the c/L tilt over the overhang."""
    return clearance / 2.0 + clearance / bearing_length * max(overhang, 0.0)


# Centre-distance terms (mm). Shaft floats and runouts can act either way;
# the printed spacing band and the cone stack's north float only open.
_SYMMETRIC_TERMS = {
    "crank float at rest": _float_at_rest(CRANK_RUNNING[1], CRANK_BEARING_LENGTH, CRANK_OVERHANG),
    "cone float at rest": _float_at_rest(CONE_RUNNING[1], CONE_BEARING_LENGTH, CONE_OVERHANG),
    "gear bore clearance": (pinion.BORE_DIAMETRAL_CLEARANCE[1] + GEAR_SEAT_CLEARANCE[1]) / 2.0,
    "tooth-to-bore cutting runout (both gears)": TOOTH_RUNOUT_TIR_MM,
    "post bore angularity at the mesh": MESH_LEVER * math.tan(math.radians(POST_ANGLE_DEG)),
}
CLOSING_TERMS = {
    **_SYMMETRIC_TERMS,
    "crank bore spacing": -(SPACING_PRINTED + post.CRANK_ABOVE_CONE_BAND[1] - FRAME_DY) * DC_PER_DY,
}
OPENING_TERMS = {
    **_SYMMETRIC_TERMS,
    "crank bore spacing": (SPACING_PRINTED + post.CRANK_ABOVE_CONE_BAND[0] - FRAME_DY) * DC_PER_DY,
    "cone stack north float": CONE_FLOAT_NORTH * SIN_I * COS_I * DC_PER_DX,
}
CENTRE_RANGE_MM = (
    FRAME_C2C - sum(max(v, 0.0) for v in CLOSING_TERMS.values()),
    FRAME_C2C + sum(max(v, 0.0) for v in OPENING_TERMS.values()),
)

_BETA = math.radians(gear64.TOOTH_INCLINATION_DEG)
EQUIVALENT_RADIUS_GROWTH_64 = R64 / math.cos(_BETA) ** 2 - R64


def _normal_section_64(profile):
    gear = plane_gear(profile, gear64.MODULE_MM, radius_growth=EQUIVALENT_RADIUS_GROWTH_64,
                      thickness_scale=math.cos(_BETA))
    return replace(gear, teeth=round(gear64.TEETH / math.cos(_BETA) ** 3))


def standard_check() -> MeshCheck:
    """AGMA-style closed-form check over every printed corner and the centre range."""
    grow = EQUIVALENT_RADIUS_GROWTH_64
    return check_mesh(
        "crank 16T/64T",
        (plane_gear(pinion.STOCK_PROFILE, pinion.MODULE_MM),
         _normal_section_64(gear64.STOCK_PROFILE), FRAME_C2C + grow),
        [plane_gear(profile, pinion.MODULE_MM) for _, profile in pinion.STOCK_PROFILE_CORNERS],
        [_normal_section_64(profile) for _, profile in gear64.STOCK_PROFILE_CORNERS],
        (CENTRE_RANGE_MM[0] + grow, CENTRE_RANGE_MM[1] + grow),
        gear64.CUTTER_PRESSURE_ANGLE_DEG,
        gear64.NORMAL_MODULE_MM,
    )


# Mid-face's distance from where the axes cross in plan, along the 64T axis:
# the plan offset FRAME_DX closes at tan(i) per unit of axis.
PLAN_CROSSING_TO_MIDFACE = FRAME_DX * COS_I / SIN_I
# South face, south quarter, mid-face, north quarter, north face (+ = north).
FACE_STATIONS_MM = tuple(gear64.FACE_WIDTH * k for k in (-0.5, -0.25, 0.0, 0.25, 0.5))


def centre_at_station(station_mm: float) -> float:
    """Nominal centre distance at a 64T face station (mm north of mid-face)."""
    plan = (PLAN_CROSSING_TO_MIDFACE + station_mm) * SIN_I / COS_I
    return math.hypot(FRAME_DY, plan)


def _gap_arc_on_pitch_circle(shift_mm: float) -> float:
    """Arc the straight tooth space takes from the pitch circle where its
    transverse section sits ``shift_mm`` off the radial line (straight_gash:
    (X, Y/cos(beta) + shift))."""
    form, cos_beta = gear64.TOOTH_SPACE_FORM, math.cos(_BETA)

    def azimuth(side: int) -> float:
        def point(u: float) -> tuple[float, float]:
            x, y = form.flank_point(u, side)
            return x, y / cos_beta + shift_mm

        low, high = form.flank_parameter_min, form.flank_parameter_max
        if not math.hypot(*point(low)) < R64 < math.hypot(*point(high)):
            raise AssertionError("the 64T pitch circle must cross the cutter flank")
        for _ in range(80):
            middle = (low + high) / 2.0
            if math.hypot(*point(middle)) < R64:
                low = middle
            else:
                high = middle
        x, y = point((low + high) / 2.0)
        return math.atan2(y, x)

    return R64 * (azimuth(1) - azimuth(-1))


def straight_tooth_thickening(station_mm: float) -> float:
    """Normal circular thickness a straight 64T tooth gains on the pitch
    circle at a face station (mm north of mid-face), over its thickness at the
    crossing station that ``standard_check`` books."""
    height = gear64.FACE_WIDTH / 2.0 + station_mm
    shift = (height - gear64.TOOTH_SPACE_CROSSING) * math.tan(_BETA)
    return (_gap_arc_on_pitch_circle(0.0) - _gap_arc_on_pitch_circle(shift)) * math.cos(_BETA)


def straight_root_rise(station_mm: float) -> float:
    """Radial rise of a straight tooth space's root at a face station."""
    height = gear64.FACE_WIDTH / 2.0 + station_mm
    shift = (height - gear64.TOOTH_SPACE_CROSSING) * math.tan(_BETA)
    return math.hypot(gear64.ROOT_DIA / 2.0, shift) - gear64.ROOT_DIA / 2.0


_LEAN_FLANK_SAMPLES = 400
_LEAN_MESH_PHASES = 61


def _as_cut_flank(shift_mm: float, side: int) -> tuple[np.ndarray, np.ndarray]:
    """(radius, azimuth) along one flank of the straight tooth space's
    transverse section ``shift_mm`` off its radial line."""
    form = gear64.TOOTH_SPACE_FORM
    points = np.array(
        [
            form.flank_point(float(u), side)
            for u in np.linspace(
                form.flank_parameter_min, form.flank_parameter_max, 801
            )
        ]
    )
    tangential = points[:, 1] / math.cos(_BETA) + shift_mm
    return np.hypot(points[:, 0], tangential), np.arctan2(tangential, points[:, 0])


def _flank_turn(shift_mm: float):
    """turn(side, radius): how far (rad) each flank of the shifted space sits
    from the crossing-station form at a radius, less the turn of the space's
    centre on the pitch circle. At R64 the two sides' difference is the
    thickening; its change with radius is the lean."""
    shifted = {side: _as_cut_flank(shift_mm, side) for side in (1, -1)}
    crossing = {side: _as_cut_flank(0.0, side) for side in (1, -1)}
    low = max(curve[0][0] for curve in (*shifted.values(), *crossing.values()))
    high = min(curve[0][-1] for curve in (*shifted.values(), *crossing.values()))

    def raw(side: int, radius):
        radius = np.clip(radius, low, high)
        return np.interp(radius, *shifted[side]) - np.interp(radius, *crossing[side])

    centre_turn = (raw(1, R64) + raw(-1, R64)) / 2.0
    return lambda side, radius: raw(side, radius) - centre_turn


def _sampled_backlash(pin, gear, centre: float, turn, resolved: bool) -> float:
    """Smallest free circular backlash (on the 16T's operating pitch circle)
    through one pitch of mesh: both involute flanks of the engaged 64T spaces,
    each turned as the straight space is, sampled against the 16T's involute
    flanks. ``resolved`` takes the turn at each sample's own radius; otherwise
    every sample takes the pitch-circle turn (the thickening alone)."""
    alpha = math.radians(gear64.CUTTER_PRESSURE_ANGLE_DEG)
    grow, cos_beta = EQUIVALENT_RADIUS_GROWTH_64, math.cos(_BETA)
    base_p, base_g = (
        pin.pitch_radius * math.cos(alpha),
        gear.pitch_radius * math.cos(alpha),
    )
    pitch = 2.0 * math.pi * pin.pitch_radius / pin.teeth

    def involute(angle):
        return np.tan(angle) - angle

    radius = np.linspace(
        max(base_g, gear.root_radius_max), gear.tip_radius, _LEAN_FLANK_SAMPLES
    )
    space_half = (
        (pitch - gear.pitch_thickness) / (2.0 * gear.pitch_radius)
        + involute(np.arccos(base_g / radius))
        - involute(alpha)
    )
    # The normal section shows a transverse arc cos(beta) shorter, on the
    # virtual radius.
    flank = {
        side: side * space_half
        + (
            turn(side, radius - grow) * (radius - grow) / radius
            if resolved
            else turn(side, R64) * R64 / gear.pitch_radius
        )
        * cos_beta
        for side in (1, -1)
    }
    tooth_half = pin.pitch_thickness / (2.0 * pin.pitch_radius) + involute(alpha)
    least = math.inf
    for phase in np.linspace(-0.5, 0.5, _LEAN_MESH_PHASES):
        free = 0.0
        for side in (1, -1):
            clear = math.inf
            for pair in (-2, -1, 0, 1, 2):
                azimuth = (phase + pair) * pitch / gear.pitch_radius + flank[side]
                x, y = radius * np.cos(azimuth) - centre, radius * np.sin(azimuth)
                reach = np.hypot(x, y)
                met = reach <= pin.tip_radius
                if not met.any():
                    continue
                tooth_centre = math.pi - (phase + pair) * 2.0 * math.pi / pin.teeth
                off_centre = (np.arctan2(y, x)[met] - tooth_centre + math.pi) % (
                    2.0 * math.pi
                ) - math.pi
                half = tooth_half - involute(
                    np.arccos(base_p / np.maximum(reach[met], base_p))
                )
                clear = min(clear, float(np.min(-side * off_centre - half)))
            free += clear
        least = min(least, free)
    return least * centre * pin.pitch_radius / (pin.pitch_radius + gear.pitch_radius)


def sampled_station_backlash(station_mm: float, *, lean: bool) -> float:
    """Worst printed corner pair's sampled backlash at a face station's closed
    centre. With ``lean`` off it is the closed form less the thickening (the
    control); with it on, the straight flanks at their own contact radii."""
    grow = EQUIVALENT_RADIUS_GROWTH_64
    height = gear64.FACE_WIDTH / 2.0 + station_mm
    turn = _flank_turn((height - gear64.TOOTH_SPACE_CROSSING) * math.tan(_BETA))
    centre = CENTRE_RANGE_MM[0] + grow + centre_at_station(station_mm) - FRAME_C2C
    return min(
        _sampled_backlash(
            plane_gear(a, pinion.MODULE_MM), _normal_section_64(b), centre, turn, lean
        )
        for _, a in pinion.STOCK_PROFILE_CORNERS
        for _, b in gear64.STOCK_PROFILE_CORNERS
    )


@functools.lru_cache(maxsize=None)
def straight_tooth_lean(station_mm: float) -> float:
    """Backlash the straight 64T tooth's radial lean takes at a face station,
    beyond its pitch-circle thickening, with drive and coast contact at their
    own radii through the mesh cycle (plane model, ideal involutes)."""
    return sampled_station_backlash(station_mm, lean=False) - sampled_station_backlash(
        station_mm, lean=True
    )


@dataclass(frozen=True)
class StationCheck:
    station_mm: float
    centre_shift_mm: float
    tooth_thickening_mm: float  # straight 64T tooth, normal circular, booked below
    tooth_lean_mm: float  # contact-radius resolved; beside backlash_min_mm, not in it
    backlash_min_mm: float  # every printed corner pair, both centre-range ends
    interference_margin_mm: float  # at the closed end; crossing-station tooth form
    root_clearance_mm: float  # at the closed end

    def text(self) -> str:
        return (
            f"station {self.station_mm:+.3f} mm: centre {self.centre_shift_mm:+.4f}, "
            f"straight tooth +{self.tooth_thickening_mm:.4f}, "
            f"lean takes {self.tooth_lean_mm:.4f} more, "
            f"backlash min {self.backlash_min_mm:.4f}, interference margin "
            f"{self.interference_margin_mm:.3f}, root clearance {self.root_clearance_mm:.3f}"
        )


def station_checks() -> tuple[StationCheck, ...]:
    """The standard check's corners at each face station's centre and straight
    tooth (reported only). Backlash loses the tooth's thickening and root
    clearance the root's rise; the interference margin keeps the
    crossing-station tooth form. The lean is reported beside the backlash and
    is not taken from it: it is a plane-model figure, and on the real crossed
    axes it does not simply add to the other terms (#2481)."""
    grow = EQUIVALENT_RADIUS_GROWTH_64
    alpha = math.radians(gear64.CUTTER_PRESSURE_ANGLE_DEG)
    pins = [plane_gear(profile, pinion.MODULE_MM) for _, profile in pinion.STOCK_PROFILE_CORNERS]
    gears = [_normal_section_64(profile) for _, profile in gear64.STOCK_PROFILE_CORNERS]
    rows = []
    for station in FACE_STATIONS_MM:
        shift = centre_at_station(station) - FRAME_C2C
        closed = CENTRE_RANGE_MM[0] + grow + shift
        thickening = straight_tooth_thickening(station)
        rows.append(StationCheck(
            station,
            shift,
            thickening,
            straight_tooth_lean(station),
            min(backlash(a, b, c + grow + shift, alpha)
                for a in pins for b in gears for c in CENTRE_RANGE_MM) - thickening,
            min(interference_margin(a, b, closed, alpha) for a in pins for b in gears),
            min(root_clearance(a, b, closed) for a in pins for b in gears)
            - straight_root_rise(station),
        ))
    return tuple(rows)


def station_text() -> str:
    return "\n".join(
        ["crank mesh by 64T face station (REPORTED, not gated; #2481):"]
        + [f"  {row.text()}" for row in station_checks()]
    )


def stack_text() -> str:
    lines = [f"fixed-centre crank mesh: nominal C {FRAME_C2C:.4f} mm, range "
             f"{CENTRE_RANGE_MM[0]:.4f}..{CENTRE_RANGE_MM[1]:.4f} mm"]
    lines += [f"  closing {name:42s} {value:.5f}" for name, value in CLOSING_TERMS.items()]
    lines += [f"  opening {name:42s} {value:.5f}" for name, value in OPENING_TERMS.items()]
    lines.append("  " + standard_check().text())
    lines.append(station_text())
    return "\n".join(lines)


if __name__ == "__main__":
    print(stack_text())
