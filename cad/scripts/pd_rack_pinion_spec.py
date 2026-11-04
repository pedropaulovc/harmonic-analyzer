r"""MHA-PD-06 rack-pinion: the 150T brass reducer disc of the translational gearing.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` import.  The disc is
driven 15:150 by the knob shaft's finite #7/reference-14 PA20 48DP form (#2034:
15:150 replaced 12:120 at the same 1:10 feed) and
screwed to the brass hub's flange (MHA-PD-17, ``pd_transgear_disc_hub_spec``) by three #0-80 fillister
screws (MHA-PD-VN-55, McMaster 91794A055; the joint is
``pd_transgear_disc_hub_geometry``'s).  Its Ø.501 REAM_H7 bore pilots on the
hub's Ø.501 SHAFT_H spigot, which passes it and seats on the pinion sleeve's (MHA-PD-10)
step face; its front face, clamped by the hub's flange, stands the spigot's
length ahead of that step, and its rear face stands in air ahead of the
sleeve's 12T, radially clear of its tips (R9-68).

Part frame: gear axis = Z through the origin; the Front plane (z = 0) is the
disc's FRONT face, the one the hub flange's rear face seats on; the body runs
z = 0..FACE_WIDTH, so local +Z is machine rearward.  The screw pattern's 0°
is local +X, counter-clockwise seen from +Z (``pd_transgear_disc_hub_geometry``).

The #0-80 taps are TRANSFERRED at assembly (ruling R9-9): with the disc on
the hub's spigot and the hub seated on the sleeve's step, each tap is spotted
through its MHA-PD-17 flange hole, then drilled and tapped, and disc and
flange are match-marked.
The model places the taps on the flange's bolt circle (the one authority);
the sheet prints the tap, its mouth breaks and the transfer, never the
bolt-circle position.

Decimal inch (#290): fabricated nominals are the exact millimetre values of
their printed inch sizes; the tooth form, its blank limits, span and centre
distance keep their gear-derived values and print with enough places.
"""

from __future__ import annotations

import math

import _config
from _fit_deviations import deviations
from _fit_ream_h7 import REAM_H7
from _gear_fit_limits import gear_tip_band_mm
from _gear_quality import toothspace_runout_tir_mm
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _mcmaster_91794a055 import FILLISTER_SIZE
from paper_drive_stock_inspection import GaugeContact, toothspace_gauge_contact_mm
from pd_transgear_disc_hub_geometry import (
    BOLT_CIRCLE_DIA,
    BOLT_CIRCLE_POSITION_TOL,
    SCREW_COUNT,
    SCREW_THREAD,
    SPIGOT_DIA,
    SPIGOT_DIA_BAND,
    screw_centres,
)
from stock_form_cutter import (
    CutterTemplate,
    StockFormProfile,
    translation_for_tangent_span,
)

MM_PER_IN = 25.4

UNIT = drawing_unit("parts/pd-rack-pinion", _config.parts("pd-rack-pinion"))


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.0019``, ``3.1650``."""
    text = f"{value_mm / MM_PER_IN:.{places}f}"
    return text[1:] if text.startswith("0.") else text


def inch_floor_mm(value_mm: float, places: int) -> float:
    """``value_mm`` floored onto the ``places``-place inch grid, in mm."""
    return math.floor(value_mm / MM_PER_IN * 10**places + 1e-9) / 10**places * MM_PER_IN


def inch_ceil_mm(value_mm: float, places: int) -> float:
    """``value_mm`` raised onto the ``places``-place inch grid, in mm."""
    return math.ceil(value_mm / MM_PER_IN * 10**places - 1e-9) / 10**places * MM_PER_IN


# --- gear ----------------------------------------------------------------------
TEETH = 150
DIAMETRAL_PITCH = 48.0
PRESSURE_ANGLE_DEG = 20.0
CUTTER_REFERENCE_TEETH = 135
CUTTER_TEMPLATE = CutterTemplate(
    CUTTER_REFERENCE_TEETH, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG
)
CUTTER_NUMBER = CUTTER_TEMPLATE.cutter_number
CUTTER_TOOTH_RANGE = CUTTER_TEMPLATE.teeth_range
MODULE_MM = CUTTER_TEMPLATE.module_mm
PITCH_DIA = TEETH * MODULE_MM
# These are the declared finite master's ground-root/tip premises, not a
# vendor certification of a 2.25m ground whole depth or generated actual-N form.
ADDENDUM_FACTOR = 1.0
DEDENDUM_FACTOR = 1.25
GROUND_WHOLE_DEPTH_PREMISE_MM = 2.25 * MODULE_MM
RADIAL_SETTING = 3.969  # axis-total rigid tool translation, NOT profile shift x
_SPAN_DESIGN_SETTING_BAND = (0.010, -0.010)
SPAN_TEETH = 17  # physical indexed teeth, never the cutter's reference count
SPAN_PLACES = 4
OUTSIDE_DIA_BAND = gear_tip_band_mm("standard")  # (upper, lower), finite-supported blank
OUTSIDE_DIA_PLACES = 4
_SUPPORT_PROFILE = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, RADIAL_SETTING
)
SPAN_NOMINAL = _SUPPORT_PROFILE.tangent_span_mm(SPAN_TEETH)
_SPAN_DESIGN_PROFILES = tuple(
    StockFormProfile(
        TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, RADIAL_SETTING + setting
    )
    for setting in _SPAN_DESIGN_SETTING_BAND
)
_SPAN_GEOMETRY_ERROR = max(
    StockFormProfile(
        TEETH, CUTTER_TEMPLATE, profile.support_radius_max_mm,
        profile.radial_translation_mm,
    ).geometry_error_bound_mm
    for profile in _SPAN_DESIGN_PROFILES
)
_SPAN_CORNERS = tuple(
    (
        profile.tangent_span_mm(SPAN_TEETH) - 2.0 * _SPAN_GEOMETRY_ERROR,
        profile.tangent_span_mm(SPAN_TEETH) + 2.0 * _SPAN_GEOMETRY_ERROR,
    )
    for profile in _SPAN_DESIGN_PROFILES
)
# Outward onto the printed .0001 in grid.
SPAN_LIMITS = (
    inch_floor_mm(min(row[0] for row in _SPAN_CORNERS), SPAN_PLACES),
    inch_ceil_mm(max(row[1] for row in _SPAN_CORNERS), SPAN_PLACES),
)
SPAN_BAND = (SPAN_LIMITS[1] - SPAN_NOMINAL, SPAN_LIMITS[0] - SPAN_NOMINAL)
SPAN_DEVIATIONS = deviations(SPAN_BAND)
SPAN_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
SPAN_PREFIX = f"SPAN {SPAN_TEETH} TEETH "
_SPAN_SENSITIVITY = 2.0 * math.sin(math.pi * SPAN_TEETH / TEETH)
_SPAN_ROUNDING_ALLOWANCE = (
    10**-SPAN_PLACES * MM_PER_IN + 4.0 * _SPAN_GEOMETRY_ERROR
) / _SPAN_SENSITIVITY
_SPAN_INVERSE_BOUNDS = (
    RADIAL_SETTING + _SPAN_DESIGN_SETTING_BAND[1] - _SPAN_ROUNDING_ALLOWANCE,
    RADIAL_SETTING + _SPAN_DESIGN_SETTING_BAND[0] + _SPAN_ROUNDING_ALLOWANCE,
)
# Every consumer spends these ACTUAL printed-span-inverted limits. The
# nominal +/- .010 tool setup is only the design input, not the accepted band.
RADIAL_SETTING_LIMITS = tuple(
    translation_for_tangent_span(
        TEETH,
        CUTTER_TEMPLATE,
        limit + sign * 2.0 * _SPAN_GEOMETRY_ERROR,
        SPAN_TEETH,
        translation_bounds_mm=_SPAN_INVERSE_BOUNDS,
    )
    for limit, sign in zip(SPAN_LIMITS, (-1.0, 1.0), strict=True)
)
RADIAL_SETTING_BAND = (
    RADIAL_SETTING_LIMITS[1] - RADIAL_SETTING,
    RADIAL_SETTING_LIMITS[0] - RADIAL_SETTING,
)
_MIN_SETTING_SUPPORT = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, RADIAL_SETTING_LIMITS[0]
)
SUPPORT_OUTSIDE_DIA_MM = 2.0 * _MIN_SETTING_SUPPORT.support_radius_max_mm
# The finite translated tip VECTOR, not T + the reference tip radius, caps
# the blank. Floor onto the printed inch grid after paying numerical error
# at the lowest accepted T.
OUTSIDE_DIA = inch_floor_mm(
    SUPPORT_OUTSIDE_DIA_MM
    - 2.0 * _MIN_SETTING_SUPPORT.geometry_error_bound_mm
    - OUTSIDE_DIA_BAND[0],
    OUTSIDE_DIA_PLACES,
)
STOCK_PROFILE = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, OUTSIDE_DIA / 2.0, RADIAL_SETTING
)


def manufactured_profiles() -> tuple[StockFormProfile, ...]:
    """The printed span family crossed with the supported blank limits."""
    return tuple(
        StockFormProfile(TEETH, CUTTER_TEMPLATE, (OUTSIDE_DIA + tip) / 2.0, setting)
        for setting in RADIAL_SETTING_LIMITS
        for tip in OUTSIDE_DIA_BAND
    )


_PROFILE_CORNERS = manufactured_profiles()
ROOT_DIA = 2.0 * STOCK_PROFILE.root_radius_min_mm
ROOT_ENVELOPE_DIA_MM = (
    2.0 * STOCK_PROFILE.root_radius_min_mm,
    2.0 * STOCK_PROFILE.root_radius_max_mm,
)
ROOT_DIA_MIN = min(2.0 * profile.root_radius_min_mm for profile in _PROFILE_CORNERS)
ROOT_DEPTH_X_MIN = min(
    profile.root_point(profile.root_half_angle_rad)[0]
    for profile in _PROFILE_CORNERS
)
WHOLE_DEPTH = STOCK_PROFILE.plunge_mm
TIP_LAND_MIN = min(profile.tip_land_mm for profile in _PROFILE_CORNERS)
FINITE_GROUND_TIP_AIR_MIN = min(
    profile.support_radius_max_mm - profile.blank_radius_mm
    for profile in _PROFILE_CORNERS
)
for _profile in _PROFILE_CORNERS:
    _profile.require_tip_land(0.25 * MODULE_MM)
    _profile.tangent_span_mm(SPAN_TEETH)  # actual blank-clipped finite contacts
    if (
        _profile.support_radius_max_mm - _profile.blank_radius_mm
        <= _profile.geometry_error_bound_mm
    ):
        raise AssertionError(f"finite #{CUTTER_NUMBER} ground tip/closure reaches the accepted blank")


# One certified pin, re-seated in every physical space, measures pattern
# eccentricity on a radial indicator. A freely translated span cannot do so.
TOOTH_SPACE_GAUGE_PIN_DIA_MM = 1.016  # .040 nominal; use the actual certified diameter
TOOTH_SPACE_RUNOUT_TIR_MM = toothspace_runout_tir_mm()  # assembled cluster, inclusive of pilot float
# The printed limit never exceeds the booked one: floored to four inch places.
TOOTH_SPACE_RUNOUT_TIR_TEXT = inch_text(inch_floor_mm(TOOTH_SPACE_RUNOUT_TIR_MM, 4), 4)


def tooth_space_gauge_contacts(actual_pin_dia_mm: float) -> tuple[GaugeContact, ...]:
    """Qualify actual certified pin contact over every accepted finite corner."""
    return tuple(
        toothspace_gauge_contact_mm(profile, actual_pin_dia_mm)
        for profile in manufactured_profiles()
    )


_GAUGE_CORNERS = tooth_space_gauge_contacts(TOOTH_SPACE_GAUGE_PIN_DIA_MM)
TOOTH_SPACE_GAUGE_ROOT_AIR_MIN_MM = min(contact.root_air_mm for contact in _GAUGE_CORNERS)
TOOTH_SPACE_GAUGE_TIP_AIR_MIN_MM = min(contact.tip_air_mm for contact in _GAUGE_CORNERS)


# The physical reducer's assembled axis datum. Both gears are shop-cut
# 48DP PA20 standard forms (the knob's 15T by a #7 cutter, this disc by a
# #1 cutter), so the centre takes ordinary fine-pitch practice: nominal
# plus a positive allowance, never minus, since a close centre binds
# (MISUMI Mech Lab, "Center to Center Spacing for Shafts with Spur Gears":
# fine pitch +0.002 in / -0); the allowance is the catalogue +0.05, the
# radius of K's drawn setting circle about S
# (stock_form_quality.reducer_k_setting_diameter_mm; owner ruling
# 2026-10-27, option A: standard gears take the standard band).
# paper_drive_mesh_check.reducer_mesh over the printed bands (tooth
# thickness at the manufactured_profiles corners, both 0.05 TIR tooth-space
# runouts) bounds the usable centres to 43.737..43.851 (standard centre
# 43.656): below, the largest disc tip reaches past the knob pinion's
# interference point at the tight extreme; above, the contact ratio at the
# minimum tips falls below 1.2. 43.794 is that window's midpoint (owner
# ruling #2034: 15:150 opens it from the 12:120's 0.008 to 0.114), and the
# whole set band 43.794..43.844 meets the full design floors (owner ruling
# on #2034 x #2011: 43.794 +0.050/-0, aim mid-band): CR 1.305 / 1.214 and
# an interference margin of 0.166 at the nominal end, CR 1.214 / 1.123 at
# the far end.
MESH_PINION_TEETH = 15
MESH_ANGLE_DEG = -168.0
CENTRE_DISTANCE = 43.794
# The setting the arm and plate sheets print: the knob bore is held this
# band from the pin bore when the pair is match-drilled, and must still be
# there with the plate screwed down.
CENTRE_DISTANCE_WINDOW = (CENTRE_DISTANCE, 43.844)
# (upper, lower) deviations from CENTRE_DISTANCE, as every band here.
CENTRE_DISTANCE_SET_BAND = (round(CENTRE_DISTANCE_WINDOW[1] - CENTRE_DISTANCE, 6), 0.0)
CENTRE_DISTANCE_SET_TEXT = (
    f"{CENTRE_DISTANCE:.3f} +{CENTRE_DISTANCE_SET_BAND[0]:.3f}/-0"
)
STANDARD_CENTRE_DISTANCE = (TEETH + MESH_PINION_TEETH) * MODULE_MM / 2.0
CENTRE_EXTENSION = CENTRE_DISTANCE - STANDARD_CENTRE_DISTANCE

# --- disc body -----------------------------------------------------------------
FACE_WIDTH = 2.9972  # .118
# Printed .XXX, functional (R9-5): the hub may never stand proud of the
# sleeve nose, and that stack reads the disc thickness.
FACE_WIDTH_PLACES = 3
BORE_DIA = SPIGOT_DIA  # .501
# Pilots on the hub's spigot (MHA-PD-17, pd_transgear_disc_hub_geometry): the
# bore reamed .501 REAM_H7 (an owned .5010 reamer) over the spigot's SHAFT_H,
# a locational clearance that assembles by hand, so the disc never binds and
# sits at most .0007 off the hub's axis while its taps are spotted.
BORE_BAND = REAM_H7  # (upper, lower) deviations: +.0005/0
BORE_DEVIATIONS = deviations(BORE_BAND)
BORE_PLACES = 4

_BAND = {places: printed_band_mm(places, unit=UNIT) for places in (1, 2, 3)}
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
# (least, greatest) diametral clearance: .0000 .. .0013.
SPIGOT_DIAMETRAL_CLEARANCE = (
    round(BORE_DIA_MIN - SPIGOT_DIA_MAX, 6),
    round(BORE_DIA_MAX - SPIGOT_DIA_MIN, 6),
)
if SPIGOT_DIAMETRAL_CLEARANCE[0] < 0.0:
    raise AssertionError(
        f"MHA-PD-06 bore binds on the MHA-PD-17 spigot: {SPIGOT_DIAMETRAL_CLEARANCE}"
    )
DISC_OFFSET_MAX = SPIGOT_DIAMETRAL_CLEARANCE[1] / 2.0
# The rear face stands in air (the hub's flange locates the front face, datum
# B), so the bore's rear edge takes the title block's break.  The front edge
# is chamfered past the spigot-to-flange corner's R.004 so the front face
# seats on the flange (pd_transgear_disc_hub_spec checks the pair): a plain
# .XXX chamfer on the title block's row, flagged at the bore with its reason.
BORE_FRONT_CHAMFER = 0.254  # .010, 45 deg
BORE_FRONT_CHAMFER_LIMITS = (
    BORE_FRONT_CHAMFER - _BAND[3],
    BORE_FRONT_CHAMFER + _BAND[3],
)  # .005-.015

# --- screw (MHA-PD-VN-55) -------------------------------------------------------------
SCREW_MAJOR_DIA, SCREW_LENGTH, _HEAD_H, _HEAD_DIA, SCREW_PITCH = FILLISTER_SIZE

# --- #0-80 taps --------------------------------------------------------------------
TAP_SPEC = HoleSpec("tapped", SCREW_THREAD)
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
TAP_MAJOR = THREAD_MAJOR_MM[SCREW_THREAD]
if abs(TAP_MAJOR - SCREW_MAJOR_DIA) > 1e-9:
    raise AssertionError(
        "the disc tap and the MHA-PD-VN-55 screw disagree on the #0-80 major"
    )
# The tapped major's allowance over basic (contract §8, "tap major 0.025" radial).
TAP_MAJOR_ALLOWANCE = 0.05
TAP_COUNT = SCREW_COUNT
TAP_CENTRES = screw_centres()

# No countersink (R9-63): a 90° countersink opening past the .060 major
# costs at least (.060 - .047) / 2 = .0065 of full thread at its mouth on
# the .118 disc, so both mouths carry a burr break only (not modelled).  Full
# thread starts where the break's 45° leg meets the tap drill.
MOUTH_BREAK_MAX = 0.1016  # .004

# --- the tap's thread losses (contract §7) -------------------------------------
# The MHA-PD-VN-55 screws are cut to fit at assembly (R9-47): their tips stop
# inside the rear face, so the joint's engagement, the cut window and the
# stock's reach are judged in pd_vn_transgear_disc_screw_spec from these losses.
ENGAGEMENT_FLOOR_D = 1.5
MOUTH_THREAD_LOSS = MOUTH_BREAK_MAX

# --- tap to bore wall (contract §8) ---------------------------------------------
# The disc prints no tap position, so its worst case is the transfer chain:
# the flange hole's bolt-circle band (MHA-PD-17), the spot's centring in that
# hole (a #51 spotting tool in the #51 drilled hole, +.004/0), and the disc's
# offset on the spigot while it is spotted.
SPOT_CENTRING_TOL = drilled_oversize_mm(unit=UNIT) / 2.0
TAP_POSITION_ERROR = BOLT_CIRCLE_POSITION_TOL + SPOT_CENTRING_TOL + DISC_OFFSET_MAX
WALL_FLOOR = WALL_TARGET_MM
TAP_TO_BORE_WALL = BOLT_CIRCLE_DIA / 2.0 - TAP_MAJOR / 2.0 - BORE_DIA / 2.0
TAP_TO_BORE_WALL_WORST = (
    BOLT_CIRCLE_DIA / 2.0
    - TAP_POSITION_ERROR
    - (TAP_MAJOR + TAP_MAJOR_ALLOWANCE) / 2.0
    - BORE_DIA_MAX / 2.0
)
if TAP_TO_BORE_WALL_WORST < WALL_FLOOR - 1e-9:
    raise AssertionError(
        f"MHA-PD-06 tap to bore wall {TAP_TO_BORE_WALL_WORST:.3f} worst < {WALL_FLOOR}"
    )

# --- sheet -------------------------------------------------------------------------
HUB_NUMBER = "MHA-PD-17"
HUB_NAME = "HUB"
SCREW_NUMBER = "MHA-PD-VN-55"
# Lines appended under the native "#0-80 UNF THRU" hole callout (the title
# block's thread row carries the 2B class).  The .004 mouth breaks are
# tighter than the title block's .010 because the MHA-PD-VN-55 engagement
# (pd_vn_transgear_disc_screw_spec) spends them; the callout names that
# screw, so no loose note repeats it.
TAP_CALLOUT_LINES = (
    f"BREAK EDGE {inch_text(MOUTH_BREAK_MAX, 3)} MAX BOTH SIDES,",
    f"KEEPS {SCREW_NUMBER} ENGAGEMENT",
    f"SPOT THRU {HUB_NUMBER} FLANGE",
    "HOLES AT ASSY, THEN DRILL",
    "AND TAP; MATCH-MARK BOTH",
)
TAP_CALLOUT_QUALIFIER = "\n".join(TAP_CALLOUT_LINES)
# The .XXX thickness is the screw engagement's: its least is the tapped
# length (pd_vn_transgear_disc_screw_spec), and .XX would cut that below
# 1.5D.
FACE_WIDTH_CALLOUT = f"SETS {SCREW_NUMBER}\nENGAGEMENT"
# Reamed: the bore pilots on the hub's spigot, clamped to the flange, so it
# is a static seat and carries no finish symbol (rule 6).  The bore's native
# limits print with the dimension; the fit note names the mate, and the
# front-edge chamfer the spigot root it clears.
BORE_CALLOUT = "THRU - REAM"
BORE_FIT_CALLOUT = "\n".join(
    (
        "BORE LIMITS GOVERN",
        f"MATE {HUB_NAME} {HUB_NUMBER} SPIGOT",
        f"(\N{DIAMETER SIGN}{inch_text(SPIGOT_DIA, 4)} "
        f"+{inch_text(SPIGOT_DIA_BAND[0], 4)}/-{inch_text(-SPIGOT_DIA_BAND[1], 4)})",
        f"(DIA CLR {inch_text(SPIGOT_DIAMETRAL_CLEARANCE[0], 4)}-"
        f"{inch_text(SPIGOT_DIAMETRAL_CLEARANCE[1], 4)})",
        f"CHAMFER {inch_text(BORE_FRONT_CHAMFER, 3)} X 45\u00b0 AT B,",
        f"CLEARS {HUB_NUMBER} SPIGOT ROOT",
    )
)

# Marked native model dimensions: the disc thickness, finite blank, bore
# and controlling actual-flank span.  No root diameter prints: the gear data
# gives the whole depth (REF), and a third diameter line through the bore
# crowded the bore's leader (machinist review).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "GearBlankProfile": {"OutsideDia"},
    "BoreProfile": {"BoreDia"},
    "SpanProfile": {"ToothSpan"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": FACE_WIDTH_PLACES},
    "GearBlankProfile": {"OutsideDia": OUTSIDE_DIA_PLACES},
    "BoreProfile": {"BoreDia": BORE_PLACES},
    "SpanProfile": {"ToothSpan": SPAN_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if {f: set(n) for f, n in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked MHA-PD-06 dimension needs its printed places")


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


KNOB_NUMBER = "MHA-PD-08"
# What a machinist needs to cut and check the teeth; design parameters stay
# in this module (Main ruling 2026-10-10).
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", inch_text(PITCH_DIA, 4)),
        ("WHOLE DEPTH (REF)", inch_text(WHOLE_DEPTH, 4)),
        (
            "CUTTER",
            # #1 is open-ended (135T to rack): print the catalogue's range.
            f"#{CUTTER_NUMBER}, {CUTTER_TOOTH_RANGE[0]}T-RACK"
            if CUTTER_TOOTH_RANGE[1] is None
            else f"#{CUTTER_NUMBER}, {CUTTER_TOOTH_RANGE[0]}-{CUTTER_TOOTH_RANGE[1]}T",
        ),
        (
            f"SPAN OVER {SPAN_TEETH} TEETH",
            f"{inch_text(min(SPAN_LIMITS), SPAN_PLACES)}-{inch_text(max(SPAN_LIMITS), SPAN_PLACES)}",
        ),
        ("MATES WITH", f"KNOB SHAFT {KNOB_NUMBER}, {MESH_PINION_TEETH}T"),
    ]
)

# The tip and span bands are the mesh's: each names the mating pinion at its
# dimension (rule 4).
MESH_CALLOUT = f"MESHES {KNOB_NUMBER} {MESH_PINION_TEETH}T"
# The blank's, stacked to stay narrow beside the edge view.
MESH_CALLOUT_STACKED = f"MESHES\n{KNOB_NUMBER} {MESH_PINION_TEETH}T"

# Spacing is held by the dividing head and is not inspected; one pin in
# every space on a radial indicator catches eccentricity and gross slips.
# The disc's own control is to its pilot datum A, accepted at the tooth
# cutting setup (the drive-train gears' convention). The mesh stack books
# the shared tooth-space TIR about the assembled running axis (the print
# floors it to the .0001 in grid). MHA-PD-00's disc-transfer step
# reaches it by tapping the disc central on the feed pinion's bore, and
# accepts it there. That tap can only move the disc within the spigot
# clearance, and the clearance may be zero. So a disc whose teeth run out
# more than the assembled budget about its own pilot cannot be centred to
# it. The part therefore takes the same limit: the loosest that cannot
# send a disc to assembly that the transfer step must reject.
TOOTH_SPACE_CALLOUT_PROPERTY = "Tooth Space Inspection"
TOOTH_SPACE_CALLOUT = "\n".join(
    (
        f"TOOTH SPACE RUNOUT {TOOTH_SPACE_RUNOUT_TIR_TEXT} TIR TO A, "
        "ACCEPT AT CUTTING SETUP",
        f"\u00d8{inch_text(TOOTH_SPACE_GAUGE_PIN_DIA_MM, 3)} PIN, ALL {TEETH} SPACES",
    )
)


# Manufacturing GD&T limits consumed by the part's drawing projection.  The
# hub's flange clamps the front face (datum B), so the rear face, toward the
# platen, is held parallel to it (the paper-drive assembly's platen air reads
# it). Tooth-space runout is to the pilot datum A (TOOTH_SPACE_CALLOUT).
# The frame prints GEOMETRIC_TOLERANCES_IN; readers take the derived mm.
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "disc rear face parallelism to front": ".002",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * MM_PER_IN for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
FRONT_FACE_DATUM = "B"
