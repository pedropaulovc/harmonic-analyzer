r"""Pure-data dimensional contract shared by the alignment pinion and its drawing.

The long 32T brass drum pinion (ch.25) that engages the whole cylinder-gear
train to zero the machine to sines or cosines. See the batch gear-drawing
pattern in ``dt_cylinder_gear_spec``.
"""

from __future__ import annotations

import math

import _config
import dt_cylinder_gear_spec as drum

from _fit_limits import deviations, gear_tip_band_mm
from _printed_tolerance import printed_deviations
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from stock_form_cutter import CutterTemplate, StockFormProfile


MM_PER_IN = 25.4

TEETH = int(_config.machine("alignment_pinion", "teeth"))
DIAMETRAL_PITCH = float(_config.machine("gear_train", "diametral_pitch"))
PRESSURE_ANGLE_DEG = float(_config.machine("gear_train", "pressure_angle_deg"))
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA_BAND = gear_tip_band_mm("contact_critical")
DEDENDUM_FACTOR = 1.25  # reference cutter root, not an actual-axis circular floor
CUTTER_NUMBER = 4
CUTTER_TEETH_RANGE = (26, 34)
CUTTER_REFERENCE_TEETH = CUTTER_TEETH_RANGE[0]
CUTTER_TEMPLATE = CutterTemplate(
    CUTTER_REFERENCE_TEETH, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG
)
CUTTER_RADIAL_TRANSLATION_MM = PITCH_DIA / 2.0 - CUTTER_TEMPLATE.pitch_radius_mm
_SUPPORT_PROFILE = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, CUTTER_RADIAL_TRANSLATION_MM
)
SUPPORT_OUTSIDE_DIA_MM = 2.0 * _SUPPORT_PROFILE.support_radius_max_mm
# Pay the retained thickness inspection band with the actual cutter
# translation.  W = 2*Rb*(beta-k) + 2*T*sin(beta), beta = 3*pi/N.
BASE_TANGENT_SPAN_TEETH = 3
# Four places keep the exact standard-depth model below its printed +0 cap;
# three places would round 4.141050... DOWN and reject the native nominal.
BASE_TANGENT_SPAN_PLACES = 4
BASE_TANGENT_SPAN = _SUPPORT_PROFILE.tangent_span_mm(BASE_TANGENT_SPAN_TEETH)
BASE_TANGENT_SPAN_BAND = (0.0, -0.100)  # retained (upper, lower) inspection band
_SPAN_TRANSLATION_SENSITIVITY = 2.0 * math.sin(
    math.pi * BASE_TANGENT_SPAN_TEETH / TEETH
)
_PRINTED_SPAN_MIN = (
    round(BASE_TANGENT_SPAN, BASE_TANGENT_SPAN_PLACES) + BASE_TANGENT_SPAN_BAND[1]
)
MIN_SPAN_CUTTER_RADIAL_TRANSLATION_MM = CUTTER_RADIAL_TRANSLATION_MM + (
    _PRINTED_SPAN_MIN - BASE_TANGENT_SPAN
) / _SPAN_TRANSLATION_SENSITIVITY
_MIN_SPAN_SUPPORT_PROFILE = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, MIN_SPAN_CUTTER_RADIAL_TRANSLATION_MM
)
MIN_SPAN_SUPPORT_OUTSIDE_DIA_MM = (
    2.0 * _MIN_SPAN_SUPPORT_PROFILE.support_radius_max_mm
)
# Turn down for the deepest accepted STOCK cutter, not only the native
# standard-depth nominal.  The explicit OD upper deviation must fit too.
OUTSIDE_DIA = math.floor(
    (MIN_SPAN_SUPPORT_OUTSIDE_DIA_MM - OUTSIDE_DIA_BAND[0]) * 100.0
) / 100.0
STOCK_FORM = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, OUTSIDE_DIA / 2.0, CUTTER_RADIAL_TRANSLATION_MM
)
ROOT_ENVELOPE_DIA_MM = (
    2.0 * STOCK_FORM.root_radius_min_mm,
    2.0 * STOCK_FORM.root_radius_max_mm,
)
WHOLE_DEPTH = STOCK_FORM.plunge_mm
MAX_CUT_DEPTH_MM = STOCK_FORM.blank_radius_mm - STOCK_FORM.root_radius_min_mm
PITCH_TOOTH_THICKNESS_MM = STOCK_FORM.pitch_tooth_thickness_mm
ENGAGED_CENTER_EXTENSION_MM = float(
    _config.machine("alignment_pinion", "engaged_center_extension_mm")
)
ENGAGED_CENTER_DISTANCE_MM = (
    PITCH_DIA + drum.PITCH_DIA
) / 2.0 + ENGAGED_CENTER_EXTENSION_MM
ENGAGED_CENTER_RADIAL_STACK_MM = float(
    _config.machine("alignment_pinion", "engaged_center_radial_stack_mm")
)
# Inspect the actual translated-template flanks, not an unrolled ideal N32
# involute.  The core refuses a span whose tangent contacts leave finite support.
TOOTH_FORM = "TRANSLATED STOCK FORM; FINITE FLANKS AND OFF-CENTRE ROOT ARC"

BORE_DIA = 8.0  # Ø8 arbor through-bore (build_dt_pinion_arbor.py)
# Slip fit bonded with Loctite 638, not a press: a press over the full 143.2
# bore is a seizing risk for a novice (U27, U6 precedent).  The band admits a
# stock 8 mm H7 reamer (8.000-8.015).  The drum sits on MHA-DT-022's bond zone,
# not its journal lands (U39: Ø8 -0.01/-0.10), so the diametral clearance
# runs from 0.010 (the drum slides on by hand) up to the drum's upper
# deviation minus the arbor's lower one (0.200), inside the 0.25 mm bond gap
# the 638 technical data sheet allows.
ARBOR_BORE_BAND = (0.100, 0.000)  # (upper, lower) deviations
RETAINING_COMPOUND = "LOCTITE 638"
RETAINING_COMPOUND_MAX_GAP_MM = 0.25
FACE_WIDTH = 143.2  # general .X; located from the back end (drawing note)
# Tips are functional gear surfaces, not routine exterior profiles.  Actual
# stock-form support, coverage/no-gap, backlash, air and TE must pay both
# printed tip corners and the retained tangent-span/fit bands independently.

# Only the reamed bore carries a roughness symbol.  The two end faces bear on
# the MHA-DT-014 straps' inner faces when the drum floats hard forward or hard
# aft, but no friction or end-play budget derives a grade from that slow,
# hand-cranked contact.  So they take the title-block finish, the loosest
# band (novice rule), rather than a 1.6 no function asks for (machinist
# review of the pc-r7 sheet: over-specification; Main ruling (a), 2026-09-26).
SURFACE_FINISHES = (
    SurfaceFinishControl("drum_bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "GearBlankProfile": {"OutsideDia"},
    "ArborBoreProfile": {"ArborBoreDia"},
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": 1},
    "GearBlankProfile": {"OutsideDia": 2},
    "ArborBoreProfile": {"ArborBoreDia": 2},
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked alignment-pinion dimension needs native precision")


def outside_dia_limits_mm() -> tuple[float, float]:
    """Accepted tooth-tip MIN/MAX from the printed nominal and native band."""
    lower, upper = printed_deviations(
        OUTSIDE_DIA,
        DRAWING_PRECISION_BY_NAME["OutsideDia"],
        deviations(OUTSIDE_DIA_BAND),
    )
    return round(OUTSIDE_DIA + lower, 12), round(OUTSIDE_DIA + upper, 12)


def base_tangent_span_limits_mm() -> tuple[float, float]:
    """Accepted span MIN/MAX from its printed gear-data nominal and band."""
    nominal = round(BASE_TANGENT_SPAN, BASE_TANGENT_SPAN_PLACES)
    upper, lower = BASE_TANGENT_SPAN_BAND
    return round(nominal + lower, 12), round(nominal + upper, 12)


def manufacturing_corner_profiles() -> tuple[StockFormProfile, ...]:
    """Finite actual profiles at every printed tip/thickness size corner."""
    return tuple(
        StockFormProfile(
            TEETH,
            CUTTER_TEMPLATE,
            tip / 2.0,
            CUTTER_RADIAL_TRANSLATION_MM
            + (span - BASE_TANGENT_SPAN) / _SPAN_TRANSLATION_SENSITIVITY,
        )
        for tip in outside_dia_limits_mm()
        for span in base_tangent_span_limits_mm()
    )


# Diagnostic only: the chosen +platen-X operating sense is crank world +Z,
# cone -U and cylinder world +Z. Finishing zeroing in that direction loads
# the lower/reverse alignment edge. The drum has NO index feature: notches
# are set by eye and the drum is then parked, so this is not a readout datum.
ENGAGED_HOME_LOADED_EDGE = "lower"


def engaged_home_clocking_rad(
    engaged_swing_rad: float, line_of_centres_rad: float
) -> tuple[float, float]:
    """Diagnostic authored-home clockings, NOT a cam/readout zero datum.

    The caller supplies the PURE park owner's engaged swing and driver-to-
    cylinder line heading; importing that owner here would create a cycle.
    The drum is identity-placed at rest and anti-spun to the strap, so its
    native tooth0 advances by the engagement swing.  Its canonical gap is
    another pi/32 ahead.  The cylinder's row-vector placement is Ry(180)
    THEN Rz(-lock): its native gap angle pi/120 maps to pi-pi/120-lock.
    The engine's driven datum already includes pi-pi/120, leaving -lock-L.
    Return absolute physical angles, not modulo/tared tooth phases.

    Zeroing sets cylinder notches by eye, independently of this arbitrary
    drum input clock, then parks the drum. No budget term uses this gauge.
    """
    if not math.isfinite(engaged_swing_rad) or not math.isfinite(line_of_centres_rad):
        raise ValueError("alignment home swing and line heading must be finite")
    lock = math.radians(float(_config.machine("gear_train", "cylinder_lock_phase_deg")))
    return (
        engaged_swing_rad + math.pi / TEETH - line_of_centres_rad,
        -lock - line_of_centres_rad,
    )


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
        (
            "ROOT ENVELOPE DIAMETER (mm, REF)",
            f"{ROOT_ENVELOPE_DIA_MM[0]:.3f}-{ROOT_ENVELOPE_DIA_MM[1]:.3f}",
        ),
        (
            "CUTTER PLUNGE (mm, REF)",
            f"{WHOLE_DEPTH:.3f}",
        ),
        (
            "FORM CUTTER (REF)",
            f"#{CUTTER_NUMBER}, {CUTTER_TEETH_RANGE[0]}-{CUTTER_TEETH_RANGE[1]}T; "
            f"{CUTTER_REFERENCE_TEETH}T REFERENCE",
        ),
        ("TOOTH FORM", TOOTH_FORM),
        ("PITCH TOOTH THICKNESS (mm, REF)", f"{PITCH_TOOTH_THICKNESS_MM:.3f}"),
        (
            f"BASE-TANGENT SPAN, OVER {BASE_TANGENT_SPAN_TEETH} TEETH (mm)",
            f"{BASE_TANGENT_SPAN:.{BASE_TANGENT_SPAN_PLACES}f} "
            f"+{BASE_TANGENT_SPAN_BAND[0]:.3f}"
            f"/{BASE_TANGENT_SPAN_BAND[1]:.3f}",
        ),
    ]
)

# Rule 6: notes never carry a dimension.  MHA-DT-022 owns its bond-zone band
# natively (BondZoneDia).  The hand slide is this part's matched-fit
# acceptance, so it rides the reamed bore's callout, not a general note
# (Codex P2 on #832).  It names the mating part as well as its number
# (codex machinist review of f0faedc51), both from the part registry.
_ARBOR = _config.parts("dt-pinion-arbor")
ARBOR_BORE_CALLOUT = (
    f"REAM THRU\nSLIDES BY HAND ON {_ARBOR['number']}\n{_ARBOR['title'].upper()}"
)
# Rule 6: the bond to MHA-DT-022 is an assembly step (dt_pinion_arbor_spec
# ASSEMBLY_STEP owns the drum joint), not a part note.
DRAWING_NOTES = "TOOTH FLANKS, TIPS, AND ROOTS: DO NOT CHAMFER OR BLEND."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
