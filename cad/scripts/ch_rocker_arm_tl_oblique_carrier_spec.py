r"""Pure-data contract for the oblique-trammel carrier (MHA-CH-06-TL-21).

R4 workholding uses three ordinary #8-32 THRU taps: two end-waste clamps
at CL/CR and a HUB clamp. All use the common 91251A197 screw. There is no
precision carrier HUB bore, underside flange seat, CL dowel or LEFT receiver.
The strap is registered by the riser's end-waste stops, clamped at both ends,
then drilled and reamed in place over the riser's relief. The product's hub
hole, not this plate's thread, locates the top-hat washer.

Carrier coordinates: origin midway between A1/B1, X along the pin line,
Y toward the strap, Z0 at the top face. The 6061 plate is faced to .47 in
from 1/2 x 6 in stock and finished to 20.5 x 5.1 in. The feed-lever taps
retain their stated short engagement. No new workholding dimension carries
a custom tolerance.

Issue #2151 (owner Option B, 2026-11-06): one native hole table locates
every top-face hole from A1's actual axis, +X along A1-B1, at .XXX under the
title-block ±.005. The sole local exception is A2/B2 Y .964 ±.002 from the
A1-B1 axis line. The HUB row is REF: TL-00 step 10 taps it in situ at the
HUB DRO setting, so it has no manufactured XY. Kinematic geometric nominals
are unchanged; their printed rounding enters the budget below.

HUB_OFFSET is an assembly setting from the actual inner-pass apex.
HUB_RADIAL_STACK is that setting's band and printed rounding plus the
pin-shoulder clearance. Every strap hole is reamed at the same setting, so
no stud, nose or slip float enters the location. ``PIN_RELATIVE_ERROR``
bounds each strap edge's correlated pin-shape error against that SAME HUB;
``PIN_RELATIVE_STACK`` adds the two once per edge against half the
strap's 0/-.020 radial band.
"""

from __future__ import annotations

import math
from itertools import product

import _config
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as pivot_spacer
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_spec as rocker
from _fit_deviations import deviations
from _fit_ream_slide import REAM_SLIDE
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    printed_band_mm,
)

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-carrier",
    _config.parts("ch-rocker-arm-tl-oblique-carrier"),
)
if UNIT != trammel.CARRIER_UNIT:
    raise AssertionError("the carrier row and the calculator disagree on its unit")


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.0010``, ``8.861``."""
    text = f"{value_mm / trammel.INCH:.{places}f}"
    return text.replace("0.", ".", 1) if text.lstrip("-").startswith("0.") else text


def prints_exactly(value_mm: float, places: int) -> bool:
    """True when ``value_mm`` is an inch value on the ``places`` grid."""
    value_in = value_mm / trammel.INCH
    return abs(value_in - round(value_in, places)) <= 1e-9


_XX = printed_band_mm(2, unit=UNIT)
# Title-block DRILLED HOLES: the tap drills print with no band of their own.
DRILLED_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)

# --- Interface (TL-26 feed lever and the jig assembly import these) ---------
# PlateLength and PlateWidth print .X (no stack, wall or fit reads them);
# PlateNearY, which the lever-tap wall reads, prints .XX.
OUTLINE_X = (-260.35, 260.35)  # 20.5 overall
OUTLINE_Y = (-44.958, 84.582)  # -1.77 (.XX); 5.1 overall
THICKNESS = trammel.CARRIER_THICK
THICKNESS_PLACES = trammel.CARRIER_THICK_PLACES
THICKNESS_BAND = trammel.CARRIER_THICK_BAND
LEVER_HOLES = ((0.0, -22.098), (0.0, -38.1))  # -.87, -1.50
LEVER_INNER_END_Y = -14.986  # -.59

PLATE_LENGTH = OUTLINE_X[1] - OUTLINE_X[0]  # 20.5
PLATE_WIDTH = OUTLINE_Y[1] - OUTLINE_Y[0]  # 5.1
PLATE_NEAR_Y = -OUTLINE_Y[0]  # 1.77: the pin line to the -Y (operator) edge
PLATE_HALF_LENGTH = OUTLINE_X[1]  # 10.25: the centreline to either end

# --- Pivot-pin holes (calc) -------------------------------------------------
PIN_HOLES = trammel.PIN_HOLES
# Each pivot bore has a named axis for the shoulder-screw mate.
PIN_HOLE_AXES = {hole: f"PinAxis{hole}" for hole in PIN_HOLES}
D1 = trammel.D1
A2_DX = trammel.A2[0] - trammel.A1[0]  # -.2844 (outward)
A2_DY = trammel.A2[1] - trammel.A1[1]  # .9638
if abs(abs(A2_DX) - (trammel.D2 - trammel.D1) / 2.0) > 1e-9:
    raise AssertionError("A2 is not chained (D2 - D1)/2 outboard of A1")
# Fit doc F17: REAM_SLIDE on the 3/8 shoulder, cut by the owned .3760 reamer.
PIN_HOLE_DIA = 9.525  # .3750
PIN_HOLE_BAND = REAM_SLIDE  # +.0015/+.0010: .3760-.3765
PIN_MATE_BAND = pivot_screw.SHOULDER_DIA_BAND
_hole_low, _hole_high = deviations(PIN_HOLE_BAND)
_mate_low, _mate_high = deviations(PIN_MATE_BAND)
PIN_CLEARANCE_MIN = _hole_low - _mate_high
PIN_CLEARANCE_MAX = _hole_high - _mate_low
# Owner Option B, #2151: table locations, not chained ±.0008 dimensions.
TABLE_LOCATION_PLACES = 3
TABLE_LOCATION_BAND = printed_band_mm(TABLE_LOCATION_PLACES, unit=UNIT)
OUTER_Y_NOMINAL = 0.964 * trammel.INCH
OUTER_Y_BAND = 0.002 * trammel.INCH
OUTER_Y_DEVIATIONS = (
    OUTER_Y_NOMINAL - A2_DY - OUTER_Y_BAND,
    OUTER_Y_NOMINAL - A2_DY + OUTER_Y_BAND,
)
OUTER_Y_NOTE = "A2, B2: Y .964 ±.002 FROM THE A1-B1 AXIS LINE"
PIN_NUMBER = "MHA-CH-06-TL-VN-77"
# Ordinary receiver only. The strap's product bore is made at assembly;
# no precision carrier bore or underside seating feature survives R4.
HUB = trammel.HUB
CLAMP_THREAD = "#8-32"
CLAMP_SPEC = HoleSpec("tapped", CLAMP_THREAD)
CLAMP_TAP_DRILL = TAP_DRILL_MM[CLAMP_THREAD]
HUB_THREAD = CLAMP_THREAD
HUB_SPEC = HoleSpec("tapped", HUB_THREAD)
HUB_TAP_CALLOUT = "CLAMPS STRAP HUB\nLOCATION: TL-00 STEP 10"
# The mate's number and name print on rows of their own: on one row they
# made the block 91 mm wide, past the inner border and across the plate
# end's extension line.
PIN_HOLE_CALLOUT = (
    f"4X REAM THRU ({inch_text(PIN_CLEARANCE_MIN, 4)}-"
    f"{inch_text(PIN_CLEARANCE_MAX, 4)}\n"
    f"DIAMETRAL CLEARANCE ON\n{PIN_NUMBER}\nSHOULDER SCREW)"
)
# Functions are carried once by the table's NOTE column.
STRAP_NUMBER = "MHA-CH-13"
STRAP_DEPTH = trammel.R_OUTER - trammel.R_INNER

# Underside chamfer: clears the entry and leaves a spacer thrust seat.
PIN_CHAMFER = 0.3048  # .012
PIN_CHAMFER_BAND = (0.1016, 0.0)  # +.004/0
PIN_CHAMFER_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints ".012 MIN"
PIN_CHAMFER_PLACES = 3
_PIN_CHAMFER_MOUTH_MAX = (
    (PIN_HOLE_DIA + PIN_HOLE_BAND[0]) / 2.0 + PIN_CHAMFER + PIN_CHAMFER_BAND[0]
)
# The AS62-18-40 spacer's smallest OD (.625 -.005) bounds its thrust seat.
if _PIN_CHAMFER_MOUTH_MAX >= (pivot_spacer.OD + pivot_spacer.OD_BAND[1]) / 2.0:
    raise AssertionError("pin-hole chamfer consumes the spacer's thrust seat")
if not prints_exactly(PIN_CHAMFER, PIN_CHAMFER_PLACES):
    raise AssertionError("the pin-hole chamfer must print exactly at its places")
# The hidden reference sketch section A-A imports (fr_nameplate's
# SectionReference): the printed chamfer leg, which drives the chamfer
# feature's distance, and the finished thickness, driven from Plate's depth. A
# partial section imports a hidden sketch in its plane (pd_platen A-A, pivot
# block B-B) but not a body feature's depth: jig-r4/r5 asked it for Plate's
# and got nothing at all, as ms_stick's G-G did for its cut depth. It lies on
# SECTION_PLANE, a named hidden plane coincident with the Front plane (the
# A1-B1 pin line, model Z = 0): every fleet section that imports a sketch
# has it on a dedicated plane in the cut (pd_platen and the pivot block's
# CboreSectionPlane, fr_nameplate's SectionAPlane); on the bare Front plane
# jig-r6's import came back empty.
SECTION_PLANE = "SectionAPlane"
SECTION_REFERENCE = "SectionReference"
PIN_CHAMFER_CALLOUT = "X 45\u00b0, 4X UNDERSIDE\nSEATS ON TL-VN-78 SPACER"
# Section A-A cuts SECTION_HALF_SPAN either side of A1's axis; the stock line
# stands STOCK_REFERENCE_INSET inside the cut's +X end, so the thickness's
# extension lines leave the slab at its end.
SECTION_HALF_SPAN = 9.0
STOCK_REFERENCE_INSET = 0.5
STOCK_REFERENCE_DX = SECTION_HALF_SPAN - STOCK_REFERENCE_INSET
if not PIN_HOLE_DIA / 2.0 + 2.0 <= STOCK_REFERENCE_DX < SECTION_HALF_SPAN:
    raise AssertionError("the stock line must stand in A1's +X wall, inside the cut")

# --- Ordinary workholding taps -----------------------------------------------
CL = trammel.CL
CR = trammel.CR
END_CLAMPS = {"CL": CL, "CR": CR}
CL_SPEC = HoleSpec("tapped", CLAMP_THREAD)
CR_SPEC = HoleSpec("tapped", CLAMP_THREAD)
END_CLAMP_TAP_CALLOUT = f"CLAMPS {STRAP_NUMBER}\nEND WASTE"
# Hidden model baseline drivers; only EdgeX remains a printed dimension.
STATION_REFERENCE = "StationReference"
REFERENCE_SKETCHES = (SECTION_REFERENCE, STATION_REFERENCE)

RISER_SCREWS = trammel.RISER_SCREWS
RISER_THREAD = "#4-40"
RISER_SPEC = HoleSpec("tapped", RISER_THREAD)
RISER_TAP_DRILL = TAP_DRILL_MM[RISER_THREAD]
# The riser (MHA-CH-06-TL-24) is self-cut along the jig's band and its holes
# are spotted through these taps at assembly, so their stations set the
# screws' worst-case walls to its cut edges: trammel.RISER_SCREW_WALLS assumes
# them at RISER_TAP_STATION_PLACES' title-block band.
RISER_STATION_PLACES = trammel.RISER_TAP_STATION_PLACES
RISER_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-riser")["number"]
RISER_TAP_CALLOUT = f"HOLDS {RISER_NUMBER} SCREWS\nCLEAR OF ITS CUT EDGES"

LEVER_THREAD = "5/16-18"
LEVER_SPEC = HoleSpec("tapped", LEVER_THREAD)
LEVER_TAP_DRILL = TAP_DRILL_MM[LEVER_THREAD]

# --- Hidden X drivers: unchanged nominal geometry, baselines from A1 ----------
# Hole Wizard placement sketches cannot contain a datum point. Keep the
# existing baseline driver sketch, but only EdgeX prints as a dimension.
# The native table reads actual hole axes, not these construction points.
STATIONS = {
    "EdgeX": (OUTLINE_X[0], OUTLINE_Y[0]),
    "ClX": CL,
    "LeverX": LEVER_HOLES[0],
    "RiserX1": RISER_SCREWS[0],
    "RiserX1R": RISER_SCREWS[1],
    "RiserX2": RISER_SCREWS[2],
    "RiserX2R": RISER_SCREWS[3],
    "CrX": CR,
}

# --- Rule 18: full thread at the worst case ------------------------------------
# Every tap runs THRU the faced plate: its finished .XX low limit, less the
# tap mouth's title-block edge break and one pitch of incomplete lead.
TAP_MOUTH_BREAK = edge_break_chamfer_mm(unit=UNIT)


def _pitch(thread: str) -> float:
    return trammel.INCH / float(thread.rsplit("-", 1)[1])


ENGAGEMENT_MM = {
    thread: THICKNESS - THICKNESS_BAND - TAP_MOUTH_BREAK - _pitch(thread)
    for thread in (CLAMP_THREAD, RISER_THREAD, LEVER_THREAD)
}
ENGAGEMENT_D = {
    thread: length / THREAD_MAJOR_MM[thread] for thread, length in ENGAGEMENT_MM.items()
}
# A finished .47 plate cannot hold 1.5D of 5/16-18: the lever taps are the one
# stated shortfall (rule 20), each value floored to its printed places (a MIN
# never rounds up, pd_transgear_arm_spec.engagement_line).
SHORT_ENGAGEMENT = (LEVER_THREAD,)
for _thread, _d in ENGAGEMENT_D.items():
    if (_d < 1.5) != (_thread in SHORT_ENGAGEMENT):
        raise AssertionError(f"{_thread} engagement {_d:.3f}D is not as stated")
_ENGAGED_IN = (
    math.floor(ENGAGEMENT_MM[LEVER_THREAD] / trammel.INCH * 1000.0 + 1e-9) / 1000.0
)
_ENGAGED_D = math.floor(ENGAGEMENT_D[LEVER_THREAD] * 100.0 + 1e-9) / 100.0
LEVER_TAP_CALLOUT = (
    f"ENGAGEMENT {inch_text(_ENGAGED_IN * trammel.INCH, 3)} MIN ({_ENGAGED_D:.2f}D)"
)

# --- Rule 17 walls at worst case (.XX stations and edge) -----------------------
_LEVER_MAJOR_R = THREAD_MAJOR_MM[LEVER_THREAD] / 2.0
WALLS_MM: dict[str, float] = {
    "lever tap to -Y edge": (PLATE_NEAR_Y - _XX)
    - (-LEVER_HOLES[1][1] + _XX)
    - _LEVER_MAJOR_R,
    "lever taps web": (LEVER_HOLES[0][1] - LEVER_HOLES[1][1] - 2.0 * _XX)
    - 2.0 * _LEVER_MAJOR_R,
}
for _wall, _mm in WALLS_MM.items():
    if _mm < WALL_TARGET_MM:
        raise AssertionError(f"carrier {_wall} wall {_mm:.3f} under rule 17's .080")

# --- No skid: sag between the pins -----------------------------------------------
E_6061 = 69_000.0  # N/mm^2
DENSITY_6061 = 2.70e-6  # kg/mm^3
_I = PLATE_WIDTH * THICKNESS**3 / 12.0
_Q = DENSITY_6061 * 9.81 * PLATE_WIDTH * THICKNESS  # N/mm
SAG_SELF_WEIGHT = 5.0 * _Q * D1**4 / (384.0 * E_6061 * _I)
CUTTING_LOAD_N = 10.0
SAG_CUTTING_LOAD = CUTTING_LOAD_N * D1**3 / (48.0 * E_6061 * _I)

# --- Drawing --------------------------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateLength", "PlateWidth", "PlateNearY"},
    "PinHoleProfile": {"PinHoleDia"},
    SECTION_REFERENCE: {"PinChamferSize", "StockThick"},
    STATION_REFERENCE: {"EdgeX"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {
        "PlateLength": 1,
        "PlateWidth": 1,
        "PlateNearY": 2,
    },
    # Size remains four-place; unprinted kinematic drivers follow table places.
    "PinHoleProfile": {
        "PinSpacing": TABLE_LOCATION_PLACES,
        "PinHoleDia": 4,
        "A2DX": TABLE_LOCATION_PLACES,
        "A2DY": TABLE_LOCATION_PLACES,
        "B2DX": TABLE_LOCATION_PLACES,
        "B2DY": TABLE_LOCATION_PLACES,
    },
    SECTION_REFERENCE: {
        "PinChamferSize": PIN_CHAMFER_PLACES,
        "StockThick": THICKNESS_PLACES,
    },
    "ClTap": {"ClY": TABLE_LOCATION_PLACES},
    # The left end at the outline's .X; the hidden drivers at table places.
    STATION_REFERENCE: {
        "EdgeX": 1,
        "ClX": TABLE_LOCATION_PLACES,
        "LeverX": TABLE_LOCATION_PLACES,
        "CrX": TABLE_LOCATION_PLACES,
        **{name: RISER_STATION_PLACES for name in STATIONS if name.startswith("Riser")},
    },
    "CrTap": {"CrY": TABLE_LOCATION_PLACES},
    "RiserTaps": {"RiserY1": RISER_STATION_PLACES, "RiserY2": RISER_STATION_PLACES},
    "LeverTaps": {"LeverY1": TABLE_LOCATION_PLACES, "LeverY2": TABLE_LOCATION_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if not set().union(*DRAWING_DIMENSIONS.values()) <= set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every marked carrier dimension needs authored places")

# The in-place STRAP hole follows the actual inner-pass apex. There is no
# stud/nose float in this location stack; the correlated pin-relative error
# below completes it.
_TOP_EDGE_HALF_BAND = (max(rocker.TOP_EDGE_BAND) - min(rocker.TOP_EDGE_BAND)) / 2.0
HUB_OFFSET_PLACES = 4  # a .0001 DRO, as the alignment table
HUB_OFFSET_BAND = 0.0005 * trammel.INCH  # ±.0005 on the DRO setting
HUB_OFFSET_PRINTED = (
    round(trammel.HUB_OFFSET / trammel.INCH, HUB_OFFSET_PLACES) * trammel.INCH
)
HUB_RADIAL_STACK = (
    HUB_OFFSET_BAND
    + abs(HUB_OFFSET_PRINTED - trammel.HUB_OFFSET)
    + trammel.RADIUS_FROM_SHOULDER_CLEARANCE
)
if HUB_RADIAL_STACK >= _TOP_EDGE_HALF_BAND:
    raise AssertionError("the HUB fit-up stack exceeds half the strap's top-edge band")


def _trig_range(a: float, b: float, c: float, angle: float) -> tuple[float, float]:
    """Exact range of a*sin(t)+b*cos(t)+c on [-angle, angle]."""
    candidates = [-angle, angle]
    phase = math.atan2(a, b)
    candidates.extend(
        t for k in range(-2, 3)
        if -angle <= (t := phase + k * math.pi) <= angle
    )
    values = [a * math.sin(t) + b * math.cos(t) + c for t in candidates]
    return min(values), max(values)


def pin_coordinate_intervals(
    location_band: float = TABLE_LOCATION_BAND,
    outer_y_band: float = OUTER_Y_BAND,
    *, include_rounding: bool = True,
) -> tuple[tuple[float, float], ...]:
    """Errors of B1.X, A2.X, B2.X, A2.Y, B2.Y, in the A1 datum frame."""
    a1 = PIN_HOLES["A1"]
    values = (
        D1, PIN_HOLES["A2"][0] - a1[0], PIN_HOLES["B2"][0] - a1[0],
        A2_DY, A2_DY,
    )
    bands = (location_band,) * 3 + (outer_y_band,) * 2
    return tuple(
        (
            (round(value / trammel.INCH, TABLE_LOCATION_PLACES) * trammel.INCH
             - value if include_rounding else 0.0) - band,
            (round(value / trammel.INCH, TABLE_LOCATION_PLACES) * trammel.INCH
             - value if include_rounding else 0.0) + band,
        )
        for value, band in zip(values, bands, strict=True)
    )


def correlated_pin_budget(
    location_band: float = TABLE_LOCATION_BAND,
    outer_y_band: float = OUTER_Y_BAND,
    *, include_rounding: bool = True,
    angle: float = trammel.TIP_ANGLE,
) -> dict[str, tuple[float, float]]:
    """Enclose the entire tolerance box and continuous strap arc, in mm.

    C=(a+b)/2 + cot(alpha)/2*(dy,-dx), R=|b-a|/(2*sin(alpha)).
    The in-situ HUB follows the INNER apex: dH=(dD/2,k*dD),
    k=(1-cos(alpha))/(2*sin(alpha)). Both cuts use that SAME HUB.
    First-order edge error is u·(dH-dC)-dR, u=(sin(t),cos(t)).
    This is affine in the five errors, so extrema lie on box corners.
    Trig extrema are analytic, not sampled. The norm Hessian is bounded by
    1/(R-|dv|); the remainder encloses every interior error as well.
    The outer chord's norm remainder is charged independently. No RSS.
    """
    if location_band < 0.0 or outer_y_band < 0.0 or not 0.0 <= angle < math.pi / 2:
        raise ValueError("invalid carrier tolerance box or arc")
    intervals = pin_coordinate_intervals(
        location_band, outer_y_band, include_rounding=include_rounding
    )
    q = trammel.RADIUS_PER_SPACING
    h = 0.5 / math.tan(trammel.ALPHA)
    k = q - h
    corners = tuple(product(*intervals))
    result = {}
    for name, radius in (("inner", trammel.R_INNER), ("outer", trammel.R_OUTER)):
        lo, hi, v_max, chord_max = math.inf, -math.inf, 0.0, 0.0
        for d, ax, bx, ay, by in corners:
            if name == "inner":
                vx, vy, dr = 0.0, q * d, q * d
            else:
                vx = d / 2.0 - (ax + bx) / 2.0 - h * (by - ay)
                vy = k * d - (ay + by) / 2.0 + h * (bx - ax)
                dr = q * (bx - ax)
                chord_max = max(chord_max, math.hypot(bx - ax, by - ay))
            low, high = _trig_range(vx, vy, -dr, angle)
            lo, hi = min(lo, low), max(hi, high)
            v_max = max(v_max, math.hypot(vx, vy))
        if v_max >= radius or chord_max >= trammel.D2:
            raise AssertionError("carrier error box no longer supports the norm bound")
        radial_remainder = v_max**2 / (2.0 * (radius - v_max))
        chord_remainder = q * chord_max**2 / (2.0 * (trammel.D2 - chord_max))
        result[name] = (lo - chord_remainder, hi + radial_remainder)
    result["R800"] = tuple(q * value for value in intervals[0])
    dx = (intervals[2][0] - intervals[1][1], intervals[2][1] - intervals[1][0])
    dy = (intervals[4][0] - intervals[3][1], intervals[4][1] - intervals[3][0])
    dy_min = 0.0 if dy[0] <= 0.0 <= dy[1] else min(abs(v) for v in dy)
    result["R816"] = (
        q * math.hypot(trammel.D2 + dx[0], dy_min) - trammel.R_C2,
        q * math.hypot(trammel.D2 + dx[1], max(abs(v) for v in dy)) - trammel.R_C2,
    )
    return result


PIN_ONLY_BUDGET = correlated_pin_budget(include_rounding=False)
PIN_ROUNDED_BUDGET = correlated_pin_budget()
PIN_RELATIVE_ERROR = {
    name: max(abs(value) for value in PIN_ROUNDED_BUDGET[name])
    for name in ("inner", "outer")
}


def pin_relative_stack(hub_radial_stack: float = HUB_RADIAL_STACK) -> dict[str, float]:
    """Each strap edge's complete error against its pivot, counted once.

    Every strap hole is reamed at the HUB DRO setting, so an edge-to-pivot
    error is that setting's stack plus the edge's correlated pin-shape error
    against the same HUB. No stud, nose or washer float locates the strap,
    and the absolute R800/R816 radius errors are already inside the same-HUB
    comparison, never added again. The hub aims mid-band, so each edge may
    spend half of its 0/-.020 radial limits (``_TOP_EDGE_HALF_BAND``).
    """
    if not math.isfinite(hub_radial_stack) or hub_radial_stack < 0.0:
        raise ValueError("HUB radial stack must be finite and nonnegative")
    stack = {name: hub_radial_stack + error for name, error in PIN_RELATIVE_ERROR.items()}
    if max(stack.values()) > _TOP_EDGE_HALF_BAND:
        raise AssertionError(
            "HUB setting plus correlated pin error exceed half the strap's "
            f"radial band: stack_mm={stack!r}, half_band_mm={_TOP_EDGE_HALF_BAND!r}"
        )
    return stack


PIN_RELATIVE_STACK = pin_relative_stack()
PIN_RELATIVE_REMAINING = {
    name: _TOP_EDGE_HALF_BAND - stack for name, stack in PIN_RELATIVE_STACK.items()
}
# Owner's approximate bounds: .0088/.0177 absolute, .0001/.0038 relative.
# The .0001 is rounded: the continuous top-edge enclosure is under .0002.
for _name, _expected in (("R800", .0089), ("R816", .0178), ("inner", .0002), ("outer", .0039)):
    if max(abs(v) for v in PIN_ONLY_BUDGET[_name]) >= _expected * trammel.INCH:
        raise AssertionError(f"pin-only {_name} exceeds the owner's expected bound")


def table_coordinate_errors(point: tuple[float, float]) -> tuple[float, float]:
    """Ordinary table row's X/Y errors, including its printed rounding."""
    return tuple(
        TABLE_LOCATION_BAND + abs(
            round(value / trammel.INCH, TABLE_LOCATION_PLACES) * trammel.INCH - value
        )
        for value in (point[0] - PIN_HOLES["A1"][0], point[1])
    )


def station_sweep_error(
    point: tuple[float, float], pass_name: str,
    station_errors: tuple[float, float] | None = None,
) -> float:
    """Bound hole-to-cutter displacement on the whole finite sweep, not radial only.

    A clamp or stop outside the arc endpoint needs a Euclidean bound. For
    each box corner, |w-dr*u|² is a single sine/cosine expression; bound its
    entire sweep analytically, then include the outer chord's norm remainder.
    ``station_errors`` defaults to the table row's own X/Y errors; a station
    set from the carrier by another ordinary band passes that band instead.
    """
    ex, ey = table_coordinate_errors(point) if station_errors is None else station_errors
    if min(ex, ey) < 0.0:
        raise ValueError("station errors must be nonnegative")
    q, h = trammel.RADIUS_PER_SPACING, .5 / math.tan(trammel.ALPHA)
    worst_squared, chord_max = 0.0, 0.0
    for d, ax, bx, ay, by in product(*pin_coordinate_intervals()):
        if pass_name == "inner":
            cx, cy, dr = d / 2.0, -h * d, q * d
        elif pass_name == "outer":
            cx, cy = (ax + bx) / 2.0 + h * (by - ay), (ay + by) / 2.0 - h * (bx - ax)
            dr = q * (bx - ax)
            chord_max = max(chord_max, math.hypot(bx - ax, by - ay))
        else:
            raise ValueError(pass_name)
        for px, py in product((-ex, ex), (-ey, ey)):
            wx, wy = px - cx, py - cy
            _low, high = _trig_range(
                -2.0 * dr * wx, -2.0 * dr * wy,
                wx * wx + wy * wy + dr * dr, trammel.SWEEP[pass_name],
            )
            worst_squared = max(worst_squared, high)
    return math.sqrt(worst_squared) + q * chord_max**2 / (2.0 * (trammel.D2 - chord_max))


def station_cut_error(point: tuple[float, float], pass_name: str) -> float:
    """Table-located hole versus self-cut edge, including printed rounding."""
    theta = math.atan2(point[0], point[1] + trammel.H1)
    sx, cy = math.sin(theta), math.cos(theta)
    station_errors = table_coordinate_errors(point)
    q, h = trammel.RADIUS_PER_SPACING, 0.5 / math.tan(trammel.ALPHA)
    worst, v_max, chord_max = 0.0, 0.0, 0.0
    for d, ax, bx, ay, by in product(*pin_coordinate_intervals()):
        if pass_name == "inner":
            cx, cy_shift, dr = d / 2.0, -h * d, q * d
        elif pass_name == "outer":
            cx = (ax + bx) / 2.0 + h * (by - ay)
            cy_shift = (ay + by) / 2.0 - h * (bx - ax)
            dr = q * (bx - ax)
            chord_max = max(chord_max, math.hypot(bx - ax, by - ay))
        else:
            raise ValueError(pass_name)
        worst = max(worst, abs(-sx * cx - cy * cy_shift - dr))
        v_max = max(v_max, math.hypot(
            abs(cx) + station_errors[0], abs(cy_shift) + station_errors[1]
        ))
    radius = math.dist(point, trammel.ARC_CENTRE)
    remainder = v_max**2 / (2.0 * (radius - v_max))
    remainder += q * chord_max**2 / (2.0 * (trammel.D2 - chord_max))
    return worst + abs(sx) * station_errors[0] + abs(cy) * station_errors[1] + remainder


# Rule 17 (riser walls): each table-located riser tap against both self-cut
# edges, charging the same correlated pin errors that move those cuts.
_RISER_MOUTH_MAX = (
    trammel.RISER_CSK_DIA + printed_band_mm(trammel.RISER_CSK_PLACES, unit=trammel.RISER_UNIT)
) / 2.0
RISER_WALLS_FROM_A1 = min(
    min(
        math.dist(point, trammel.ARC_CENTRE) - trammel.RISER_INNER_RADIUS
        - station_cut_error(point, "inner"),
        trammel.RISER_OUTER_RADIUS - math.dist(point, trammel.ARC_CENTRE)
        - station_cut_error(point, "outer"),
    ) - _RISER_MOUTH_MAX
    for point in RISER_SCREWS
)
if RISER_WALLS_FROM_A1 < WALL_TARGET_MM:
    raise AssertionError("a riser countersink breaks rule 17's .080 wall from A1")

CALLOUTS_BELOW = {
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "PinChamferSize": PIN_CHAMFER_CALLOUT,
}
CALLOUT_PREFIXES: dict[str, str] = {}

# Every top-face hole, the in-situ HUB tap included: its LOC cells are REF.
TABLE_HOLES = {
    **{key: (*point, PIN_HOLE_DIA) for key, point in PIN_HOLES.items()},
    **{key: (*point, CLAMP_TAP_DRILL) for key, point in END_CLAMPS.items()},
    **{f"R{i}": (*point, RISER_TAP_DRILL) for i, point in enumerate(RISER_SCREWS, 1)},
    **{f"L{i}": (*point, LEVER_TAP_DRILL) for i, point in enumerate(LEVER_HOLES, 1)},
    "HUB": (*HUB, CLAMP_TAP_DRILL),
}
TABLE_ROW_NOTES = {
    "A1": "ORIGIN; R800 / MHA-CH-13",
    "B1": "X AXIS; R800 / MHA-CH-13",
    "A2": "R816 / MHA-CH-13; NOTE 1",
    "B2": "R816 / MHA-CH-13; NOTE 1",
    "CL": "END CLAMP; SEE CALLOUT",
    "CR": "END CLAMP; SEE CALLOUT",
    **{f"R{i}": "LOCATES TL-24 RISER" for i in range(1, 5)},
    **{f"L{i}": "FEED LEVER; SEE CALLOUT" for i in range(1, 3)},
    "HUB": "LOCATIONS REF; TL-00 STEP 10",
}

DRAWING_NOTES = OUTER_Y_NOTE
ISOMETRIC_VIEW_SCALE = (1, 8)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
