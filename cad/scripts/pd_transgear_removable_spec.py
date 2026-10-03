r"""MHA-PD-009 transgear-removable: the ANSI #25 sprocket and its seat interface.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in the import
closure.  One authority for the numbers the removable sprocket, the two
shafts it seats on (crankshaft MHA-DT-011, knob shaft MHA-PD-008), the drive-train
and paper-drive assemblies and the chain solver ``_chain`` all share.

Evidence: ch23 p.56 (catalog photo: #25 chain, plate, bore and the two
drive-pin holes nearly touching the bore), p.61 and video frame f_0215/f_0210.

Machine frame: +Y up, -Z = machine FRONT, +X = operator's left.  Both mounted
wheels (crank T12, knob T24) occupy the SAME z band: rear face on the shaft's
seat face at ``SEAT_FACE_Z``, front face at ``BAND_FRONT_Z``, so the chain
runs in one plane, ``CHAIN_MID_Z``, on both shafts.  Each shaft's seat is a
flat ``SEAT_SPIGOT_DIA`` face carrying two pressed 3/32 dowels: small enough
that the #25 chain's plates wrap the T12 clear of it.

Tooth form: the ANSI B29.1 standard (American Chain Association) #25
roller-chain sprocket form, the one a #25 sprocket cutter reproduces, in
every configuration.  Seating curve ``SEAT_CURVE_R`` = 0.5025 Dr + 0.0015 in
centred on the pitch circle (point a); working curve ``WORKING_CURVE_R``
(E = 1.3025 Dr + 0.0015 in) about c, ``WORKING_CENTRE_OFFSET`` (ac = 0.8 Dr)
from a at A = 35 + 60/N deg, spanning B = 18 - 56/N deg; the straight yz
tangent to it; the topping curve F about b, ``TOPPING_CENTRE_OFFSET``
(ab = 1.4 Dr) from a along the pitch chord, out to the turned outside
diameter p (0.6 + cot(180/N)).  The bottom diameter is PD - Dr (for even N
also the caliper diameter); its minus-only commercial tolerance
0.002 P sqrt(N) + 0.006 in holds the as-cut seat bottom PD - 2 R.  Sources:
the ACA formulas as reproduced in GEARS-IDS "Designing and Drawing a
Sprocket", p. 2 Table 1 (http://www.gearseds.com/files/design_draw_sprocket_5.pdf);
diameters, caliper diameter and tolerances, Machinery's Handbook 31st ed.
pp. 2621-2623 (https://online.flippingbook.com/view/954046886/1316/ to
/1318/).  :func:`gap_area` is the exact in-plate area one tooth gap removes,
so the part's volume check tests the tooth SHAPE, not merely that some cut
happened.

Part frame (``build_transgear_removable``): axis Z through the origin, plate
z = 0..PLATE, drive-pin holes on local +/-Y, a TOOTH (not a gap) centred on
local +X; the gaps are centred at ``pi / N + k * 2 pi / N``.
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4

# --- ANSI #25 roller chain ---------------------------------------------------
# ANSI B29.1 #25 link-plate height (0.230 in).  The CAD chain's plates are
# drawn lower (``_chain.PLATE_HEIGHT``), so a seat that clears only the CAD
# link could still foul a bought chain: the clearance checks use both.
ANSI_PLATE_HEIGHT = 0.230 * MM_PER_IN  # 5.842
# A bought chain's axial envelope (PEER Chain 25R size chart, read
# 2026-09-30, https://www.peerchain.com/chain-pitches/): roller width W, the
# width between the inner plates, 0.125 in; chain centreline to the riveted
# pin head F 0.154 in and to the connecting link's clip G 0.185 in.  The
# CAD links (``_chain.PIN_HALF_LEN``) are narrower.  The clearance stacks take
# G on both sides (the clip may face either way) at every radius the plates
# reach, which also covers the riveted heads.
ANSI_ROLLER_WIDTH = 0.125 * MM_PER_IN  # 3.175
ANSI_HALF_WIDTH = 0.185 * MM_PER_IN  # 4.699
CHAIN_PITCH = 0.25 * MM_PER_IN  # 6.35
ROLLER_DIA = 3.30  # 0.130 in

# --- ANSI B29.1 (ACA) standard tooth form --------------------------------------
# The standard writes its formulas in inches; every one is linear in Dr and its
# 0.0015 in clearance, so they hold in mm with the clearance converted.
ACA_CLEARANCE = 0.0015 * MM_PER_IN  # 0.0381
SEAT_CURVE_R = 0.5025 * ROLLER_DIA + ACA_CLEARANCE  # R = Ds / 2, 1.696
WORKING_CURVE_R = 1.3025 * ROLLER_DIA + ACA_CLEARANCE  # E, 4.336
WORKING_CENTRE_OFFSET = 0.8 * ROLLER_DIA  # ac = E - R, 2.640
TOPPING_CENTRE_OFFSET = 1.4 * ROLLER_DIA  # ab, 4.620


def working_angle(teeth: int) -> float:
    """ACA A = 35 deg + 60 deg / N (rad): the line c-a-x off the pitch tangent."""
    return math.radians(35.0 + 60.0 / teeth)


def working_arc(teeth: int) -> float:
    """ACA B = 18 deg - 56 deg / N (rad): the working curve's arc x-y about c."""
    return math.radians(18.0 - 56.0 / teeth)


def topping_curve_r(teeth: int) -> float:
    """ACA topping-curve radius F (mm).

    F = Dr [0.8 cos(18 - 56/N) + 1.4 cos(17 - 64/N) - 1.3025] - 0.0015 in.
    """
    return (
        ROLLER_DIA
        * (
            0.8 * math.cos(working_arc(teeth))
            + 1.4 * math.cos(math.radians(17.0 - 64.0 / teeth))
            - 1.3025
        )
        - ACA_CLEARANCE
    )


def caliper_minus_tol(teeth: int) -> float:
    """Commercial minus-only caliper tolerance 0.002 P sqrt(N) + 0.006 in (mm)."""
    return (0.002 * CHAIN_PITCH / MM_PER_IN * math.sqrt(teeth) + 0.006) * MM_PER_IN


# --- plate and mounting interface (all three configurations) -----------------
PLATE = 2.8  # 0.110 in, the #25 tooth width; flat both faces, no hub
# Faced to thickness, never over nominal: the hub's rear face stands 0.7 in
# front of the wheel, and the chain's inner plates straddle it.
PLATE_BAND = (0.0, -0.10)  # (upper, lower) deviations
# Float model: the chain rides the 2.8 wheel and floats axially until an
# inner plate's inner face meets a wheel face.  Measured from the SEAT face
# (the wheel's rear face): frontmost, the rear inner plate lies on the seat
# face; rearmost, the front inner plate lies on the front face of the
# thinnest wheel the band allows.
CHAIN_REACH_FRONT = ANSI_ROLLER_WIDTH / 2.0 + ANSI_HALF_WIDTH  # 6.286


def chain_reach_rear(plate: float) -> float:
    """How far behind the seat face the chain's envelope reaches on a wheel
    ``plate`` thick."""
    return ANSI_ROLLER_WIDTH / 2.0 + ANSI_HALF_WIDTH - plate


CHAIN_REACH_REAR_WORST = chain_reach_rear(PLATE + min(PLATE_BAND))  # 3.587
if PLATE + max(PLATE_BAND) >= ANSI_ROLLER_WIDTH:
    raise AssertionError("the #25 inner plates must straddle the thickest wheel")
BORE_DIA = 10.3  # 13/32 in, 0.39 radial clear of the Ø9.525 shaft/pilot
PIN_HOLE_DIA = 2.5  # slip over the Ø2.38 drive pins (0.06 radial)
PIN_CIRCLE_DIA = 14.0
PIN_CIRCLE_RADIUS = PIN_CIRCLE_DIA / 2.0
# Two holes at 180 deg on the part's (and the shafts') +/-Y: 12 and 6 o'clock.
PIN_HOLE_ANGLES_DEG = (90.0, 270.0)
# Each drive pin (in either shaft's seat) and each of these holes is located
# +/-0.025 from the axis, printed at .XXX: the holes slip over the pins with
# 0.119 diametral clearance, which absorbs the spacing error of both parts,
# each spending half of it.  The shafts read these (dt_crankshaft_spec).
DRIVE_PIN_OFFSET_PLACES = 3
DRIVE_PIN_OFFSET_TOL = 0.025

# Bore <-> pin-hole web.  Photo-faithful to the p.56 catalog view, where the
# holes nearly touch the bore; under the policy's 1.5 wall floor, accepted by
# name (drawing-simplicity-policy.md, "Named exceptions").  Its printed worst
# case is sheet text (pd_transgear_removable_notes.BORE_PIN_WEB_WORST): it reads
# the title block's drilled-hole row, which this module's importers must not.
BORE_PIN_WEB = PIN_CIRCLE_RADIUS - PIN_HOLE_DIA / 2.0 - BORE_DIA / 2.0  # 0.60

CONFIGS: tuple[tuple[str, int], ...] = (("T12", 12), ("T18", 18), ("T24", 24))
TEETH = dict(CONFIGS)
DEFAULT_CONFIG = "T24"  # the part saves on T24

# --- manufacturing drawing (one sheet: the T24 views plus one edge view each
# of T12 and T18; SPROCKET DATA lists all three configurations) --------------
# The plate thickness carries PLATE_BAND; the bore and the pin holes are
# drilled (the title block's DRILLED HOLES row governs them); each pin centre
# carries +/-DRIVE_PIN_OFFSET_TOL at .XXX.  PinNegDia is the same global as
# PinPosDia and prints once as its "2X".  BlankDia, the turned outside
# diameter, is configuration-driven ("2 * Ra") and prints once per
# configuration at .X, the title block's one-place row.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlankProfile": {"BlankDia", "BlankWidth"},
    "BorePinsProfile": {"BoreDiaDim", "PinPosDia", "PinPosY", "PinNegY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlankProfile": {"BlankDia": 1, "BlankWidth": 2},
    "BorePinsProfile": {
        "BoreDiaDim": 2,
        "PinPosDia": 2,
        "PinPosY": DRIVE_PIN_OFFSET_PLACES,
        "PinNegY": DRIVE_PIN_OFFSET_PLACES,
    },
}
if {feature: set(names) for feature, names in DRAWING_PRECISION.items()} != (
    DRAWING_DIMENSIONS
):
    raise AssertionError("every marked dimension prints at part-authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}

# --- shared machine z band (both shafts) -------------------------------------
# User ruling 2026-09-30: 1.8 forward of the first seat (-152.5); the chain
# plane, both wheels and both shafts' seat faces moved with it.
SEAT_FACE_Z = -154.3  # wheel rear face = shaft seat face (the stack datum)
BAND_FRONT_Z = SEAT_FACE_Z - PLATE  # -157.1, wheel front face
CHAIN_MID_Z = SEAT_FACE_Z - PLATE / 2.0  # -155.7, the ONE chain plane

# --- drive-pin seat interface (both shafts carry it) -------------------------
# Two purchased 3/32 dowels pressed into each shaft's seat face, rounded end
# proud by DRIVE_PIN_PROUD: 1/4 long in the crank (crank-seat-drive-pin,
# MHA-VN-044), 3/16 in the knob shaft (transgear-knob-drive-pin, MHA-VN-038).  Their
# lengths and press depths are the shafts'; the diameter is the interface's.
DRIVE_PIN_DIA = 3.0 / 32.0 * MM_PER_IN  # 2.38125; each pin spec asserts its own
DRIVE_PIN_PROUD = 2.4  # standing out of the seat face
DRIVE_PIN_TIP_Z = SEAT_FACE_Z - DRIVE_PIN_PROUD  # -156.7
DRIVE_PIN_HOLE_DIA = 2.38  # reamed for the press (3/32 nominal)

# --- shaft seat face (both shafts carry the same seat) -----------------------
# The flat face the wheel's rear face beds on: a Ø17.5 spigot on the crank
# collar, the whole Ø17.5 collar on the knob shaft.  Small enough that the
# #25 plates wrapping the T12 clear it (Main's ruling, 2026-09-30).
SEAT_SPIGOT_DIA = 17.5
# Pin hole to the spigot's rim: under the 1.5 wall floor (Named exceptions).
SEAT_SPIGOT_RIM = (
    SEAT_SPIGOT_DIA / 2.0 - PIN_CIRCLE_RADIUS - DRIVE_PIN_HOLE_DIA / 2.0
)  # 0.56

if not BAND_FRONT_Z < DRIVE_PIN_TIP_Z < SEAT_FACE_Z:
    raise AssertionError("drive-pin tips must end inside the wheel's plate")
if PIN_HOLE_DIA <= DRIVE_PIN_DIA:
    raise AssertionError("the wheel's pin holes must slip over the drive pins")
if abs(BORE_PIN_WEB - 0.6) > 1e-9:
    raise AssertionError("bore/pin-hole web moved off the contracted 0.60")
if SEAT_SPIGOT_RIM <= 0.0:
    raise AssertionError("the seat spigot must enclose the drive-pin holes")


def chain_plate_inner_radius(teeth: int, plate_height: float) -> float:
    """Closest approach of a wrapped link plate's inner edge to the axis.

    A plate spans one pitch chord between two rollers on the pitch circle;
    its inner edge sits half the plate height inside the chord, nearest the
    axis at the chord's midpoint: r_p cos(180/N) - h/2 (T12, ANSI: 8.928).
    """
    return pitch_dia(teeth) / 2.0 * math.cos(math.pi / teeth) - plate_height / 2.0


def pitch_dia(teeth: int) -> float:
    """Sprocket pitch diameter p / sin(180/N)."""
    return CHAIN_PITCH / math.sin(math.pi / teeth)


def outside_dia(teeth: int) -> float:
    """ANSI outside (tip) diameter p (0.6 + cot(180/N))."""
    return CHAIN_PITCH * (0.6 + 1.0 / math.tan(math.pi / teeth))


def bottom_dia(teeth: int) -> float:
    """ANSI B29.1 bottom diameter PD - roller (even N: the caliper diameter)."""
    return pitch_dia(teeth) - ROLLER_DIA


def seat_bottom_dia(teeth: int) -> float:
    """Diameter through the seating-curve bottoms, PD - 2 R (the as-cut root)."""
    return pitch_dia(teeth) - 2.0 * SEAT_CURVE_R


def gap_geometry(teeth: int) -> dict[str, float]:
    """One tooth gap in its own frame (gap centred on +X, lengths mm, angles rad).

    The pocket centre (ACA point a) is (``rp``, 0); these are the upper
    (+Y) side's curves, the lower side is their mirror in the X axis.  In
    boundary order from the bottom out, angles about each curve's centre:

    * seating arc about a, radius ``seat_r``, from pi (the bottom) to
      ``seat_start`` = pi/2 + A at x;
    * working arc about c (``working_cx``, ``working_cy``), radius
      ``working_r``, from ``seat_start`` at x (c, a and x are collinear) to
      ``working_end`` = pi/2 + A - B at y (``flank_start``);
    * the straight yz, tangent to the working arc at y and to the topping arc
      at z (``flank_end``);
    * topping arc about b (``topping_cx``, ``topping_cy``), radius
      ``topping_r``, from ``topping_start`` = A - B - pi/2 at z to
      ``topping_end`` at the ``corner`` where it meets the outside diameter,
      ``corner_angle`` off the gap centreline about the axis.
    """
    half = math.pi / teeth
    ra = outside_dia(teeth) / 2.0
    rp = pitch_dia(teeth) / 2.0
    a_ang, b_ang = working_angle(teeth), working_arc(teeth)
    r, e, f = SEAT_CURVE_R, WORKING_CURVE_R, topping_curve_r(teeth)
    # c sits ac back from a along x -> a, on the far side of the gap centreline
    # (ACA offsets M = ac cos A along the pitch tangent, T = ac sin A outward).
    wx = rp + WORKING_CENTRE_OFFSET * math.sin(a_ang)
    wy = -WORKING_CENTRE_OFFSET * math.cos(a_ang)
    seat_start = math.pi / 2.0 + a_ang
    working_end = seat_start - b_ang
    yx, yy = wx + e * math.cos(working_end), wy + e * math.sin(working_end)
    # b sits ab from a along the chord to the next pocket (ACA offsets
    # W = ab cos(180/N) along the tangent, V = ab sin(180/N) inward).
    tx = rp - TOPPING_CENTRE_OFFSET * math.sin(half)
    ty = TOPPING_CENTRE_OFFSET * math.cos(half)
    topping_start = a_ang - b_ang - math.pi / 2.0
    zx, zy = tx + f * math.cos(topping_start), ty + f * math.sin(topping_start)
    # The turned OD meets the topping circle ``gamma`` short of b's bearing.
    dist = math.hypot(tx, ty)
    cos_gamma = (dist * dist + ra * ra - f * f) / (2.0 * dist * ra)
    if not -1.0 < cos_gamma < 1.0:
        raise AssertionError(f"T{teeth}: the outside diameter misses the topping curve")
    corner_ang = math.atan2(ty, tx) - math.acos(cos_gamma)
    cx, cy = ra * math.cos(corner_ang), ra * math.sin(corner_ang)
    topping_end = math.atan2(cy - ty, cx - tx)
    x_r = math.hypot(rp + r * math.cos(seat_start), r * math.sin(seat_start))
    if not x_r < math.hypot(yx, yy) < math.hypot(zx, zy) < ra:
        raise AssertionError(f"T{teeth}: the tooth flank does not rise to the OD")
    if not topping_start < topping_end:
        raise AssertionError(f"T{teeth}: the OD cuts the topping curve before z")
    if not 0.0 < corner_ang < half:
        raise AssertionError(f"T{teeth}: the turned OD leaves no tip land")
    return {
        "half_pitch_angle": half,
        "ra": ra,
        "rp": rp,
        "seat_r": r,
        "seat_start": seat_start,
        "working_r": e,
        "working_cx": wx,
        "working_cy": wy,
        "working_end": working_end,
        "flank_start_x": yx,
        "flank_start_y": yy,
        "flank_end_x": zx,
        "flank_end_y": zy,
        "topping_r": f,
        "topping_cx": tx,
        "topping_cy": ty,
        "topping_start": topping_start,
        "topping_end": topping_end,
        "corner_angle": corner_ang,
        "corner_x": cx,
        "corner_y": cy,
    }


def _arc_term(cx: float, cy: float, r: float, a1: float, a2: float) -> float:
    """Green's-theorem term (x dy - y dx) of an arc run from a1 to a2, doubled."""
    return r * r * (a2 - a1) + r * (
        cx * (math.sin(a2) - math.sin(a1)) - cy * (math.cos(a2) - math.cos(a1))
    )


def gap_area(teeth: int) -> float:
    """Exact in-plate area (mm^2) one tooth gap removes, by Green's theorem.

    The gap is symmetric about the X axis, so its area is twice the upper
    half's, whose CCW boundary is: along the axis from the seat bottom to the
    OD (no term), the OD arc to the corner, the topping arc back to z, the
    straight to y, the working arc to x, the seating arc to the bottom (the
    beyond-OD part of the cut removes nothing).
    """
    g = gap_geometry(teeth)
    top = (g["topping_cx"], g["topping_cy"], g["topping_r"])
    work = (g["working_cx"], g["working_cy"], g["working_r"])
    y = (g["flank_start_x"], g["flank_start_y"])
    z = (g["flank_end_x"], g["flank_end_y"])
    twice = _arc_term(0.0, 0.0, g["ra"], 0.0, g["corner_angle"])
    twice += _arc_term(*top, g["topping_end"], g["topping_start"])
    twice += z[0] * y[1] - y[0] * z[1]  # the straight z -> y
    twice += _arc_term(*work, g["working_end"], g["seat_start"])
    twice += _arc_term(g["rp"], 0.0, g["seat_r"], g["seat_start"], math.pi)
    return twice  # 2 x (twice / 2)


# Static cross-section the bore and two pin holes remove (mm^2).
BORE_PINS_AREA = (
    math.pi * (BORE_DIA / 2.0) ** 2 + 2.0 * math.pi * (PIN_HOLE_DIA / 2.0) ** 2
)


def blank_volume(teeth: int) -> float:
    """Volume (mm^3) of the untoothed OD disc."""
    return math.pi * (outside_dia(teeth) / 2.0) ** 2 * PLATE


def toothed_volume(teeth: int) -> float:
    """Volume (mm^3) after the tooth gaps, before the bore and pin holes."""
    return blank_volume(teeth) - teeth * gap_area(teeth) * PLATE


def part_volume(teeth: int) -> float:
    """Finished part volume (mm^3) of one configuration."""
    return toothed_volume(teeth) - BORE_PINS_AREA * PLATE


def root_to_pin_hole(teeth: int) -> float:
    """Radial ligament from the ANSI bottom circle to a pin hole's outer edge."""
    return bottom_dia(teeth) / 2.0 - PIN_CIRCLE_RADIUS - PIN_HOLE_DIA / 2.0


for _name, _n in CONFIGS:
    if seat_bottom_dia(_n) / 2.0 <= PIN_CIRCLE_RADIUS + PIN_HOLE_DIA / 2.0:
        raise AssertionError(f"{_name}: seating curve breaks into the pin holes")
    if not 0.0 <= bottom_dia(_n) - seat_bottom_dia(_n) <= caliper_minus_tol(_n):
        raise AssertionError(f"{_name}: seat bottom outside the ANSI caliper tolerance")
    if gap_area(_n) <= 0.0:
        raise AssertionError(f"{_name}: tooth gap has no area")
