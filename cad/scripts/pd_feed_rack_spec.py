r"""Pure-data contract for the MHA-PD-26 feed rack.

The rack is purchased SDP/SI A 1B12-Y324, a 48 in commercial brass strip.
Its catalog face width and height are 3/16 in; its pitch and pressure angle
must match the feed sleeve. It is cut to the platen length and screwed by
its flat top to the MHA-PD-27 bottom guide rail's underside with four
#0-80 screws in taps transferred through the rail at assembly, each over a
tooth (owner rulings 2026-11-13, #2410: no backer, no solder). No
tooth-form accuracy or inventory promise is invented. The CAD represents
nominal standard straight-flank rack teeth; profile shift changes assembly
axis distance, not the rack.

Local frame: length along +X, the flat top at Y=0, tooth crests at
RACK_HEIGHT, front face at Z=0. Routine fabricated sizes use the title-block
.XX band. Bought strip sizes are parenthesized references; the SKU, not a
new accuracy band, owns them. The nominal CAD end phase is not a
cut-indexing requirement: the strip slides under the rail until a tooth
stands under the first screw hole, and the mesh is set at assembly.
The separate paper_drive_rack_travel contract clips every physical carrier
to the shortest finished cut length, reserves an end-affected strip at each
phase-unknown end and defines the mandatory engaged-feed operating window. That
assembly/traveler requirement is not a hardware stop or supplier accuracy
claim, and it must preserve the complete located recording-paper sweep.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import _config
import _gear_quality as quality
from _hole_spec import (
    DRILL_POINT_H,
    TAP_DRILL_MM,
    THREAD_MAJOR_MM,
    HoleSpec,
    blind_cut_dia_mm,
)
import _mcmaster_91794a060 as _screw
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
)
from _package_units import drawing_unit
from _inch_wall_limits import WALL_FLOOR_MM

import pd_transgear_feed_pinion_spec as FEED
from pd_platen_spec import GUIDE_HOLE_X, PLATE_WIDTH

# #290: the sheet prints decimal inch.
UNIT = drawing_unit("parts/pd-feed-rack", _config.parts("pd-feed-rack"))

MM_PER_IN = FEED.MM_PER_IN
DP = FEED.DIAMETRAL_PITCH
PA_DEG = FEED.PRESSURE_ANGLE_DEG
MODULE_MM = FEED.MODULE_MM

# Primary product fields: https://shop.sdp-si.com/a-1b12-y324.html .
# Catalog p1-193: https://sdp-si.com/D820/PDFS/Gears.pdf (Y = PA20).
# Commercial class supplies no numerical pitch-accuracy certificate here.
PURCHASED_RACK_SUPPLIER = "SDP/SI"
PURCHASED_RACK_SKU = "A 1B12-Y324"
PURCHASED_RACK_MATERIAL = "Brass"
PURCHASED_RACK_DP = 32.0
PURCHASED_RACK_PA_DEG = 20.0
PURCHASED_RACK_LENGTH_IN = 48.0
PURCHASED_RACK_LENGTH_MM = PURCHASED_RACK_LENGTH_IN * MM_PER_IN
PURCHASED_RACK_FACE_WIDTH_IN = 3.0 / 16.0
PURCHASED_RACK_HEIGHT_IN = 3.0 / 16.0
PURCHASED_RACK_QUALITY_CLASS = "Commercial"
# SDP/SI publishes no face-width or height tolerance for the strip (product
# page and catalogue p. 1-193 checked 2026-11-13, #2694); its only published
# accuracy is pitch. Drawn 3/16 square brass bar is held to .003 (Alro Metals
# Guide p. 7-3, CDA 360 / ASTM B16 square rod). The receiving geometry gives
# the strip twice that either side of its 3/16 REF in height and face width:
# the rail's top under the support bar (the rail rides on the strip's top), the
# cut-end section reserve, the feed's lateral terms and the four taps over the
# teeth are paid at these limits, so any ordinary strip is accepted as
# supplied, with no receiving gauge and no limit on the sheet.
PURCHASED_RACK_SECTION_ROOM_IN = 2.0 * 0.003
PURCHASED_RACK_HEIGHT_MAX_MM = (
    PURCHASED_RACK_HEIGHT_IN + PURCHASED_RACK_SECTION_ROOM_IN
) * MM_PER_IN
PURCHASED_RACK_HEIGHT_MIN_MM = (
    PURCHASED_RACK_HEIGHT_IN - PURCHASED_RACK_SECTION_ROOM_IN
) * MM_PER_IN
PURCHASED_RACK_FACE_WIDTH_MAX_MM = (
    PURCHASED_RACK_FACE_WIDTH_IN + PURCHASED_RACK_SECTION_ROOM_IN
) * MM_PER_IN
PURCHASED_RACK_FACE_WIDTH_MIN_MM = (
    PURCHASED_RACK_FACE_WIDTH_IN - PURCHASED_RACK_SECTION_ROOM_IN
) * MM_PER_IN
if DP != PURCHASED_RACK_DP or PA_DEG != PURCHASED_RACK_PA_DEG:
    raise AssertionError("purchased rack pitch/PA no longer match the feed sleeve")

# Owner rulings 2026-11-13 (#2410): no backer and no solder. The strip is cut
# to the platen's width and screwed by its flat top to the underside of the
# MHA-PD-27 bottom guide rail.
CUT_LENGTH_MM = PLATE_WIDTH
BAR_LENGTH = CUT_LENGTH_MM
RACK_HEIGHT = PURCHASED_RACK_HEIGHT_IN * MM_PER_IN
RACK_THICKNESS = PURCHASED_RACK_FACE_WIDTH_IN * MM_PER_IN

PITCH = math.pi * MODULE_MM
ADDENDUM = MODULE_MM
DEDENDUM = FEED.DEDENDUM_FACTOR * MODULE_MM
PITCH_LINE_Y = RACK_HEIGHT - ADDENDUM
ROOT_Y = PITCH_LINE_Y - DEDENDUM
CUT_TOP_Y = RACK_HEIGHT + 1.0  # seed-cut overrun, not a finished size
TAN_PA = math.tan(math.radians(PA_DEG))
GAP_COUNT = int(BAR_LENGTH / PITCH)
FIRST_GAP_X = PITCH / 2.0  # nominal CAD phase; not a finished-end control
# The gaps centre half a pitch in, so the teeth centre on whole pitches.
TOOTH_CENTRE_PHASE_X = FIRST_GAP_X - PITCH / 2.0

# --- Placement under the rail (owner rulings 2026-11-13 #2410, 2026-11-26 #3738) ---
# The strip's front face stands this far behind the platen's back face (the
# rail's platen-mating face), so the 12T's full-depth teeth cover the strip's
# whole face while MHA-PD-27's Ø.125 +.005/-0 counterbores keep the .044 MIN
# front wall; its ends lie flush with the rail's (and so the platen's). It is
# set there against a rule when the rail's holes are struck from its taps at
# MHA-PD-00 (FRONT_SET_BAND); the screws then return it to that place.
FRONT_BEHIND_PLATEN = 0.048 * MM_PER_IN
FRONT_SET_BAND = 0.010 * MM_PER_IN

# --- Rack-screw taps (drawing-guidelines.md rules 17, 18, 20) ----------------
# Four #0-80 taps in the strip's flat top, each on a TOOTH centre (over a
# tooth space the drill would break through the space's root), 22 rack
# pitches apart: whole teeth, so the spacing is the rack's, printed REF.
# The strip is drilled and tapped on its own; the MHA-PD-27 rail's four holes
# are then struck from these taps at MHA-PD-00 with a transfer screw, so the
# taps' places along the strip need no fit to the rail (delegated ruling
# 2026-11-14 (Main), pending owner confirmation; owner review #2144, #2410;
# precedent R9-9, the disc's taps spotted through MHA-PD-17's holes at
# assembly).
TAP_SIZE = "#0-80"
TAP_PITCH = MM_PER_IN / 80.0
TAP_MAJOR_DIA = THREAD_MAJOR_MM[TAP_SIZE]
TAP_PLACES = 3
TAP_BAND = printed_band_mm(TAP_PLACES, unit=UNIT)
# A bottoming tap's full thread stops 1 to 1.5 pitches short of the drill's
# shoulder (rule 18's 1.5 pitches).
TAP_LEAD_LIMITS = (TAP_PITCH, 1.5 * TAP_PITCH)
# The four taps' target stations along the platen: centred on the platen's
# centre (its middle guide hole), +-11 and +-33 pitches from it (owner ruling
# 2026-11-13). The cut ends' tooth phase is not controlled, so each tap
# stands on the tooth centre nearest its station, within half a pitch; the
# rail's holes follow the taps wherever they fall, and each clears every rail
# tap by >= 19 mm (pd_platen_bottom_guide_spec asserts it).
TAP_STATION_PITCHES = (-33, -11, 11, 33)
TAP_STATION_X = tuple(
    GUIDE_HOLE_X[len(GUIDE_HOLE_X) // 2] + n * PITCH for n in TAP_STATION_PITCHES
)
TAP_TOOTH_INDEX = tuple(
    round((x - TOOTH_CENTRE_PHASE_X) / PITCH) for x in TAP_STATION_X
)
TAP_X = tuple(TOOTH_CENTRE_PHASE_X + k * PITCH for k in TAP_TOOTH_INDEX)
if any(
    abs(x - station) > PITCH / 2.0
    for x, station in zip(TAP_X, TAP_STATION_X, strict=True)
):
    raise AssertionError("a rack tap is more than half a pitch off its station")
# The first tap's printed window about its place from the cut end, a plain
# inch step just over half a pitch (machinist review r9, rule 4): the builder
# drills the tooth centre inside it, the others whole pitches from it, so a
# tap stands at most this far from its CAD place, the slip the MHA-PD-27
# hole-to-tap walls pay.
TAP_START_BAND = 0.050 * MM_PER_IN
if TAP_START_BAND < PITCH / 2.0:
    raise AssertionError("the first tap's window holds no tooth centre at some phase")
TAP_STATION_SLIP_MAX = TAP_START_BAND
TAP_SPACING_PITCHES = TAP_TOOTH_INDEX[1] - TAP_TOOTH_INDEX[0]
TAP_SPACING = TAP_SPACING_PITCHES * PITCH
# On the strip's centreline, located from its front face at the .XXX band.
TAP_Z = RACK_THICKNESS / 2.0
# Each tap sits on its own tooth centre to the .XXX band along the strip.
TAP_TOOTH_OFFSET_MAX = TAP_BAND
# The title block's .010 tap mouth break, charged on the taps' face walls and
# on the screws' full thread, as MHA-PD-27's taps and MHA-PD-VN-60's
# engagement pay it.
TAP_MOUTH_BREAK = max(edge_break_chamfer_mm(unit=UNIT), edge_break_radius_mm(unit=UNIT))


def tooth_width_at_depth_mm(depth_from_top_mm: float, strip_height_mm: float) -> float:
    """A tooth's width along X this far below the strip's flat top.

    The teeth are cut from the crest side, so a shorter strip has less solid
    above its roots; past the root line the tooth narrows along its flanks.
    """
    below_root = depth_from_top_mm - (strip_height_mm - ADDENDUM - DEDENDUM)
    return PITCH / 2.0 + 2.0 * DEDENDUM * TAN_PA - 2.0 * below_root * TAN_PA


def _deepest_inside_tooth_mm(width_mm: float, strip_height_mm: float) -> float:
    """The deepest a centred-to-band ``width_mm`` feature stays in the tooth."""
    root_depth = strip_height_mm - ADDENDUM - DEDENDUM
    full = PITCH / 2.0 + 2.0 * DEDENDUM * TAN_PA
    return root_depth + (full - width_mm - 2.0 * TAP_TOOTH_OFFSET_MAX) / (2.0 * TAN_PA)


def _floor_in(value_mm: float) -> float:
    return math.floor(round(value_mm / MM_PER_IN * 1000.0, 6)) / 1000.0 * MM_PER_IN


def _ceil_in(value_mm: float) -> float:
    return math.ceil(round(value_mm / MM_PER_IN * 1000.0, 6)) / 1000.0 * MM_PER_IN


# The depths, from the strip's flat top, each at the .XXX band. Sized at the
# strip's least height (the receiving room) so the tap drill (Ø at its
# drilled-hole oversize) and the deepest full thread (the drill's deepest
# shoulder less the tap's least lead) both stay inside the tooth at the
# station band, every corner.
_TAP_DRILL_DIA_MAX = TAP_DRILL_MM[TAP_SIZE] + drilled_oversize_mm(unit=UNIT)
_DRILL_DEPTH_MAX = min(
    _deepest_inside_tooth_mm(_TAP_DRILL_DIA_MAX, PURCHASED_RACK_HEIGHT_MIN_MM),
    _deepest_inside_tooth_mm(TAP_MAJOR_DIA, PURCHASED_RACK_HEIGHT_MIN_MM)
    + TAP_LEAD_LIMITS[0],
)
TAP_DRILL_DEPTH = _floor_in(_DRILL_DEPTH_MAX - TAP_BAND)  # .129
# The printed full thread: what the bottoming tap reaches from the drill's
# nominal shoulder, so its lower limit is met at the drill's.
TAP_THREAD_DEPTH = _floor_in(TAP_DRILL_DEPTH - TAP_LEAD_LIMITS[1])  # .110
TAP_THREAD_DEPTH_MIN = TAP_THREAD_DEPTH - TAP_BAND
TAP_THREAD_DEPTH_MAX = TAP_DRILL_DEPTH + TAP_BAND - TAP_LEAD_LIMITS[0]
TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    TAP_SIZE,
    end="blind",
    depth_mm=TAP_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": TAP_THREAD_DEPTH},
)
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
if TAP_THREAD_DEPTH_MIN > TAP_DRILL_DEPTH - TAP_BAND - TAP_LEAD_LIMITS[1] + 1e-9:
    raise AssertionError("the rack tap's full thread cannot reach its printed minimum")


def tap_tooth_margins_mm(
    strip_height_mm: float = PURCHASED_RACK_HEIGHT_MIN_MM,
    offset_mm: float = TAP_TOOTH_OFFSET_MAX,
    *,
    drill_depth_mm: float = TAP_DRILL_DEPTH + TAP_BAND,
    thread_depth_mm: float = TAP_THREAD_DEPTH_MAX,
    drill_dia_mm: float = _TAP_DRILL_DIA_MAX,
) -> dict[str, float]:
    """The metal on the near side of a tap's drill and thread major inside
    its tooth, ``offset_mm`` off the tooth centre; negative breaks into the
    tooth space. The defaults are the worst corner."""
    return {
        "drill": (
            tooth_width_at_depth_mm(drill_depth_mm, strip_height_mm) - drill_dia_mm
        )
        / 2.0
        - offset_mm,
        "thread": (
            tooth_width_at_depth_mm(thread_depth_mm, strip_height_mm) - TAP_MAJOR_DIA
        )
        / 2.0
        - offset_mm,
        # The 118-degree point narrows faster than the tooth does, so its cone
        # stays in metal once the shoulder does; its tip stays under the crest.
        "point_to_crest": strip_height_mm
        - (drill_depth_mm + drill_dia_mm / 2.0 * DRILL_POINT_H),
    }


TAP_TOOTH_MARGINS_MM = tap_tooth_margins_mm()
# Nominal: the 3/16 strip, the tap on its tooth centre, nominal depths.
TAP_TOOTH_MARGINS_NOMINAL_MM = tap_tooth_margins_mm(
    RACK_HEIGHT,
    0.0,
    drill_depth_mm=TAP_DRILL_DEPTH,
    thread_depth_mm=TAP_THREAD_DEPTH,
    drill_dia_mm=TAP_DRILL_MM[TAP_SIZE],
)
if min(TAP_TOOTH_MARGINS_MM.values()) < 0.0:
    raise AssertionError(f"a #0-80 rack tap breaks out of its tooth: {TAP_TOOTH_MARGINS_MM}")
# The tooth-root wall at the worst corner (RV-03): the deepest thread grazes
# the root fillet, which lies below the 12T's working depth.
TAP_TOOTH_WALL_MIN = min(TAP_TOOTH_MARGINS_MM["drill"], TAP_TOOTH_MARGINS_MM["thread"])
TAP_TOOTH_WALL_NOMINAL = min(
    TAP_TOOTH_MARGINS_NOMINAL_MM["drill"], TAP_TOOTH_MARGINS_NOMINAL_MM["thread"]
)
# The tap's wall to the strip's front and back faces (RV-03). It is located
# from the front face (TapFromFront, .XXX), so the back wall also pays the
# strip's least face width (its receiving room); both pay the thread major and
# the tap's mouth break.
TAP_FRONT_WALL_MIN = TAP_Z - TAP_BAND - TAP_MAJOR_DIA / 2.0 - TAP_MOUTH_BREAK
TAP_BACK_WALL_MIN = (
    PURCHASED_RACK_FACE_WIDTH_MIN_MM
    - (TAP_Z + TAP_BAND)
    - TAP_MAJOR_DIA / 2.0
    - TAP_MOUTH_BREAK
)
TAP_FACE_WALL_MIN = min(TAP_FRONT_WALL_MIN, TAP_BACK_WALL_MIN)
TAP_FACE_WALL_NOMINAL = (RACK_THICKNESS - TAP_MAJOR_DIA) / 2.0
if TAP_FACE_WALL_MIN <= 0.0:
    raise AssertionError("a #0-80 rack tap breaks out of the strip's face")


def _wall_text(value_mm: float) -> str:
    return f"{_floor_in(max(value_mm, 0.0)) / MM_PER_IN:.3f}".removeprefix("0")


# Rule 20's stated walls, floored to .001 in: to the faces, and inside the
# tooth at the deepest thread.
TAP_FACE_WALL_STATEMENT = (
    f"TAPS: WALL {_wall_text(TAP_FACE_WALL_MIN)} MIN TO FRONT AND BACK FACES,\n"
    f"{_wall_text(TAP_TOOTH_WALL_MIN)} MIN TO TOOTH ROOT."
)
if any(
    abs((x - TOOTH_CENTRE_PHASE_X) / PITCH - k) > 1e-9
    for x, k in zip(TAP_X, TAP_TOOTH_INDEX, strict=True)
):
    raise AssertionError("a rack tap is off a tooth centre")
if len({b - a for a, b in zip(TAP_TOOTH_INDEX, TAP_TOOTH_INDEX[1:])}) != 1:
    raise AssertionError("the rack taps are not equally spaced in whole teeth")
if not all(0.0 < x < BAR_LENGTH for x in TAP_X):
    raise AssertionError("a rack tap is off the strip")

# --- The rack screws' engagement (rule 18; RV-02) ----------------------------
# Four stock 91794A060 #0-80 x 1/2 fillisters, untrimmed (owner ruling
# 2026-11-26, #3738), their heads on the floor of the MHA-PD-27 rail's
# counterbores. The floor (rail underside to counterbore floor) is the rail's
# .XXX height less the native callout's counterbore depth from its top, which
# prints its own .219 ±.005 (#3738; at the wizard pocket's ±.01 of rule 3 this
# stack fails), so it carries both bands. It is the least that keeps the
# longest stock screw on the thinnest floor at or above the least full thread,
# so no tip reaches the tap's lead.
SCREW_LENGTH = _screw.SHANK_LEN
SCREW_LENGTH_MIN = SCREW_LENGTH - 0.03 * MM_PER_IN  # ASME B18.6.3 length band
SCREW_FIRST_THREAD_LOSS = _screw.PITCH
SCREW_FLOOR_BAND = 2.0 * TAP_BAND  # rail height .XXX + counterbore depth's own ±.005
SCREW_FLOOR = _ceil_in(SCREW_LENGTH - TAP_THREAD_DEPTH_MIN + SCREW_FLOOR_BAND)  # .405
SCREW_TIP_REACH_MAX = SCREW_LENGTH - (SCREW_FLOOR - SCREW_FLOOR_BAND)
# The margin is ZERO at the printed bands: the longest .500 screw on the
# thinnest .395 floor reaches .105, the tap's least full thread exactly
# (owner rulings 2026-11-25 #3620 and 2026-11-26 #3738).
# The guard has no rounding and no epsilon: the difference is exactly 0.0 mm
# here, and any negative fails.
SCREW_TIP_MARGIN = TAP_THREAD_DEPTH_MIN - SCREW_TIP_REACH_MAX
if not SCREW_TIP_MARGIN >= 0.0:
    raise AssertionError(
        "the longest rack screw can reach its tap's lead (margin is zero at the "
        "printed bands; any negative fails)"
    )
# Full-thread engagement: shortest stock on the thickest floor, the screw's
# first thread and the tap's mouth break lost (rule 18 counts full threads
# only); nominal: the catalogue length on the nominal floor.
ENGAGEMENT_WORST = (
    SCREW_LENGTH_MIN
    - (SCREW_FLOOR + SCREW_FLOOR_BAND)
    - SCREW_FIRST_THREAD_LOSS
    - TAP_MOUTH_BREAK
)
ENGAGEMENT_NOMINAL = (
    SCREW_LENGTH - SCREW_FLOOR - SCREW_FIRST_THREAD_LOSS - TAP_MOUTH_BREAK
)
ENGAGEMENT_WORST_D = ENGAGEMENT_WORST / TAP_MAJOR_DIA
ENGAGEMENT_NOMINAL_D = ENGAGEMENT_NOMINAL / TAP_MAJOR_DIA
ENGAGEMENT_TARGET_D = 1.5
if ENGAGEMENT_WORST <= 0.0:
    raise AssertionError("the rack screws have no full-thread engagement")
# Rule 20's stated fact, floored (never rounded up): .001 in and .01D.
ENGAGEMENT_CALLOUT_MIN = _floor_in(ENGAGEMENT_WORST) / MM_PER_IN
ENGAGEMENT_CALLOUT_D = math.floor(round(ENGAGEMENT_WORST_D * 100.0, 6)) / 100.0
ENGAGEMENT_STATEMENT = (
    f"ENGAGEMENT {f'{ENGAGEMENT_CALLOUT_MIN:.3f}'.removeprefix('0')} MIN "
    f"({ENGAGEMENT_CALLOUT_D:.2f}D)"
)


def _require_minor(exception_id: str, what: str) -> None:
    """Refuse a shortfall the registry row does not declare as a ``minor``
    (sm_gooseneck_spring_joint.owner_minor)."""
    declared = _config.parts("pd-feed-rack").get("machinist_exceptions") or ()
    if not any(
        isinstance(entry, dict)
        and entry.get("id") == exception_id
        and entry.get("kind") == "minor"
        for entry in declared
    ):
        raise AssertionError(f"pd-feed-rack: no minor {exception_id} declares the {what}")


if ENGAGEMENT_WORST_D < ENGAGEMENT_TARGET_D:
    _require_minor("RV-02", "rack-screw engagement under 1.5D")
if min(TAP_FACE_WALL_MIN, TAP_TOOTH_WALL_MIN) < WALL_FLOOR_MM:
    _require_minor("RV-03", "rack-tap walls under the .060 floor")


def half_width(y: float) -> float:
    """Gap half-width in mm: quarter pitch at the reference line."""
    return PITCH / 4.0 + (y - PITCH_LINE_Y) * TAN_PA


# One-millimetre pins fit the purchased 32-DP, 20-degree straight flanks.
# Actual certified pin diameters, not this nominal, enter every correction.
INCOMING_GAUGE_PIN_DIA_MM = 1.0


class RackGaugePinContact(NamedTuple):
    centre_y_mm: float
    flank_contact_y_mm: float
    root_clearance_mm: float


def rack_gauge_pin_contact_mm(actual_pin_diameter_mm: float) -> RackGaugePinContact:
    """Nominal flank seating; verify both flanks and root freedom on receipt.

    This proves the chosen pin's source-profile seat, not purchased accuracy.
    A physically obstructed or incomplete seat is an incoming REJECT.
    """
    if (
        isinstance(actual_pin_diameter_mm, bool)
        or not math.isfinite(actual_pin_diameter_mm)
        or actual_pin_diameter_mm <= 0.0
    ):
        raise ValueError("rack gauge pin diameter must be finite and positive")
    radius = actual_pin_diameter_mm / 2.0
    angle = math.radians(PA_DEG)
    centre_y = PITCH_LINE_Y + (radius / math.cos(angle) - PITCH / 4.0) / TAN_PA
    contact_y = centre_y - radius * math.sin(angle)
    root_clearance = centre_y - radius - ROOT_Y
    if not (ROOT_Y < contact_y < RACK_HEIGHT and root_clearance > 0.0):
        raise ValueError("rack gauge pin cannot seat on both full flanks clear of the root")
    return RackGaugePinContact(centre_y, contact_y, root_clearance)


def rack_over_pins_span_mm(
    *, pitch_intervals: int, actual_pin_diameters_mm: tuple[float, float]
) -> float:
    """Outside-pin MACHINE-X span, parallel to the rack, for counted gaps.

    The finished cut phase is irrelevant. Count actual intervening pitches;
    never substitute FIRST_GAP_X/GAP_COUNT for the physical station manifest.
    Unequal pin diameters change seat heights, so Euclidean distance is NOT
    this measurement. Correct using each pin's actual certified diameter.
    This span controls gap-centre index only: symmetric gap-width variation
    can leave it unchanged. It does NOT certify both-flank normal/thickness
    errors or the complete rack contact profile.
    """
    if (
        isinstance(pitch_intervals, bool)
        or not isinstance(pitch_intervals, int)
        or pitch_intervals < 1
    ):
        raise ValueError("rack gauge span needs a positive counted pitch interval")
    if len(actual_pin_diameters_mm) != 2:
        raise ValueError("rack gauge span needs two actual certified pin diameters")
    first, second = actual_pin_diameters_mm
    rack_gauge_pin_contact_mm(first)
    rack_gauge_pin_contact_mm(second)
    return pitch_intervals * PITCH + (first + second) / 2.0


def _require_stock_dimension_maximum_mm(
    label: str, measured_maximum_mm: float, uncertainty_mm: float, limit_mm: float
) -> float:
    if not all(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value > 0.0
        for value in (measured_maximum_mm, uncertainty_mm)
    ):
        raise ValueError(f"incoming rack {label} and uncertainty must be finite positive values")
    paid_upper = math.nextafter(math.fsum((measured_maximum_mm, uncertainty_mm)), math.inf)
    if paid_upper > limit_mm:
        raise ValueError(
            f"REJECT incoming rack {label} upper {paid_upper:.6f} mm exceeds "
            f"source maximum {limit_mm:.6f} mm"
        )
    return paid_upper


def require_rack_stock_section_measurements_mm(
    *,
    measured_stock_height_max_mm: float,
    stock_height_measurement_uncertainty_mm: float,
    measured_face_width_max_mm: float,
    face_width_measurement_uncertainty_mm: float,
) -> tuple[float, float]:
    """Receive actual whole-stock height/face extrema with paid calibration.

    Height and face width are separate measurements, not a catalog-square
    equality. Extrema cover the complete stock used; isolated sample readings
    do not supply them. This accepts only section size, NOT product identity,
    flank seating, pitch/index, full-face lead or the loaded assembly.
    """
    return (
        _require_stock_dimension_maximum_mm(
            "stock height", measured_stock_height_max_mm,
            stock_height_measurement_uncertainty_mm, PURCHASED_RACK_HEIGHT_MAX_MM,
        ),
        _require_stock_dimension_maximum_mm(
            "face width", measured_face_width_max_mm,
            face_width_measurement_uncertainty_mm, PURCHASED_RACK_FACE_WIDTH_MAX_MM,
        ),
    )

class RackMeasuredUpperBound(NamedTuple):
    """Certified whole-domain maximum and its positive compound uncertainty.

    Uncertainty includes calibration, datum capture, actual gauge radii and
    any enclosure/model adjustment used by the named inspection method.
    The owning field supplies units; zero is allowed for a measured error,
    never for its uncertainty. These are enclosures, not sample extrema.
    """

    measured_maximum: float
    uncertainty: float


class RackFeatureMapping(NamedTuple):
    """One connected native feature in the common physical stock datum.

    Patches are (u0, u1, v0, v1) rectangles. Each encloses its CONTINUOUS
    domain, with u normalized over the whole native feature and v over the
    actual complete measured face. Never renormalize individual patches.
    Crest indices run 0..N; gap stations identify both flanks and roots.
    The mapping covers the entire material boundary outside the certified
    root envelope. No rack-normal or normal-derivative bound is inferred.
    """

    feature_id: str
    kind: str
    station: int
    start_vertex_id: str
    end_vertex_id: str
    parameter_patches: tuple[tuple[float, float, float, float], ...]
    global_datum_id: str
    native_mapping_ref: str


class RackWireSecantReading(NamedTuple):
    """Wire CENTRE coordinates in the one material XY datum.

    Each positive XY uncertainty is compound method/datum/calibration error,
    not a source instrument floor substituted for an actual calibration.
    The SAME physical wire/entered diameter at both heights has one common
    normal-radius offset, which cancels only under the straight-SIDE MODEL.
    """

    xy_mm: tuple[float, float]
    x_uncertainty_mm: float
    y_uncertainty_mm: float
    wire_id: str
    wire_diameter_mm: float


class RackFlankEnclosure(NamedTuple):
    mapping: RackFeatureMapping
    # Signed X-equivalent errors x +/- tan(PA)*y, NOT unit-normal distance.
    constraint_error_band_mm: tuple[float, float]
    constraint_uncertainty_mm: float
    boundary_mm: RackMeasuredUpperBound
    side_secant: tuple[RackWireSecantReading, RackWireSecantReading]


class RackCrestEnclosure(NamedTuple):
    mapping: RackFeatureMapping
    boundary_mm: RackMeasuredUpperBound


class RackRootEnclosure(NamedTuple):
    mapping: RackFeatureMapping
    # Encloses ALL root material toward the pinion, including transitions.
    intrusion_mm: RackMeasuredUpperBound


class RackFormInspectionReceipt(NamedTuple):
    """External whole-material POINT enclosures, not a point-cloud adapter.

    A qualified extrusion process or actual functional roll must justify
    complete material, both-side intercept and root envelopes over every
    native feature and the complete actual face. A scalar roll result alone
    cannot establish these XY enclosures. The named evidence is a premise,
    not a synthetic vendor certificate or a local rack-normal/C1 bound.
    One independently captured material/fixture/end XY reference applies to
    every station, face and side; even a global flank/pin-seat Y fit is
    forbidden because it can erase uniform tooth-thickness error. Each
    compound uncertainty pays actual calibration, datum, angle/projection,
    gauge diameter, certification and thermal effects above the source
    instrument-only floor. No real receipt is synthesized by this module.
    """

    stock_id: str
    global_datum_id: str
    datum_reference_kind: str
    datum_reference_xy_mm: tuple[float, float]
    method_ref: str
    calibration_ref: str
    trace_ref: str
    whole_point_enclosure_ref: str
    inspection_basis: str
    boundary_partition_ref: str
    native_mapping_ref: str
    parameterization: str
    physical_gap_stations: tuple[int, ...]
    stock_height_mm: RackMeasuredUpperBound
    face_width_mm: RackMeasuredUpperBound
    # Minimum carrying face after ALL actual edge zones; does not crop v.
    measured_usable_face_min_mm: float
    usable_face_measurement_uncertainty_mm: float
    enclosures: tuple[RackFlankEnclosure | RackCrestEnclosure | RackRootEnclosure, ...]


class RackFormAdmissionReport(NamedTuple):
    """Conditional drawn-form conformance, NEVER a hardware/mesh verdict.

    The physical qualifier must still pay root intrusion and prove >=.25 mm
    whole-box separation; root normals are not assumed inactive here.
    Separate index receipts and assembled rigid face/axis alignment remain
    independent obligations. No hardware qualification boolean is returned.
    """

    scope: str
    constraint_relative_mm: float
    active_boundary_mm: float
    root_intrusion_mm: float
    global_datum_id: str
    station_ids: tuple[int, ...]
    feature_ids: tuple[str, ...]
    stock_height_upper_mm: float
    face_width_upper_mm: float
    status_text: str
    usable_face_lower_mm: float
    receipt: RackFormInspectionReceipt
    working_side_form_model_premise: str
    working_side_angle_bands_rad: tuple[tuple[str, tuple[float, float]], ...]


def _rack_receiving_number(value: float, label: str, *, positive: bool = False) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (positive and value <= 0.0)):
        raise ValueError(f"UNKNOWN rack {label}: finite numeric"
                         + (" positive" if positive else "") + " value required")
    return float(value)


def _rack_receiving_reference(value: str, label: str) -> None:
    if (type(value) is not str or not value.strip()
            or value.strip().lower() in {"unknown", "none", "n/a", "todo"}):
        raise ValueError(f"UNKNOWN rack {label}: actual evidence reference required")


def _rack_paid_form_maximum(
    record: RackMeasuredUpperBound, limit: float, label: str, *, minimum_uncertainty: float
) -> float:
    if not isinstance(record, RackMeasuredUpperBound):
        raise ValueError(f"UNKNOWN rack {label}: certified maximum/uncertainty required")
    measured = _rack_receiving_number(record.measured_maximum, label)
    uncertainty = _rack_receiving_number(record.uncertainty, f"{label} uncertainty",
                                         positive=True)
    if uncertainty < minimum_uncertainty:
        raise ValueError(f"UNKNOWN rack {label}: uncertainty below declared shop floor")
    if measured < 0.0:
        raise ValueError(f"UNKNOWN rack {label}: nonnegative maximum required")
    paid = math.nextafter(math.fsum((measured, uncertainty)), math.inf)
    if paid > limit:
        raise ValueError(f"REJECT rack {label}: paid {paid!r} exceeds source {limit!r}")
    return paid


def _require_rack_continuous_coverage(mapping: RackFeatureMapping) -> None:
    """Prove rectangle-union coverage, not a grid/sample-point assertion."""
    patches = mapping.parameter_patches
    if not isinstance(patches, tuple) or not patches:
        raise ValueError("UNKNOWN rack continuous feature/face coverage")
    for patch in patches:
        if not isinstance(patch, tuple) or len(patch) != 4:
            raise ValueError("UNKNOWN rack continuous parameter patch")
        u0, u1, v0, v1 = (
            _rack_receiving_number(value, "parameter patch") for value in patch
        )
        if not (0.0 <= u0 < u1 <= 1.0 and 0.0 <= v0 < v1 <= 1.0):
            raise ValueError("UNKNOWN rack full-native u/full-face v parameter patch")
    u_edges = sorted({0.0, 1.0, *(value for patch in patches for value in patch[:2])})
    for u0, u1 in zip(u_edges, u_edges[1:]):
        intervals = sorted((v0, v1) for a, b, v0, v1 in patches if a <= u0 and b >= u1)
        covered_to = 0.0
        for v0, v1 in intervals:
            if v0 > covered_to:
                break
            covered_to = max(covered_to, v1)
        if covered_to < 1.0:
            raise ValueError("UNKNOWN rack incomplete continuous feature/face coverage")


def require_rack_working_side_secant_angle_band_rad(
    *, readings: tuple[RackWireSecantReading, RackWireSecantReading], flank_kind: str,
) -> tuple[float, float]:
    """Paid secant angle under the named straight/smooth working-SIDE model.

    This backs its conditional angular admission; it never infers arbitrary
    local normals, straightness, roughness or a vendor certificate from pins.
    Both wire centres are in the same native material XY datum, lower then
    upper Y. A common actual radius is NOT corrected twice with nominal wire
    data: its fixed normal-offset vector cancels in the difference.
    """
    from _platen_rack_receiving import feed_rack_working_side_angle_band_rad

    quality.purchased_rack_working_side_form_model_premise()
    if (not isinstance(readings, tuple) or len(readings) != 2
            or any(not isinstance(reading, RackWireSecantReading) for reading in readings)):
        raise ValueError("UNKNOWN rack two typed same-wire centre secant readings")
    if flank_kind not in {"left-flank", "right-flank"}:
        raise ValueError("UNKNOWN rack working-side secant native flank identity")
    for reading in readings:
        _rack_receiving_reference(reading.wire_id, "secant actual wire identity")
        _rack_receiving_number(reading.wire_diameter_mm, "secant actual wire diameter", positive=True)
        if not isinstance(reading.xy_mm, tuple) or len(reading.xy_mm) != 2:
            raise ValueError("UNKNOWN rack secant centre coordinates in the common XY datum")
        for coordinate in reading.xy_mm:
            _rack_receiving_number(coordinate, "secant wire centre coordinate")
        ux = _rack_receiving_number(reading.x_uncertainty_mm, "secant centre X uncertainty", positive=True)
        uy = _rack_receiving_number(reading.y_uncertainty_mm, "secant centre Y uncertainty", positive=True)
        if ux < quality.wire_measurement_uncertainty_mm() or uy < quality.pitch_index_measurement_uncertainty_mm():
            raise ValueError("UNKNOWN rack secant XY uncertainty below source instrument floors")
    lower, upper = readings
    if lower.wire_id != upper.wire_id or lower.wire_diameter_mm != upper.wire_diameter_mm:
        raise ValueError("REJECT rack secant requires SAME physical wire and diameter at both heights")
    dy = math.fsum((upper.xy_mm[1], -lower.xy_mm[1]))
    if dy < quality.rack_flank_secant_minimum_height_mm():
        raise ValueError("REJECT rack measured secant height separation below source minimum")
    sign = -1 if flank_kind == "left-flank" else 1
    dx = sign * math.fsum((upper.xy_mm[0], -lower.xy_mm[0]))
    ux = math.nextafter(math.fsum((lower.x_uncertainty_mm, upper.x_uncertainty_mm)), math.inf)
    uy = math.nextafter(math.fsum((lower.y_uncertainty_mm, upper.y_uncertainty_mm)), math.inf)
    dx_low = math.nextafter(dx - ux, -math.inf)
    dx_high = math.nextafter(dx + ux, math.inf)
    dy_low = math.nextafter(dy - uy, -math.inf)
    dy_high = math.nextafter(dy + uy, math.inf)
    if dx_low <= 0.0 or dy_low <= 0.0:
        raise ValueError("REJECT rack secant uncertainty does not retain native flank/height direction")
    angle = (
        math.nextafter(math.atan2(dx_low, dy_high), -math.inf),
        math.nextafter(math.atan2(dx_high, dy_low), math.inf),
    )
    required = feed_rack_working_side_angle_band_rad()
    if angle[0] < required[0] or angle[1] > required[1]:
        raise ValueError("REJECT rack complete paid secant-angle interval leaves source working-SIDE band")
    return angle


def require_rack_form_admission_mm(
    *, receipt: RackFormInspectionReceipt, required_gap_stations: tuple[int, ...]
) -> RackFormAdmissionReport:
    """Receive the whole finite material envelope at the source shop resolution.

    Corrected pin XY/actual-diameter observations can inform the external
    method, but finite contacts, raw clouds and filtered/C1 booleans cannot
    establish a whole point envelope. Only the explicit process/functional
    evidence and continuous material data above are admitted, including
    every physically manifested station. The report is conditional on
    truthful external evidence, not a claim that purchased stock was measured.
    """
    # Receiving limits are independent of the installed paper-drive geometry.
    # Caller-supplied limits and missing-source nominal fallbacks are not allowed.
    from _platen_rack_receiving import (
        feed_rack_form_admission_controls,
        feed_rack_receiving_boundary_uncertainty_mm,
        feed_rack_receiving_constraint_uncertainty_mm,
        feed_rack_receiving_root_uncertainty_mm,
    )
    from _printed_tolerance import printed_deviations

    controls = feed_rack_form_admission_controls()
    if not isinstance(receipt, RackFormInspectionReceipt):
        raise ValueError("UNKNOWN rack whole-point-envelope inspection receipt")
    stations = required_gap_stations
    if (not isinstance(stations, tuple) or not stations
            or any(type(station) is not int or station < 0 for station in stations)
            or stations != tuple(range(len(stations)))
            or not isinstance(receipt.physical_gap_stations, tuple)
            or any(type(station) is not int for station in receipt.physical_gap_stations)
            or receipt.physical_gap_stations != stations):
        raise ValueError("UNKNOWN rack complete physical gap-station manifest")
    # Cut phase is uncontrolled. Two pitch end strips and one complete-feature
    # span give this conservative necessary count, NOT the nominal CAD count.
    minimum_length = CUT_LENGTH_MM + printed_deviations(
        CUT_LENGTH_MM, DRAWING_PRECISION_BY_NAME["Length"], unit=UNIT
    )[0]
    minimum_count = math.floor(minimum_length / PITCH) - 3
    if len(stations) < minimum_count:
        raise ValueError("UNKNOWN rack sample-only manifest cannot cover the finite stock")
    for field in (
        "stock_id", "global_datum_id", "method_ref", "calibration_ref", "trace_ref",
        "whole_point_enclosure_ref", "boundary_partition_ref", "native_mapping_ref",
    ):
        _rack_receiving_reference(getattr(receipt, field), field)
    if receipt.inspection_basis not in {"qualified-extrusion-process", "actual-functional-roll"}:
        raise ValueError("UNKNOWN rack whole-point process/functional evidence basis")
    if receipt.datum_reference_kind not in {"independent-material", "independent-fixture",
                                            "independent-end"}:
        raise ValueError("UNKNOWN rack independent global XY datum; no flank/pin fitting")
    if (not isinstance(receipt.datum_reference_xy_mm, tuple)
            or len(receipt.datum_reference_xy_mm) != 2):
        raise ValueError("UNKNOWN rack actual global XY datum coordinates")
    for value in receipt.datum_reference_xy_mm:
        _rack_receiving_number(value, "global XY datum coordinate")
    if receipt.parameterization != "full-native-u/full-actual-face-v":
        raise ValueError("UNKNOWN rack whole-native/whole-face parameterization")
    if not isinstance(receipt.stock_height_mm, RackMeasuredUpperBound) or not isinstance(
        receipt.face_width_mm, RackMeasuredUpperBound
    ):
        raise ValueError("UNKNOWN rack separate actual stock section receipts")
    height, width = require_rack_stock_section_measurements_mm(
        measured_stock_height_max_mm=receipt.stock_height_mm.measured_maximum,
        stock_height_measurement_uncertainty_mm=receipt.stock_height_mm.uncertainty,
        measured_face_width_max_mm=receipt.face_width_mm.measured_maximum,
        face_width_measurement_uncertainty_mm=receipt.face_width_mm.uncertainty,
    )
    usable_face = _rack_receiving_number(receipt.measured_usable_face_min_mm,
                                         "actual usable face minimum", positive=True)
    usable_uncertainty = _rack_receiving_number(
        receipt.usable_face_measurement_uncertainty_mm, "usable face uncertainty", positive=True
    )
    usable_lower = math.nextafter(math.fsum((usable_face, -usable_uncertainty)), -math.inf)
    usable_upper = math.nextafter(math.fsum((usable_face, usable_uncertainty)), math.inf)
    if usable_lower <= 0.0 or usable_upper > width:
        raise ValueError("UNKNOWN rack nonempty calibrated whole usable face after edge zones")
    expected = {
        *((kind, station) for station in stations for kind in ("left-flank", "right-flank", "root")),
        *(("crest", index) for index in range(len(stations) + 1)),
    }
    if not isinstance(receipt.enclosures, tuple) or not receipt.enclosures:
        raise ValueError("UNKNOWN rack full feature enclosures")
    by_feature = {}
    feature_ids = set()
    constraint_lows, constraint_highs = [], []
    maxima = {"active_boundary_mm": 0.0, "root_intrusion_mm": 0.0}
    side_angle_bands = []
    boundary_uncertainty_floor = feed_rack_receiving_boundary_uncertainty_mm()
    constraint_uncertainty_floor = feed_rack_receiving_constraint_uncertainty_mm()
    root_uncertainty_floor = feed_rack_receiving_root_uncertainty_mm()
    for enclosure in receipt.enclosures:
        if not isinstance(enclosure, (RackFlankEnclosure, RackCrestEnclosure, RackRootEnclosure)):
            raise ValueError("UNKNOWN rack typed complete feature enclosure")
        mapping = enclosure.mapping
        if not isinstance(mapping, RackFeatureMapping) or type(mapping.station) is not int:
            raise ValueError("UNKNOWN rack connected native feature mapping")
        for field in ("feature_id", "start_vertex_id", "end_vertex_id", "global_datum_id",
                      "native_mapping_ref"):
            _rack_receiving_reference(getattr(mapping, field), field)
        if (mapping.global_datum_id != receipt.global_datum_id
                or mapping.native_mapping_ref != receipt.native_mapping_ref):
            raise ValueError("UNKNOWN rack per-feature datum/refit is forbidden")
        key = (mapping.kind, mapping.station)
        if (key not in expected or key in by_feature or mapping.feature_id in feature_ids
                or mapping.start_vertex_id == mapping.end_vertex_id):
            raise ValueError("UNKNOWN rack duplicate/unexpected/disconnected feature")
        if ((isinstance(enclosure, RackFlankEnclosure)
             and mapping.kind not in {"left-flank", "right-flank"})
                or (isinstance(enclosure, RackCrestEnclosure) and mapping.kind != "crest")
                or (isinstance(enclosure, RackRootEnclosure) and mapping.kind != "root")):
            raise ValueError("UNKNOWN rack feature type disagrees with native mapping")
        _require_rack_continuous_coverage(mapping)
        by_feature[key] = mapping
        feature_ids.add(mapping.feature_id)
        if isinstance(enclosure, RackRootEnclosure):
            paid = _rack_paid_form_maximum(
                enclosure.intrusion_mm, controls["root_intrusion_mm"],
                "whole root-material intrusion",
                minimum_uncertainty=root_uncertainty_floor,
            )
            maxima["root_intrusion_mm"] = max(maxima["root_intrusion_mm"], paid)
            continue
        paid = _rack_paid_form_maximum(
            enclosure.boundary_mm, controls["active_boundary_mm"],
            "whole active material point boundary",
            minimum_uncertainty=boundary_uncertainty_floor,
        )
        maxima["active_boundary_mm"] = max(maxima["active_boundary_mm"], paid)
        if isinstance(enclosure, RackFlankEnclosure):
            side_angle_bands.append((
                mapping.feature_id,
                require_rack_working_side_secant_angle_band_rad(
                    readings=enclosure.side_secant, flank_kind=mapping.kind,
                ),
            ))
            band = enclosure.constraint_error_band_mm
            if not isinstance(band, tuple) or len(band) != 2:
                raise ValueError("UNKNOWN rack both-flank signed constraint enclosure")
            low, high = (_rack_receiving_number(value, "flank constraint") for value in band)
            if low > high:
                raise ValueError("UNKNOWN rack ordered flank constraint enclosure")
            uncertainty = _rack_receiving_number(enclosure.constraint_uncertainty_mm,
                                                 "flank constraint uncertainty", positive=True)
            if uncertainty < constraint_uncertainty_floor:
                raise ValueError("UNKNOWN rack flank constraint uncertainty below declared shop floor")
            constraint_lows.append(math.nextafter(math.fsum((low, -uncertainty)), -math.inf))
            constraint_highs.append(math.nextafter(math.fsum((high, uncertainty)), math.inf))
    if set(by_feature) != expected:
        raise ValueError("UNKNOWN rack missing either flank/crest/root or physical station")
    chain = [by_feature[("crest", 0)]]
    for index, station in enumerate(stations):
        chain.extend((by_feature[("left-flank", station)], by_feature[("root", station)],
                      by_feature[("right-flank", station)], by_feature[("crest", index + 1)]))
    if any(first.end_vertex_id != second.start_vertex_id
           for first, second in zip(chain, chain[1:])):
        raise ValueError("UNKNOWN rack full native boundary partition is disconnected")
    vertices = (chain[0].start_vertex_id, *(mapping.end_vertex_id for mapping in chain))
    if len(set(vertices)) != len(vertices):
        raise ValueError("UNKNOWN rack boundary mapping loops or refits features")
    relative = math.nextafter(math.fsum((max(constraint_highs), -min(constraint_lows))), math.inf)
    if relative > controls["constraint_relative_mm"]:
        raise ValueError("REJECT rack BOTH-flank relative constraint range exceeds source")
    return RackFormAdmissionReport(
        "whole-point-envelope", relative, maxima["active_boundary_mm"],
        maxima["root_intrusion_mm"],
        receipt.global_datum_id, stations, tuple(mapping.feature_id for mapping in chain),
        height, width, controls["status_text"], usable_lower, receipt,
        controls["working_side_form_model_premise"], tuple(side_angle_bands),
    )


GAP_AREA = (half_width(ROOT_Y) + half_width(RACK_HEIGHT)) * (RACK_HEIGHT - ROOT_Y)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Length", "RackHeight"},
    "Bar": {"RackDepth"},
    "TapStations": {
        "TapStart",
        "TapStation2",
        "TapStation3",
        "TapStation4",
        "TapFromFront",
    },
}
# The cut length serves no fit but bounds the operating window
# (paper_drive_rack_travel), so it prints .XX. The purchased 3/16 strip's
# height and face width print their exact decimals as plain references
# (#2694, #2147): the receiving geometry has room for any ordinary strip.
# Each tap stands on its own tooth centre to the .XXX band. The cut ends'
# tooth phase is not controlled, so the first tap's station from the cut end
# prints .XX with its plain-step window (TAP_START_BAND), inside which the
# builder drills a tooth centre; the other three are whole pitches from the
# first tap, printed .XXX on the title block's band (machinist review r7-r9:
# rule 26, a location is a dimension, not a sentence; rule 4, a plain inch
# step). The tap's place across the strip is drilled to the title block's .XXX.
_PLACES = {
    "Length": 2,
    "RackDepth": 4,
    "RackHeight": 4,
    "TapStart": 2,
    "TapStation2": TAP_PLACES,
    "TapStation3": TAP_PLACES,
    "TapStation4": TAP_PLACES,
    "TapFromFront": TAP_PLACES,
}
DRAWING_PRECISION = {
    feature: {name: _PLACES[name] for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
# The sizes the builder tolerances itself (swTolSYMMETRIC); every other
# printed size takes the title block's band or prints as a reference.
DRAWING_SYMMETRIC_BANDS_MM = {"TapStart": TAP_START_BAND}
DRAWING_REFERENCE_DIMENSIONS = frozenset({"RackDepth", "RackHeight"})
DRAWING_NOMINALS_MM = {
    "Length": BAR_LENGTH,
    "RackDepth": RACK_THICKNESS,
    "RackHeight": RACK_HEIGHT,
    "TapStart": TAP_X[0],
    "TapStation2": TAP_X[1] - TAP_X[0],
    "TapStation3": TAP_X[2] - TAP_X[0],
    "TapStation4": TAP_X[3] - TAP_X[0],
    "TapFromFront": TAP_Z,
}
# The tap callout's drill Ø and both depths print .XXX, the band the tooth
# and engagement stacks above are paid at.
TAP_CALLOUT_PRECISION = {
    "hw-tapdrldia": TAP_PLACES,
    "hw-threaddepth": TAP_PLACES,
    "hw-tapdrldepth": TAP_PLACES,
}


# The purchase identity defines the teeth; no finite form-cutter alternative.
PURCHASED_RACK_NOTE = (
    f"PURCHASED RACK: {PURCHASED_RACK_SUPPLIER} {PURCHASED_RACK_SKU}; "
    f"{PURCHASED_RACK_LENGTH_IN:g} IN"
)
# The material is the title block's; the note does not repeat it.
GEAR_DATA = f"{PURCHASED_RACK_NOTE}; {DP:g} DP, {PA_DEG:g}\N{DEGREE SIGN} PA"
# A purchased rack is received by its catalogue identity and (.1875) REF
# sizes; its pitch accuracy is the catalogue part's, checked only by the
# running mesh at assembly. The two stock sizes print as plain (.1875) REF
# with no receiving limit (#2694).
DRAWING_NOTES = "END TOOTH PHASE NOT CONTROLLED"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
# The *Right view: the front view's right end (machinist review round 6 on
# the retired MHA-PD-05: "END VIEW" named no end).
ENLARGED_END_VIEW_NOTE = "ENLARGED RIGHT END VIEW SCALE 4:1"
