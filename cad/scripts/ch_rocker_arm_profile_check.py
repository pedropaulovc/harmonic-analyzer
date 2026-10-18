r"""The rocker arm's surface-profile check (plan ch_rocker_arm S7 op 97).

Both printed profile zones (MHA-CH-006: the top edge's 0.5 Ⓤ0.5 and the lower
outline's 0.5 Ⓤ0 between J and K, each to A|B|C) are read against the arm
outline template (MHA-CH-006-TL-13, inventory gauges.rocker-profile-gauge),
pinned on the arm in datums A and C. A DTI (gauges.dti) on the height gauge's
scriber (gauges.height-gauge) is zeroed on the template's edge and read on
the arm's edge directly above it, so each reading o is how far the arm's edge
stands out beyond the template's (+ proud, - shy), along the edge's normal.

Accept windows, per outline segment (the arithmetic, at any point Q of it at
least ``INSET_MM`` from a corner):

* tau(Q): the template edge's offset into the material from the rocker's
  BASIC outline, from the template spec's actual geometry (lines at mid-zone,
  arcs on the trammel radii, so tau carries the arcs' mid-zone residual
  exactly);
* the zone, into the material: d in [-U, t - U] (t, U the printed frame's);
* the arm reads o = tau - d, so the zone is o in [tau - (t - U), tau + U];
* the guard g(Q) = the template's clocking_error at Q (half its printed
  surface profile, ``OUTLINE_PROFILE_ZONE``, plus the pins' registration) + the DTI's resolution;
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
import ch_rocker_arm_tl_outline_template_spec as template
import draw_ch_rocker_arm as drawing
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
_CENTRE = (0.0, rocker.CENTER_Y - rocker.PIVOT_MID_Y)
_XY = tuple[float, float]


def _arc(radius: float, x: float) -> _XY:
    return (x, template.CENTER_Y - math.sqrt(radius**2 - x**2))


def _line_offset(point: _XY, line: tuple[_XY, _XY]) -> float:
    """``point``'s offset into the material from the rocker's BASIC ``line``."""
    normal = template._inward(*line)
    return (point[0] - line[0][0]) * normal[0] + (point[1] - line[0][1]) * normal[1]


def _radial(point: _XY) -> float:
    return math.hypot(point[0] - _CENTRE[0], point[1] - _CENTRE[1])


# Each segment: the drawing feature, its printed frame, the template's edge
# end to end along the +X half, and tau. The -X half is the mirror image.
_TOP_END = (template.TOP_END_X, template.TOP_END_Y)
_TIP = (template.TIP_X, template.TIP_Y)
_BOT_END = (template.BOT_END_X, template.BOT_END_Y)
SEGMENTS: dict[str, dict] = {
    "top arc": {
        "features": ("top_edge",),
        "frame": "TopRadius",
        "label": f"the R{rocker.R_TOP:g} top arc",
        "edge": lambda s: _arc(template.R_TOP, s * template.TOP_END_X),
        "length": template.R_TOP * template.ALPHA_TOP,
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
        "length": template.TIP_FACE,
        "tau": lambda q: _line_offset(q, template.ROCKER_LAND),
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
        "tau": lambda q: _line_offset(q, template.ROCKER_TAPER),
    },
    "bottom arc": {
        "features": ("profile_outer",),
        "frame": "BottomRadius",
        "label": f"the R{rocker.R_BOTTOM:g} bottom arc",
        "edge": lambda s: _arc(template.R_BOTTOM, s * template.BOT_END_X),
        "length": template.R_BOTTOM * template.ALPHA_BOT,
        "tau": lambda q: (
            rocker.R_BOTTOM - _radial(q)
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
    return template.clocking_error(point, normal) + DTI_RESOLUTION_MM


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
TEMPLATE_READ_MM = round(template.THICK / 2.0, 1)  # 1.6
ARM_READ_MM = round(template.THICK + rocker.HUB_LENGTH / 2.0, 1)  # 6.7


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
        f"Both printed profile zones, read against the arm outline template (gauges.rocker-profile-gauge) "
        f"pinned in datums A and C: the top edge ({ZONE_MM:g}, all outside the R{rocker.R_TOP:g} BASIC arc) and "
        f"the lower outline J to K ({ZONE_MM:g}, all inside the BASIC outline: the R{rocker.R_BOTTOM:g} arc, both "
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
        f"template's edge sits in it, shrunk at every point by the template's clocking_error (half its own "
        f"{template.OUTLINE_PROFILE_ZONE:g} mm surface profile to {'|'.join(template.OUTLINE_PROFILE_DATUMS)}, "
        f"plus the pins' registration, at most {template.ROD_CLOCKING_WORST:.3f} mm) and the DTI's "
        f"{DTI_RESOLUTION_MM:.4f} mm resolution, rounded inward to 0.01 mm. The pin plays are #1413 placeholders, "
        f"not a calibration; remeasure them before shop acceptance.",
    ]
