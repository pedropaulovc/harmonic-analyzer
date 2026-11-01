r"""Pure-data dimensional contract shared by the crank pinion and its drawing.

The 16T straight-spur pinion on the crankshaft that meshes the 64T crank-drive
gear (4:1 crank-to-cone reduction), with the plain hub boss on its outboard
face that the ch. 12 p. 19 photos show (page002_img02 / img06): a cylinder at
the tooth root, a little over half a face long, edge rounded, and the small
head of a radial retention pin on its side (the photo's crankshaft end sits
inside the boss; owner ruling D1 leaves it proud of the north face). The pin
is what keeps the "removable" pinion on the shaft.

Recreated under ``cad/docs/drawing-guidelines.md``. The sizes a
machinist turns, bores and drills -- outside diameter, face width, bore, boss
diameter, overall length, pin station -- are NATIVE model dimensions carrying
their own decimal places and bands (drawing-guidelines.md rule 2 (the title block is the general specification), drawing-guidelines.md rule 3 (decimal places carry the tolerance) and drawing-guidelines.md rule 5 (avoid excessive GD&T)); the tooth system that a
cut-gear print cannot express as dimensions stays in the gear-data block drawing-guidelines.md rule 7 (notes: few, flagged, never a method)
allows, with cutter inputs and actual root/depth data marked REF. Exact stock
base-tangent span carries the part's functional tooth-control limits; circular
pitch thickness is REF. Nothing here restates the title block.

PURE DATA, no SolidWorks/COM imports: ``build_dt_crank_pinion`` marks and
tolerances exactly ``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model,
``draw_dt_crank_pinion`` keeps exactly the same names, and the offline test
(``test_dt_crank_pinion_drawing.py``) fails the moment one side drifts.
"""

from __future__ import annotations

import math

import _config
import cone_line
import _cone_axis_constants
import dt_crank_drive_gear_spec
import dt_crank_hub_geometry
from _fit_deviations import deviations
from _hole_spec import FRACTIONAL_DRILL_MM, HoleSpec
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm, printed_deviations
from dt_crank_drive_gear_spec import floor_inch_mm, inch_text
from _surface_finish import SurfaceFinishControl
from stock_form_cutter import (
    StockFormProfile,
    template_for_teeth,
    translation_for_pitch_tooth_thickness,
    translation_for_tangent_span,
)


MM_PER_IN = 25.4
# #290: the registry row's drawing_unit (in) is this sheet's unit; the bands,
# places and callout text below are authored for it.
UNIT = drawing_unit("parts/dt-crank-pinion", _config.parts("dt-crank-pinion"))


def prints_exactly(value_mm: float, places: int, unit: str = UNIT) -> bool:
    """Whether ``value_mm`` sits on the ``places``-place grid of ``unit``."""
    shown = value_mm / (MM_PER_IN if unit == "in" else 1.0)
    return abs(shown - round(shown, places)) <= 1e-9


TEETH = 16
# The straight pinion uses the pair's standard normal-pitch system with a
# 14--16T form cutter, distinct from the helix's virtual-tooth cutter.
DIAMETRAL_PITCH = dt_crank_drive_gear_spec.CUTTER_DIAMETRAL_PITCH
PRESSURE_ANGLE_DEG = dt_crank_drive_gear_spec.CUTTER_PRESSURE_ANGLE_DEG
DEDENDUM_FACTOR = dt_crank_drive_gear_spec.DEDENDUM_FACTOR
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
# Preserve zero upper thickness deviation: the tight stack books the
# thickest accepted mate tooth and all axis/fit allowances. The lower side
# retains the established tooth-control capability.
TOOTH_THICKNESS_UPPER_DEVIATION = 0.000
TOOTH_THICKNESS_LOWER_DEVIATION = -0.020

# A straight spur's normal and transverse sections coincide; its own stock
# form cutter uses the physical tooth count, unlike the helical mate's.
CUTTER_TEMPLATE = template_for_teeth(TEETH, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG)
CUTTER_NUMBER = CUTTER_TEMPLATE.cutter_number
CUTTER_TEETH_RANGE = CUTTER_TEMPLATE.teeth_range

# The blank tip circles retain the ruled turning band, +/-.004 in. The
# fixed-centre mesh's nonbinding stack, rather than an eccentric fit-up, owns
# tip/root air.
OUTSIDE_DIA_TOLERANCE_MM = 0.1016
OUTSIDE_DIA_PLACES = 3
# Same retained critical cutting setup as the mate, indicated to this bore;
# no datum frame or general part-runout tolerance is implied.
TOOTH_RUNOUT_TIR_MM = _config.fit("crank_mesh", "tooth_cutting_runout_tir_mm")
MESH_C2C_SLACK_MM = _config.fit("crank_mesh")["c2c_slack_mm"]
TIP_CLEARANCE_MM = (DEDENDUM_FACTOR - 1.0) * MODULE_MM

# Standard root placement uses the finite 14T tool, not an ideal 16T involute.
# The source allocations become exact stock tangent-span acceptance limits.
STOCK_TOOL_TRANSLATION_MM = PITCH_DIA / 2.0 - CUTTER_TEMPLATE.pitch_radius_mm
_PITCH_PROBE = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, STOCK_TOOL_TRANSLATION_MM
)
TRANSVERSE_CIRCULAR_TOOTH_THICKNESS = _PITCH_PROBE.pitch_tooth_thickness_mm
BASE_TANGENT_SPAN_TEETH = math.floor(TEETH * PRESSURE_ANGLE_DEG / 180.0 + 0.5)
BASE_TANGENT_SPAN_PLACES = 4
_SPAN_SCALE = 10**BASE_TANGENT_SPAN_PLACES
_RAW_TRANSLATIONS = tuple(
    translation_for_pitch_tooth_thickness(
        TEETH, CUTTER_TEMPLATE, TRANSVERSE_CIRCULAR_TOOTH_THICKNESS + deviation
    )
    for deviation in (
        TOOTH_THICKNESS_LOWER_DEVIATION, TOOTH_THICKNESS_UPPER_DEVIATION
    )
)
_RAW_SPANS = tuple(
    StockFormProfile(TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, value)
    .tangent_span_mm(BASE_TANGENT_SPAN_TEETH, normal_plane=True)
    for value in _RAW_TRANSLATIONS
)
BASE_TANGENT_SPAN_MM = _PITCH_PROBE.tangent_span_mm(
    BASE_TANGENT_SPAN_TEETH, normal_plane=True
)
# Both ends rounded UP onto the inch grid the sheet prints them at: the
# lower end inward (an accepted part keeps the source's thinnest tooth), the
# upper end outward so the modelled nominal -- the source's thickest tooth,
# zero upper deviation -- stays inside the printed acceptance.
BASE_TANGENT_SPAN_LIMITS_MM = tuple(
    math.ceil(round(span / MM_PER_IN * _SPAN_SCALE, 6)) / _SPAN_SCALE * MM_PER_IN
    for span in (min(_RAW_SPANS), max(_RAW_SPANS))
)
_INVERSE_BRACKET = (
    min(_RAW_TRANSLATIONS) - MODULE_MM / 100.0,
    max(_RAW_TRANSLATIONS) + MODULE_MM / 100.0,
)
STOCK_TOOL_TRANSLATION_LIMITS_MM = tuple(
    translation_for_tangent_span(
        TEETH, CUTTER_TEMPLATE, span, BASE_TANGENT_SPAN_TEETH,
        translation_bounds_mm=_INVERSE_BRACKET,
    )
    for span in BASE_TANGENT_SPAN_LIMITS_MM
)
_CORNER_PROBES = tuple(
    StockFormProfile(TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, value)
    for value in STOCK_TOOL_TRANSLATION_LIMITS_MM
)
# Floored to the .001 in grid it prints at, so the printed size is the model.
OUTSIDE_DIA = floor_inch_mm(
    2.0 * min(profile.support_radius_max_mm for profile in _CORNER_PROBES)
    - OUTSIDE_DIA_TOLERANCE_MM,
    OUTSIDE_DIA_PLACES,
)
STOCK_PROFILE = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, OUTSIDE_DIA / 2.0, STOCK_TOOL_TRANSLATION_MM
)
ROOT_DIA_MIN = 2.0 * STOCK_PROFILE.root_radius_min_mm
ROOT_DIA_MAX = 2.0 * STOCK_PROFILE.root_radius_max_mm
ROOT_DIA = ROOT_DIA_MIN
WHOLE_DEPTH = STOCK_PROFILE.blank_radius_mm - STOCK_PROFILE.root_radius_min_mm
TOOL_PLUNGE_MM = STOCK_PROFILE.plunge_mm


def stock_profile(
    *, outside_dia_mm: float | None = None, tooth_thickness_mm: float | None = None
) -> StockFormProfile:
    """Actual finite 14T tool form; no ideal-N thinning or flank extrapolation."""
    translation = (
        STOCK_TOOL_TRANSLATION_MM if tooth_thickness_mm is None
        else translation_for_pitch_tooth_thickness(TEETH, CUTTER_TEMPLATE, tooth_thickness_mm)
    )
    return StockFormProfile(
        TEETH, CUTTER_TEMPLATE,
        (OUTSIDE_DIA if outside_dia_mm is None else outside_dia_mm) / 2.0, translation,
    )


STOCK_PROFILE_CORNERS = tuple(
    (
        f"span {span_side}, outside diameter {od_side}",
        StockFormProfile(
            TEETH, CUTTER_TEMPLATE, (OUTSIDE_DIA + od_deviation) / 2.0, translation
        ),
    )
    for span_side, translation in zip(("lower", "upper"), STOCK_TOOL_TRANSLATION_LIMITS_MM)
    for od_side, od_deviation in (
        ("lower", -OUTSIDE_DIA_TOLERANCE_MM), ("upper", OUTSIDE_DIA_TOLERANCE_MM)
    )
)

# The crankshaft's .3125 in step and matching bore (#290, inch fit row K11:
# the owned .3135 reamer cuts the bore). The seat keeps the through shaft's
# size band and fit, while the live boss wall guard checks the standard
# full-depth root over that bore.
SEAT_DIA = 7.9375  # .3125

# The bore over the crankshaft's seat is the part's one critical fit, and the
# only reason anything here prints a third decimal: a slip fit exists only if
# the size limits on BOTH mating features are narrower than the clearance band
# it claims (tolerance-policy.md step 6b). The feature callout names the mate
# and publishes the required diametral-clearance range; the dimensional band is
# DERIVED -- never a per-part number -- from that named fit class and the
# seat's own published limits: bore_min = seat_max + clearance_min,
# bore_max = seat_min + clearance_max. Move either input and this moves with it.
BORE_DIA = SEAT_DIA
BORE_DIAMETRAL_CLEARANCE = tuple(
    _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
)
_CLEARANCE_MIN, _CLEARANCE_MAX = BORE_DIAMETRAL_CLEARANCE
_SHAFT_UPPER, _SHAFT_LOWER = dt_crank_hub_geometry.SHAFT_DIA_BAND
BORE_DIA_BAND = (  # (upper, lower) deviations
    round(_SHAFT_LOWER + _CLEARANCE_MAX, 5),
    round(_SHAFT_UPPER + _CLEARANCE_MIN, 5),
)

FACE_WIDTH = 11.684  # .46: teeth grown north past the 64T row; south face stays seated
# The retained south-face datum and full tooth length still locate the boss
# step. FaceWidth remains the native GearBlank extrusion with its existing
# +.000/-.010 functional band, not the general .XX grade. Actual stock-form
# acceptance must prove at least the source-owned row engagement fraction
# at every manufactured/pose case. The former ideal-profile slice calculation
# is not a certificate for this cutter-native pinion. The long limit also
# bounds the turned band's physical T120 clearance independently of contact.
FACE_WIDTH_BAND = (0.0, -0.254)  # (upper, lower) deviations: +.000/-.010
FACE_WIDTH_LIMITS = deviations(FACE_WIDTH_BAND)  # (lower, upper)
# Full-OD shoulder: OutsideDia over SHOULDER_LENGTH from the south face,
# with its +.000/-.010 band. The assembly retains the 0.25-mm T120
# air floor, all axis/fit offsets, the fit-up feeler and the row contact gate.
# The toothed south face is set directly off the restored MHA-DT-05 north
# boss face with the assembly step-4 feeler. There is no spot-face retreat
# or eccentric sleeve in this stack.
SEAT_FEELER_MM = 0.25
SEAT_GAP_MAX_MM = 1.0
PINION_BOSS_NORTH_GAP_RANGE = (SEAT_FEELER_MM, SEAT_GAP_MAX_MM)


SHOULDER_LENGTH = 8.382  # .33
SHOULDER_LENGTH_BAND = (0.0, -0.254)  # +.000/-.010
SHOULDER_LENGTH_LIMITS = deviations(SHOULDER_LENGTH_BAND)
# Retain a real north band below the actual finite-supported full blank.
# guards check its upper size against T120 and its lower size over the row.
TURNED_DIA = 18.542  # .730
TURNED_DIA_TOLERANCE_MM = 0.1016  # +/-.004
TURNED_LENGTH = FACE_WIDTH - SHOULDER_LENGTH
# T120 envelope facts are checked against the assembly's exact printed-corner
# calculation. Finite clearance is rounded down to 0.01; positive infinity
# means that no T120 section reaches the full-tip shoulder envelope.
# Both sheets describe that absence rather than printing an infinite size.
T120_SHOULDER_AIR_WORST = math.inf
# 1.8608 exact with the cone swing set 0.20 above standard (edge slack moves
# X_PITCH; user ruling 2026-10-10), the inch running fits and the inch-printed
# turned band (#290), floored to 1.86; the ordinary floor is 0.25.
T120_TURNED_BAND_RADIAL_WORST = 1.86
# The independent fit-up feeler check remains: MHA-DT-10 and T120 are
# pushed toward each other to take up every running play. A band that stops
# the feeler is turned down, never under TURNED_DIA_FITUP_MIN; a shoulder
# that stops it is faced back, never under its printed short limit. The
# assembly proves the fit-up limits clear the feeler and retain engagement.
T120_FITUP_FEELER_MM = 0.10
TURNED_DIA_FITUP_MIN = 18.2372  # .718
SHOULDER_LENGTH_FITUP_MIN = SHOULDER_LENGTH + SHOULDER_LENGTH_LIMITS[0]

# --- Hub boss + retention pin (ch. 12 p. 19, page002_img02 / img06) ---------
#
# The boss is turned to the actual minimum root envelope beyond the toothed
# length, retaining the photo's root-matched tool runout without replacing the
# translated stock floor by a concentric circle. Actual mating-tip air is a
# crossed-mesh requirement, not a standard ideal-N clearance assertion.
# It runs to the overall length past the toothed length; the crankshaft fills
# it and stands proud of its north face (owner ruling D1, 2026-10-15:
# dt_crankshaft_spec.SHAFT_END_PROUD_RANGE); its length is derived below
# (W15). The boss is
# extruded from the SAME faced end as the teeth, so the print carries one
# overall length from that end (drawing-guidelines.md rule 11 (turned parts read like the lathe): lengths from one faced end, the overall
# length real and conspicuous), and the toothed length is FaceWidth.
# The boss's outer end edge takes the title block's edge break: the sized
# chamfer that once imitated the photo's rounding had no function, and at its
# general grade it could reach the bore (machinist review of 4d4e038e3).


def ceil_to_places(value: float, places: int, unit: str = UNIT) -> float:
    """``value`` (mm) rounded up to the ``places``-place grid of ``unit``."""
    per = MM_PER_IN if unit == "in" else 1.0
    scale = 10.0**places
    return round(math.ceil(round(value / per * scale, 6)) / scale * per, 9)


def floor_to_places(value: float, places: int, unit: str = UNIT) -> float:
    """``value`` (mm) rounded down to the ``places``-place grid of ``unit``."""
    per = MM_PER_IN if unit == "in" else 1.0
    scale = 10.0**places
    return round(math.floor(round(value / per * scale, 6)) / scale * per, 9)


def print_step(places: int, unit: str = UNIT) -> float:
    """One step of the ``places``-place grid of ``unit``, in mm."""
    return 10.0**-places * (MM_PER_IN if unit == "in" else 1.0)


# USER RULING 2026-09-25, MHA-DT-10 boss option C: the boss stays at the tooth
# root, where a form cutter runs out onto it untouched and the photo reads it;
# a boss proud of the root is scalloped by the cutter's arc up to the pin hole.
# #290: the root floored to the .01 in grid it prints at, so the boss sits
# just under the root.  Over the .3125 bore its worst wall -- the printed
# diameter at its .XX row over the bore's upper limit -- meets the .080 in
# rule-17 target (the #1374 shortfall is gone); an OD, tooth or bore change
# that eats into it fails loud.
BOSS_DIA_PLACES = 2
BOSS_DIA = floor_to_places(ROOT_DIA_MIN, BOSS_DIA_PLACES)
_BORE_LOWER, _BORE_UPPER = deviations(BORE_DIA_BAND)
_BOSS_DIA_LOWER, _BOSS_DIA_UPPER = printed_deviations(BOSS_DIA, BOSS_DIA_PLACES, unit=UNIT)
BOSS_WALL_WORST = (BOSS_DIA + _BOSS_DIA_LOWER - (BORE_DIA + _BORE_UPPER)) / 2.0
if BOSS_WALL_WORST < WALL_TARGET_MM:
    raise AssertionError(
        f"16T boss worst wall {BOSS_WALL_WORST:.3f} is under the .080 in target"
    )

# The internal shoulder where the turned band steps down to the boss at the
# tooth face is a lathe corner, so it carries a single-limit radius (machinist
# review of 88d48ad2a7b4, drawing-guidelines.md rules 11 and 16): sharp up to
# this maximum, printed "R.016 MAX" from the model value (swTolMAX).  Only the
# 64T crank-drive gear's tooth row reaches over the boss there; its worst tip
# (max OD at the closest pose the drive train allows) keeps radial air to a
# full R.016 ring around the boss.
# The spaces' form cutter runs out through the ring, so TOOTH_RUNOUT_NOTE stays
# true; the ring sits north of the teeth and changes no fit or wall.
SHOULDER_RADIUS = 0.4064  # .016
# (upper, lower) deviations: the nominal IS the limit, down to sharp.
SHOULDER_RADIUS_BAND = (0.0, -SHOULDER_RADIUS)
SHOULDER_RADIUS_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.016 MAX"
SHOULDER_RADIUS_PLACES = 3
if not prints_exactly(SHOULDER_RADIUS, SHOULDER_RADIUS_PLACES):
    raise AssertionError("the shoulder radius must print exactly at its places")
if BOSS_DIA / 2.0 + SHOULDER_RADIUS >= (TURNED_DIA - TURNED_DIA_TOLERANCE_MM) / 2.0:
    raise AssertionError("the shoulder radius must end on the turned band's face")

# Retention pin: a plain 1/8 in straight pin (stock drill rod) through the boss
# and crankshaft, match-drilled at assembly with the pinion on its seat. The
# drawing therefore governs the hole by its fit to the named pin, not by the
# model's nominal drill diameter: the shop drills undersize and reams until the
# actual pin is a light drive fit. The callout locates the operation at the
# boss mid-length and requires the fitted pin flush on both sides. The hole sits
# on the pinion's local -X; its clocking against the 64T tooth-in-gap seed is
# carried by the crankshaft hole. Physical datum geometry here is independent
# of the source-qualified phase selected by the native publication callers.
PIN_HOLE_SPEC = HoleSpec("drilled_fractional", "1/8")
PIN_DIA = FRACTIONAL_DRILL_MM["1/8"]  # 3.175
PIN_LENGTH = BOSS_DIA  # flush both sides

# --- W15: shortest boss that still protects the match-drilled pin ----------
#
# Owner ruling D1 (2026-10-15): the crankshaft's collar is pulled onto the
# MHA-DT-05 boss's south face, this pinion is set on its feeler off the north
# face and only then is the pin match-drilled, and the shaft is long enough
# that its end stands proud of this boss's north face at every accepted part
# set (dt_crankshaft_spec.SHAFT_END_PROUD_RANGE).  The shaft therefore fills
# the boss, and its wall past the pin is never shorter than the boss's own:
# the binding ligament is the pin's to the boss's north face, held at
# PIN_EDGE_MIN_WORST (the .080 in rule-17 target) at print-worst.  The
# Ø.125 pin stays at the actual boss mid-length, with a .010 in layout
# allowance.
PIN_EDGE_MIN_WORST = WALL_TARGET_MM
PIN_STATION_LAYOUT_ALLOWANCE_MM = 0.254
# The overall length prints at OVERALL_LENGTH_PLACES (.XX +/-.01), and the
# pin is laid out at the actual boss's middle, so a short boss splits its
# shortfall between the two ligaments.
OVERALL_LENGTH_PLACES = 2
SHAFT_LENGTH_PLACES = 2  # dt_crankshaft_spec prints its Depth here
FACE_WIDTH_PLACES = 2
SHOULDER_LENGTH_PLACES = FACE_WIDTH_PLACES  # stated like FaceWidth
TURNED_DIA_PLACES = 3  # stated like the OutsideDia it cuts into
OVERALL_LENGTH_GRADE_MM = printed_band_mm(OVERALL_LENGTH_PLACES, unit=UNIT)
# W15 sizes the boss for a face accepted anywhere in the .XX row. The printed
# band sits inside that row, so every W15 stack only gains margin.
W15_FACE_ALLOWANCE_MM = printed_band_mm(FACE_WIDTH_PLACES, unit=UNIT)
_FACE_LOWER, _FACE_UPPER = FACE_WIDTH_LIMITS
if _FACE_LOWER < -W15_FACE_ALLOWANCE_MM - 1e-9 or _FACE_UPPER > W15_FACE_ALLOWANCE_MM:
    raise AssertionError("the 16T face band left the .XX row W15 sizes the boss for")
# The pin's drilled-hole grade grows its radius by half the printed oversize.
_PIN_HOLE_RADIUS_GROWTH = drilled_oversize_mm(unit=UNIT) / 2.0


def pin_axial_ligament_worst(boss_length: float) -> float:
    """Print-worst wall from the pin hole to the boss's north face: the boss
    short by its face and overall rows, halved at the laid-out middle, less
    the pin's radius, the drill's oversize and the layout allowance."""
    return (
        (boss_length - W15_FACE_ALLOWANCE_MM - OVERALL_LENGTH_GRADE_MM) / 2.0
        - PIN_DIA / 2.0
        - _PIN_HOLE_RADIUS_GROWTH
        - PIN_STATION_LAYOUT_ALLOWANCE_MM
    )


BOSS_LENGTH_PLACES = OVERALL_LENGTH_PLACES
BOSS_LENGTH = ceil_to_places(
    2.0 * (
        PIN_EDGE_MIN_WORST
        + PIN_DIA / 2.0
        + _PIN_HOLE_RADIUS_GROWTH
        + PIN_STATION_LAYOUT_ALLOWANCE_MM
    )
    + W15_FACE_ALLOWANCE_MM
    + OVERALL_LENGTH_GRADE_MM,
    BOSS_LENGTH_PLACES,
)
OVERALL_LENGTH = round(FACE_WIDTH + BOSS_LENGTH, 9)
for _name, _value, _places in (
    ("FACE_WIDTH", FACE_WIDTH, FACE_WIDTH_PLACES),
    ("OVERALL_LENGTH", OVERALL_LENGTH, OVERALL_LENGTH_PLACES),
    ("SHOULDER_LENGTH", SHOULDER_LENGTH, SHOULDER_LENGTH_PLACES),
    ("TURNED_DIA", TURNED_DIA, TURNED_DIA_PLACES),
    ("TURNED_DIA_FITUP_MIN", TURNED_DIA_FITUP_MIN, TURNED_DIA_PLACES),
):
    if not prints_exactly(_value, _places):
        raise AssertionError(f"{_name} {_value!r} does not print exactly at {_places} places")
# The turned band is a real band of stub teeth at every accepted size: the
# shoulder ends short of the tooth end, and the turned diameter stays above
# the root (where the boss is) and below the tip.
if SHOULDER_LENGTH + SHOULDER_LENGTH_LIMITS[1] >= FACE_WIDTH + FACE_WIDTH_LIMITS[0]:
    raise AssertionError("the 16T full-OD shoulder reaches the tooth end")
if not (
    BOSS_DIA < TURNED_DIA - TURNED_DIA_TOLERANCE_MM
    and TURNED_DIA + TURNED_DIA_TOLERANCE_MM < OUTSIDE_DIA - OUTSIDE_DIA_TOLERANCE_MM
):
    raise AssertionError("the 16T turned band must lie between the root and the tip")
# The fit-up turn-down leaves stub teeth: above the pitch circle, below the band.
if not PITCH_DIA < TURNED_DIA_FITUP_MIN < TURNED_DIA - TURNED_DIA_TOLERANCE_MM:
    raise AssertionError("the 16T fit-up turn-down must stay over the pitch circle")
PIN_STATION = FACE_WIDTH + BOSS_LENGTH / 2.0
PIN_AXIAL_LIGAMENT_WORST = pin_axial_ligament_worst(BOSS_LENGTH)
if PIN_AXIAL_LIGAMENT_WORST < PIN_EDGE_MIN_WORST - 1e-9:
    raise AssertionError("match-drilled pin's wall to the boss end falls below its print-worst floor")
if (
    pin_axial_ligament_worst(BOSS_LENGTH - print_step(BOSS_LENGTH_PLACES))
    >= PIN_EDGE_MIN_WORST - 1e-9
):
    raise AssertionError("a boss one print step shorter still holds W15: not the shortest")
# The print locates the match-drilled hole from the boss's north face, the
# faced end whose wall the hole must keep (drawing-guidelines.md rule 10: a
# centre from a real feature, never "mid-length" in words; machinist review
# r1 of #1652). It carries the layout allowance the boss length budgets as
# its own band, and at that band the hole still keeps the W15 floor to the
# north face.
PIN_FROM_BOSS_END = BOSS_LENGTH / 2.0
PIN_FROM_BOSS_END_PLACES = BOSS_LENGTH_PLACES + 1
PIN_FROM_BOSS_END_TOL = PIN_STATION_LAYOUT_ALLOWANCE_MM
if not prints_exactly(PIN_FROM_BOSS_END, PIN_FROM_BOSS_END_PLACES):
    raise AssertionError("the pin's station from the boss end does not print exactly")
PIN_FROM_BOSS_END_LIGAMENT_WORST = (
    PIN_FROM_BOSS_END
    - PIN_FROM_BOSS_END_TOL
    - PIN_DIA / 2.0
    - _PIN_HOLE_RADIUS_GROWTH
)
if PIN_FROM_BOSS_END_LIGAMENT_WORST < PIN_EDGE_MIN_WORST - 1e-9:
    raise AssertionError("the printed pin station lets the hole break the boss's north wall")
# The hole is reamed to fit the pin, so its printed size is a reference
# nominal from the pin's own diameter, at the drilled-hole row's three places.
PIN_HOLE_DIA_PLACES = 3


def pitch_point_azimuths(
    x_offset_mm: float, rise_mm: float, incline_deg: float, r64_mm: float
) -> tuple[float, float]:
    """(64T, 16T) plane-local azimuths of the 64T mid-plane pitch-circle point
    nearest the crank axis: the pitch point the tooth-in-gap seed must use.

    ``x_offset_mm`` is the 64T centre's machine x past the crank axis,
    ``rise_mm`` the crank axis's height over the cone axis. The crank axis is
    machine z but the 64T plane leans by the incline, so seen along the crank
    axis the pitch circle is an ellipse (x times cos i), and its nearest point
    is not on the line of centres. Each azimuth reads from the in-plane
    horizontal toward the other axis, the seed's chirality-free convention.
    Minimising |P - crank axis|^2 over the 64T azimuth a gives
    x cos(i) sin(a) - rise cos(a) + R sin^2(i) sin(a) cos(a) = 0 (Newton from
    the line-of-centres azimuth).
    """
    incline = math.radians(incline_deg)
    cos_i, sin_i = math.cos(incline), math.sin(incline)
    alpha = math.atan2(rise_mm, x_offset_mm * cos_i)
    for _ in range(20):
        residual = (
            x_offset_mm * cos_i * math.sin(alpha)
            - rise_mm * math.cos(alpha)
            + r64_mm * sin_i**2 * math.sin(alpha) * math.cos(alpha)
        )
        slope = (
            x_offset_mm * cos_i * math.cos(alpha)
            + rise_mm * math.sin(alpha)
            + r64_mm * sin_i**2 * math.cos(2.0 * alpha)
        )
        step = residual / slope
        alpha -= step
        if abs(step) < 1e-14:
            break
    alpha16 = math.atan2(
        rise_mm - r64_mm * math.sin(alpha),
        x_offset_mm - r64_mm * math.cos(alpha) * cos_i,
    )
    return math.degrees(alpha), math.degrees(alpha16)


def tooth_in_gap_seed_deg(alpha64_deg: float, alpha16_deg: float) -> float:
    """Pinion clocking (one 16T pitch) that puts its gap on the 64T tooth
    nearest the pitch point: the 64T is keyed at its authored phase (a tooth
    centred at azimuth 0, mid-face for the helix), so its nearest tooth leads
    the pitch point by delta; the pinion's gap sits that same arc (64/16
    pinion degrees per 64T degree) past the pitch point on its side."""
    pitch64 = 360.0 / dt_crank_drive_gear_spec.TEETH
    delta64 = round(alpha64_deg / pitch64) * pitch64 - alpha64_deg
    return (
        (alpha16_deg + 180.0)
        - delta64 * (dt_crank_drive_gear_spec.TEETH / TEETH)
        - 360.0 / TEETH / 2.0
    ) % (360.0 / TEETH)


# Tooth-in-gap datum at the pitch point, from the placement geometry.
# gear_train.crank_mesh_phase_offset_deg is the one configured offset from it.
# The line-of-centres azimuths this replaced sat 1.68 pinion degrees off the
# pitch point here: the 8e991c4ac assembly's 16T/64T interference (0.46 and
# 0.02 mm^3). On main's 12.5182 deg pair the same correction is -1.63 deg,
# inside the exact-solid free window [-2.789, -0.215] main measured round
# the old formula (MESH_WINDOW_CENTRE_DEG -1.49).
_GEAR64_CENTRE_STATION = (
    dt_crank_drive_gear_spec.LAYOUT_CENTRE_STATION
    + _cone_axis_constants.GEAR_AXIS_SHIFT
    + dt_crank_drive_gear_spec.CENTRE_SHIFT_NORTH
)
_GEAR64_SEAT = cone_line.cone_station(_GEAR64_CENTRE_STATION)
_PINION_DATUM_CLOCK_DEG = tooth_in_gap_seed_deg(*pitch_point_azimuths(
    _GEAR64_SEAT[0] - cone_line.X_CRANK,
    cone_line.Y_CRANK - cone_line.Y_DRIVE,
    cone_line.INCLINE_DEG,
    dt_crank_drive_gear_spec.PITCH_DIA / 2.0,
))
PIN_CLOCKING_DEG = _PINION_DATUM_CLOCK_DEG + float(
    _config.machine("gear_train", "crank_mesh_phase_offset_deg")
)
if not 0.0 <= PIN_CLOCKING_DEG < 360.0 / TEETH:
    raise AssertionError("pinion retention-hole clocking must lie within one tooth pitch")


# The matched-hole callout on both part records identifies both seated parts,
# the shared operation and the actual fitted pin. Reaming to a functional
# acceptance governs, so the pinion prints the hole's size only as a
# reference nominal on its native diameter, and locates it from the boss's
# north face (PIN_FROM_BOSS_END); the pin identity, acceptance and flush
# condition ride that callout.
# The part numbers are hard-coded, not read from ``_config.parts``.
# test_dt_crank_pinion_drawing checks them against the registry offline.
CRANKSHAFT_NUMBER = "MHA-DT-11"
PINION_NUMBER = "MHA-DT-10"
PIN_NUMBER = "MHA-DT-29"
# The 64T this pinion meshes with, and the cone gear whose T120 the turned
# band and the shoulder clear (MHA-DT-00's T120 check).
MESH_GEAR_NUMBER = "MHA-DT-07"
CONE_GEAR_NUMBER = "MHA-DT-03"
BORE_PROCESS_CALLOUT = "REAM THRU"
BORE_FIT_CALLOUT = "\n".join(
    (
        "BORE LIMITS GOVERN",
        f"MATE SHAFT {CRANKSHAFT_NUMBER}",
        f"(\N{DIAMETER SIGN}{inch_text(SEAT_DIA, 4)} "
        f"+{inch_text(_SHAFT_UPPER, 4)}/{inch_text(_SHAFT_LOWER, 4)})",
        f"(DIA CLR {inch_text(_CLEARANCE_MIN, 4)}-{inch_text(_CLEARANCE_MAX, 4)})",
    )
)
# One matched-fit note, printed on BOTH sheets (machinist review of 4d4e038e3):
# a sheet stands alone, so each carries all four facts --
# match drill at assembly, ream to fit the named pin, the fit's acceptance,
# flush -- with the other part and where on this one the hole runs.
# Four lines, no dimensions (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)); MHA-DT-00 step 4 reads the shaft's.
PIN_FIT_LINES = (
    f"REAM TO FIT PIN {PIN_NUMBER}, LIGHT HAMMER FIT",
    "NOT REMOVABLE BY HAND, FLUSH BOTH SIDES",
)


def pin_hole_note(mate_number: str, where: str) -> str:
    return "\n".join((f"MATCH DRILL AT ASSY WITH {mate_number}", where, *PIN_FIT_LINES))


# The pinion's callout hangs under its reference Ø: the station is a native
# dimension now, so the words carry only the operation, mate and fit.
PIN_HOLE_PROCESS = "\n".join(
    (f"MATCH DRILL AT ASSY WITH {CRANKSHAFT_NUMBER}", *PIN_FIT_LINES)
)
# The shaft's narrower field needs the reaming instruction split before the
# pin identity, without changing any process words or the four-line height.
# A note carries no dimension: the pin's size is on MHA-DT-29's own sheet.
CRANKSHAFT_PIN_HOLE_PROCESS = pin_hole_note(
    PINION_NUMBER, "AT ITS BOSS MID-LENGTH"
).replace("\nREAM TO FIT PIN ", " REAM TO FIT\nPIN ")

# No roughness symbol: the bore is pinned to the crankshaft (match-drilled
# pin MHA-DT-29), so it turns with the shaft and never runs, slides or
# locates against it (drawing-guidelines.md rule 6: pinned bores carry no
# symbol; machinist review r1 of #1652). The reamed limits and the named mate
# control the fit.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_dt_crank_pinion`` marks exactly these; ``draw_dt_crank_pinion``
# keeps exactly their union across its per-view ``keep`` maps. The
# ``BossProfile`` is a Right-plane revolve profile with construction-only
# witnesses. It therefore owns every printed turned diameter and length on the
# side view but the turned band's, without changing the solid: ``BossDia``,
# ``OverallLength`` and the shoulder's single-limit ``ShoulderRadius`` drive
# the revolve, while ``OutsideDia``, ``BoreDia``,
# ``FaceWidth``, ``ShoulderLength``, ``PinHoleDia`` and ``PinFromBossEnd`` are
# equation-driven native reference dimensions on construction witnesses
# (drawing-simplicity-policy.md `How the repository implements the
# guidelines`'s reference-sketch allowance and drawing-guidelines.md rule 11
# (turned parts read like the lathe)'s turned-part layout). The lengths ride a
# witness along the section's LOWER outline, so their extension lines start at
# the corners they measure instead of crossing the hatch and the bore from the
# upper half-profile (machinist review r1 of #1652). The
# ``TurnedBandProfile`` is the Right-plane revolve cut that turns the teeth
# down north of the shoulder; its turned diameter drives it. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BossProfile": {
        "OutsideDia",
        "BoreDia",
        "BossDia",
        "OverallLength",
        "FaceWidth",
        "ShoulderLength",
        "PinHoleDia",
        "PinFromBossEnd",
        "ShoulderRadius",
    },
    "TurnedBandProfile": {"TurnedDia"},
}

# --- Decimal places, authored ON THE PART ------------------------------------
#
# drawing-simplicity-policy.md `How the repository implements the guidelines`: the places a dimension prints are part of the tolerance it
# claims, and the model owns both. ``build_dt_crank_pinion`` applies this table
# natively (``_drawing_precision.apply_drawing_precision``) right after the drawing
# marks, so ``draw_dt_crank_pinion`` imports each dimension verbatim and only reads
# ``GetPrimaryPrecision2()`` back off the sheet.
#
# Inch sheet (#290). The bore is the only size fit on the part and prints
# four places with its derived band. The outside diameter prints three with
# its own +/-.004. The face width prints two places with its own +.000/-.010
# (FACE_WIDTH_BAND): the assembly proves the 64T row overlap at its short
# limit and the turned band's T120 clearance at its long one. The shoulder
# length prints two places and the turned diameter three, each with the band
# its reason is recorded at above. The boss diameter is routine .XX, not a
# running surface. The match-drilled hole prints its reference size at three
# places and its station from the boss's north face at three
# (PIN_FROM_BOSS_END). The overall length prints two places like the face,
# with the W15 boss sized for the pin's wall to its north face. The shoulder
# radius prints its single limit at three places.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BossProfile": {
        "OutsideDia": OUTSIDE_DIA_PLACES,
        "BoreDia": 4,
        "BossDia": BOSS_DIA_PLACES,
        "OverallLength": OVERALL_LENGTH_PLACES,
        "FaceWidth": FACE_WIDTH_PLACES,
        "ShoulderLength": SHOULDER_LENGTH_PLACES,
        "PinHoleDia": PIN_HOLE_DIA_PLACES,
        "PinFromBossEnd": PIN_FROM_BOSS_END_PLACES,
        "ShoulderRadius": SHOULDER_RADIUS_PLACES,
    },
    "TurnedBandProfile": {"TurnedDia": TURNED_DIA_PLACES},
}

# The drawing reads this flat view back off the sheet: a dimension name is
# unique across the features that expose one, and a marked dimension nobody
# authored places for would otherwise print SolidWorks' template default.
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"{_feature}: precision authored for unmarked dimensions {_unmarked}"
        )



# The drive-train fit-up may turn the band down past its printed band (the
# T120 feeler check, MHA-DT-00's crank step), and only when the band itself
# fails that check (a shoulder failure is the shoulder's to correct); the
# sheet permits it only as that check directs and states the floor, so the
# part stays conforming after the fit-up cut.  Codex P1 on #1154 (review 3).
# The worst-case clearances to T120 are a design-check result, so only the
# assembly's crank step prints them (T120_FITUP_ASSEMBLY_CHECK).  The sheet
# names the check, not its step number: a part never reads the step registry
# (Main's TbPB ruling 2; test_part_isolation).  The allowance rides the
# turned diameter's own callout, so it cannot be read against the tip
# diameter (machinist review r1 of #1652), and says who turns it, when and
# on what result (r2: "MAY TURN" named neither).
T120_SHOULDER_CLEARANCE_TEXT = (
    "NO AXIAL OVERLAP"
    if T120_SHOULDER_AIR_WORST == math.inf
    else f"{T120_SHOULDER_AIR_WORST:.2f}"
)
TURNED_DIA_FITUP_CALLOUT = "\n".join(
    (
        f"{CONE_GEAR_NUMBER} T120 CLR",
        "IF MHA-DT-00 T120",
        "FEELER CHECK FAILS,",
        "TURN AT ASSY TO CLEAR,",
        f"Ø{inch_text(TURNED_DIA_FITUP_MIN, TURNED_DIA_PLACES)} MIN",
    )
)
# Section A-A cuts through a tooth, so the band reads as a solid ring and the
# spaces seem to stop against it (machinist review of the stack build). They
# do not: the band is the teeth turned down, and the spaces run the whole face
# width out over the boss, turned to the root (BOSS_DIA = ROOT_DIA_MIN), which
# is where the form cutter runs out. The boss's .X band allows it above the
# root, so a cutter mark on the boss is permitted, not a reject.
TOOTH_RUNOUT_NOTE = (
    "TEETH RUN FULL LENGTH THROUGH THE TURNED BAND; CUTTER RUNOUT INTO BOSS OK."
)
if not BOSS_DIA <= ROOT_DIA_MIN:
    raise AssertionError("the 16T boss must be turned to the root for the cutter runout")
DRAWING_NOTES = TOOTH_RUNOUT_NOTE
# The MHA-DT-00 crank step's T120 check (user, 2026-09-30, #1154), printed by
# draw_dt_drive_train_assembly: the pinion on its seat feeler, MHA-DT-10 and T120
# pushed toward each other (taking up every running play), turned by hand and
# read all round before the step's free-running revolution (it may rub until
# the check closes: Codex P2 on #1154, review 3).  Each cut answers its own
# reading only (build_dt_drive_train_assembly.t120_fitup_cuts).  Either fit-up
# limit passes the feeler at every corner (build_dt_drive_train_assembly asserts
# it), so the check always closes.  Its last line is short: the step carries
# on after it on the same line.
T120_FITUP_PUSHED = (PINION_NUMBER, "T120")
T120_FITUP_ASSEMBLY_CHECK = "\n".join(
    (
        f"   WORST-CASE T120 CLEARANCE: TURNED BAND {T120_TURNED_BAND_RADIAL_WORST:.2f}, "
        f"SHOULDER {T120_SHOULDER_CLEARANCE_TEXT}. PUSH",
        f"   {T120_FITUP_PUSHED[0]} AND {T120_FITUP_PUSHED[1]} TOWARD EACH OTHER; "
        "TURN MHA-DT-07 SLOWLY BY HAND,",
        f"   READING A {T120_FITUP_FEELER_MM:.2f} FEELER ALL ROUND. BAND TO T120 TIPS: "
        "IF THE FEELER",
        "   STOPS, TURN BAND DOWN, "
        f"Ø{TURNED_DIA_FITUP_MIN:.2f} MIN. SHOULDER TO T120 SOUTH FACE: IF",
        "   THE FEELER STOPS, FACE SHOULDER BACK, "
        f"{SHOULDER_LENGTH_FITUP_MIN:.2f} MIN. RESET, RECHECK.",
    )
)
