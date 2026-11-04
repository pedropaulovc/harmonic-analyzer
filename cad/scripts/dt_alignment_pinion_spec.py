r"""Pure-data dimensional contract shared by the alignment pinion and its drawing.

The long 32T brass drum pinion (ch.25) that engages the whole cylinder-gear
train to zero the machine to sines or cosines. See the batch gear-drawing
pattern in ``dt_cylinder_gear_spec``.
"""

from __future__ import annotations

import math

import _config
import dt_cylinder_gear_spec as drum

from _fit_deviations import deviations
from _fit_ream_slide import REAM_SLIDE
from _gear_fit_limits import gear_tip_band_mm
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations
from _gtol_cylinder import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from stock_form_cutter import TOOTH_FORM_NOTE, CutterTemplate, StockFormProfile


MM_PER_IN = 25.4
# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/dt-alignment-pinion", _config.parts("dt-alignment-pinion"))

TEETH = int(_config.machine("alignment_pinion", "teeth"))
DIAMETRAL_PITCH = float(_config.machine("gear_train", "diametral_pitch"))
PRESSURE_ANGLE_DEG = float(_config.machine("gear_train", "pressure_angle_deg"))
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA_BAND = gear_tip_band_mm("standard")
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
BASE_TANGENT_SPAN = _SUPPORT_PROFILE.tangent_span_mm(BASE_TANGENT_SPAN_TEETH)
# The gear-data block prints the span in inches at four places, rounded UP so
# the exact standard-depth model stays under its printed +0 cap (.163033...
# would round down to .1630 and reject the native nominal).
BASE_TANGENT_SPAN_PLACES = 4
BASE_TANGENT_SPAN_PRINTED_MM = (
    math.ceil(BASE_TANGENT_SPAN / MM_PER_IN * 10**BASE_TANGENT_SPAN_PLACES - 1e-9)
    / 10**BASE_TANGENT_SPAN_PLACES
    * MM_PER_IN
)
BASE_TANGENT_SPAN_BAND = (0.0, -0.1016)  # retained (upper, lower): +.0000/-.0040 in
_SPAN_TRANSLATION_SENSITIVITY = 2.0 * math.sin(
    math.pi * BASE_TANGENT_SPAN_TEETH / TEETH
)
_PRINTED_SPAN_MIN = BASE_TANGENT_SPAN_PRINTED_MM + BASE_TANGENT_SPAN_BAND[1]
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
# Floored to the .001-in grid the tip prints at (.694).
OUTSIDE_DIA_PLACES = 3
OUTSIDE_DIA = round(
    math.floor(
        (MIN_SPAN_SUPPORT_OUTSIDE_DIA_MM - OUTSIDE_DIA_BAND[0])
        / MM_PER_IN
        * 10**OUTSIDE_DIA_PLACES
    )
    / 10**OUTSIDE_DIA_PLACES
    * MM_PER_IN,
    9,
)
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
# The stock #4 cutter, plunged on the gear axis, defines the form; the span
# below is its acceptance.  The core refuses a span whose tangent contacts
# leave the cut flanks.
TOOTH_FORM = TOOTH_FORM_NOTE

BORE_DIA = 7.9375  # 5/16 arbor through-bore (build_dt_pinion_arbor.py)
# Slip fit bonded with Loctite 638, not a press: a press over the full drum
# bore is a seizing risk for a novice (U27, U6 precedent).  The bore is
# REAM_SLIDE, cut by the owned .3135 over reamer.  The drum sits on
# MHA-DT-22's bond zone, not its journal lands (U39: 5/16 -.0004/-.0038 in),
# so the diametral clearance runs from .0014 in (the drum slides on by hand)
# up to the drum's upper deviation minus the arbor's lower one (.0053 in),
# inside the 0.25 mm bond gap the 638 technical data sheet allows.
ARBOR_BORE_BAND = REAM_SLIDE  # (upper, lower) deviations
RETAINING_COMPOUND = "LOCTITE 638"
RETAINING_COMPOUND_MAX_GAP_MM = 0.25
# Prints .XX (5.64): the pinion-rig end-play budget reads its band
# (pinion_rig_layout.DRUM_LEN), so it cannot take the .X row.
FACE_WIDTH = 143.256  # 5.64; located from the back end (drawing note)
# Tips are functional gear surfaces, not routine exterior profiles.  Actual
# stock-form support, coverage/no-gap, backlash, air and TE must pay both
# printed tip corners and the retained tangent-span/fit bands independently.

# Only the reamed bore carries a roughness symbol.  The two end faces bear on
# the MHA-DT-14 straps' inner faces when the drum floats hard forward or hard
# aft, but no friction or end-play budget derives a grade from that slow,
# hand-cranked contact.  So they take the title-block finish, the loosest
# band (novice rule), rather than a 1.6 no function asks for (machinist
# review of the pc-r7 sheet: over-specification; Main ruling (a), 2026-09-26).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "drum_bore", MACHINED_UM, CylinderFace(BORE_DIA), display_unit=UNIT
    ),
)

# The tip diameter prints on the side view beside the length it runs
# (drawing-guidelines.md rule 11 (turned parts read like the lathe)).  The gear
# helper's blank circle must stay on Front to cut the teeth, so a hidden
# Right-plane reference sketch carries the printed, banded OutsideDia
# (drawing-simplicity-policy.md: a hidden reference sketch whose one driving
# dimension is the value); GearBlankProfile's own OutsideDia still drives the
# solid from the same global.
OUTSIDE_DIA_REFERENCE = "OutsideDiaReference"
REFERENCE_SKETCHES = (OUTSIDE_DIA_REFERENCE,)
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    OUTSIDE_DIA_REFERENCE: {"OutsideDia"},
    "ArborBoreProfile": {"ArborBoreDia"},
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": 2},
    OUTSIDE_DIA_REFERENCE: {"OutsideDia": OUTSIDE_DIA_PLACES},
    # Four places print the 5/16 bore (.3125) and its REAM_SLIDE band.
    "ArborBoreProfile": {"ArborBoreDia": 4},
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
        unit=UNIT,
    )
    return round(OUTSIDE_DIA + lower, 12), round(OUTSIDE_DIA + upper, 12)


def base_tangent_span_limits_mm() -> tuple[float, float]:
    """Accepted span MIN/MAX from its printed gear-data nominal and band."""
    upper, lower = BASE_TANGENT_SPAN_BAND
    nominal = BASE_TANGENT_SPAN_PRINTED_MM
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


def _inch(value_mm: float, places: int) -> str:
    """An mm length as ASME decimal-inch text (no leading zero)."""
    text = f"{value_mm / MM_PER_IN:.{places}f}"
    return text[1:] if text.startswith("0.") else text.replace("-0.", "-.")


# The tight tip and tooth-thickness bands exist for the mesh with the 20
# cylinder gears, so the block names that mate and why the span is tight
# (drawing-guidelines.md rule 4 (tighten only for function, and name the mate);
# machinist review r1 of 680e8eea5).
_CYLINDER_GEAR = _config.parts("dt-cylinder-gear")
MESH_MATE = f"CYLINDER GEAR {_CYLINDER_GEAR['number']}"
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", _inch(PITCH_DIA, 4)),
        # The finite form's off-centre root arc spans only microns; one REF
        # value, not a range that reads like a working band (review r1 minor).
        (
            "ROOT ENVELOPE DIAMETER (REF)",
            _inch(sum(ROOT_ENVELOPE_DIA_MM) / 2.0, 4),
        ),
        ("CUTTER PLUNGE (REF)", _inch(WHOLE_DEPTH, 4)),
        (
            "FORM CUTTER",
            f"#{CUTTER_NUMBER}, {CUTTER_TEETH_RANGE[0]}-{CUTTER_TEETH_RANGE[1]}T; "
            f"{CUTTER_REFERENCE_TEETH}T REFERENCE",
        ),
        ("TOOTH FORM", TOOTH_FORM),
        # The tip sits under the standard (N+2)/DP blank on purpose (the
        # cutter's support radius sets it); machinist reviews r5 and r6 asked
        # the block to say so.
        (
            "TIP",
            f"TOPPED, UNDER THE STANDARD {TEETH + 2}/DP BLANK; SIZE ON SIDE VIEW",
        ),
        ("PITCH TOOTH THICKNESS (REF)", _inch(PITCH_TOOTH_THICKNESS_MM, 4)),
        (
            f"BASE-TANGENT SPAN, OVER {BASE_TANGENT_SPAN_TEETH} TEETH",
            f"{_inch(BASE_TANGENT_SPAN_PRINTED_MM, BASE_TANGENT_SPAN_PLACES)} "
            f"+{_inch(BASE_TANGENT_SPAN_BAND[0], BASE_TANGENT_SPAN_PLACES)}"
            f"/{_inch(BASE_TANGENT_SPAN_BAND[1], BASE_TANGENT_SPAN_PLACES)}",
        ),
        (
            "MATES WITH",
            f"{MESH_MATE} (ALL {int(_CYLINDER_GEAR['quantity'])}), {drum.TEETH}T; "
            "SPAN SETS MESH BACKLASH",
        ),
    ]
)
# The tip band's mate rides its callout (rule 4).
OUTSIDE_DIA_CALLOUT = f"MESHES WITH\n{MESH_MATE}"

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): notes never carry a dimension.  MHA-DT-22 owns its bond-zone band
# natively (BondZoneDia).  The hand slide is this part's matched-fit
# acceptance, so it rides the reamed bore's callout, not a general note
# (Codex P2 on #832).  It names the mating part as well as its number
# (codex machinist review of f0faedc51), both from the part registry.
_ARBOR = _config.parts("dt-pinion-arbor")
# The arbor's title is bracketed so it reads as the mate's name, not this
# part's (machinist review r1 minor).
ARBOR_BORE_CALLOUT = (
    f"REAM THRU\nSLIDES BY HAND ON {_ARBOR['number']}\n({_ARBOR['title'].upper()})"
)
# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the bond to MHA-DT-22 is an assembly step (dt_pinion_arbor_spec
# ASSEMBLY_STEP owns the drum joint), not a part note.  The one note is a
# do-not-cut requirement, so it is leadered to the teeth on the side view and
# says what the tooth ends at both end faces get instead of the title-block
# edge break (machinist review r1: the free note left them ambiguous).
DRAWING_NOTES = (
    "TEETH, INCLUDING TOOTH ENDS AT BOTH FACES:\n"
    "REMOVE BURRS ONLY; DO NOT CHAMFER OR BLEND."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
END_VIEW_NOTE = "END VIEW SCALE 2:1"
