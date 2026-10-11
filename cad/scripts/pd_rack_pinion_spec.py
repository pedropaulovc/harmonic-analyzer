r"""MHA-PD-006 rack-pinion: the 120T brass reducer disc of the translational gearing.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` import.  The disc is
driven 12:120 by the knob shaft's finite #8/reference-12 PA20 48DP form and
screwed to the brass hub's flange (MHA-PD-017, ``pd_transgear_disc_hub_spec``) by three #0-80 fillister
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

import math

from _fit_deviations import deviations
from _gear_quality import (
    pinion_pitch_index_deviation_mm,
    pitch_index_measurement_uncertainty_mm,
    require_pitch_index_measurements_mm,
    toothspace_runout_tir_mm,
)
from _gtol_cylinder import CylinderFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from _mcmaster_91794a055 import FILLISTER_SIZE
from paper_drive_stock_inspection import GaugeContact, toothspace_gauge_contact_mm
from pd_transgear_disc_hub_geometry import (
    BOLT_CIRCLE_DIA,
    BOLT_CIRCLE_POSITION_TOL,
    SCREW_COUNT,
    SCREW_HOLE_DIA,
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

# --- gear ----------------------------------------------------------------------
TEETH = 120
DIAMETRAL_PITCH = 48.0
PRESSURE_ANGLE_DEG = 20.0
CUTTER_REFERENCE_TEETH = 55
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
RADIAL_SETTING = 17.210  # axis-total rigid tool translation, NOT profile shift x
_SPAN_DESIGN_SETTING_BAND = (0.010, -0.010)
SPAN_TEETH = 13  # physical indexed teeth, never the cutter's reference count
SPAN_PLACES = 4
OUTSIDE_DIA_BAND = (0.0, -0.10)  # (upper, lower), finite-supported blank
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
SPAN_LIMITS = (
    math.floor(min(row[0] for row in _SPAN_CORNERS) * 10**SPAN_PLACES)
    / 10**SPAN_PLACES,
    math.ceil(max(row[1] for row in _SPAN_CORNERS) * 10**SPAN_PLACES)
    / 10**SPAN_PLACES,
)
SPAN_BAND = (SPAN_LIMITS[1] - SPAN_NOMINAL, SPAN_LIMITS[0] - SPAN_NOMINAL)
SPAN_DEVIATIONS = deviations(SPAN_BAND)
SPAN_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
SPAN_PREFIX = f"SPAN {SPAN_TEETH} TEETH "
_SPAN_SENSITIVITY = 2.0 * math.sin(math.pi * SPAN_TEETH / TEETH)
_SPAN_ROUNDING_ALLOWANCE = (
    10**-SPAN_PLACES + 4.0 * _SPAN_GEOMETRY_ERROR
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
# the blank. Floor after paying numerical error at the lowest accepted T.
OUTSIDE_DIA = math.floor(
    (
        SUPPORT_OUTSIDE_DIA_MM
        - 2.0 * _MIN_SETTING_SUPPORT.geometry_error_bound_mm
        - OUTSIDE_DIA_BAND[0]
    )
    * 100.0
) / 100.0
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
TOOTH_THICKNESS = STOCK_PROFILE.pitch_tooth_thickness_mm
ROOT_DIA = 2.0 * STOCK_PROFILE.root_radius_min_mm
ROOT_ENVELOPE_DIA_MM = (
    2.0 * STOCK_PROFILE.root_radius_min_mm,
    2.0 * STOCK_PROFILE.root_radius_max_mm,
)
ROOT_DIA_PLACES = 3
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
        raise AssertionError("finite #2 ground tip/closure reaches the accepted blank")


# One certified pin, re-seated in every physical space, measures pattern
# eccentricity on a radial indicator. A freely translated span cannot do so.
TOOTH_SPACE_GAUGE_PIN_DIA_MM = 1.0  # nominal; use the actual certified diameter
TOOTH_SPACE_RUNOUT_TIR_MM = toothspace_runout_tir_mm()  # assembled cluster, inclusive of pilot float
# Relative index is separate from span thickness and radial TIR. Convert the
# actual-pin/contact-corrected angular observations at this pitch-reference
# radius, not the measuring pin's centre radius.
PITCH_INDEX_REFERENCE_RADIUS_MM = PITCH_DIA / 2.0
PITCH_INDEX_DEVIATION_MM = pinion_pitch_index_deviation_mm()
PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM = pitch_index_measurement_uncertainty_mm()
PITCH_INDEX_STATIONS = tuple(range(TEETH + 1))  # station TEETH is the full wrap


def tooth_space_gauge_contacts(actual_pin_dia_mm: float) -> tuple[GaugeContact, ...]:
    """Qualify actual certified pin contact over every accepted finite corner."""
    return tuple(
        toothspace_gauge_contact_mm(profile, actual_pin_dia_mm)
        for profile in manufactured_profiles()
    )


def require_pitch_index_errors_mm(measured_index_errors_mm: dict[int, float]) -> float:
    """Receive every calibrated assembled running-bore index, including wrap.

    At station i the error is R_ref * (observed_angle_i - datum_angle -
    2*pi*i/TEETH). Angles are unwrapped and actual-pin/contact corrected about
    the assembled feed running bore A against one physical index datum; a
    floating best-fit tooth axis must not remove eccentricity. Relative
    index does not replace radial TIR, span thickness or absolute drive clock.
    The returned range pays both stations' calibration uncertainty.
    """
    return require_pitch_index_measurements_mm(
        measured_index_errors_mm=measured_index_errors_mm,
        required_stations=PITCH_INDEX_STATIONS,
        relative_deviation_limit_mm=PITCH_INDEX_DEVIATION_MM,
        absolute_measurement_uncertainty_mm=PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM,
    )


_GAUGE_CORNERS = tooth_space_gauge_contacts(TOOTH_SPACE_GAUGE_PIN_DIA_MM)
TOOTH_SPACE_GAUGE_ROOT_AIR_MIN_MM = min(contact.root_air_mm for contact in _GAUGE_CORNERS)
TOOTH_SPACE_GAUGE_TIP_AIR_MIN_MM = min(contact.tip_air_mm for contact in _GAUGE_CORNERS)


# The physical reducer's assembled axis datum, set from the closed-form
# checks in paper_drive_mesh_check.reducer_mesh over the printed bands:
# knob-pinion and disc tooth thickness at the pitch circle (the
# manufactured_profiles corners) and both tooth-space runouts of 0.05 TIR,
# which together move the working centre by (0.05 + 0.05)/2 = 0.05.
# Bisecting those two gates gives the usable window 35.097..35.105 mm:
#   - below 35.097 the largest disc tip reaches past the knob pinion's
#     interference point (its base-circle tangency) at the tight extreme
#     (35.097 - 0.05);
#   - above 35.105 the contact ratio at the minimum tips (7.38 and 64.44 OD)
#     falls below 1.2.
# 35.101 is the window's midpoint (Main ruling 2026-10-10: the design takes
# an ordinary 0.05 TIR; 35.080 admitted only 0.005). It gives CR 1.207,
# backlash 0.069 at the tight extreme and 0.170 at the loose one, root
# clearance 0.240 (AGMA fine-pitch floor 0.157) and an interference margin
# of 0.012 mm.
MESH_PINION_TEETH = 12
MESH_ANGLE_DEG = -168.0
CENTRE_DISTANCE = 35.101
STANDARD_CENTRE_DISTANCE = (TEETH + MESH_PINION_TEETH) * MODULE_MM / 2.0
CENTRE_EXTENSION = CENTRE_DISTANCE - STANDARD_CENTRE_DISTANCE

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
SCREW_MAJOR_DIA, SCREW_LENGTH, _HEAD_H, _HEAD_DIA, SCREW_PITCH = FILLISTER_SIZE

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

# Marked native model dimensions: the disc thickness, finite blank, bore
# and controlling actual-flank span. Root-envelope data are axis references;
# neither OD touch-off nor free span variation certifies tooth-space runout.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "GearBlankProfile": {"OutsideDia"},
    "BoreProfile": {"BoreDia"},
    "SpanProfile": {"ToothSpan"},
    "RootInspectionProfile": {"RootEnvelope"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": FACE_WIDTH_PLACES},
    "GearBlankProfile": {"OutsideDia": 2},
    "BoreProfile": {"BoreDia": BORE_PLACES},
    "SpanProfile": {"ToothSpan": SPAN_PLACES},
    "RootInspectionProfile": {"RootEnvelope": ROOT_DIA_PLACES},
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


KNOB_NUMBER = "MHA-PD-008"
# What a machinist needs to cut and check the teeth; design parameters stay
# in this module (Main ruling 2026-10-10).
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.2f}"),
        ("CIRCULAR THICKNESS AT PD (mm, REF)", f"{TOOTH_THICKNESS:.3f}"),
        ("WHOLE DEPTH (mm, REF)", f"{WHOLE_DEPTH:.3f}"),
        ("CUTTER", f"#{CUTTER_NUMBER}, {CUTTER_TOOTH_RANGE[0]}-{CUTTER_TOOTH_RANGE[1]}T"),
        (
            f"SPAN OVER {SPAN_TEETH} TEETH",
            f"{min(SPAN_LIMITS):.{SPAN_PLACES}f}-{max(SPAN_LIMITS):.{SPAN_PLACES}f}",
        ),
        ("MATES WITH", f"KNOB SHAFT {KNOB_NUMBER}, {MESH_PINION_TEETH}T"),
    ]
)

# The teeth are stated by the gear data block; the build appends the disc
# screw's engagement line (vn_transgear_disc_screw_spec imports this module).
# A shop note states the requirement, not the measuring method or the design
# history (Main ruling 2026-10-10).
DRAWING_NOTES = BORE_FRONT_CHAMFER_NOTE

TOOTH_SPACE_CALLOUT_PROPERTY = "Tooth Space Inspection"
TOOTH_SPACE_CALLOUT = "\n".join(
    (
        f"TOOTH SPACE RUNOUT {TOOTH_SPACE_RUNOUT_TIR_MM:.2f} TIR TO FEED BORE A (ASSY)",
        f"\u00d8{TOOTH_SPACE_GAUGE_PIN_DIA_MM:.3f} PIN, ALL {TEETH} SPACES",
        f"INDEX RANGE {PITCH_INDEX_DEVIATION_MM:.2f} MAX",
    )
)


# Manufacturing GD&T limits consumed by the part's drawing projection.  The
# hub's flange clamps the front face (datum B), so the rear face, toward the
# platen, is held parallel to it (the paper-drive assembly's platen air reads
# it). Tooth-space runout is controlled on the assembled cluster's actual
# running bore, NOT on this disc's separate 13.1 pilot datum A.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "disc rear face parallelism to front": "0.05",
}
FRONT_FACE_DATUM = "B"
