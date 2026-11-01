r"""The rocker arm's surface-profile check (plan ch_rocker_arm S7 op 97).

Both printed profile zones (MHA-CH-06: the top edge's 0.5 Ⓤ0.5 and the lower
outline's 0.5 Ⓤ0 between J and K, each to A|B|C) are read against the arm
outline template (inventory gauges.arm-outline-template), pinned on the arm in
datums A and C. A DTI (gauges.dti) on the height gauge's scriber
(gauges.height-gauge) is zeroed on the template's edge and read on the arm's
edge directly above it, so each reading o is how far the arm's edge stands out
beyond the template's (+ proud, - shy), along the edge's normal.

The template is a shop-made gauge, not a CAD part: its retired TL CAD part's
Number stays reserved (cad/docs/subsystem-identities.md). This module owns the
gauge geometry the check reads (its edge and the two pins that register it on
the arm); the inventory record carries its physical envelope and acceptance.

Accept windows, per outline segment (the arithmetic, at any point Q of it at
least ``INSET_MM`` from a corner):

* tau(Q): the template edge's offset into the material from the rocker's
  BASIC outline, from the template's actual geometry below (lines at
  mid-zone, arcs on the trammel radii, so tau carries the arcs' mid-zone
  residual exactly);
* the zone, into the material: d in [-U, t - U] (t, U the printed frame's);
* the arm reads o = tau - d, so the zone is o in [tau - (t - U), tau + U];
* the guard g(Q) = the template's clocking_error at Q (its +/-0.03 profile
  acceptance plus the pins' registration) + the DTI's resolution;
* accept: o in [max(tau - (t - U) + g), min(tau + U - g)], rounded inward to
  0.01; reject: o outside [min(tau - (t - U) - g), max(tau + U + g)], rounded
  outward; between them (or off the dial) the reading is indeterminate.

AUTHOR'S CHOICE (like S7 op 30's position guardband): the guard, the 1 mm
corner inset and the 0.01 rounding. Pedro may overrule them.
"""

from __future__ import annotations

import math
import tomllib

import ch_rocker_arm_spec as rocker
import _rocker_interface as rocker_interface
import draw_ch_rocker_arm as drawing
from _hole_spec import blind_cut_dia_mm
from _printed_tolerance import (
    drilled_oversize_mm,
    drilled_undersize_mm,
    printed_band_mm,
)
from _process_plans import PROCESS_ROOT

INCH = 25.4
INSET_MM = 1.0  # stations stay this far from a corner (AUTHOR'S CHOICE)
_SAMPLES = 64
_PLACES = 2

_GAUGES = tomllib.loads(
    (PROCESS_ROOT / "shop" / "inventory.toml").read_text(encoding="utf-8")
)["gauges"]
DTI_RESOLUTION_MM = _GAUGES["dti"]["resolution_in"]["value"] * INCH  # 0.0127
DTI_TRAVEL_IN = _GAUGES["dti"]["range_in"]
ZONE_MM = float(drawing.ARC_PROFILE_ZONE_MM)
OUTSIDE_MM = {
    frame: float(value) for frame, value in drawing.ARC_PROFILE_OUTSIDE_MM.items()
}
_CENTRE = (0.0, rocker_interface.CENTER_Y - rocker_interface.PIVOT_MID_Y)
_XY = tuple[float, float]

# ---------------------------------------------------------------------------
# The arm outline template (gauges.arm-outline-template): an O1 plate carrying
# the rocker's finished outline (the R800 top and R816 bottom arcs about the
# pivot, the radial tip lands and the tapered ends), a reamed hole for a pin
# gauge in the arm's pivot bore and a radial slot for a second pin gauge in
# its rod-pin hole, which clocks it. Frame: origin on the pivot-hole axis in
# the face laid on the arm, +Y toward the arcs' common centre (the mirror line
# is the Y axis), +X toward the rocker's connecting-rod end, plate Z0..THICK.
#
# Every edge derives from the rocker's own CAD source and aims at the middle
# of its 0.5 surface-profile zone (rocker.TOP_EDGE_BAND): outside on the top
# arc, inside on the lower outline, leaving the zone's whole width to the
# filing that follows. The arcs sit half the zone higher, on the trammel's own
# radii; the tip lands and tapered ends are offset half the zone along their
# own normals, since a rigid +Y shift put each tip land 0.0453 OUTSIDE the
# lower zone (#1544).
R_TOP = rocker.R_TOP
R_BOTTOM = rocker_interface.R_BOTTOM
_ROCKER_ZONE = rocker.TOP_EDGE_BAND[0] - rocker.TOP_EDGE_BAND[1]
_MID_ZONE = _ROCKER_ZONE / 2.0  # 0.254 into the material on the lower outline
# The aim: the middle of the rocker's one-sided top-edge band.
_ROCKER_TOP_LOW = rocker.TOP_EDGE_ABOVE_PIVOT + rocker.TOP_EDGE_BAND[1]
_ROCKER_TOP_HIGH = rocker.TOP_EDGE_ABOVE_PIVOT + rocker.TOP_EDGE_BAND[0]
TOP_ABOVE_PIVOT = round((_ROCKER_TOP_LOW + _ROCKER_TOP_HIGH) / 2.0, 3)  # 8.254
CENTER_Y = TOP_ABOVE_PIVOT + R_TOP  # 808.254
BOTTOM_BELOW_PIVOT = round(R_BOTTOM - CENTER_Y, 3)  # 7.746
if abs(R_BOTTOM - R_TOP - rocker_interface.ARM_DEPTH) > 1e-9:
    raise AssertionError("rocker arcs are no longer ARM_DEPTH apart")
if abs(TOP_ABOVE_PIVOT + BOTTOM_BELOW_PIVOT - rocker_interface.ARM_DEPTH) > 1e-9:
    raise AssertionError(
        "template arcs are no longer ARM_DEPTH apart on the mirror line"
    )
if abs(_CENTRE[1] + (TOP_ABOVE_PIVOT - rocker.TOP_EDGE_ABOVE_PIVOT) - CENTER_Y) > 1e-9:
    raise AssertionError(
        "template arc centre is not the rocker's, raised by the aim offset"
    )
# The outline's stations are made to three places.
END_PLACES = 3
_ROCKER_MIDDLE = (0.0, _CENTRE[1] - (R_TOP + R_BOTTOM) / 2.0)


def _inward(start: _XY, end: _XY) -> _XY:
    """Unit normal of start -> end toward the arm's material."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    normal = (-dy / length, dx / length)
    side = (_ROCKER_MIDDLE[0] - start[0]) * normal[0] + (
        _ROCKER_MIDDLE[1] - start[1]
    ) * normal[1]
    return normal if side > 0.0 else (-normal[0], -normal[1])


def _offset(points: tuple[_XY, ...], by: float) -> tuple[_XY, ...]:
    normal = _inward(points[0], points[-1])
    return tuple((x + by * normal[0], y + by * normal[1]) for x, y in points)


def _crossing(p: _XY, d: _XY, q: _XY, e: _XY) -> _XY:
    s = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / (d[0] * e[1] - d[1] * e[0])
    return (p[0] + s * d[0], p[1] + s * d[1])


# The rocker's BASIC +X land (radial from its top-arc end) and taper, pivot frame.
_ROCKER_TOP_END = (
    R_TOP * math.sin(rocker._ALPHA_TOP),
    _CENTRE[1] - R_TOP * math.cos(rocker._ALPHA_TOP),
)
_ROCKER_TIP = (
    _ROCKER_TOP_END[0] + rocker.TIP_FACE * math.sin(rocker._ALPHA_TOP),
    _ROCKER_TOP_END[1] - rocker.TIP_FACE * math.cos(rocker._ALPHA_TOP),
)
_ROCKER_BOT_END = (
    rocker.BOT_END_X,
    _CENTRE[1] - math.sqrt(R_BOTTOM**2 - rocker.BOT_END_X**2),
)
ROCKER_LAND = (_ROCKER_TOP_END, _ROCKER_TIP)
ROCKER_TAPER = (_ROCKER_TIP, _ROCKER_BOT_END)
_LAND_AIM = _offset(ROCKER_LAND, _MID_ZONE)
_TAPER_AIM = _offset(ROCKER_TAPER, _MID_ZONE)
_TAPER_DIRECTION = (
    _TAPER_AIM[1][0] - _TAPER_AIM[0][0],
    _TAPER_AIM[1][1] - _TAPER_AIM[0][1],
)
# The land stays radial to CENTER_Y, aimed through its mid-zone line's middle;
# the half-angles are re-derived from the rounded stations so the outline
# closes exactly.
_LAND_AIM_MIDDLE = tuple((a + b) / 2.0 for a, b in zip(*_LAND_AIM, strict=True))
TOP_END_X = round(
    R_TOP
    * _LAND_AIM_MIDDLE[0]
    / math.hypot(_LAND_AIM_MIDDLE[0], _LAND_AIM_MIDDLE[1] - CENTER_Y),
    END_PLACES,
)  # 144.951
ALPHA_TOP = math.asin(TOP_END_X / R_TOP)
TOP_END_Y = CENTER_Y - R_TOP * math.cos(ALPHA_TOP)  # 21.491
_LAND_DIRECTION = (math.sin(ALPHA_TOP), -math.cos(ALPHA_TOP))
# Each tip land runs radially outward from the top arc's end to the mid-zone
# taper; the tapered end runs from its foot to the bottom arc's end.
TIP_FACE = round(
    math.dist(
        (TOP_END_X, TOP_END_Y),
        _crossing(
            (TOP_END_X, TOP_END_Y), _LAND_DIRECTION, _TAPER_AIM[0], _TAPER_DIRECTION
        ),
    ),
    END_PLACES,
)  # 5.699
TIP_X = TOP_END_X + TIP_FACE * _LAND_DIRECTION[0]  # 145.984
TIP_Y = TOP_END_Y + TIP_FACE * _LAND_DIRECTION[1]  # 15.887


def _taper_meets_bottom_arc() -> float:
    """X where the mid-zone taper line meets the template's bottom arc."""
    length = math.hypot(*_TAPER_DIRECTION)
    ex, ey = _TAPER_DIRECTION[0] / length, _TAPER_DIRECTION[1] / length
    fx, fy = _TAPER_AIM[0][0], _TAPER_AIM[0][1] - CENTER_Y
    b = fx * ex + fy * ey
    along = -b + math.sqrt(b * b - (fx * fx + fy * fy - R_BOTTOM**2))
    return _TAPER_AIM[0][0] + along * ex


BOT_END_X = round(_taper_meets_bottom_arc(), END_PLACES)  # 132.636
ALPHA_BOT = math.asin(BOT_END_X / R_BOTTOM)
BOT_END_Y = CENTER_Y - R_BOTTOM * math.cos(ALPHA_BOT)  # 3.102

# Plate: O1 ground flat stock, 1/8 in, thickness as supplied.
THICK = 3.175

# Shop acceptance (inventory gauges.arm-outline-template, Pedro 2026-10-11):
# DTI stations within +/-0.03 of nominal, taken about the pivot hole and the
# rod slot with pins in both.
DTI_ACCEPTANCE = 0.03

# Pivot locating hole: the rocker's Ø.256 bore size, reamed +.0006/.0000 so
# one bought 0.2558 in Class X minus pin gauge (gauges.vermont-class-x-2558-minus:
# 0.25576-0.25580 in, 6.4963-6.4973) locates it in the arm's bore. The shop's
# 0.001 in Class ZZ set stops at 0.2550, whose play alone is 0.0505;
# auto-selected 2026-10-15 after review timeout, Pedro may revisit.
PIVOT_HOLE_DIA = rocker.PIVOT_HOLE_DIA
PIVOT_HOLE_BAND = (0.01524, 0.0)  # +.0006/.0000
PIN_GAUGE_IN = 0.2558
PIN_GAUGE_CLASS_X_IN = 0.00004  # Class X tolerance, minus direction
PIN_GAUGE_MIN = (PIN_GAUGE_IN - PIN_GAUGE_CLASS_X_IN) * INCH  # 6.4963
PIN_GAUGE_MAX = PIN_GAUGE_IN * INCH  # 6.4973
_ROCKER_BORE_LOW = rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1]
_ROCKER_BORE_HIGH = rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0]
if PIN_GAUGE_MAX >= PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[1]:
    raise AssertionError("pin gauge does not enter the template hole")
if PIN_GAUGE_MAX >= _ROCKER_BORE_LOW:
    raise AssertionError("pin gauge does not enter the rocker's pivot bore")
# Laid on the arm, the pin's worst-case play in both bores (each at its
# largest, the pin at its smallest) shifts the template's edges.
LOCATOR_REGISTRATION_MAX = (
    math.ceil(
        1e4
        * (
            (PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0] - PIN_GAUGE_MIN) / 2.0
            + (_ROCKER_BORE_HIGH - PIN_GAUGE_MIN) / 2.0
        )
    )
    / 1e4
)  # 0.0265 = 0.0107 template + 0.0158 rocker, rounded up

# Rod-pin slot: the template's clocking. The rocker's datum C is its #47
# rod-pin hole (MHA-CH-06, Ø.008 position to A|B). The pivot pin alone leaves
# the template free to turn about the pivot; a pin gauge in the arm's rod-pin
# hole, through a slot at that hole's BASIC station, clocks it. The slot runs
# radially from the pivot, so the hole's radial position error and the pin's
# play only slide the pin along it: the slot's width alone sets the clocking.
_ROD_SLOT_PLACES = 3
ROD_SLOT_X = round(rocker_interface.ROD_HOLE_X, _ROD_SLOT_PLACES)  # 133.067 BASIC
ROD_SLOT_Y = round(
    rocker_interface.ROD_HOLE_Y - rocker_interface.PIVOT_MID_Y, _ROD_SLOT_PLACES
)  # 8.456
ROD_SLOT_LEVER = math.hypot(ROD_SLOT_X, ROD_SLOT_Y)  # 133.335
ROD_SLOT_AXIS = (ROD_SLOT_X / ROD_SLOT_LEVER, ROD_SLOT_Y / ROD_SLOT_LEVER)
_ROD_SLOT_TANGENT = (-ROD_SLOT_AXIS[1], ROD_SLOT_AXIS[0])
# The pin: the largest of the shop's 0.001 in Class ZZ minus set
# (gauges.pin-gauges; ASME B89.1.5 Class ZZ is 0.0002 in at this size) that
# enters the #47 hole at its drilled minimum.
ROD_PIN_GAUGE_IN = 0.0780
ROD_PIN_CLASS_ZZ_IN = 0.0002
ROD_PIN_MAX = ROD_PIN_GAUGE_IN * INCH  # 1.98120
ROD_PIN_MIN = (ROD_PIN_GAUGE_IN - ROD_PIN_CLASS_ZZ_IN) * INCH  # 1.97612
# The rocker's #47 hole at its sheet's drilled-hole band.
_ROD_HOLE_DIA = blind_cut_dia_mm(rocker.ROD_HOLE_SPEC)
_ROD_HOLE_LOW = _ROD_HOLE_DIA - drilled_undersize_mm(unit=rocker.UNIT)  # 1.994
_ROD_HOLE_HIGH = _ROD_HOLE_DIA + drilled_oversize_mm(unit=rocker.UNIT)  # 2.0956
if not ROD_PIN_MAX < _ROD_HOLE_LOW <= (ROD_PIN_GAUGE_IN + 0.001) * INCH:
    raise AssertionError("the rod-hole pin is no longer the set's largest that enters")
# The slot is a matched width on that pin: .078 +.0004/+.0001.
ROD_SLOT_WIDTH = 1.9812  # .078
ROD_SLOT_WIDTH_BAND = (0.01016, 0.00254)  # (upper, lower)
ROD_SLOT_WIDTH_MIN = ROD_SLOT_WIDTH + ROD_SLOT_WIDTH_BAND[1]
ROD_SLOT_WIDTH_MAX = ROD_SLOT_WIDTH + ROD_SLOT_WIDTH_BAND[0]
if ROD_SLOT_WIDTH_MIN - ROD_PIN_MAX <= 0.0:
    raise AssertionError("the rod-hole pin does not enter the smallest slot")
ROD_HOLE_RADIAL = float(rocker.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"]) / 2.0
ROD_HOLE_PLAY = (_ROD_HOLE_HIGH - ROD_PIN_MIN) / 2.0  # 0.0597
ROD_SLOT_PLAY = (ROD_SLOT_WIDTH_MAX - ROD_PIN_MIN) / 2.0  # 0.0076
# The slot's 0.75 run (inventory gauges.arm-outline-template; formerly
# ROD_SLOT_FLAT, three places) must admit the pin at the rocker's worst
# radial position error and play, so the radial slot absorbs that error and
# only its width sets the clocking below.
ROD_SLOT_FLAT = 0.75
if (ROD_SLOT_FLAT - printed_band_mm(_ROD_SLOT_PLACES)) / 2.0 < (
    ROD_HOLE_RADIAL + ROD_HOLE_PLAY + printed_band_mm(_ROD_SLOT_PLACES)
):
    raise AssertionError("the rod slot's run no longer lets the pin in")
# Clocking budget. A template laid on the arm moves rigidly: the pivot pin
# lets it shift by up to LOCATOR_REGISTRATION_MAX, and the rod pin lets the
# slot's centre move across the slot by up to ROD_CLOCKING_PLAY (its play in
# the rocker's hole and in the slot, plus the BASIC station's rounding off
# the rocker's hole). For an edge point p with unit normal n, the rotation
# that the slot allows is (e - d.t)/lever, where d is the pivot shift, e the
# cross-slot shift and t the slot's cross direction, so the edge moves
#     d.(n - g t) + g e,  g = (z x p).n / lever,
# at most |n - g t| LOCATOR_REGISTRATION_MAX + |g| ROD_CLOCKING_PLAY, plus the
# template's own DTI_ACCEPTANCE. The lever arm g reaches 1.10 at the tail end,
# whose top end is the worst station (top ends -X 0.159, +X 0.108; bottom
# ends 0.148 / 0.099; tapers 0.134 / 0.106; tip lands 0.062 / 0.062; apex 0.057).
_ROD_SLOT_ROUNDING = abs(
    (ROD_SLOT_X - rocker_interface.ROD_HOLE_X) * _ROD_SLOT_TANGENT[0]
    + (ROD_SLOT_Y - (rocker_interface.ROD_HOLE_Y - rocker_interface.PIVOT_MID_Y))
    * _ROD_SLOT_TANGENT[1]
)
ROD_CLOCKING_PLAY = ROD_HOLE_PLAY + ROD_SLOT_PLAY + _ROD_SLOT_ROUNDING  # 0.0674
# The template's share of the rocker's half-zone (0.25 either side of the
# aim): a template-gauge allocation, not a part tolerance. The other 0.09 is
# left to filing to the scribed line (#1545, approved 2026-10-15).
END_STATION_SHARE = 0.16


def clocking_error(point: _XY, normal: _XY, play: float | None = None) -> float:
    """Worst normal error of an outline point laid on the arm (unit ``normal``):
    the template's own acceptance plus the rigid motion the two pins allow.
    ``play`` overrides the cross-slot play (a round hole's, in the tests)."""
    cross = ROD_CLOCKING_PLAY if play is None else play
    gain = (point[0] * normal[1] - point[1] * normal[0]) / ROD_SLOT_LEVER
    pivot = math.hypot(
        normal[0] - gain * _ROD_SLOT_TANGENT[0], normal[1] - gain * _ROD_SLOT_TANGENT[1]
    )
    return DTI_ACCEPTANCE + pivot * LOCATOR_REGISTRATION_MAX + abs(gain) * cross


def outline_points(n: int = 200) -> list[_XY]:
    """The closed outline, bottom arc rod->tail, tail tip, top arc tail->rod, rod tip."""
    points: list[_XY] = []
    for i in range(n + 1):
        a = ALPHA_BOT - 2.0 * ALPHA_BOT * i / n
        points.append((R_BOTTOM * math.sin(a), CENTER_Y - R_BOTTOM * math.cos(a)))
    points.append((-TIP_X, TIP_Y))
    for i in range(n + 1):
        a = -ALPHA_TOP + 2.0 * ALPHA_TOP * i / n
        points.append((R_TOP * math.sin(a), CENTER_Y - R_TOP * math.cos(a)))
    points.append((TIP_X, TIP_Y))
    return points


def outline_clocking_errors(play: float | None = None) -> list[float]:
    """``clocking_error`` at both ends of every sampled outline segment, each
    with that segment's normal: arcs, tip lands and tapered ends alike."""
    points = outline_points()
    errors: list[float] = []
    for a, b in zip(points, points[1:] + points[:1], strict=True):
        length = math.dist(a, b)
        normal = ((a[1] - b[1]) / length, (b[0] - a[0]) / length)
        errors += [clocking_error(a, normal, play), clocking_error(b, normal, play)]
    return errors


if END_STATION_SHARE >= _ROCKER_ZONE / 2.0:
    raise AssertionError("the template's clocking share leaves nothing for filing")
ROD_CLOCKING_WORST = max(outline_clocking_errors())  # 0.1586, the tail's top end
if ROD_CLOCKING_WORST > END_STATION_SHARE + 1e-9:
    raise AssertionError(
        "pivot and rod-pin play carry an outline edge outside the template's share"
    )
# ---------------------------------------------------------------------------


def _arc(radius: float, x: float) -> _XY:
    return (x, CENTER_Y - math.sqrt(radius**2 - x**2))


def _line_offset(point: _XY, line: tuple[_XY, _XY]) -> float:
    """``point``'s offset into the material from the rocker's BASIC ``line``."""
    normal = _inward(*line)
    return (point[0] - line[0][0]) * normal[0] + (point[1] - line[0][1]) * normal[1]


def _radial(point: _XY) -> float:
    return math.hypot(point[0] - _CENTRE[0], point[1] - _CENTRE[1])


# Each segment: the drawing feature, its printed frame, the template's edge
# end to end along the +X half, and tau. The -X half is the mirror image.
_TOP_END = (TOP_END_X, TOP_END_Y)
_TIP = (TIP_X, TIP_Y)
_BOT_END = (BOT_END_X, BOT_END_Y)
SEGMENTS: dict[str, dict] = {
    "top arc": {
        "features": ("top_edge",),
        "frame": "TopRadius",
        "label": f"the R{rocker.R_TOP:g} top arc",
        "edge": lambda s: _arc(R_TOP, s * TOP_END_X),
        "length": R_TOP * ALPHA_TOP,
        "tau": lambda q: (
            _radial(q) - rocker.R_TOP
        ),  # the material lies away from the centre
    },
    "tip land": {
        "features": ("tip_land_pos_x", "tip_land_neg_x"),
        "frame": "BottomRadius",
        "label": "each tip land",
        "edge": lambda s: (
            _TOP_END[0] + s * (_TIP[0] - _TOP_END[0]),
            _TOP_END[1] + s * (_TIP[1] - _TOP_END[1]),
        ),
        "length": TIP_FACE,
        "tau": lambda q: _line_offset(q, ROCKER_LAND),
    },
    "taper": {
        "features": ("profile_outer",),
        "frame": "BottomRadius",
        "label": "each tapered end",
        "edge": lambda s: (
            _TIP[0] + s * (_BOT_END[0] - _TIP[0]),
            _TIP[1] + s * (_BOT_END[1] - _TIP[1]),
        ),
        "length": math.dist(_TIP, _BOT_END),
        "tau": lambda q: _line_offset(q, ROCKER_TAPER),
    },
    "bottom arc": {
        "features": ("profile_outer",),
        "frame": "BottomRadius",
        "label": f"the R{rocker_interface.R_BOTTOM:g} bottom arc",
        "edge": lambda s: _arc(R_BOTTOM, s * BOT_END_X),
        "length": R_BOTTOM * ALPHA_BOT,
        "tau": lambda q: (
            rocker_interface.R_BOTTOM - _radial(q)
        ),  # the material lies toward the centre
    },
}


def samples(name: str) -> list[tuple[_XY, _XY]]:
    """(point, unit normal) along a segment's +X and -X halves, inset from its corners."""
    segment = SEGMENTS[name]
    inset = INSET_MM / segment["length"]
    arc = name.endswith("arc")
    start = 0.0 if arc else inset  # an arc's mirror-line end is no corner
    points = []
    for i in range(_SAMPLES + 1):
        s = start + (1.0 - inset - start) * i / _SAMPLES
        a, b = segment["edge"](max(0.0, s - 1e-4)), segment["edge"](min(1.0, s + 1e-4))
        length = math.dist(a, b)
        normal = ((a[1] - b[1]) / length, (b[0] - a[0]) / length)
        point = segment["edge"](s)
        points += [(point, normal), ((-point[0], point[1]), (-normal[0], normal[1]))]
    return points


def guard(point: _XY, normal: _XY) -> float:
    return clocking_error(point, normal) + DTI_RESOLUTION_MM


def zone_readings(name: str, point: _XY) -> tuple[float, float]:
    """The readings o that keep the arm's edge in its zone at ``point``."""
    segment = SEGMENTS[name]
    u = OUTSIDE_MM[segment["frame"]]
    tau = segment["tau"]((abs(point[0]), point[1]))
    return tau - (ZONE_MM - u), tau + u


def window(name: str) -> dict[str, tuple[float, float]]:
    rows = [
        (zone_readings(name, point), guard(point, normal))
        for point, normal in samples(name)
    ]
    scale = 10**_PLACES
    return {
        "accept": (
            math.ceil(max(lo + g for (lo, _hi), g in rows) * scale - 1e-9) / scale,
            math.floor(min(hi - g for (_lo, hi), g in rows) * scale + 1e-9) / scale,
        ),
        "reject": (
            math.floor(min(lo - g for (lo, _hi), g in rows) * scale + 1e-9) / scale,
            math.ceil(max(hi + g for (_lo, hi), g in rows) * scale - 1e-9) / scale,
        ),
    }


WINDOWS = {name: window(name) for name in SEGMENTS}
for _name, _window in WINDOWS.items():
    if not _window["accept"][0] < 0.0 < _window["accept"][1]:
        raise AssertionError(
            f"{_name}: an edge filed to the template's line is not accepted"
        )
    if max(map(abs, _window["accept"])) > DTI_TRAVEL_IN * INCH / 2.0:
        raise AssertionError(f"{_name}: the accept window leaves the DTI's half travel")

# Read heights above the granite: the template's mid-thickness, then the
# strap's mid-plane, which is the hub's, so half the hub length above the
# template the arm's +Z hub face rests on.
TEMPLATE_READ_MM = round(THICK / 2.0, 1)  # 1.6
ARM_READ_MM = round(THICK + rocker.HUB_LENGTH / 2.0, 1)  # 6.7


def _signed(value: float) -> str:
    return f"{value:+.{_PLACES}f}"


def method_steps() -> list[str]:
    """The authored inspection_methods.surface_profile procedure, verbatim."""
    rows = "; ".join(
        f"{segment['label']} ({', '.join(segment['features'])}): accept {_signed(WINDOWS[name]['accept'][0])} to "
        f"{_signed(WINDOWS[name]['accept'][1])}, reject below {_signed(WINDOWS[name]['reject'][0])} "
        f"or above {_signed(WINDOWS[name]['reject'][1])}"
        for name, segment in SEGMENTS.items()
    )
    half_travel = DTI_TRAVEL_IN / 2.0
    return [
        f"Both printed profile zones, read against the arm outline template (gauges.arm-outline-template) "
        f"pinned in datums A and C: the top edge ({ZONE_MM:g}, all outside the R{rocker.R_TOP:g} BASIC arc) and "
        f"the lower outline J to K ({ZONE_MM:g}, all inside the BASIC outline: the R{rocker_interface.R_BOTTOM:g} arc, both "
        f"tapers and both tip lands, so the tip_land_pos_x and tip_land_neg_x zones are read here too). Done on "
        f"the granite surface plate (gauges.granite-surface-plate), off the rest plate.",
        "Clean the arm, the template and both pins and leave them on the granite for 30 min to reach its temperature.",
        "Lay the template flat on the granite, the face that is laid on the arm up.",
        "Seating: lower the arm onto it with strap datum B (the +Z strap face) down, so its +Z hub face rests on the "
        "template and the rod-pin hole sits over the rod slot. Datum A: push the 0.2558 in Class X pin "
        "(gauges.vermont-class-x-2558-minus) down through the pivot bore and the template's pivot hole to the "
        "granite. Datum C: push the 0.0780 in pin (gauges.pin-gauges) down through the rod-pin hole into the slot "
        "to the granite. Press on the hub: the arm must not rock; if it does, clean and reseat.",
        f"Gauge: the DTI (gauges.dti) on the height gauge's scriber (gauges.height-gauge), stylus horizontal, "
        f"its ball approaching each edge square to it from outside the part. A higher reading is an edge standing "
        f"farther out. The DTI reads inches: o (mm) = reading x {INCH:g}.",
        f"Stations (20; each at least {INSET_MM:g} mm from a corner, placed by eye): each arc on the mirror line, "
        f"halfway out and 2 mm short of each end (5 per arc); each tip land a third and two thirds along (2 per "
        f"land); each tapered end 2 mm from each corner and halfway (3 per taper).",
        f"At each station, zero: set the slider so the ball is {TEMPLATE_READ_MM:g} mm above the granite (the "
        f"template's mid-thickness), slide the gauge base in until the dial has turned half its travel "
        f"({half_travel:g} in) and set the bezel to zero. Read: without moving the base, raise only the slider "
        f"to {ARM_READ_MM:g} mm (the strap's mid-plane), letting the ball ride onto the arm's edge, and copy "
        f"{{o}}. Lower it back to {TEMPLATE_READ_MM:g} mm: if the dial is not back at zero within one division, "
        f"redo the station.",
        f"Decide each station with its segment's window, o in mm: {rows}. Between accept and reject, or off the "
        f"dial either way, the station is indeterminate: re-check on a CMM. The profile is accepted only when "
        f"every station accepts.",
        f"AUTHOR'S CHOICE guard (ch_rocker_arm_profile_check): each window is the zone, offset by where the "
        f"template's edge sits in it, shrunk at every point by the template's clocking_error (its own "
        f"{DTI_ACCEPTANCE:g} mm profile acceptance plus the pins' registration, at most "
        f"{ROD_CLOCKING_WORST:.3f} mm) and the DTI's {DTI_RESOLUTION_MM:.4f} mm resolution, rounded "
        f"inward to 0.01 mm. The template's acceptance and the pin plays are #1413 placeholders, not a "
        f"calibration; remeasure them before shop acceptance.",
    ]
