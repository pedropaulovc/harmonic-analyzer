r"""MHA-070 rack-pinion: the 120T brass reducer disc of the translational gearing.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` import.  The disc is
driven 12:120 by the knob shaft's 12T DP38 and screwed to the brass hub's
flange (MHA-159, ``transgear_disc_hub_spec``) by three #0-80 fillister
screws (MHA-161, McMaster 91794A055).  Its Ø10 bore slips on the pinion
sleeve's spigot (contract §2.3 / §2.5).

Part frame: gear axis = Z through the origin; the Front plane (z = 0) is the
disc's FRONT face, the one the hub flange's rear face seats on; the body runs
z = 0..FACE_WIDTH, so local +Z is machine rearward.  The screw pattern's 0°
is local +X, counter-clockwise seen from +Z (``transgear_disc_hub_geometry``).

The #0-80 taps are TRANSFERRED at assembly (ruling R9-9): with the disc on
the spigot and the hub pressed on, each tap is spotted through its MHA-159
flange hole, then drilled and tapped, and disc and flange are match-marked.
The model places the taps on the flange's bolt circle (the one authority);
the sheet prints the tap, its countersink and the transfer, never the
bolt-circle position.
"""

from __future__ import annotations

from _fit_limits import REAM_SLIDE, SHAFT_H, deviations
from _gtol_spec import CylinderFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES
from transgear_disc_hub_geometry import (
    BOLT_CIRCLE_DIA,
    BOLT_CIRCLE_POSITION_TOL,
    SCREW_COUNT,
    SCREW_THREAD,
    screw_centres,
)
from transgear_disc_hub_spec import (
    FLANGE_THICK,
    FLANGE_THICK_PLACES,
    SCREW_HOLE_DIA,
    SCREW_SKU,
)

MM_PER_IN = 25.4

# --- gear ----------------------------------------------------------------------
TEETH = 120
DIAMETRAL_PITCH = 38.0  # disc OD ~82 at 120T (build_rack_pinion.py)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN

# The permanent mesh with the knob shaft's 12T DP38: the standard centre
# distance plus the contract's 0.65 extension (backlash), unchanged.
MESH_PINION_TEETH = 12
CENTRE_DISTANCE = 44.766
CENTRE_EXTENSION = CENTRE_DISTANCE - (
    (TEETH + MESH_PINION_TEETH) / (2.0 * DIAMETRAL_PITCH) * MM_PER_IN
)
if not 0.6 < CENTRE_EXTENSION < 0.7:
    raise AssertionError(f"12:120 centre extension moved: {CENTRE_EXTENSION:.3f}")

# --- disc body -----------------------------------------------------------------
FACE_WIDTH = 3.0
# Printed .XXX, functional (R9-5): the hub may never stand proud of the
# sleeve nose, and that stack reads the disc thickness.
FACE_WIDTH_PLACES = 3
BORE_DIA = 10.0
# Slips on the pinion sleeve's Ø10 spigot (MHA-110).  The .XXX rows would let
# a Ø9.870 bore meet a Ø10.130 spigot, so the bore is reamed to the fleet's
# REAM_SLIDE band over the spigot's SHAFT_H band: guaranteed slip clearance.
BORE_BAND = REAM_SLIDE  # (upper, lower) deviations
BORE_DEVIATIONS = deviations(BORE_BAND)
BORE_PLACES = 3

_BAND = {places: printed_band_mm(places) for places in (1, 2, 3)}
FACE_WIDTH_MIN = FACE_WIDTH - _BAND[FACE_WIDTH_PLACES]
FACE_WIDTH_MAX = FACE_WIDTH + _BAND[FACE_WIDTH_PLACES]
BORE_DIA_MIN = BORE_DIA + BORE_BAND[1]
BORE_DIA_MAX = BORE_DIA + BORE_BAND[0]

# The sleeve's spigot (MHA-110), turned to the SHAFT_H band the sleeve's model
# carries (transgear_feed_pinion_spec reads it here).  Its limits and the
# bore's give the slip clearance and bound how far the disc can sit off the
# sleeve axis while the taps are spotted through the flange.
SLEEVE_NUMBER = "MHA-110"
SPIGOT_DIA = 10.0
SPIGOT_DIA_BAND = SHAFT_H  # (upper, lower) deviations
SPIGOT_DIA_MIN = SPIGOT_DIA + SPIGOT_DIA_BAND[1]
SPIGOT_DIA_MAX = SPIGOT_DIA + SPIGOT_DIA_BAND[0]
# (least, greatest) diametral clearance: 0.010 .. 0.045.
SPIGOT_DIAMETRAL_CLEARANCE = (
    round(BORE_DIA_MIN - SPIGOT_DIA_MAX, 3),
    round(BORE_DIA_MAX - SPIGOT_DIA_MIN, 3),
)
if SPIGOT_DIAMETRAL_CLEARANCE[0] <= 0.0:
    raise AssertionError(
        f"MHA-070 bore binds on the MHA-110 spigot: {SPIGOT_DIAMETRAL_CLEARANCE}"
    )
DISC_OFFSET_MAX = SPIGOT_DIAMETRAL_CLEARANCE[1] / 2.0

# --- screw (MHA-161) -------------------------------------------------------------
SCREW_MAJOR_DIA, SCREW_LENGTH, _HEAD_H, _HEAD_DIA, SCREW_PITCH = FILLISTER_SIZES[
    SCREW_SKU
]

# --- #0-80 taps --------------------------------------------------------------------
TAP_SPEC = HoleSpec("tapped", SCREW_THREAD)
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
TAP_MAJOR = THREAD_MAJOR_MM[SCREW_THREAD]
if abs(TAP_MAJOR - SCREW_MAJOR_DIA) > 1e-9:
    raise AssertionError(
        "the disc tap and the MHA-161 screw disagree on the #0-80 major"
    )
# The tapped major's allowance over basic (contract §8, "tap major 0.025" radial).
TAP_MAJOR_ALLOWANCE = 0.05
TAP_COUNT = SCREW_COUNT
TAP_CENTRES = screw_centres()

# 90° entry countersink at the FRONT face, drilled-hole class; the rear face
# gets a burr break only.
CSK_DIA = 1.7
CSK_BAND = (0.10, 0.0)  # (upper, lower)
CSK_ANGLE_DEG = 90.0
CSK_DIA_MAX = CSK_DIA + max(CSK_BAND)
if CSK_DIA <= TAP_MAJOR:
    raise AssertionError("the tap countersink must open past the #0-80 major")
# The modelled 45° leg on the tap-drill rim.
CSK_LEG = (CSK_DIA - TAP_DRILL_DIA) / 2.0
REAR_BREAK_MAX = 0.05

# --- engagement of MHA-161 in the disc (contract §7) ---------------------------
# The screw runs through the whole disc (its tip stands past the rear face),
# so the full thread is the disc less the countersink's thread loss and the
# rear burr break.
ENGAGEMENT_FLOOR_D = 1.5
CSK_THREAD_LOSS = (CSK_DIA - TAP_MAJOR) / 2.0
CSK_THREAD_LOSS_WORST = (CSK_DIA_MAX - TAP_MAJOR) / 2.0
ENGAGEMENT_NOMINAL = FACE_WIDTH - CSK_THREAD_LOSS - REAR_BREAK_MAX
ENGAGEMENT_WORST = FACE_WIDTH_MIN - CSK_THREAD_LOSS_WORST - REAR_BREAK_MAX
ENGAGEMENT_NOMINAL_D = ENGAGEMENT_NOMINAL / SCREW_MAJOR_DIA
ENGAGEMENT_WORST_D = ENGAGEMENT_WORST / SCREW_MAJOR_DIA
if ENGAGEMENT_WORST_D < ENGAGEMENT_FLOOR_D - 1e-9:
    raise AssertionError(
        f"MHA-161 engages MHA-070 {ENGAGEMENT_WORST_D:.3f} D worst, under "
        f"{ENGAGEMENT_FLOOR_D} D"
    )

# Screw tip past the disc's rear face: 6.35 under the head, less the flange
# and the disc.  At the shortest reach the tip still clears the rear face by
# more than one pitch, so the screw's incomplete end thread never sits in the
# disc.  The platen air behind it is the assembly's.
_FLANGE_BAND = _BAND[FLANGE_THICK_PLACES]
SCREW_TIP_PAST_REAR = SCREW_LENGTH - FLANGE_THICK - FACE_WIDTH
SCREW_TIP_PAST_REAR_MIN = SCREW_LENGTH - (FLANGE_THICK + _FLANGE_BAND) - FACE_WIDTH_MAX
SCREW_TIP_PAST_REAR_MAX = SCREW_LENGTH - (FLANGE_THICK - _FLANGE_BAND) - FACE_WIDTH_MIN
if abs(SCREW_TIP_PAST_REAR - 0.95) > 1e-9:
    raise AssertionError(
        f"disc-screw tip moved: {SCREW_TIP_PAST_REAR:.3f} past the rear face"
    )
if SCREW_TIP_PAST_REAR_MIN < SCREW_PITCH:
    raise AssertionError(
        "the disc screw's incomplete end thread can sit inside the disc"
    )

# --- tap to bore wall (contract §8) ---------------------------------------------
# The disc prints no tap position, so its worst case is the transfer chain:
# the flange hole's bolt-circle band (MHA-159), the spot's centring in that
# hole (a Ø1.7 spotting tool in the Ø1.7 +0.10/0 hole), and the disc's offset
# on the spigot while it is spotted.
SPOT_CENTRING_TOL = (SCREW_HOLE_DIA + 0.10 - SCREW_HOLE_DIA) / 2.0
TAP_POSITION_ERROR = BOLT_CIRCLE_POSITION_TOL + SPOT_CENTRING_TOL + DISC_OFFSET_MAX
WALL_FLOOR = 2.0
TAP_TO_BORE_WALL = BOLT_CIRCLE_DIA / 2.0 - TAP_MAJOR / 2.0 - BORE_DIA / 2.0
TAP_TO_BORE_WALL_WORST = (
    BOLT_CIRCLE_DIA / 2.0
    - TAP_POSITION_ERROR
    - (TAP_MAJOR + TAP_MAJOR_ALLOWANCE) / 2.0
    - BORE_DIA_MAX / 2.0
)
if TAP_TO_BORE_WALL_WORST < WALL_FLOOR - 1e-9:
    raise AssertionError(
        f"MHA-070 tap to bore wall {TAP_TO_BORE_WALL_WORST:.3f} worst < {WALL_FLOOR}"
    )
# The countersink's mouth to the bore edge on the front face: a 0.14-deep
# lip, informational (reported with the wall, never under the 1.5 floor).
CSK_TO_BORE_WORST = (
    BOLT_CIRCLE_DIA / 2.0 - TAP_POSITION_ERROR - CSK_DIA_MAX / 2.0 - BORE_DIA_MAX / 2.0
)
if CSK_TO_BORE_WORST < 1.5 - 1e-9:
    raise AssertionError(f"MHA-070 countersink to bore {CSK_TO_BORE_WORST:.3f} < 1.5")

# --- sheet -------------------------------------------------------------------------
HUB_NUMBER = "MHA-159"
# Lines appended under the native "#0-80 UNF-2B THRU" hole callout.  The
# face view looks at the REAR face (*Front, from +Z): the countersink is on
# the far side, the burr break on the near side.
TAP_CALLOUT_LINES = (
    f"{CSK_ANGLE_DEG:.0f}\u00b0 CSK \u00d8{CSK_DIA:.1f} +{CSK_BAND[0]:.2f}/0 FAR SIDE",
    f"NEAR SIDE BREAK EDGE {REAR_BREAK_MAX:.2f} MAX",
    f"SPOT THRU {HUB_NUMBER} FLANGE HOLES AT ASSY,",
    "THEN DRILL AND TAP; MATCH-MARK DISC AND FLANGE",
)
TAP_CALLOUT_QUALIFIER = "\n".join(TAP_CALLOUT_LINES)
# Reamed: the bore carries the Ra 1.6 finish and slips on the spigot.  The
# bore's native limits print with the dimension; the fit note names the mate.
BORE_CALLOUT = "THRU - REAM"
BORE_FIT_CALLOUT = "\n".join(
    (
        "BORE LIMITS GOVERN",
        f"MATE SLEEVE {SLEEVE_NUMBER} SPIGOT",
        f"(\N{DIAMETER SIGN}{SPIGOT_DIA:.3f} +{SPIGOT_DIA_BAND[0]:.3f}/"
        f"{SPIGOT_DIA_BAND[1]:.3f})",
        f"(DIA CLR {SPIGOT_DIAMETRAL_CLEARANCE[0]:.3f}-"
        f"{SPIGOT_DIAMETRAL_CLEARANCE[1]:.3f} mm)",
    )
)

SURFACE_FINISHES = (SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE_DIA)),)

# Marked model dimensions and the places the model authors on them (policy
# rule 2): the disc thickness (the gear blank's extrude depth) and the bore.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "BoreProfile": {"BoreDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": FACE_WIDTH_PLACES},
    "BoreProfile": {"BoreDia": BORE_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if {f: set(n) for f, n in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked MHA-070 dimension needs its printed places")


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("MODULE (mm, REF)", f"{MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER (mm)", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        ("WHOLE DEPTH (mm)", f"{WHOLE_DEPTH:.2f} REF"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "CUT TEETH PER GEAR DATA.",
        "THIN DISC GEAR; GEAR TEETH: CIRCULAR RUNOUT 0.05 MAX ABOUT DATUM A, MEASURED AT THE TOOTH TIPS.",
    )
)


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "disc face squareness to bore": "0.05",
}
