r"""MHA-DT-37-TL-01: the DT6-FORM1 fly-cutter bit, dimensional contract.

PURE DATA, no SolidWorks/COM and no drawing imports.  Shop tooling
(cad/docs/subsystem-identities.md): the single-point form tool that cuts the
six tooth spaces of the cone tip gear MHA-DT-37, held in the fly-cutter bar
MHA-DT-37-TL-02 (fixture MHA-DT-37-TL-00).  Issue #2358: the tool is drawn as
a tool -- blank, rake, clearance, holder, hardening -- and accepted by the gear
it cuts.

The cutting edge IS the T006 tooth space (MHA-DT-37 is a spur gear cut on
centre), so the form is imported, never copied: the face carries the tooth
space's own native curves (``dt_cone_tip_gear_spec.PROFILE``'s root arc, relief
and finite involute flank, run out to DT6-FORM1's finite tip radius), and the
reference widths the sheet prints are MHA-DT-37 sheet 2's own table points
(``dt_cone_gear_spec.custom_six_form_points_mm``).

Bit frame: model +X along the bit axis toward the tip, the shank end at
x = -BIT_LENGTH; the origin is P1, the tip centre on the face.  The face (zero
rake) is the Top Plane, y = 0, through the bit axis; the bit's material keeps
y < 0 at the head (the flat to centre takes y > 0 over FLAT_LENGTH).  The form
lies across model Z (Z = the tooth space's own across-the-gap axis).  A face
point (x, 0, z) is the tooth-space point (xg, yg) = (ROOT_RADIUS - x, z) of the
gear frame (``stock_form_cutter``: xg radial from the gear axis).

Clearance is two prisms of the face form, not a drafted offset (the relief's
curvature radius falls to 0.12 mm, under any useful drafted offset): each
prism runs from the face along (-tan front, -1, -/+tan side), so under the
face every cutting edge falls back FRONT_CLEARANCE_DEG and both flanks close
in SIDE_CLEARANCE_DEG.  The face section is the form exactly.
"""

from __future__ import annotations

import math
from dataclasses import replace
from functools import lru_cache

import _config
import dt_cone_gear_spec as family
import dt_cone_tip_gear_spec as tip
from _package_units import drawing_unit

STEM = "dt-cone-tip-gear-tl-form-cutter"
_ROW = _config.parts("dt-cone-tip-gear-tl-form-cutter")
UNIT = drawing_unit("parts/dt-cone-tip-gear-tl-form-cutter", _ROW)
NUMBER = str(_ROW["number"])
QUANTITY = 1
INCH = 25.4
GEAR_NUMBER = tip.PART_NUMBER
BAR_NUMBER = str(_config.parts("dt-cone-tip-gear-tl-cutter-bar")["number"])
FIXTURE_NUMBER = "MHA-DT-37-TL-00"

# --- The form: the T006 tooth space, run out to DT6-FORM1's finite tip -------
TEMPLATE = tip.TEMPLATE
if TEMPLATE.name != "DT6-FORM1":
    raise AssertionError("the bit grinds DT6-FORM1, the T006 custom form")
# The nominal standard-depth cut (radial translation 0), its flanks run to the
# finite tool's own tip radius so the form stands clear of the blank OD.
TOOL_PROFILE = replace(
    tip.PROFILE,
    blank_radius_mm=TEMPLATE.tip_radius_mm,
    radial_translation_mm=0.0,
)
ROOT_RADIUS = TEMPLATE.root_radius_mm
# The closing arc of ``native_segments`` lies outside the form and is not
# used: the loop below closes on the shoulders instead.
_CLEARANCE_RADIUS = TEMPLATE.tip_radius_mm + 1.0
FORM_SEGMENT_NAMES = (
    "RootArc",
    "LowerRelief",
    "LowerFiniteFlank",
    "UpperFiniteFlank",
    "UpperRelief",
)


def form_segments(unit_scale: float = 1.0 / INCH) -> tuple:
    """The tooth space's native edge curves, in the gear frame, loop order."""
    loop = TOOL_PROFILE.native_segments(
        unit_scale=unit_scale, clearance_radius_mm=_CLEARANCE_RADIUS
    )
    kept = tuple(segment for segment in loop if segment.name in FORM_SEGMENT_NAMES)
    if tuple(sorted(s.name for s in kept)) != tuple(sorted(FORM_SEGMENT_NAMES)):
        raise AssertionError(
            f"tooth-space loop lost a form curve: {[s.name for s in kept]}"
        )
    if any(segment.kind not in {"root_arc", "relief", "flank"} for segment in kept):
        raise AssertionError("the form takes only the root arc, reliefs and flanks")
    return kept


def face_point(xg: float, yg: float) -> tuple[float, float]:
    """Face (x, z) of a gear-frame tooth-space point (mm)."""
    return ROOT_RADIUS - xg, yg


_SEGMENTS_MM = {segment.name: segment for segment in form_segments(unit_scale=1.0)}
# The flank ends: where each finite flank meets its shoulder (gear frame).
FLANK_END_G = _SEGMENTS_MM["UpperFiniteFlank"].point(0.0)
if abs(math.hypot(*FLANK_END_G) - TEMPLATE.tip_radius_mm) > 1e-6:
    raise AssertionError("the finite flank must end on DT6-FORM1's tip radius")
SHOULDER_X, FLANK_END_Z = face_point(*FLANK_END_G)


def upper_edge_mm(samples: int = 120) -> tuple[tuple[float, float], ...]:
    """The face form's upper (z >= 0) edge, face (x, z) mm, from P1 on the
    axis out along the root arc, the relief and the flank to the shoulder."""
    arc = _SEGMENTS_MM["RootArc"]
    half = samples // 2
    points = [arc.point(0.5 - 0.5 * i / half) for i in range(half + 1)]
    for name in ("UpperRelief", "UpperFiniteFlank"):
        segment = _SEGMENTS_MM[name]
        points += [segment.point(1.0 - i / samples) for i in range(1, samples + 1)]
    return tuple(face_point(*point) for point in points)


_EDGE = upper_edge_mm()
# The form's most forward point: the root arc's ends, where the reliefs start.
FORM_X_MAX = max(x for x, _ in _EDGE)
# The tool never reaches inside the gear's root circle, so it runs off over
# both Ø.0625 stems by the gear's own CUTTER_RUNOFF_MM (MHA-DT-37).
FORM_RADIUS_MIN = min(math.hypot(ROOT_RADIUS - x, z) for x, z in _EDGE)
if FORM_RADIUS_MIN < ROOT_RADIUS - 1e-9:
    raise AssertionError("a point of the form digs below the T006 root circle")
if tip.CUTTER_RUNOFF_MM <= 0.0:
    raise AssertionError("the form would cut into a Ø.0625 stem")

# --- The blank: 1/8 O1 drill rod --------------------------------------------
# 1/8 is the smallest stock drill rod that holds the full finite form (2.225
# mm wide at the shoulders) with a shoulder each side.  Supplied ground to the
# drill rod's +/-.0005 (dt_pinion_cam_pin_spec's convention); the band is the
# slip fit in the bar's reamed cross hole.
BIT_DIA = 3.175  # .1250
BIT_DIA_PLACES = 4
BIT_DIA_TOL = 0.0127  # +/-.0005, as supplied
BIT_RADIUS = BIT_DIA / 2.0
BIT_DIA_LIMITS = (BIT_DIA - BIT_DIA_TOL, BIT_DIA + BIT_DIA_TOL)
# Shank end to P1, .XX: the fixture's stick-out leaves the tail inside the bar.
BIT_LENGTH = 11.43  # .45
BIT_LENGTH_PLACES = 2
# The rod as revolved runs this far past P1; the form cut takes it back.
TIP_STOCK = 0.254
# Flat to centre: from P1 back past the gear blank's reach, .XX.
FLAT_LENGTH = 1.524  # .06
FLAT_LENGTH_PLACES = 2
# The flat's depth, printed as what stays: the flat to the rod's far side,
# read with a micrometer, nominal half the rod (the face on the axis, zero
# rake).  A face FLAT_FACE_OFFSET_MAX off the axis turns the rake by at most
# dt_cone_tip_gear_tl_cutter_spec.RAKE_ERROR_DEG_MAX and moves the form
# outward under .002 mm, so the title block's .XXX band holds it, printed
# explicitly because four places give the half-rod nominal exactly.
FLAT_DEPTH = BIT_RADIUS  # .0625
FLAT_DEPTH_PLACES = 4
FLAT_DEPTH_TOL = 0.127  # +/-.005, the title block's .XXX row
FLAT_FACE_OFFSET_MAX = FLAT_DEPTH_TOL + BIT_DIA_TOL / 2.0
FRONT_CLEARANCE_DEG = 10.0
SIDE_CLEARANCE_DEG = 3.0
CLEARANCE_PLACES = 0
TAN_FRONT = math.tan(math.radians(FRONT_CLEARANCE_DEG))
TAN_SIDE = math.tan(math.radians(SIDE_CLEARANCE_DEG))
# The form cut's box in the face: forward of the rod's end at every depth,
# beyond the rod's sides at every depth.
FORM_BOX_X = 1.27
FORM_BOX_Z = 2.54
# Mid-plane depth of each clearance prism (total), through the rod both ways.
FORM_CUT_DEPTH = 2.0 * (BIT_DIA + 1.0)

if TIP_STOCK <= FORM_X_MAX:
    raise AssertionError("the revolved rod must reach past the form's tip")
if BIT_RADIUS - FLANK_END_Z < 0.25:
    raise AssertionError("the form needs a shoulder each side inside the 1/8 rod")
# The gear blank reaches back to x = ROOT - OD/2 on the face; the flat clears it.
BLANK_REACH_X = ROOT_RADIUS - tip.OUTSIDE_DIA / 2.0
if FLAT_LENGTH + BLANK_REACH_X < 0.25:
    raise AssertionError("the flat to centre must run back past the gear blank")
if FORM_BOX_X < TIP_STOCK + BIT_RADIUS * TAN_FRONT + 0.2:
    raise AssertionError("the form box must stay ahead of the rod's end")
if FORM_BOX_Z < BIT_RADIUS * (1.0 + TAN_SIDE) + 0.2:
    raise AssertionError("the form box must reach past the rod's sides")
if FLAT_LENGTH < -SHOULDER_X + BIT_RADIUS * TAN_FRONT:
    raise AssertionError("the shoulders above the face must fall inside the flat")


def clearance_direction(side: int) -> tuple[float, float, float]:
    """Unit direction of one clearance prism from the face into the bit:
    back by the front clearance, in by the side clearance toward ``side``'s
    flank (+1: the +Z flank closes, -1: the -Z flank)."""
    vector = (-TAN_FRONT, -1.0, -side * TAN_SIDE)
    length = math.sqrt(sum(c * c for c in vector))
    return tuple(c / length for c in vector)


def shoulder_loop_g() -> tuple[tuple[float, float], ...]:
    """The cut loop's straight run, gear frame (mm): from the upper flank's end
    out along its shoulder, round the box ahead of the tip, back along the
    lower shoulder to the lower flank's end.  The form curves close it."""
    xe, ze = FLANK_END_G
    x_box = ROOT_RADIUS - FORM_BOX_X
    return (
        (xe, ze),
        (xe, FORM_BOX_Z),
        (x_box, FORM_BOX_Z),
        (x_box, -FORM_BOX_Z),
        (xe, -FORM_BOX_Z),
        (xe, -ze),
    )


# --- Volume: the face section and its two clearance prisms --------------------
def _face_intervals(u: float) -> tuple[tuple[float, float], ...]:
    """The face form's material z-intervals at face station x = u (forward of
    the shoulder), by even-odd crossings of the closed symmetric edge."""
    crossings = []
    edge = _EDGE
    for (x1, z1), (x2, z2) in zip(edge, edge[1:]):
        if (x1 - u) * (x2 - u) < 0.0 or (x2 == u and x1 != u):
            z = z1 + (z2 - z1) * (u - x1) / (x2 - x1)
            crossings += [z, -z]
    crossings.sort()
    return tuple(zip(crossings[0::2], crossings[1::2]))


_STATION_STEP = 0.0005


@lru_cache(maxsize=1)
def _stations() -> tuple[tuple[float, tuple[tuple[float, float], ...]], ...]:
    count = int(math.ceil((FORM_X_MAX - SHOULDER_X) / _STATION_STEP))
    step = (FORM_X_MAX - SHOULDER_X) / count
    return tuple(
        (
            SHOULDER_X + i * step,
            _face_intervals(SHOULDER_X + i * step + (1e-9 if i == 0 else 0.0)),
        )
        for i in range(count + 1)
    )


def _measure(intervals, shifts: tuple[float, ...], chord: float) -> float:
    """Length of the intersection, over ``shifts``, of the shifted interval sets,
    inside |z| <= chord."""
    current = [(-chord, chord)]
    for shift in shifts:
        moved = [(a + shift, b + shift) for a, b in intervals]
        current = [
            (max(a, c), min(b, d))
            for a, b in current
            for c, d in moved
            if min(b, d) > max(a, c)
        ]
    return sum(b - a for a, b in current)


def _form_area(shifts: tuple[float, ...], chord: float) -> float:
    stations = _stations()
    total = 0.0
    for (u0, i0), (u1, i1) in zip(stations, stations[1:]):
        total += (
            0.5
            * (u1 - u0)
            * (_measure(i0, shifts, chord) + _measure(i1, shifts, chord))
        )
    return total


STAGES = ("revolve", "flat", "form_plus", "form")


def bit_volume_mm3(stage: str = "form", *, slices: int = 48) -> float:
    """The bit's volume after ``stage`` (mm^3): the face form at depth d
    under the face is the face section shifted back d tan(front) and, for
    each prism cut so far, sideways d tan(side); the shank behind the
    shoulder is the full rod chord."""
    if stage not in STAGES:
        raise ValueError(f"unknown bit stage {stage!r}")
    rod = math.pi * BIT_RADIUS**2
    if stage == "revolve":
        return rod * (BIT_LENGTH + TIP_STOCK)
    above = rod / 2.0 * (BIT_LENGTH - FLAT_LENGTH)
    if stage == "flat":
        return above + rod / 2.0 * (BIT_LENGTH + TIP_STOCK)
    sides = (1,) if stage == "form_plus" else (1, -1)
    # d = R sin(theta): the chord is R cos(theta), smooth to the rod's bottom.
    step = (math.pi / 2.0) / slices
    total = 0.0
    for i in range(slices + 1):
        theta = i * step
        depth, chord = BIT_RADIUS * math.sin(theta), BIT_RADIUS * math.cos(theta)
        shank = 2.0 * chord * (BIT_LENGTH + SHOULDER_X - depth * TAN_FRONT)
        area = shank + _form_area(tuple(s * depth * TAN_SIDE for s in sides), chord)
        weight = 1 if i in (0, slices) else (4 if i % 2 else 2)
        total += weight * area * BIT_RADIUS * math.cos(theta)
    return above + total * step / 3.0


# The volume gate's band: the sampled form against SolidWorks' exact curves.
VOLUME_TOL_MM3 = 0.02


_REACH_STEP = 0.0005


@lru_cache(maxsize=1)
def _face_reach_table() -> tuple[float, ...]:
    """Face reach at z = k * _REACH_STEP (k >= 0) up to the blank radius: the
    most forward face x whose edge crosses that z (the shoulder beyond the
    flank end), or the blank surface's x where that lies further forward
    (points behind it sweep air)."""
    blank = tip.OUTSIDE_DIA / 2.0
    table = []
    for k in range(int(blank / _REACH_STEP) + 1):
        z = k * _REACH_STEP
        best = SHOULDER_X
        for (x1, z1), (x2, z2) in zip(_EDGE, _EDGE[1:]):
            if (z1 - z) * (z2 - z) <= 0.0 and z1 != z2:
                best = max(best, x1 + (x2 - x1) * (z - z1) / (z2 - z1))
        table.append(
            max(best, ROOT_RADIUS - math.sqrt(max(blank * blank - z * z, 0.0)))
        )
    return tuple(table)


def _face_reach(z: float) -> float:
    """Conservative face reach at |z|: the lesser of the bracketing table rows."""
    table = _face_reach_table()
    index = abs(z) / _REACH_STEP
    low = int(index)
    if low + 1 >= len(table):
        return math.inf  # beyond the blank: no gear material this far across
    return min(table[low], table[low + 1])


def trailing_reach_excess_mm(swing_radius: float, *, depths: int = 16) -> float:
    """Worst radial overreach (mm) of any point under the face beyond what
    the face itself, or the gear's air outside its blank, allows at that z
    when the bit swings at ``swing_radius`` (tip P1 radius from the bar axis).

    A point d under the face, at face station u of the prism-shifted section,
    sweeps sqrt((Rs + u - d tan(front))^2 + d^2); the face sweeps Rs + x at
    the same z.  Negative everywhere: nothing under the face recuts the
    generated tooth space."""
    worst = -math.inf
    for k in range(1, depths + 1):
        depth = BIT_RADIUS * k / depths
        chord = math.sqrt(max(BIT_RADIUS**2 - depth**2, 0.0))
        shift = depth * TAN_SIDE
        for u, intervals in _stations()[::4]:
            moved = [
                (max(a + shift, c - shift), min(b + shift, d - shift))
                for a, b in intervals
                for c, d in intervals
                if min(b + shift, d - shift) > max(a + shift, c - shift)
            ]
            reach = math.hypot(swing_radius + u - depth * TAN_FRONT, depth)
            for a, b in moved:
                for z in (a, (a + b) / 2.0, b):
                    if abs(z) <= chord:
                        worst = max(worst, reach - (swing_radius + _face_reach(z)))
    return worst


# --- MHA-DT-37 sheet 2's table, the reference envelope the sheet prints -----
FORM_PLACES = family.FORM_PLACES
_POINTS = family.custom_six_form_points_mm()
# (R, X, Y): X across from the tool centreline, Y back from the tip centre.
_P2, _P12, _P17 = _POINTS[1], _POINTS[11], _POINTS[16]
if abs(_P17[0] - tip.OUTSIDE_DIA / 2.0) > 1e-6:
    raise AssertionError("P17 must be the form's point on the blank OD")
TIP_WIDTH = 2.0 * _P2[1]
TIP_DEPTH = _P2[2]  # P2's station ahead of (negative) or behind P1
JUNCTION_WIDTH = 2.0 * _P12[1]
JUNCTION_DEPTH = _P12[2]
FORM_WIDTH = 2.0 * _P17[1]
FORM_DEPTH = _P17[2]
if not 0.0 < TIP_WIDTH < JUNCTION_WIDTH < FORM_WIDTH < 2.0 * FLANK_END_Z:
    raise AssertionError("the table's widths must open from the tip to the OD")

# --- Native drawing contract --------------------------------------------------
FRONT_CLEARANCE_SKETCH = "FrontClearanceReference"
SIDE_CLEARANCE_SKETCH = "SideClearanceReference"
FORM_REFERENCE_SKETCH = "FormEnvelopeReference"
REFERENCE_SKETCHES = (
    FRONT_CLEARANCE_SKETCH,
    SIDE_CLEARANCE_SKETCH,
    FORM_REFERENCE_SKETCH,
)
REFERENCE_DIMENSIONS = frozenset(
    {"TipWidth", "JunctionWidth", "JunctionDepth", "FormWidth", "FormDepth"}
)
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BitProfile": {"BitDia", "BitLength"},
    "FlatProfile": {"FlatLength", "FlatDepth"},
    FRONT_CLEARANCE_SKETCH: {"FrontClearance"},
    SIDE_CLEARANCE_SKETCH: {"SideClearance"},
    FORM_REFERENCE_SKETCH: set(REFERENCE_DIMENSIONS),
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BitProfile": {"BitDia": BIT_DIA_PLACES, "BitLength": BIT_LENGTH_PLACES},
    "FlatProfile": {"FlatLength": FLAT_LENGTH_PLACES, "FlatDepth": FLAT_DEPTH_PLACES},
    FRONT_CLEARANCE_SKETCH: {"FrontClearance": CLEARANCE_PLACES},
    SIDE_CLEARANCE_SKETCH: {"SideClearance": CLEARANCE_PLACES},
    FORM_REFERENCE_SKETCH: {name: FORM_PLACES for name in REFERENCE_DIMENSIONS},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if set(DRAWING_PRECISION) != set(DRAWING_DIMENSIONS) or any(
    set(DRAWING_PRECISION[feature]) != DRAWING_DIMENSIONS[feature]
    for feature in DRAWING_DIMENSIONS
):
    raise AssertionError("every printed dimension needs its places, and only those")

# Rule 4: the band names its mate; rule 7: words, no method.  The material
# block names the drill rod, so the Ø says only that it stays as supplied.
# The flat's length and depth print bare: the depth dimension is the flat.
DIMENSION_CALLOUTS: dict[str, str] = {
    "BitDia": f"AS SUPPLIED\nSLIDING FIT IN {BAR_NUMBER}",
    "FrontClearance": "FRONT CLEARANCE",
    "SideClearance": "SIDE CLEARANCE,\nBOTH FLANKS",
}
SHEET_NOTES = "\n".join(
    (
        f"1. FACE FORM: TOOTH SPACE OF {GEAR_NUMBER}, SHEET 2 (P1-P17), CENTERED ON BIT AXIS.",
        "2. ZERO RAKE; CUTTING EDGES SHARP, NO BURR.",
        f"3. ACCEPT BY THE GEAR IT CUTS: {GEAR_NUMBER} OVER-PINS AND ASSEMBLY BACKLASH.",
    )
)
if len(SHEET_NOTES.splitlines()) > 4:
    raise AssertionError("at most four note lines")
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 5:1"
