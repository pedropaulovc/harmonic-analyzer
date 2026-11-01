r"""MHA-PD-18 transgear-arm: the drawing contract of the made steel arm.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Every number is ``pd_transgear_arm_geometry``'s (the numbers authority
the plate, the pivot hardware and the paper-drive assembly share); this
module adds only what the sheet needs: the printed places of each marked
dimension, the explicit model bands, and the printed callout text.

Part frame (``pd_transgear_arm_geometry``): origin on the pivot axis P on the
FRONT face; +X along the centreline to the square end; +Y toward the upper
tangent edge; +Z through the thickness to the REAR face (z = THICKNESS).
"""

from __future__ import annotations

import math

import _config
from _gtol_controls import GeometricControl, PartDatum
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _hole_spec import blind_cut_dia_mm

import pd_vn_transgear_latch_pin_spec as LATCH_PIN
import pd_transgear_arm_geometry as ARM
import pd_vn_transgear_arm_plate_locating_pin_spec as LOCATOR_PIN
import _transgear_arm_plate_locating_interface as LOCATING_PIN
import paper_drive_arm_registration as REGISTRATION
import pd_transgear_pin_spec as PIN
from pd_transgear_arm_geometry import (
    REDUCER_POSITION_DIAMETER,
    PIN_BORE_DIA,
    PIN_STATION,
    PIVOT_BORE_DIA,
    PLATE_TAP_SPEC,
    PLATE_TAP_STATIONS,
    THICKNESS,
    PIN_HOLE_DIA,
    PIN_HOLE_DIA_BAND,
    PIVOT_BORE_DIAMETRAL_CLEARANCE,
    PIVOT_FIT_CLEARANCE_PLACES,
    PIVOT_END_R,
    SPOT_FACE_DIA_GROWTH,
    STOCK_THICKNESS_IN,
    TIP_STATION,
    UNIT,
)

# Places each printed dimension carries (contract §3.1 / §12), in inches
# (#290): the hull radius and the end-face width print .XX, rounded from
# their mm models (``pd_transgear_arm_geometry.OUTLINE_PLACES``); the tip
# station is .XX (R9-23, ``pd_transgear_arm_geometry.TIP_STATION``); the
# thickness is the ground stock's, a reference (the stock band governs it,
# ``STOCK_TEXT_PREFIX``); the pivot bore's model size is REF, with acceptance
# matched to the measured shoulder; the latch-pin hole and pin bore print
# under their explicit ream bands; the reducer stations and locating sites
# are BASIC under circular position controls; the end-face latch-hole height
# is an ordinary .XXX row the title block governs (coordinator ruling (a),
# #2019: no tightened band); the pin-hole depth is .XX.  The geometry module
# judges the walls and the hanger joints at each print's reach.
OUTLINE_PLACES = ARM.OUTLINE_PLACES
TIP_STATION_PLACES = ARM.TIP_STATION_PLACES
THICKNESS_PLACES = 4
PIVOT_BORE_PLACES = 4
SPOT_FACE_DIA_PLACES = 3
SPOT_FACE_FLOOR_PLACES = ARM.SPOT_FACE_FLOOR_PLACES
STATION_PLACES = 4
PIN_HOLE_DIA_PLACES = 4
PIN_BORE_DIA_PLACES = 4
PIN_HOLE_DEPTH_PLACES = ARM.PIN_HOLE_DEPTH_PLACES

# Explicit model bands, (upper, lower) deviations where one-sided.
# The counterbore only cuts oversize (drilled-hole row).
SPOT_FACE_DIA_BAND = (SPOT_FACE_DIA_GROWTH, 0.0)
# Floor from the FRONT face: the MHA-PD-VN-63 spring's room under the head (R9-71).
SPOT_FACE_FLOOR_TOLERANCE = ARM.SPOT_FACE_FLOOR_TOLERANCE

BASIC_REDUCER_DIMENSIONS = (
    ("StationReference", "PinStation"),
    ("StationReference", "PlateTapStation1"),
    ("StationReference", "PlateTapStation2"),
)
BASIC_REDUCER_DIMENSIONS += tuple(
    ("LocatorProfile", name) for name in ("LocatorX1", "LocatorY1", "LocatorX2", "LocatorY2")
)
PART_DATUMS = (
    PartDatum("A", PlanarFace((0.0, 0.0, -1.0), 0.0)),
    PartDatum("B", CylinderFace(PIVOT_BORE_DIA)),
    PartDatum("C", CylinderFace(PIN_BORE_DIA, contains_x_mm=PIN_STATION)),
)
# The frames print in inches (#290), floored to four places so each printed
# zone stays inside the 0.05 zones the reducer stacks were judged at.
GEOMETRIC_TOLERANCES_IN = {"position": ".0019", "projected_axis": ".0019"}
GEOMETRIC_TOLERANCES_MM = {key: float(value) * 25.4 for key, value in GEOMETRIC_TOLERANCES_IN.items()}
if (
    GEOMETRIC_TOLERANCES_MM["position"] > REDUCER_POSITION_DIAMETER
    or GEOMETRIC_TOLERANCES_MM["projected_axis"] > REGISTRATION.AXIS_PROJECTED_ZONE_DIAMETER_MM
):
    raise AssertionError("MHA-PD-18 prints a reducer zone wider than its stacks assume")
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "feed_stud_position", "position", GEOMETRIC_TOLERANCES_IN["position"],
        CylinderFace(PIN_BORE_DIA, contains_x_mm=PIN_STATION),
        ("A", "B"), "diametral",
    ),
    *(
        GeometricControl(
            f"plate_tap_{index}_position", "position",
            GEOMETRIC_TOLERANCES_IN["position"],
            CylinderFace(
                blind_cut_dia_mm(PLATE_TAP_SPEC), contains_x_mm=station,
                contains_z_mm=THICKNESS / 2.0,
            ),
            ("A", "B", "C"), "diametral",
            projected_zone_height_mm=ARM.CLAMP_TAP_PROJECTED_HEIGHT_MM,
            projection_unit=UNIT,
        )
        for index, station in enumerate(PLATE_TAP_STATIONS, 1)
    ),
)
GEOMETRIC_CONTROLS += (
    GeometricControl(
        "feed_stud_projected_axis", "perpendicularity",
        GEOMETRIC_TOLERANCES_IN["projected_axis"],
        CylinderFace(PIN_BORE_DIA, contains_x_mm=PIN_STATION),
        ("A",), "diametral",
        projected_zone_height_mm=REGISTRATION.S_PROJECTED_HEIGHT_MM,
        projection_unit=UNIT,
    ),
    # No frame on the rear face (machinist review, rule 5): the 9517K466
    # ground stock's thickness band carries its parallelism to A
    # (paper_drive_arm_registration.ARM_OPPOSITE_FACE_PARALLELISM_MM).
    *(
        GeometricControl(
            f"arm_locator_{index}_position", "position", GEOMETRIC_TOLERANCES_IN["position"],
            CylinderFace(
                ARM.LOCATOR_HOLE_DIA_MM, contains_x_mm=x, contains_y_mm=y,
                contains_z_mm=THICKNESS / 2.0,
            ),
            ("A", "B", "C"), "diametral",
        ) for index, (x, y) in enumerate(ARM.LOCATOR_SITES_MM, 1)
    ),
)


def _inch(value_mm: float, places: int) -> str:
    """``value_mm`` printed in inches to ``places``, without the leading zero."""
    return f"{value_mm / 25.4:.{places}f}".removeprefix("0")


def _floor_mm(value_mm: float, places: int) -> float:
    """``value_mm`` floored to the inch grid of ``places``, back in mm."""
    return math.floor(value_mm / 25.4 * 10**places + 1e-6) / 10**places * 25.4


def _ceil_mm(value_mm: float, places: int) -> float:
    """``value_mm`` rounded up to the inch grid of ``places``, back in mm."""
    return math.ceil(value_mm / 25.4 * 10**places - 1e-6) / 10**places * 25.4


# The press and its proud set are assembly (MHA-PD-00 "arm-plate-located").
# The callout names the dowel the reamed holes take and its press (rule 4),
# and says what the small mouth breaks keep: the dowel's full-diameter grip
# (``pd_transgear_arm_geometry.LOCATOR_FULL_CYLINDER_SPAN_MIN_MM``). The
# drawing adds the match-drill with the plate and its assembly step.  The
# press is the dowel's band against the printed ream's limits.
LOCATOR_PRESS_INTERFERENCE = (
    LOCATOR_PIN.DIA_LIMITS[0] - ARM.LOCATOR_HOLE_PRINTED_LIMITS_MM[1],
    LOCATOR_PIN.DIA_LIMITS[1] - ARM.LOCATOR_HOLE_PRINTED_LIMITS_MM[0],
)
if LOCATOR_PRESS_INTERFERENCE[0] <= 0.0:
    raise AssertionError("the MHA-PD-18 locating ream loses MHA-PD-VN-64's press")
LOCATOR_CALLOUT = "\n".join((
    "2X REAM THRU",
    f"MOUTH BREAKS {_inch(_floor_mm(LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM, 4), 4)}"
    " MAX: DOWEL GRIP",
    f"PRESS FIT DOWEL {LOCATOR_PIN.PART_NUMBER}",
    f"{_inch(_floor_mm(LOCATOR_PRESS_INTERFERENCE[0], 4), 4)}/"
    f"{_inch(_ceil_mm(LOCATOR_PRESS_INTERFERENCE[1], 4), 4)} INTERFERENCE",
))
# Machinist review (rule 16): a pressed dowel needs a way out. The reams run
# through, and the dowel pressed from the rear to its proud set stops short
# of the front face's mouth break on the thinnest stock, so a punch from the
# front drives it out.
LOCATOR_PUNCH_AIR_MIN_MM = (
    THICKNESS - ARM.THICKNESS_BAND - LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM
    - LOCATOR_PIN.INSERTION_LIMITS_MM[1]
)
if LOCATOR_PUNCH_AIR_MIN_MM <= 0.0:
    raise AssertionError("the MHA-PD-VN-64 dowel reaches the MHA-PD-18 front face")

# --- Printed text -------------------------------------------------------------
# The thickness is the stock's: it prints "5/16 ±.001 (.3125) GROUND
# STOCK", prefix and suffix around the imported model value, which the
# parentheses mark as reference, so the title block's rows never apply to
# it. The stock's own band is printed because the seat tilt and the plate
# screw's engagement are judged at it (codjiflo review of #2015).
STOCK_THICKNESS_BAND_IN_TEXT = f"±{_inch(ARM.THICKNESS_BAND, 3)}"
STOCK_TEXT_PREFIX = f"{STOCK_THICKNESS_IN} {STOCK_THICKNESS_BAND_IN_TEXT} ("
# REF: an as-bought size with the supplier's tolerance (units guidance).
STOCK_TEXT_SUFFIX = ") GROUND STOCK REF"
PLATE_TAP_EDGE_BREAK_CALLOUT = (
    f"ENTRY / EXIT EDGE BREAK {_inch(ARM.PLATE_TAP_ENTRY_BREAK_MAX_MM, 3)} MAX BOTH SIDES"
)
# Where each projected zone starts and which way it runs, at the feature
# (machinist review, rule 7; it was general note 1): the sheet draws each
# zone as a heavy chain line from front face A (z = 0) along the hole's
# axis and dimensions its height (ASME Y14.5-2018: the extent and direction
# of a projected zone, a dimensioned chain line on the hole's axis). Model
# +Z runs rearward. The plate taps' zones run rearward, through the arm into
# the MHA-PD-19 plate past the seated screw-head contact
# (transgear_hanger_joints.PLATE_SCREW_CONTACT_ARM_LOCAL_Z_MAX_MM, from A);
# the pin bore's runs forward to the chain plane
# (paper_drive_arm_registration.S_PROJECTED_HEIGHT_MM). The sheet carries no
# general notes: the matched-pair setting and fit-up check are MHA-PD-00's
# steps, and the match-drill rides the locating holes' callout.
PROJECTED_ZONE_REARWARD = 1.0
PROJECTED_ZONE_FORWARD = -1.0
PROJECTED_ZONE_DIRECTION: dict[str, float] = {
    **{
        f"plate_tap_{index}_position": PROJECTED_ZONE_REARWARD
        for index in range(1, len(PLATE_TAP_STATIONS) + 1)
    },
    "feed_stud_projected_axis": PROJECTED_ZONE_FORWARD,
}
if set(PROJECTED_ZONE_DIRECTION) != {
    control.key for control in GEOMETRIC_CONTROLS
    if control.projected_zone_height_mm is not None
}:
    raise AssertionError("every projected zone needs exactly one drawn direction")
# The heights are sheet-derived (each measures its own chain line) and print
# to DRAWING_REFERENCE_PRECISION, as the frames print them (Ⓟ .580, Ⓟ 1.273).
# The counterbore seats the MHA-PD-VN-63 spring's rim under the MHA-PD-VN-57
# head, and its floor from the FRONT face (datum A) sets the spring's room
# there (transgear_hanger_joints.SPRING_ROOM_*): the callout names the
# spring, and the floor's text says what its band sets (rule 4 (name the
# mate)).  Machinist review (all three runs): "REAR FACE" / "FRONT FACE" read
# against the plan, which is drawn from the rear, so both callouts name the
# faces by datum A, which section A-A tags on the front face.
_SPRING = _config.parts("pd-vn-transgear-pivot-spring")
_PIVOT_SCREW = _config.parts("pd-vn-transgear-pivot-screw")
SPOT_FACE_CALLOUT = "\n".join((
    "COUNTERBORE OPPOSITE A",
    f"SEATS PIVOT SPRING {_SPRING['number']}",
))
# The floor's band names the mate it serves at its own callout (review of
# 2ac1bdb28, rule 4): it sets the pivot spring's preload.
FLOOR_DEPTH_CALLOUT = "\n".join((
    "FLOOR FROM A:",
    "SETS PRELOAD OF",
    "PIVOT SPRING",
    _SPRING["number"],
))
# Conditional measured-shoulder clearance on the named pivot screw, with
# ordinary squareness paid; not an absolute H7/g6 bore zone. The bore's 90°
# to the front face is implied and takes the title block's angular row.
PIVOT_BORE_CALLOUT = "\n".join((
    "REAM TO MEASURED SHOULDER:",
    f"{_inch(PIVOT_BORE_DIAMETRAL_CLEARANCE[0], PIVOT_FIT_CLEARANCE_PLACES)}-"
    f"{_inch(PIVOT_BORE_DIAMETRAL_CLEARANCE[1], PIVOT_FIT_CLEARANCE_PLACES)}"
    " DIAMETRAL CLEARANCE",
    f"ON PIVOT SCREW {_PIVOT_SCREW['number']}",
    "MATCHED SET; NOT INTERCHANGEABLE",
))

# --- The MHA-PD-23 pin's press in the reamed bore at S (R9-68) -----------------
# The pin spec owns the press (it imports the arm geometry, so the geometry
# cannot import it back); the arm prints it under the bore.
PIN_PRESS_INTERFERENCE = PIN.PRESS_INTERFERENCE
if not all(
    math.isclose(value, expected, abs_tol=1e-9)
    for value, expected in zip(PIN_PRESS_INTERFERENCE, (0.00762, 0.02794), strict=True)
):
    raise AssertionError(
        f"MHA-PD-18 pin bore press on MHA-PD-23 is {PIN_PRESS_INTERFERENCE}, "
        "not .0003..0011"
    )
# Three short lines under the Ø: the operation, the mating pin, the press.
PIN_BORE_CALLOUT = "\n".join(
    (
        "REAM THRU",
        f"PRESS FIT PIN {PIN.PIN_NUMBER}",
        f"{_inch(PIN_PRESS_INTERFERENCE[0], 4)}/{_inch(PIN_PRESS_INTERFERENCE[1], 4)}"
        " INTERFERENCE",
    )
)


def engagement_line(worst_mm: float, worst_d: float) -> str:
    """The installed full-thread engagement a tap callout states: the
    worst-case length in inches and its multiple of the major diameter, each
    floored (a MIN never rounds up), pending ruling #1385."""
    d = int(worst_d * 100.0 + 1e-9) / 100.0
    return f"ENGAGEMENT {_inch(_floor_mm(worst_mm, 3), 3)} MIN ({d:.2f}D)"


# The true overall, pivot-end extreme to the square end, prints as a
# reference; a derived reference has no part-side places, so the spec owns
# its digits (three, as the projected heights).
OVERALL_LENGTH = PIVOT_END_R + TIP_STATION
DRAWING_REFERENCE_PRECISION = 3

# --- The MHA-PD-VN-58 latch pin's press in the blind ream -------------------------
# (loosest, tightest) from the printed ream band and the dowel's catalogue
# band.  The callout rounds both outward to four inch places, so the range
# it names holds every pin and hole the two bands accept.
LATCH_PIN_NUMBER = "MHA-PD-VN-58"
LATCH_PIN_PRESS_INTERFERENCE = (
    round(
        LATCH_PIN.DIA + min(LATCH_PIN.DIA_BAND) - PIN_HOLE_DIA - max(PIN_HOLE_DIA_BAND),
        6,
    ),
    round(
        LATCH_PIN.DIA + max(LATCH_PIN.DIA_BAND) - PIN_HOLE_DIA - min(PIN_HOLE_DIA_BAND),
        6,
    ),
)
if LATCH_PIN_PRESS_INTERFERENCE[0] <= 0.0:
    raise AssertionError("the MHA-PD-18 latch-pin ream loses MHA-PD-VN-58's press")
LATCH_PIN_PRESS_PRINTED = (
    _floor_mm(LATCH_PIN_PRESS_INTERFERENCE[0], 4),
    _ceil_mm(LATCH_PIN_PRESS_INTERFERENCE[1], 4),
)  # .0006, .0013
# The pin bore's three lines (the operation, the mating pin, the press), plus
# the ligament to the faces as a plain fact: .065 MIN at full budget is the
# owner-accepted shortfall (machinist_exceptions RV-04; #2019 tracks the next
# stock size up). Pressing it to the floor is MHA-PD-00's latch-pin-pressed
# step (policy option (c)); the callout stands below the end view, inside the
# border.
LATCH_PIN_WALL_PRINTED = _floor_mm(ARM.WALLS["pin hole to faces"][1], 3)
PIN_HOLE_CALLOUT = "\n".join(
    (
        "BLIND FLAT-BOTTOM REAM",
        f"PRESS FIT PIN {LATCH_PIN_NUMBER}",
        f"{_inch(LATCH_PIN_PRESS_PRINTED[0], 4)}/{_inch(LATCH_PIN_PRESS_PRINTED[1], 4)}"
        " INTERFERENCE",
        f"PIN HOLE TO FACES {_inch(LATCH_PIN_WALL_PRINTED, 3)} MIN",
    )
)

ISO_VIEW_SCALE = (1, 2)
ISOMETRIC_VIEW_NOTE = f"ISOMETRIC VIEW SCALE {ISO_VIEW_SCALE[0]}:{ISO_VIEW_SCALE[1]}"

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity-policy.md `How the repository implements the guidelines`).  The hole stations live in the blanked
# ``StationReference`` sketch: the Hole Wizard placement sketches that drive
# the taps are not importable, and the pin bore's station prints with them.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArmOutline": {"PivotEndR", "TipStation", "EndWidth"},
    "Arm": {"Depth"},
    "PivotBoreProfile": {"PivotBoreDia"},
    "PinBoreProfile": {"PinBoreDia"},
    "SpotFaceProfile": {"SpotFaceDia", "FloorDepth"},
    "StationReference": {"PinStation", "PlateTapStation1", "PlateTapStation2"},
    "PinHoleProfile": {"PinHoleDia", "PinHoleZ"},
    "PinHole": {"PinHoleDepth"},
    "LocatorProfile": {"LocatorX1", "LocatorY1", "LocatorY2", "LocatorDia1"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ArmOutline": {
        "PivotEndR": OUTLINE_PLACES,
        "TipStation": TIP_STATION_PLACES,
        "EndWidth": OUTLINE_PLACES,
    },
    "Arm": {"Depth": THICKNESS_PLACES},
    "PivotBoreProfile": {"PivotBoreDia": PIVOT_BORE_PLACES},
    "PinBoreProfile": {"PinBoreDia": PIN_BORE_DIA_PLACES},
    "SpotFaceProfile": {
        "SpotFaceDia": SPOT_FACE_DIA_PLACES,
        "FloorDepth": SPOT_FACE_FLOOR_PLACES,
    },
    "StationReference": {
        "PinStation": STATION_PLACES,
        "PlateTapStation1": STATION_PLACES,
        "PlateTapStation2": STATION_PLACES,
    },
    "PinHoleProfile": {
        "PinHoleDia": PIN_HOLE_DIA_PLACES,
        "PinHoleZ": ARM.LATCH_PIN_HEIGHT_PLACES,
    },
    "PinHole": {"PinHoleDepth": PIN_HOLE_DEPTH_PLACES},
    "LocatorProfile": {
        "LocatorX1": STATION_PLACES, "LocatorY1": STATION_PLACES,
        "LocatorY2": STATION_PLACES, "LocatorDia1": ARM.LOCATOR_HOLE_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if {
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
} != {
    (feature, name) for feature, names in DRAWING_DIMENSIONS.items() for name in names
}:
    raise AssertionError("MHA-PD-18 marked dimensions and authored places disagree")
