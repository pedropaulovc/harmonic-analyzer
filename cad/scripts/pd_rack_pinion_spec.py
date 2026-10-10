r"""MHA-PD-006 rack-pinion: the 120T brass reducer disc of the translational gearing.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` import.  The disc is
driven 12:120 by the knob shaft's 12T DP38 and screwed to the brass hub's
flange (MHA-PD-017, ``pd_transgear_disc_hub_spec``) by three #0-80 fillister
screws (MHA-VN-039, McMaster 91794A055; the joint is
``pd_transgear_disc_hub_geometry``'s).  Its Ø13.1 H7 bore pilots on the hub's
Ø13.1 h6 spigot, which passes it and seats on the pinion sleeve's (MHA-PD-010)
step face; its front face, clamped by the hub's flange, stands the spigot's
length ahead of that step, and its rear face stands in air ahead of the
sleeve's 12T, radially clear of its tips (R9-68).

Part frame: gear axis = Z through the origin; the Front plane (z = 0) is the
disc's FRONT face, the one the hub flange's rear face seats on; the body runs
z = 0..FACE_WIDTH, so local +Z is machine rearward.  The screw pattern's 0°
is local +X, counter-clockwise seen from +Z (``pd_transgear_disc_hub_geometry``).

The #0-80 taps are TRANSFERRED at assembly (ruling R9-9): with the disc on
the hub's spigot and the hub seated on the sleeve's step, each tap is spotted
through its MHA-PD-017 flange hole, then drilled and tapped, and disc and
flange are match-marked.
The model places the taps on the flange's bolt circle (the one authority);
the sheet prints the tap, its mouth breaks and the transfer, never the
bolt-circle position.
"""

from __future__ import annotations

from _fit_deviations import deviations
from _gtol_cylinder import CylinderFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES
from pd_transgear_disc_hub_geometry import (
    BOLT_CIRCLE_DIA,
    BOLT_CIRCLE_POSITION_TOL,
    SCREW_COUNT,
    SCREW_HOLE_DIA,
    SCREW_SKU,
    SCREW_THREAD,
    SPIGOT_DIA,
    SPIGOT_DIA_BAND,
    screw_centres,
)

MM_PER_IN = 25.4

# --- gear ----------------------------------------------------------------------
TEETH = 120
DIAMETRAL_PITCH = 38.0  # disc OD ~82 at 120T (build_pd_rack_pinion.py)
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
BORE_DIA = SPIGOT_DIA  # 13.1
# Pilots on the hub's spigot (MHA-PD-017, pd_transgear_disc_hub_geometry): one ISO
# fit, the bore reamed H7 at 10-18 mm over the spigot's h6, a locational
# clearance that assembles by hand, so the disc never binds and sits at most
# 0.0145 off the hub's axis while its taps are spotted.
BORE_BAND = (0.018, 0.0)  # (upper, lower) deviations, H7
BORE_DEVIATIONS = deviations(BORE_BAND)
BORE_PLACES = 3

_BAND = {places: printed_band_mm(places) for places in (1, 2, 3)}
FACE_WIDTH_MIN = FACE_WIDTH - _BAND[FACE_WIDTH_PLACES]
FACE_WIDTH_MAX = FACE_WIDTH + _BAND[FACE_WIDTH_PLACES]
BORE_DIA_MIN = BORE_DIA + BORE_BAND[1]
BORE_DIA_MAX = BORE_DIA + BORE_BAND[0]

# The hub's spigot, turned to the h6 band the hub's model carries.  Its
# limits and the bore's give the locating clearance and bound how far the
# disc can sit off the hub's axis while the taps are spotted through the
# flange.
SPIGOT_DIA_MIN = SPIGOT_DIA + SPIGOT_DIA_BAND[1]
SPIGOT_DIA_MAX = SPIGOT_DIA + SPIGOT_DIA_BAND[0]
# (least, greatest) diametral clearance: 0.000 .. 0.029.
SPIGOT_DIAMETRAL_CLEARANCE = (
    round(BORE_DIA_MIN - SPIGOT_DIA_MAX, 3),
    round(BORE_DIA_MAX - SPIGOT_DIA_MIN, 3),
)
if SPIGOT_DIAMETRAL_CLEARANCE[0] < 0.0:
    raise AssertionError(
        f"MHA-PD-006 bore binds on the MHA-PD-017 spigot: {SPIGOT_DIAMETRAL_CLEARANCE}"
    )
DISC_OFFSET_MAX = SPIGOT_DIAMETRAL_CLEARANCE[1] / 2.0
# The rear face stands in air (the hub's flange locates the front face), so
# the bore's rear edge takes the title block's break.  The front edge is
# chamfered past the spigot-to-flange corner's R0.1 so the front face seats
# on the flange (pd_transgear_disc_hub_spec checks the pair).
BORE_FRONT_CHAMFER_LIMITS = (0.15, 0.25)  # 45 deg
BORE_FRONT_CHAMFER_NOTE = (
    f"BORE FRONT EDGE CHAMFER {BORE_FRONT_CHAMFER_LIMITS[0]:.2f}-"
    f"{BORE_FRONT_CHAMFER_LIMITS[1]:.2f} X 45\u00b0."
)

# --- screw (MHA-VN-039) -------------------------------------------------------------
SCREW_MAJOR_DIA, SCREW_LENGTH, _HEAD_H, _HEAD_DIA, SCREW_PITCH = FILLISTER_SIZES[
    SCREW_SKU
]

# --- #0-80 taps --------------------------------------------------------------------
TAP_SPEC = HoleSpec("tapped", SCREW_THREAD)
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
TAP_MAJOR = THREAD_MAJOR_MM[SCREW_THREAD]
if abs(TAP_MAJOR - SCREW_MAJOR_DIA) > 1e-9:
    raise AssertionError(
        "the disc tap and the MHA-VN-039 screw disagree on the #0-80 major"
    )
# The tapped major's allowance over basic (contract §8, "tap major 0.025" radial).
TAP_MAJOR_ALLOWANCE = 0.05
TAP_COUNT = SCREW_COUNT
TAP_CENTRES = screw_centres()

# No countersink (R9-63): a 90° countersink opening past the 1.524 major
# costs at least (1.524 - 1.191) / 2 = 0.167 of full thread at its mouth on
# the 3.0 disc, so both mouths carry a burr break only (not modelled).  Full
# thread starts where the break's 45° leg meets the tap drill.
MOUTH_BREAK_MAX = 0.10

# --- the tap's thread losses (contract §7) -------------------------------------
# The MHA-VN-039 screws are cut to fit at assembly (R9-47): their tips stop
# inside the rear face, so the joint's engagement, the cut window and the
# stock's reach are judged in vn_transgear_disc_screw_spec from these losses.
ENGAGEMENT_FLOOR_D = 1.5
MOUTH_THREAD_LOSS = MOUTH_BREAK_MAX

# --- tap to bore wall (contract §8) ---------------------------------------------
# The disc prints no tap position, so its worst case is the transfer chain:
# the flange hole's bolt-circle band (MHA-PD-017), the spot's centring in that
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
        f"MHA-PD-006 tap to bore wall {TAP_TO_BORE_WALL_WORST:.3f} worst < {WALL_FLOOR}"
    )

# --- sheet -------------------------------------------------------------------------
HUB_NUMBER = "MHA-PD-017"
HUB_NAME = "HUB"
# Lines appended under the native "#0-80 UNF-2B THRU" hole callout.
TAP_CALLOUT_LINES = (
    f"BREAK EDGE {MOUTH_BREAK_MAX:.2f} MAX BOTH SIDES",
    f"SPOT THRU {HUB_NUMBER} FLANGE HOLES AT ASSY,",
    "THEN DRILL AND TAP; MATCH-MARK DISC AND FLANGE",
)
TAP_CALLOUT_QUALIFIER = "\n".join(TAP_CALLOUT_LINES)
# Reamed: the bore carries the Ra 1.6 finish and pilots on the hub's spigot.
# The bore's native limits print with the dimension; the fit note names the
# mate.
BORE_CALLOUT = "THRU - REAM"
BORE_FIT_CALLOUT = "\n".join(
    (
        "BORE LIMITS GOVERN",
        f"MATE {HUB_NAME} {HUB_NUMBER} SPIGOT",
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
    raise AssertionError("every marked MHA-PD-006 dimension needs its printed places")


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

# The teeth are stated by the gear data block; the build appends the disc
# screw's engagement line (vn_transgear_disc_screw_spec imports this module).
DRAWING_NOTES = "\n".join(
    (
        "GEAR TEETH: CIRCULAR RUNOUT 0.05 MAX TO DATUM A AT THE TOOTH TIPS.",
        BORE_FRONT_CHAMFER_NOTE,
    )
)


# Manufacturing GD&T limits consumed by the part's drawing projection.  The
# hub's flange clamps the front face (datum B), so the rear face, toward the
# platen, is held parallel to it (the paper-drive assembly's platen air reads
# it); the bore (datum A) carries the tooth-tip runout note.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "disc rear face parallelism to front": "0.05",
}
FRONT_FACE_DATUM = "B"
