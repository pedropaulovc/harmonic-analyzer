r"""Pure-data dimensional contract shared by the crank-drive gear and its drawing.

The dark steel 64T gear at the cone set's large end; its straight teeth,
inclined to its axis, carry the crossed-axis accommodation for its straight
16T crank pinion mate (4:1 crank-to-cone reduction).

Recreated under ``cad/docs/drawing-guidelines.md``. The six blank,
bore and entry sizes -- outside diameter, face width, round bore, keyway
width and T, and south bore chamfer -- are NATIVE model dimensions carrying
their own decimal places and, where a mate needs one, their own bands; the
tooth system a cut-gear print cannot express as dimensions stays in the
gear-data block drawing-guidelines.md rule 7 (notes: few, flagged, never a
method) allows, with every generating number marked REF.

PURE DATA, no SolidWorks/COM imports: ``build_dt_crank_drive_gear`` marks and
tolerances exactly ``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model,
``draw_dt_crank_drive_gear`` keeps exactly the same names, and the offline test
(``test_dt_crank_drive_gear_drawing.py``) fails the moment one side drifts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import cone_land_key
import cone_line
from gear_face_band import GEAR_FACE_WIDTH_BAND
import cone_shaft_land_bands
import gear_seat_fit
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm, printed_deviations
from _surface_finish import SurfaceFinishControl
from stock_form_cutter import (
    StockFormProfile,
    template_for_teeth,
    translation_for_pitch_tooth_thickness,
    translation_for_tangent_span,
)
from gear_seat_fit import GEAR_SEAT_CLEARANCE, seat_bore_band
from straight_gash import StraightGash, midface_gap_azimuth_rad


MM_PER_IN = 25.4
# #290: the registry row's drawing_unit (in) is this sheet's unit; the bands,
# places and gear-data text below are authored for it.
UNIT = drawing_unit("parts/dt-crank-drive-gear", _config.parts("dt-crank-drive-gear"))


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.375``, ``2.797``."""
    text = f"{value_mm / MM_PER_IN:.{places}f}"
    return text[1:] if text.startswith("0.") else text.replace("-0.", "-.")


def floor_inch_mm(value_mm: float, places: int) -> float:
    """``value_mm`` floored to the ``places``-place inch grid, in mm."""
    scale = 10.0**places
    return round(math.floor(round(value_mm / MM_PER_IN * scale, 6)) / scale * MM_PER_IN, 9)


TEETH = 64

# Straight teeth inclined to the 64T's axis by the actual cone-shaft incline,
# right hand (owner ruling 2026-11-10 on #2332, option A, superseding the
# true-helix tooth): its straight 16T mate shares the configured normal-pitch
# cutter system, and the crossing is the cone incline because the crankshaft
# stays parallel to the cylinders.
TOOTH_INCLINATION_DEG = cone_line.INCLINE_DEG

# Face width.  The v36 MHA-DT-05 casting is restored: its crank boss's north
# face is the collar's tangent plane again, so the 64T's SOUTH face -- seated
# on MHA-DT-04's thrust collar -- stays where the #1126 ruling put it, 1.5 north
# of the 8.0 face the 19.9 station was laid out on (crank_boss_rim holds every
# MHA-DT-05 north feature off it).  The cone set is a solid stack (user ruling
# 2026-09-28, dt_cone_gear_stack): the 64T grows NORTH until it bears on T120's
# grown south face, so its face is the gap between the collar and T120,
# floored to four mm places (a stack closure that T120's face meets exactly,
# so it is not snapped to the inch grid; the sheet prints it rounded at four
# inch places).  dt_cone_gear_stack pins the two faces together.  The band is
# +/-.001 in about the PRINTED .XXXX: FACE_WIDTH_BAND is that band's limits as
# deviations from the model, the form every stack reads.
LAYOUT_REFERENCE_FACE_WIDTH = 10.0
LAYOUT_CENTRE_STATION = (
    cone_line.SHAFT_T120_STATION
    - (cone_line.CONE_FACE_STATION_REFERENCE + LAYOUT_REFERENCE_FACE_WIDTH) / 2.0
    - 0.1
)
LAYOUT_FACE_WIDTH = 8.0
SOUTH_FACE_SHIFT_NORTH = 1.5
FACE_WIDTH = round(
    cone_line.SHAFT_T120_STATION
    + cone_line.CONE_FACE_STATION_REFERENCE / 2.0
    - math.floor(cone_line.SEAT_PITCH * 1e4) / 1e4
    - (LAYOUT_CENTRE_STATION - LAYOUT_FACE_WIDTH / 2.0 + SOUTH_FACE_SHIFT_NORTH),
    4,
)
FACE_WIDTH_PLACES = 4
_face_lower, _face_upper = printed_deviations(
    FACE_WIDTH,
    FACE_WIDTH_PLACES,
    (GEAR_FACE_WIDTH_BAND[1], GEAR_FACE_WIDTH_BAND[0]),  # +/-.001 in, the cone gears' own
    unit=UNIT,
)
FACE_WIDTH_BAND = (_face_upper, _face_lower)  # (upper, lower), printed limits
# The centre sits CENTRE_SHIFT_NORTH north of the 19.9 layout station.
CENTRE_SHIFT_NORTH = SOUTH_FACE_SHIFT_NORTH + (FACE_WIDTH - LAYOUT_FACE_WIDTH) / 2.0
if not LAYOUT_FACE_WIDTH - SOUTH_FACE_SHIFT_NORTH < FACE_WIDTH < LAYOUT_FACE_WIDTH:
    raise AssertionError(
        f"64T face {FACE_WIDTH} must grow past the #1126 6.5 face "
        f"and stay inside the {LAYOUT_FACE_WIDTH} layout face"
    )

# Both gears use the same standard normal-pitch/pressure-angle system.
# Form milling uses a 14--16T cutter for the straight pinion and a
# 55--134 virtual-tooth cutter for the inclined 64T (z/cos(beta)^3: the
# normal section's pitch-point curvature is the same as a helix's).
NORMAL_MODULE_MM = _config.machine("gear_train", "crank_drive_normal_module_mm")
_COS_INCLINE = math.cos(math.radians(TOOTH_INCLINATION_DEG))
CUTTER_DIAMETRAL_PITCH = MM_PER_IN / NORMAL_MODULE_MM
CUTTER_PRESSURE_ANGLE_DEG = _config.machine(
    "gear_train", "crank_drive_pressure_angle_deg"
)
DIAMETRAL_PITCH = CUTTER_DIAMETRAL_PITCH * _COS_INCLINE
PRESSURE_ANGLE_DEG = math.degrees(
    math.atan(math.tan(math.radians(CUTTER_PRESSURE_ANGLE_DEG)) / _COS_INCLINE)
)
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH  # transverse
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
# The finite #2 master retains standard normal root placement. The actual
# blank is turned down to support every published manufacturing corner.
DEDENDUM_FACTOR = 1.25

# Hand: the tooth azimuth advances counter-clockwise about +z as z increases
# (straight_gash: the tooth line d = cos(beta) z + sin(beta) t), a RIGHT-hand
# tooth. It is the one tooth-system fact a mirrored part would get wrong, so
# the data block states it in words.
TOOTH_HAND = "RIGHT HAND"

# Form-cutter selection uses the inclined teeth's equivalent normal-section
# tooth count, not their physical count.
CUTTER_TEMPLATE = template_for_teeth(
    TEETH / _COS_INCLINE**3, CUTTER_DIAMETRAL_PITCH, CUTTER_PRESSURE_ANGLE_DEG
)
CUTTER_NUMBER = CUTTER_TEMPLATE.cutter_number
CUTTER_TEETH_RANGE = CUTTER_TEMPLATE.teeth_range
VIRTUAL_TEETH = TEETH / _COS_INCLINE**3
# The inclination prints in the gear data at one place under the title
# block's +/-1 deg, as the helix angle did. A setting error d(beta) shifts the
# 64T normal pitch by p_t sin(beta) d(beta), 0.013 mm at 1 deg, and across the
# face turns the tooth line against the 16T about the crossing station. The
# +/-1 deg is kept (decision 2026-11-11 on #2481, option T): MESH_THINNING_MM
# below pays for it, and crank_mesh_free_play gates the print-worst corner at
# these limits.
TOOTH_INCLINATION_TOLERANCE_DEG = 1.0
TOOTH_INCLINATION_PLACES = 1
GEAR_DATA_REFERENCE_PLACES = 3

# The blank's outside diameter is the one tooth-system number the turner sets
# before a cutter touches the part, so it prints as a NATIVE dimension instead
# of as text in the data block.  The user ruled +/-0.10 on both gears' tips
# (2026-09-26, #906), held with a micrometer before cutting, as on the cone
# gears' blanks.  The mesh runs at a fixed centre with no adjustment (user
# ruling 2026-09-28): ``crank_mesh_stack`` books this band as the tip-to-root
# term of its closing corner (TIP_ROOT_BAND_RADIAL), and crank_boss_rim grows
# the tip by half of it toward MHA-DT-05.  #290: +/-.004 in.
OUTSIDE_DIA_TOLERANCE_MM = 0.1016
OUTSIDE_DIA_PLACES = 3
# Critical tooth-cutting setup, indicated to the finished bore. This process
# limit is shared by both shop gears; it is not an AGMA/form accuracy class.
TOOTH_RUNOUT_TIR_MM = _config.fit("crank_mesh", "tooth_cutting_runout_tir_mm")
# Native fidelity bound for the cut tooth space (_straight_gash_gear's flank probe), NOT a
# machining band. Bore TIR allows TIR/2 radial eccentricity; the equation-
# curve profile's numerical sag may use one tenth of that, TIR/20 (0.0025 mm
# at the configured 0.05 TIR). A wrong hand, inclination, crossing or seed
# moves a three-quarter-face flank by tenths of a millimetre or more, so
# detection holds.
NATIVE_FLANK_BOUND_MM = TOOTH_RUNOUT_TIR_MM / 20.0

# Geometry selection is finite-support-qualified, not a crossed-mesh certificate.
# The cutting band is about the STANDARD-depth thickness (cutter reference
# pitch line on the gear's pitch circle). It is thin-only (Main ruling
# 2026-10-10) so the fixed-centre closing corner keeps positive backlash; the
# part is modelled at the band's maximum-material limit, the 16T's convention.
#
# MESH_THINNING_MM moves both ends of that band thinner (normal circular):
# the same #2 cutter sunk deeper on the same setup, accepted on the printed
# span over BASE_TANGENT_SPAN_TEETH teeth, with the blank turned down to the
# deeper cutter's reach by the OUTSIDE_DIA rule below. Decision 2026-11-11 on
# #2481 (option T) keeps the title block's +/-1 deg on the tooth line and pays
# for it here. The value is derived, not chosen: test_crank_mesh_free_play
# holds it at the least MESH_THINNING_STEP_MM step that leaves the print-worst
# corner crank_mesh_free_play.MARGIN_MM clear in both tooth models, so a pitch,
# centre or face change fails there with the re-derived value. 0 reverses it.
#
# The printed tooth numbers (thickness, span, root, plunge, tip support) are
# read from the cutter's normal-section SCREW model at the inclination
# (StockFormProfile's helix_angle_deg): at the crossing station the straight
# tooth space below IS that normal section, and its transverse section there
# differs from the screw model's by under 3 um (test_straight_gash), inside the
# span's .0001 in printing grid.
CUTTING_BAND_DEVIATIONS = tuple(
    _config.fit("crank_mesh", "gear64_tooth_thickness_deviations_mm")
)
MESH_THINNING_MM = _config.fit("crank_mesh", "gear64_mesh_thinning_mm")
MESH_THINNING_STEP_MM = 0.01
_STANDARD_TRANSLATION_MM = PITCH_DIA / 2.0 - CUTTER_TEMPLATE.pitch_radius_mm
STANDARD_TRANSVERSE_TOOTH_THICKNESS = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, _STANDARD_TRANSLATION_MM, TOOTH_INCLINATION_DEG
).pitch_tooth_thickness_mm
BASE_TANGENT_SPAN_TEETH = math.floor(TEETH * CUTTER_PRESSURE_ANGLE_DEG / 180.0 + 0.5)
BASE_TANGENT_SPAN_PLACES = 4
_SPAN_SCALE = 10**BASE_TANGENT_SPAN_PLACES


@dataclass(frozen=True)
class ToothBand:
    """The printed tooth-thickness band for one mesh thinning."""

    deviations: tuple[float, float]  # (upper, lower), transverse, about standard depth
    span_limits_mm: tuple[float, float]  # printed, (lower, upper)
    translation_limits_mm: tuple[float, float]  # the span limits' tool translations
    outside_dia: float  # the printed blank, floored to its .001 in grid


def tooth_band(mesh_thinning_mm: float) -> ToothBand:
    """The cutting band moved ``mesh_thinning_mm`` (normal circular) thinner,
    with the span limits and blank the sheet prints for it."""
    deviations = tuple(
        deviation - mesh_thinning_mm / _COS_INCLINE for deviation in CUTTING_BAND_DEVIATIONS
    )
    raw_translations = tuple(
        translation_for_pitch_tooth_thickness(
            TEETH, CUTTER_TEMPLATE, STANDARD_TRANSVERSE_TOOTH_THICKNESS + deviation,
            TOOTH_INCLINATION_DEG,
        )
        for deviation in reversed(deviations)
    )
    raw_spans = tuple(
        StockFormProfile(TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, value, TOOTH_INCLINATION_DEG)
        .tangent_span_mm(BASE_TANGENT_SPAN_TEETH, normal_plane=True)
        for value in raw_translations
    )
    # Both ends rounded UP onto the inch grid the sheet prints them at: the
    # lower end inward (an accepted part keeps the source's thinnest tooth),
    # the upper end outward so the modelled nominal -- the source's thickest
    # tooth -- stays inside the printed acceptance.
    span_limits = tuple(
        math.ceil(round(span / MM_PER_IN * _SPAN_SCALE, 6)) / _SPAN_SCALE * MM_PER_IN
        for span in (min(raw_spans), max(raw_spans))
    )
    # The extra search bracket is numerical only; the printed span endpoints,
    # not this bracket, define the actual accepted tool-translation interval.
    bracket = (
        min(raw_translations) - NORMAL_MODULE_MM / 100.0,
        max(raw_translations) + NORMAL_MODULE_MM / 100.0,
    )
    translation_limits = tuple(
        translation_for_tangent_span(
            TEETH, CUTTER_TEMPLATE, span, BASE_TANGENT_SPAN_TEETH, TOOTH_INCLINATION_DEG,
            translation_bounds_mm=bracket,
        )
        for span in span_limits
    )
    # Floored to the .001 in grid it prints at, so the printed size is the model.
    outside_dia = floor_inch_mm(
        2.0 * min(
            StockFormProfile(
                TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, value, TOOTH_INCLINATION_DEG
            ).support_radius_max_mm
            for value in translation_limits
        )
        - OUTSIDE_DIA_TOLERANCE_MM,
        OUTSIDE_DIA_PLACES,
    )
    return ToothBand(deviations, span_limits, translation_limits, outside_dia)


def profile_corners(band: ToothBand) -> tuple[tuple[str, StockFormProfile], ...]:
    """Every printed span and outside-diameter corner of ``band``."""
    return tuple(
        (
            f"span {span_side}, outside diameter {od_side}",
            StockFormProfile(
                TEETH, CUTTER_TEMPLATE, (band.outside_dia + od_deviation) / 2.0,
                translation, TOOTH_INCLINATION_DEG,
            ),
        )
        for span_side, translation in zip(("lower", "upper"), band.translation_limits_mm)
        for od_side, od_deviation in (
            ("lower", -OUTSIDE_DIA_TOLERANCE_MM), ("upper", OUTSIDE_DIA_TOLERANCE_MM)
        )
    )


TOOTH_BAND = tooth_band(MESH_THINNING_MM)
TOOTH_THICKNESS_DEVIATIONS = TOOTH_BAND.deviations
STOCK_TOOL_TRANSLATION_MM = translation_for_pitch_tooth_thickness(
    TEETH, CUTTER_TEMPLATE,
    STANDARD_TRANSVERSE_TOOTH_THICKNESS + max(TOOTH_THICKNESS_DEVIATIONS),
    TOOTH_INCLINATION_DEG,
)
_PITCH_PROBE = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, STOCK_TOOL_TRANSLATION_MM, TOOTH_INCLINATION_DEG
)
TRANSVERSE_CIRCULAR_TOOTH_THICKNESS = _PITCH_PROBE.pitch_tooth_thickness_mm
BASE_TANGENT_SPAN_MM = _PITCH_PROBE.tangent_span_mm(
    BASE_TANGENT_SPAN_TEETH, normal_plane=True
)
BASE_TANGENT_SPAN_LIMITS_MM = TOOTH_BAND.span_limits_mm
STOCK_TOOL_TRANSLATION_LIMITS_MM = TOOTH_BAND.translation_limits_mm
OUTSIDE_DIA = TOOTH_BAND.outside_dia
STOCK_PROFILE = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, OUTSIDE_DIA / 2.0, STOCK_TOOL_TRANSLATION_MM, TOOTH_INCLINATION_DEG
)
ROOT_DIA_MIN = 2.0 * STOCK_PROFILE.root_radius_min_mm
ROOT_DIA_MAX = 2.0 * STOCK_PROFILE.root_radius_max_mm
ROOT_DIA = ROOT_DIA_MIN
WHOLE_DEPTH = STOCK_PROFILE.blank_radius_mm - STOCK_PROFILE.root_radius_min_mm
TOOL_PLUNGE_MM = STOCK_PROFILE.plunge_mm

# The straight tooth space (straight_gash). Each space is exactly the
# cutter's form where the cutter's centre plane crosses the blank axis,
# TOOTH_SPACE_CROSSING north of the SOUTH (collar, z = 0) face; elsewhere it
# leans against the screw model by (1 - rho/R) of its tangential shift, zero
# on the pitch circle. The 16T bears on the south edge: the layout closes the
# centre toward the south face, where the axes cross in plan
# (crank_mesh_stack.centre_at_station). Exact anywhere from
# mid-face to the south face keeps that edge within the helix's mesh; the
# station is the middle of that range, a quarter face north of the collar
# face (equally, a quarter face toward it from mid-face), on the .XX grid the
# gear data prints, whose title-block band keeps it inside the range.
TOOTH_SPACE_CROSSING_PLACES = 2
TOOTH_SPACE_CROSSING = (
    round(FACE_WIDTH / 4.0 / MM_PER_IN, TOOTH_SPACE_CROSSING_PLACES) * MM_PER_IN
)
_CROSSING_ROW = printed_band_mm(TOOTH_SPACE_CROSSING_PLACES, unit=UNIT)
if not 0.0 < TOOTH_SPACE_CROSSING - _CROSSING_ROW < TOOTH_SPACE_CROSSING + _CROSSING_ROW < FACE_WIDTH / 2.0:
    raise AssertionError("the tooth-space crossing band leaves the south half-face")
# The cutter form in its own plane, reaching 0.05 mm past the tip so every
# normal-section point the blank cylinder can hold is cutter form
# (StraightGash.removed_volume_mm3 refuses otherwise); the tip support stays
# 0.19 mm beyond that.
TOOTH_SPACE_FORM = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, OUTSIDE_DIA / 2.0 + 0.05, STOCK_TOOL_TRANSLATION_MM, 0.0
)
# The seed space is clocked so a TOOTH is centred on +X on the pitch circle at
# mid-face, the authored phase the assembly meshes the 16T against.
TOOTH_SPACE = StraightGash(
    TOOTH_INCLINATION_DEG,
    TOOTH_SPACE_CROSSING,
    midface_gap_azimuth_rad(
        TEETH, PITCH_DIA / 2.0, TOOTH_INCLINATION_DEG, TOOTH_SPACE_CROSSING, FACE_WIDTH
    ),
    FACE_WIDTH,
    OUTSIDE_DIA / 2.0,
)


def stock_profile(
    *, outside_dia_mm: float | None = None, tooth_thickness_mm: float | None = None
) -> StockFormProfile:
    """Actual finite normal-tool form; thickness selects total radial translation."""
    translation = (
        STOCK_TOOL_TRANSLATION_MM if tooth_thickness_mm is None
        else translation_for_pitch_tooth_thickness(
            TEETH, CUTTER_TEMPLATE, tooth_thickness_mm, TOOTH_INCLINATION_DEG
        )
    )
    return StockFormProfile(
        TEETH, CUTTER_TEMPLATE,
        (OUTSIDE_DIA if outside_dia_mm is None else outside_dia_mm) / 2.0,
        translation, TOOTH_INCLINATION_DEG,
    )


STOCK_PROFILE_CORNERS = profile_corners(TOOTH_BAND)

# The Ø9.525 MHA-DT-04 land-1 gear seat. This shared spec owns its nominal,
# round slide-fit clearance and the 1/16 keyway's numbers without pulling the
# part builder into drawing recipes.
BORE_DIA = 0.375 * MM_PER_IN  # 9.525
if abs(BORE_DIA - cone_land_key.LAND_DIA_MM) > 1e-9:
    raise AssertionError("the 64T bore no longer matches the keyed land 1")

# A printable slide fit on the land-1 gear seat. BoreDia sets radial runout;
# the key in the +X keyway (owner decision C1 keyed, 2026-11-09, PR #1992)
# carries the drive. No joining compound is involved.
_LAND_UPPER, _LAND_LOWER = cone_shaft_land_bands.SECTION_DIA_BANDS[1]
if (_LAND_UPPER, _LAND_LOWER) != cone_shaft_land_bands.GEAR_SEAT_BAND:
    raise AssertionError("the 64T no longer rides a gear-seat land")
BORE_DIA_BAND = seat_bore_band(cone_shaft_land_bands.GEAR_SEAT_BAND)
BORE_DIAMETRAL_CLEARANCE = (
    round(BORE_DIA_BAND[1] - _LAND_UPPER, 6),
    round(BORE_DIA_BAND[0] - _LAND_LOWER, 6),
)
if BORE_DIAMETRAL_CLEARANCE != GEAR_SEAT_CLEARANCE:
    raise AssertionError("64T bore lost its round slide-fit clearance")

# One broached 1/16 keyway on local +X, the clock the retired D-flat held,
# for the MHA-DT-VN-71 key in MHA-DT-04's land-1 keyseat. Width and T (top to
# the bore's far side, ANSI B17.1) come from cone_land_key; the 64T forks none.
KEYWAY_WIDTH = cone_land_key.KEYWAY_WIDTH_MM
KEYWAY_WIDTH_BAND = cone_land_key.KEYWAY_WIDTH_BAND
KEYWAY_T = cone_land_key.KEYWAY_T_MM
KEYWAY_T_BAND = cone_land_key.KEYWAY_T_BAND
KEYWAY_PLACES = cone_land_key.KEYWAY_PLACES
# The keyway top's nominal distance from the bore axis, on +X.
KEYWAY_TOP_OFFSET = cone_land_key.keyway_top_offset_mm(BORE_DIA)

# Web under the keyway: the keyway's top corner at its print limits against
# the minimum root circle. Rule 17 books .080 in as the web target.
WEB_TARGET_MM = 0.080 * MM_PER_IN
KEYWAY_CORNER_RADIUS_MAX = cone_land_key.hub_keyway_corner_radius_max_mm(
    BORE_DIA + BORE_DIA_BAND[1]
)
KEYWAY_WEB_MIN = ROOT_DIA_MIN / 2.0 - KEYWAY_CORNER_RADIUS_MAX
if KEYWAY_WEB_MIN < WEB_TARGET_MM:
    raise AssertionError(
        f"64T web over the keyway {KEYWAY_WEB_MIN:.4f} mm is under the "
        f"{WEB_TARGET_MM:.4f} mm rule-17 target"
    )

# MHA-DT-04's land-1 root into its thrust collar, mirrored here because
# dt_cone_gear_shaft_spec imports this gear (an import here would cycle); the
# offline drawing test cross-checks it against COLLAR_ROOT_RADIUS_MAX.
_SHAFT_COLLAR_ROOT_RADIUS_MAX = 0.0508  # .002
# The south bore entry clears that root so the south face seats flat on the
# collar. It needs no band of its own: the title block's .XX band alone keeps
# the chamfer's minimum clear of the root (machinist review r1 of #1641: a
# 1.00 +0.10/0 leg read as a tight band with no named mate; rule 4 (tighten
# only for function, and name the mate) and the owner's standing preference
# to move the nominal rather than print a tight band). The keyway breaks
# through the chamfer on +X; the key ends KEY_END_SET short of the collar.
BORE_SOUTH_CHAMFER = 1.524  # .06
BORE_SOUTH_CHAMFER_PLACES = 2
# The limits a part accepted against the printed leg may show: the general
# .XX row read at the places the leg prints. Not a fit band (the part
# authors no tolerance on the leg), so plain limits, not a band tuple.
_CHAMFER_ROW = printed_band_mm(BORE_SOUTH_CHAMFER_PLACES, unit=UNIT)
BORE_SOUTH_CHAMFER_MIN = BORE_SOUTH_CHAMFER - _CHAMFER_ROW
BORE_SOUTH_CHAMFER_MAX = BORE_SOUTH_CHAMFER + _CHAMFER_ROW
if BORE_SOUTH_CHAMFER_MIN <= _SHAFT_COLLAR_ROOT_RADIUS_MAX:
    raise AssertionError("the south bore chamfer no longer clears the collar root")

# Even at the collar's supplied 5/8-in stock lower bound and the bore/chamfer
# upper bounds, the mouth ends before the collar's outer bearing annulus.
# Mirror the stock class here: dt_cone_gear_shaft_spec imports this gear's face
# width, so importing its COLLAR_DIA here would form an import cycle. The
# offline drawing test cross-checks these numbers against the shaft spec.
_COLLAR_MIN_R = (0.625 * MM_PER_IN - 0.002 * MM_PER_IN) / 2.0
_BORE_MAX_R = (
    BORE_DIA + gear_seat_fit.seat_bore_band(cone_shaft_land_bands.GEAR_SEAT_BAND)[0]
) / 2.0
COLLAR_BEARING_ANNULUS = _COLLAR_MIN_R - (_BORE_MAX_R + BORE_SOUTH_CHAMFER_MAX)
if COLLAR_BEARING_ANNULUS <= 0:
    raise AssertionError("the chamfer reaches the collar's bearing outer rim")
BORE_ENGAGEMENT_MIN = FACE_WIDTH + FACE_WIDTH_BAND[1] - BORE_SOUTH_CHAMFER_MAX

# No roughness symbol: the bore is a gear seat that drives through its key
# and does not run, and drawing-guidelines.md rule 6 (roughness symbols only
# where a surface runs, slides or locates) puts no symbol on a gear's seat
# bore (machinist review r1 of #1641, all three runs). The teeth and end
# faces carry none either; the title block's process row covers them.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_dt_crank_drive_gear`` marks exactly these;
# ``draw_dt_crank_drive_gear`` keeps exactly their union across its per-view
# ``keep`` maps. ---
#
# ``OutsideDiaReference`` is a construction-geometry sketch whose single driving
# dimension IS the tip circle the turner sets: it carries the band and callout
# independently of whichever recipe cuts the teeth, and
# drawing-simplicity-policy.md `How the repository implements the guidelines` says model it rather than type it into the data block.
# The tooth line has no native dimension: no view shows a tooth's line on a
# drawn edge (machinist review of farm proof r3 on #2482 refused a 13 deg
# measured between construction rays in the bore), so its inclination, hand
# and crossing station print in the gear data, as the helix angle did.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OutsideDiaReference": {"OutsideDia"},
    "GearBlank": {"FaceWidth"},
    "BoreProfile": {"BoreDia", "KeywayWidth", "KeywayT"},
    "BoreSouthChamfer": {"BoreSouthChamferSize"},
}

# --- Decimal places, authored ON THE PART ------------------------------------
#
# drawing-simplicity-policy.md `How the repository implements the guidelines`: the places a dimension prints are part of the tolerance it
# claims, and the model owns both. ``build_dt_crank_drive_gear`` applies this table
# natively (``_drawing_precision.apply_drawing_precision``) right after the drawing
# marks, so ``draw_dt_crank_drive_gear`` imports each dimension verbatim and only
# reads ``GetPrimaryPrecision2()`` back off the sheet.
#
# Inch places: the round bore carries its fit band at four (+.0018/+.0010)
# and the keyway its width and T bands at four. The outside diameter prints three with
# +/-.004. The face width is the four-place +/-.001 member of the solid gear
# stack; its south face seats on the collar and the tolerance only shifts the
# north face. The south chamfer leg prints two places under the title block's
# .XX band, with no band of its own.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OutsideDiaReference": {"OutsideDia": OUTSIDE_DIA_PLACES},
    "GearBlank": {"FaceWidth": FACE_WIDTH_PLACES},
    "BoreProfile": {"BoreDia": 4, "KeywayWidth": KEYWAY_PLACES, "KeywayT": KEYWAY_PLACES},
    "BoreSouthChamfer": {"BoreSouthChamferSize": BORE_SOUTH_CHAMFER_PLACES},
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
