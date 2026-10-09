r"""MHA-PD-018 transgear-arm: the drawing contract of the made steel arm.

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
from _gtol_spec import CylinderFace, GeometricControl, PartDatum, PlanarFace
from _hole_spec import blind_cut_dia_mm

import vn_transgear_latch_pin_spec as LATCH_PIN
import pd_transgear_arm_geometry as ARM
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
    PIVOT_BORE_TO_FRONT_FACE_ANGLE_DEG,
    PIVOT_FIT_CLEARANCE_PLACES,
    PIVOT_END_R,
    SPOT_FACE_DIA_GROWTH,
    SPOT_FACE_FLOOR_BAND,
    STOCK_THICKNESS_IN,
    TIP_STATION,
    TIP_STATION_BAND,
)

# The general-tolerance band each printed place count claims (the title-block
# rows the geometry module hard-codes, policy rule 12).
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
            f"MHA-PD-018 {_label} prints {_places} places (±{BAND_BY_PLACES[_places]}),"
            f" not the ±{_band} its walls assume"
        )

# Explicit model bands, (upper, lower) deviations where one-sided.
# The counterbore only cuts oversize (drilled-hole row).
SPOT_FACE_DIA_BAND = (SPOT_FACE_DIA_GROWTH, 0.0)
# Floor from the FRONT face: the MHA-VN-049 spring's room under the head (R9-71).
SPOT_FACE_FLOOR_TOLERANCE = SPOT_FACE_FLOOR_BAND
# The blind end-face latch hole is not a reducer locating-hole control.
LATCH_PIN_HEIGHT_TOLERANCE = LATCH_PIN_HEIGHT_BAND

BASIC_REDUCER_DIMENSIONS = (
    ("StationReference", "PinStation"),
    ("StationReference", "PlateTapStation1"),
    ("StationReference", "PlateTapStation2"),
)
BASIC_REDUCER_DIMENSIONS += (
    ("StationReference", "ReducerDeltaX"), ("StationReference", "ReducerDeltaY"),
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
    GeometricControl(
        "arm_rear_parallel", "parallelism",
        f"{REGISTRATION.ARM_OPPOSITE_FACE_PARALLELISM_MM:.3f}",
        PlanarFace((0.0, 0.0, 1.0), THICKNESS), ("A",),
    ),
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
REDUCER_POSITION_INSPECTION_NOTE = REGISTRATION.MATCHED_REGISTRATION_NOTE
ARM_PLATE_NORMAL_INSPECTION_NOTE = REGISTRATION.NORMAL_INSPECTION_NOTE
CLAMP_AXIS_INSPECTION_NOTE = REGISTRATION.CLAMP_AXIS_INSPECTION_NOTE
LOCATOR_CALLOUT = (
    "2X REAM PRESS BORES; FLAT BOTTOM\n"
    f"PRESS MHA-VN-051 {ARM.LOCATOR_PROUD_MM:.2f} +/-{ARM.LOCATOR_PROUD_BAND_MM:.2f} PROUD\n"
    f"MOUTH BREAK {ARM.LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM:.2f} AXIAL/RADIAL MAX; DO NOT BOTTOM"
)

# --- Printed text -------------------------------------------------------------
# The thickness is the stock's: it prints "5/16 (7.94) GROUND STOCK", prefix
# and suffix around the imported model value, which the parentheses mark as
# reference, so the title block's .XX band never applies to it.
STOCK_TEXT_PREFIX = f"{STOCK_THICKNESS_IN} ("
STOCK_TEXT_SUFFIX = ") GROUND STOCK"
PLATE_TAP_EDGE_BREAK_CALLOUT = (
    f"ENTRY / EXIT EDGE BREAK {ARM.PLATE_TAP_ENTRY_BREAK_MAX_MM:g} MAX BOTH SIDES"
)
SPOT_FACE_CALLOUT = "COUNTERBORE, REAR FACE"
# Two short lines: the text stands under the section's pivot end, inside the
# left border.
FLOOR_DEPTH_CALLOUT = "FLOOR FROM\nFRONT FACE"
# Conditional measured-shaft clearance with ordinary squareness paid; not an
# absolute H7/g6 bore zone. The stated 90-degree angle takes the angular row.
PIVOT_BORE_CALLOUT = "\n".join((
    "REAM TO MEASURED VN041",
    f"SHOULDER +{PIVOT_BORE_DIAMETRAL_CLEARANCE[0]:.{PIVOT_FIT_CLEARANCE_PLACES}f}"
    f"/+{PIVOT_BORE_DIAMETRAL_CLEARANCE[1]:.{PIVOT_FIT_CLEARANCE_PLACES}f} DIA",
    "MATCHED SET; NOT INTERCHANGEABLE",
    f"BORE AXIS {PIVOT_BORE_TO_FRONT_FACE_ANGLE_DEG:.0f}° TO FRONT FACE",
))
PIVOT_FIT_INSPECTION_NOTE = "\n".join((
    "PIVOT: FINAL REAM AFTER FINISH.",
    "MEASURE VN041 STRAIGHT SHOULDER, CLEAR OF RADII.",
    "MICROMETER + BORE/PIN GAUGE, 0.001 mm RESOLUTION.",
    "RECORD PAIRED SHAFT OD, BORE ID AND PART IDS.",
    "REPLACEMENT VN041 REQUIRES NEW PAIRED FIT CHECK.",
))

# --- The MHA-PD-023 pin's press in the reamed bore at S (R9-68) -----------------
# The pin spec owns the press (it imports the arm geometry, so the geometry
# cannot import it back); the arm prints it under the bore.
PIN_PRESS_INTERFERENCE = PIN.PRESS_INTERFERENCE
if PIN_PRESS_INTERFERENCE != (0.010, 0.026):
    raise AssertionError(
        f"MHA-PD-018 pin bore press on MHA-PD-023 is {PIN_PRESS_INTERFERENCE}, "
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
    to two places (a MIN never rounds up), as the policy's rows state it."""
    mm = int(worst_mm * 100.0 + 1e-9) / 100.0
    d = int(worst_d * 100.0 + 1e-9) / 100.0
    return f"ENGAGEMENT {mm:.2f} MIN ({d:.2f}D)"


# The true overall, pivot-end extreme to the square end, prints as a
# reference; a derived reference has no part-side places, so the spec owns
# its digit.
OVERALL_LENGTH = PIVOT_END_R + TIP_STATION
DRAWING_REFERENCE_PRECISION = 1

# --- The MHA-VN-042 latch pin's press in the blind ream -------------------------
# (loosest, tightest) from the printed ream band and the dowel's catalogue
# band: 0.00254..0.01762.  The callout rounds both outward to four places,
# so the range it names holds every pin and hole the two bands accept.
LATCH_PIN_NUMBER = "MHA-VN-042"
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
    raise AssertionError("the MHA-PD-018 latch-pin ream loses MHA-VN-042's press")
LATCH_PIN_PRESS_PRINTED = (
    math.floor(LATCH_PIN_PRESS_INTERFERENCE[0] * 1e4 + 1e-6) / 1e4,
    math.ceil(LATCH_PIN_PRESS_INTERFERENCE[1] * 1e4 - 1e-6) / 1e4,
)  # 0.0025, 0.0177
# The pin goes in to the hole's flat floor, which sets its proud length.
# Three lines no wider than before: the callout's right edge sits inside the
# border and its top under the stock thickness text.
PIN_HOLE_CALLOUT = "\n".join(
    (
        "BLIND FLAT-BOTTOM REAM",
        f"PRESS PIN {LATCH_PIN_NUMBER} TO FLOOR",
        f"{LATCH_PIN_PRESS_PRINTED[0]:.4f}/{LATCH_PIN_PRESS_PRINTED[1]:.4f}"
        " INTERFERENCE",
    )
)

ISO_VIEW_SCALE = (1, 2)
ISOMETRIC_VIEW_NOTE = f"ISOMETRIC VIEW SCALE {ISO_VIEW_SCALE[0]}:{ISO_VIEW_SCALE[1]}"

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2).  The hole stations live in the blanked
# ``StationReference`` sketch: the Hole Wizard placement sketches that drive
# the taps are not importable, and the pin bore's station prints with them.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArmOutline": {"PivotEndR", "TipStation", "EndWidth"},
    "Arm": {"Depth"},
    "PivotBoreProfile": {"PivotBoreDia"},
    "PinBoreProfile": {"PinBoreDia"},
    "SpotFaceProfile": {"SpotFaceDia", "FloorDepth"},
    "StationReference": {"PinStation", "PlateTapStation1", "PlateTapStation2", "ReducerDeltaX", "ReducerDeltaY"},
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
        "ReducerDeltaX": 6,
        "ReducerDeltaY": 6,
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
    raise AssertionError("MHA-PD-018 marked dimensions and authored places disagree")
