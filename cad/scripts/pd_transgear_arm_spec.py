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
    BAND_X,
    BAND_XX,
    BAND_XXX,
    LATCH_PIN_HEIGHT_BAND,
    REDUCER_POSITION_DIAMETER,
    PIN_BORE_DIA,
    PIN_STATION,
    PIVOT_BORE_DIA,
    PLATE_TAP_SPEC,
    PLATE_TAP_STATIONS,
    THICKNESS,
    PIN_HOLE_DEPTH_BAND,
    PIN_HOLE_DIA,
    PIN_HOLE_DIA_BAND,
    PIVOT_BORE_DIAMETRAL_CLEARANCE,
    PIVOT_FIT_CLEARANCE_PLACES,
    PIVOT_END_R,
    SPOT_FACE_DIA_GROWTH,
    SPOT_FACE_FLOOR_BAND,
    STOCK_THICKNESS_IN,
    TIP_STATION,
    TIP_STATION_BAND,
)

# The general-tolerance band each printed place count claims (the title-block
# rows the geometry module hard-codes, drawing-guidelines.md rule 3 (decimal places carry the tolerance)).
BAND_BY_PLACES: dict[int, float] = {1: BAND_X, 2: BAND_XX, 3: BAND_XXX}

# Places each printed dimension carries (contract §3.1 / §12):
# the hull radius and the end-face width are routine .X; the tip station is
# .XX (R9-23: at .X the latch pin's full diameter can stop inside the hook
# strip, see ``pd_transgear_arm_geometry.TIP_STATION``); the thickness is the
# ground stock's, printed to two places as a reference (the stock band
# governs it, ``STOCK_TEXT_PREFIX``); the pivot bore's .XXX model size is REF,
# with acceptance matched to the measured shoulder; the latch-pin hole and
# pin bore print .XXX under their explicit ream
# bands; the reducer stations are BASIC under circular position controls;
# only the end-face latch-hole height retains its ordinary ± height band.
# pin-hole depth is .XX, the band the pin's grip and proud range are judged
# at (``PIN_HOLE_DEPTH_BAND``).
OUTLINE_PLACES = 1
TIP_STATION_PLACES = 2
THICKNESS_PLACES = 2
PIVOT_BORE_PLACES = 3
SPOT_FACE_DIA_PLACES = 3
SPOT_FACE_FLOOR_PLACES = 2
STATION_PLACES = 3
PIN_HOLE_DIA_PLACES = 3
PIN_BORE_DIA_PLACES = 3
PIN_HOLE_DEPTH_PLACES = 2

# The places must claim the bands the geometry module's walls and the
# hanger joints were judged at.
for _label, _places, _band in (
    ("tip station", TIP_STATION_PLACES, TIP_STATION_BAND),
    ("latch-pin hole depth", PIN_HOLE_DEPTH_PLACES, PIN_HOLE_DEPTH_BAND),
):
    if abs(BAND_BY_PLACES[_places] - _band) > 1e-9:
        raise AssertionError(
            f"MHA-PD-18 {_label} prints {_places} places (±{BAND_BY_PLACES[_places]}),"
            f" not the ±{_band} its walls assume"
        )

# Explicit model bands, (upper, lower) deviations where one-sided.
# The counterbore only cuts oversize (drilled-hole row).
SPOT_FACE_DIA_BAND = (SPOT_FACE_DIA_GROWTH, 0.0)
# Floor from the FRONT face: the MHA-PD-VN-63 spring's room under the head (R9-71).
SPOT_FACE_FLOOR_TOLERANCE = SPOT_FACE_FLOOR_BAND
# The blind end-face latch hole is not a reducer locating-hole control.
LATCH_PIN_HEIGHT_TOLERANCE = LATCH_PIN_HEIGHT_BAND

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
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "feed_stud_position", "position", f"{REDUCER_POSITION_DIAMETER:.3f}",
        CylinderFace(PIN_BORE_DIA, contains_x_mm=PIN_STATION),
        ("A", "B"), "diametral",
    ),
    *(
        GeometricControl(
            f"plate_tap_{index}_position", "position",
            f"{REDUCER_POSITION_DIAMETER:.3f}",
            CylinderFace(
                blind_cut_dia_mm(PLATE_TAP_SPEC), contains_x_mm=station,
                contains_z_mm=THICKNESS / 2.0,
            ),
            ("A", "B", "C"), "diametral",
            projected_zone_height_mm=ARM.CLAMP_TAP_PROJECTED_HEIGHT_MM,
        )
        for index, station in enumerate(PLATE_TAP_STATIONS, 1)
    ),
)
GEOMETRIC_CONTROLS += (
    GeometricControl(
        "feed_stud_projected_axis", "perpendicularity",
        f"{REGISTRATION.AXIS_PROJECTED_ZONE_DIAMETER_MM:.3f}",
        CylinderFace(PIN_BORE_DIA, contains_x_mm=PIN_STATION),
        ("A",), "diametral",
        projected_zone_height_mm=REGISTRATION.S_PROJECTED_HEIGHT_MM,
    ),
    # No frame on the rear face (machinist review, rule 5): the 9517K466
    # ground stock's thickness band carries its parallelism to A
    # (paper_drive_arm_registration.ARM_OPPOSITE_FACE_PARALLELISM_MM).
    *(
        GeometricControl(
            f"arm_locator_{index}_position", "position", f"{REDUCER_POSITION_DIAMETER:.3f}",
            CylinderFace(
                ARM.LOCATOR_HOLE_DIA_MM, contains_x_mm=x, contains_y_mm=y,
                contains_z_mm=THICKNESS - ARM.LOCATOR_BLIND_DEPTH_MM / 2.0,
            ),
            ("A", "B", "C"), "diametral",
        ) for index, (x, y) in enumerate(ARM.LOCATOR_SITES_MM, 1)
    ),
)
# The press and its proud set are assembly (MHA-PD-00 "arm-plate-located").
# The callout names the dowel the reamed holes take and its press (rule 4),
# and says what the small mouth break keeps: the dowel's full-diameter grip
# (``pd_transgear_arm_geometry.LOCATOR_FULL_CYLINDER_SPAN_MIN_MM``). The
# drawing adds the match-drill with the plate and its assembly step.
LOCATOR_PRESS_INTERFERENCE = LOCATOR_PIN.PRESS_INTERFERENCE_MM
if LOCATOR_PRESS_INTERFERENCE[0] <= 0.0:
    raise AssertionError("the MHA-PD-18 locating ream loses MHA-PD-VN-64's press")
LOCATOR_CALLOUT = "\n".join((
    "2X REAM, FLAT BOTTOM",
    f"MOUTH BREAK {LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM:.2f} MAX: DOWEL GRIP",
    f"PRESS FIT DOWEL {LOCATOR_PIN.PART_NUMBER}",
    f"{LOCATOR_PRESS_INTERFERENCE[0]:.3f}/{LOCATOR_PRESS_INTERFERENCE[1]:.3f} INTERFERENCE",
))

# --- Printed text -------------------------------------------------------------
# The thickness is the stock's: it prints "5/16 (7.94) GROUND STOCK", prefix
# and suffix around the imported model value, which the parentheses mark as
# reference, so the title block's .XX band never applies to it.
STOCK_TEXT_PREFIX = f"{STOCK_THICKNESS_IN} ("
STOCK_TEXT_SUFFIX = ") GROUND STOCK"
PLATE_TAP_EDGE_BREAK_CALLOUT = (
    f"ENTRY / EXIT EDGE BREAK {ARM.PLATE_TAP_ENTRY_BREAK_MAX_MM:g} MAX BOTH SIDES"
)
# Where each projected zone starts and which way it runs. Both start at
# front face A (z = 0): the plate taps' run rearward through the arm into
# the MHA-PD-19 plate to the seated screw-head contact
# (transgear_hanger_joints.PLATE_SCREW_CONTACT_ARM_LOCAL_Z_MAX_MM, from A);
# the pin bore's runs forward to the chain plane
# (paper_drive_arm_registration.S_PROJECTED_HEIGHT_MM). It is the sheet's
# only note: the matched-pair setting and fit-up check are MHA-PD-00's
# steps, and the match-drill rides the locating holes' callout (rule 7).
PROJECTED_ZONE_NOTE = "\n".join((
    "1. PROJECTED ZONES START AT FRONT FACE A: PLATE TAPS",
    f"   {ARM.CLAMP_TAP_PROJECTED_HEIGHT_MM:.1f} REARWARD; PIN BORE "
    f"{REGISTRATION.S_PROJECTED_HEIGHT_MM:.1f} FORWARD.",
))
# The counterbore seats the MHA-PD-VN-63 spring's rim under the MHA-PD-VN-57
# head, and its floor from the FRONT face sets the spring's room there
# (transgear_hanger_joints.SPRING_ROOM_*): the callout names the spring, and
# the floor's text says what its band sets (rule 4 (name the mate)).
_SPRING = _config.parts("pd-vn-transgear-pivot-spring")
_PIVOT_SCREW = _config.parts("pd-vn-transgear-pivot-screw")
SPOT_FACE_CALLOUT = "\n".join((
    "COUNTERBORE, REAR FACE",
    f"SEATS PIVOT SPRING {_SPRING['number']}",
))
# Four short lines: the text stands under the section's pivot end, inside
# the left border.
FLOOR_DEPTH_CALLOUT = "FLOOR FROM\nFRONT FACE\nFOR SPRING\nPRELOAD"
# Conditional measured-shoulder clearance on the named pivot screw, with
# ordinary squareness paid; not an absolute H7/g6 bore zone. The bore's 90°
# to the front face is implied and takes the title block's angular row.
PIVOT_BORE_CALLOUT = "\n".join((
    "REAM TO MEASURED SHOULDER:",
    f"{PIVOT_BORE_DIAMETRAL_CLEARANCE[0]:.{PIVOT_FIT_CLEARANCE_PLACES}f}-"
    f"{PIVOT_BORE_DIAMETRAL_CLEARANCE[1]:.{PIVOT_FIT_CLEARANCE_PLACES}f}"
    " DIAMETRAL CLEARANCE",
    f"ON PIVOT SCREW {_PIVOT_SCREW['number']}",
    "MATCHED SET; NOT INTERCHANGEABLE",
))

# --- The MHA-PD-23 pin's press in the reamed bore at S (R9-68) -----------------
# The pin spec owns the press (it imports the arm geometry, so the geometry
# cannot import it back); the arm prints it under the bore.
PIN_PRESS_INTERFERENCE = PIN.PRESS_INTERFERENCE
if PIN_PRESS_INTERFERENCE != (0.010, 0.026):
    raise AssertionError(
        f"MHA-PD-18 pin bore press on MHA-PD-23 is {PIN_PRESS_INTERFERENCE}, "
        "not 0.010..0.026"
    )
# Three short lines under the Ø: the operation, the mating pin, the press.
PIN_BORE_CALLOUT = "\n".join(
    (
        "REAM THRU",
        f"PRESS FIT PIN {PIN.PIN_NUMBER}",
        f"{PIN_PRESS_INTERFERENCE[0]:.3f}/{PIN_PRESS_INTERFERENCE[1]:.3f} INTERFERENCE",
    )
)


def engagement_line(worst_mm: float, worst_d: float) -> str:
    """The installed full-thread engagement a tap callout states: the
    worst-case length and its multiple of the major diameter, each floored
    to two places (a MIN never rounds up), pending ruling #1385."""
    mm = int(worst_mm * 100.0 + 1e-9) / 100.0
    d = int(worst_d * 100.0 + 1e-9) / 100.0
    return f"ENGAGEMENT {mm:.2f} MIN ({d:.2f}D)"


# The true overall, pivot-end extreme to the square end, prints as a
# reference; a derived reference has no part-side places, so the spec owns
# its digit.
OVERALL_LENGTH = PIVOT_END_R + TIP_STATION
DRAWING_REFERENCE_PRECISION = 1

# --- The MHA-PD-VN-58 latch pin's press in the blind ream -------------------------
# (loosest, tightest) from the printed ream band and the dowel's catalogue
# band: 0.00254..0.01762.  The callout rounds both outward to four places,
# so the range it names holds every pin and hole the two bands accept.
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
    math.floor(LATCH_PIN_PRESS_INTERFERENCE[0] * 1e4 + 1e-6) / 1e4,
    math.ceil(LATCH_PIN_PRESS_INTERFERENCE[1] * 1e4 - 1e-6) / 1e4,
)  # 0.0025, 0.0177
# Three lines as the pin bore's: the operation, the mating pin, the press.
# Pressing it to the floor is MHA-PD-00's latch-pin-pressed step (policy
# option (c)); the callout stands below the end view, inside the border.
PIN_HOLE_CALLOUT = "\n".join(
    (
        "BLIND FLAT-BOTTOM REAM",
        f"PRESS FIT PIN {LATCH_PIN_NUMBER}",
        f"{LATCH_PIN_PRESS_PRINTED[0]:.4f}/{LATCH_PIN_PRESS_PRINTED[1]:.4f}"
        " INTERFERENCE",
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
    "LocatorHoles": {"LocatorDepth"},
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
        "PinHoleZ": STATION_PLACES,
    },
    "PinHole": {"PinHoleDepth": PIN_HOLE_DEPTH_PLACES},
    "LocatorProfile": {
        "LocatorX1": 3, "LocatorY1": 3, "LocatorY2": 3, "LocatorDia1": 3,
    },
    "LocatorHoles": {"LocatorDepth": 3},
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
