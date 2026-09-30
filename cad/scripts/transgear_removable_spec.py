r"""MHA-081 transgear-removable: the ANSI #25 sprocket and its seat interface.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in the import
closure.  One authority for the numbers the removable sprocket, the two
shafts it seats on (crankshaft MHA-026, knob shaft MHA-078), the drive-train
and paper-drive assemblies and the chain solver ``_chain`` all share.

Evidence: ch23 p.56 (catalog photo: #25 chain, plate, bore and the two
drive-pin holes nearly touching the bore), p.61 and video frame f_0215/f_0210.

Machine frame: +Y up, -Z = machine FRONT, +X = operator's left.  Both mounted
wheels (crank T12, knob T24) occupy the SAME z band: rear face on the shaft's
seat face at ``SEAT_FACE_Z``, front face at ``BAND_FRONT_Z``, so the chain
runs in one plane, ``CHAIN_MID_Z``, on both shafts.  Each shaft's seat is a
flat ``SEAT_SPIGOT_DIA`` face carrying two pressed 3/32 dowels: small enough
that the #25 chain's plates wrap the T12 clear of it.

Tooth form (ANSI B29.1 / ISO 606 proportions): a roller seating curve of
radius ``SEAT_CURVE_R`` centred on the pitch circle, straight flanks tangent
to it, and a flat tip ``TIP_FLAT`` wide (chord) on the outside diameter.  The
exact commercial profile differs slightly (Toolbox/hobbed), but pitch,
outside and bottom diameters are the standard ones.  :func:`gap_area` is the
exact in-plate area one tooth gap removes, so the part's volume check tests
the tooth SHAPE, not merely that some cut happened.

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
# ISO 606 maximum roller-seating radius (mm formula): 0.505 d1 + 0.069 d1^(1/3).
SEAT_CURVE_R = 0.505 * ROLLER_DIA + 0.069 * ROLLER_DIA ** (1.0 / 3.0)  # 1.769
TIP_FLAT = 1.6  # tip flat width (chord on the OD)

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
# each spending half of it.  The shafts read these (crankshaft_spec).
DRIVE_PIN_OFFSET_PLACES = 3
DRIVE_PIN_OFFSET_TOL = 0.025

# Bore <-> pin-hole web.  Photo-faithful to the p.56 catalog view, where the
# holes nearly touch the bore; under the policy's 1.5 wall floor, accepted by
# name (drawing-simplicity-policy.md, "Named exceptions").  Its printed worst
# case is sheet text (transgear_removable_notes.BORE_PIN_WEB_WORST): it reads
# the title block's drilled-hole row, which this module's importers must not.
BORE_PIN_WEB = PIN_CIRCLE_RADIUS - PIN_HOLE_DIA / 2.0 - BORE_DIA / 2.0  # 0.60

CONFIGS: tuple[tuple[str, int], ...] = (("T12", 12), ("T18", 18), ("T24", 24))
TEETH = dict(CONFIGS)
DEFAULT_CONFIG = "T24"  # the part saves on T24

# --- manufacturing drawing (one sheet, the T24 views; SPROCKET DATA lists all
# three configurations) --------------------------------------------------------
# The plate thickness carries PLATE_BAND; the bore and the pin holes are
# drilled (the title block's DRILLED HOLES row governs them); each pin centre
# carries +/-DRIVE_PIN_OFFSET_TOL at .XXX.  PinNegDia is the same global as
# PinPosDia and prints once as its "2X".
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlankProfile": {"BlankWidth"},
    "BorePinsProfile": {"BoreDiaDim", "PinPosDia", "PinPosY", "PinNegY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlankProfile": {"BlankWidth": 2},
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
SEAT_FACE_Z = -152.5  # wheel rear face = shaft seat face (the stack datum)
BAND_FRONT_Z = SEAT_FACE_Z - PLATE  # -155.3, wheel front face
CHAIN_MID_Z = SEAT_FACE_Z - PLATE / 2.0  # -153.9, the ONE chain plane

# --- drive-pin seat interface (both shafts carry it) -------------------------
# Two purchased 3/32 dowels pressed into each shaft's seat face, rounded end
# proud by DRIVE_PIN_PROUD: 1/4 long in the crank (crank-seat-drive-pin,
# MHA-173), 3/16 in the knob shaft (transgear-knob-drive-pin, MHA-155).  Their
# lengths and press depths are the shafts'; the diameter is the interface's.
DRIVE_PIN_DIA = 3.0 / 32.0 * MM_PER_IN  # 2.38125; each pin spec asserts its own
DRIVE_PIN_PROUD = 2.4  # standing out of the seat face
DRIVE_PIN_TIP_Z = SEAT_FACE_Z - DRIVE_PIN_PROUD  # -154.9
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
    """ANSI B29.1 bottom diameter PD - roller (the caliper root)."""
    return pitch_dia(teeth) - ROLLER_DIA


def seat_bottom_dia(teeth: int) -> float:
    """Diameter through the seating-curve bottoms, PD - 2 R (the as-cut root)."""
    return pitch_dia(teeth) - 2.0 * SEAT_CURVE_R


def gap_geometry(teeth: int) -> dict[str, float]:
    """One tooth gap in its own frame (gap centred on +X, lengths mm, angles rad).

    ``corner`` is the tip-flat corner on the OD (upper side), ``tangent`` the
    point where the straight flank meets the seating curve, ``seat_start`` its
    angle about the pocket centre; the pocket arc runs from ``seat_start`` to
    ``2 pi - seat_start`` through the bottom (angle pi).
    """
    half = math.pi / teeth
    ra = outside_dia(teeth) / 2.0
    rp = pitch_dia(teeth) / 2.0
    r = SEAT_CURVE_R
    phi = math.asin(TIP_FLAT / 2.0 / ra)
    corner_ang = half - phi
    cx, cy = ra * math.cos(corner_ang), ra * math.sin(corner_ang)
    vx, vy = cx - rp, cy
    d = math.hypot(vx, vy)
    if d <= r:
        raise AssertionError(f"T{teeth}: tip corner inside the seating curve")
    seat_start = math.atan2(vy, vx) + math.acos(r / d)
    if not math.pi / 2.0 < seat_start < math.pi:
        raise AssertionError(f"T{teeth}: flank tangency off the seat's upper quadrant")
    return {
        "half_pitch_angle": half,
        "ra": ra,
        "rp": rp,
        "seat_r": r,
        "tip_half_angle": phi,
        "corner_angle": corner_ang,
        "corner_x": cx,
        "corner_y": cy,
        "seat_start": seat_start,
        "tangent_x": rp + r * math.cos(seat_start),
        "tangent_y": r * math.sin(seat_start),
    }


def _arc_term(cx: float, cy: float, r: float, a1: float, a2: float) -> float:
    """Green's-theorem term (x dy - y dx) of a CCW arc, doubled."""
    return r * r * (a2 - a1) + r * (
        cx * (math.sin(a2) - math.sin(a1)) - cy * (math.cos(a2) - math.cos(a1))
    )


def gap_area(teeth: int) -> float:
    """Exact in-plate area (mm^2) one tooth gap removes, by Green's theorem.

    CCW boundary: OD arc lower corner -> upper corner, upper flank to its
    seating-curve tangent, the seating arc through the bottom, lower flank
    back to the lower corner (the beyond-OD part of the cut removes nothing).
    """
    g = gap_geometry(teeth)
    cx, cy, tx, ty = g["corner_x"], g["corner_y"], g["tangent_x"], g["tangent_y"]
    twice = _arc_term(0.0, 0.0, g["ra"], -g["corner_angle"], g["corner_angle"])
    twice += cx * ty - tx * cy  # upper flank corner -> tangent
    twice += _arc_term(
        g["rp"], 0.0, g["seat_r"], g["seat_start"], 2.0 * math.pi - g["seat_start"]
    )
    twice += tx * (-cy) - cx * (-ty)  # lower flank tangent' -> corner'
    return twice / 2.0


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
    if gap_area(_n) <= 0.0:
        raise AssertionError(f"{_name}: tooth gap has no area")
