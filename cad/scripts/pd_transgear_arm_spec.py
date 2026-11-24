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

from _gtol_controls import GeometricControl, PartDatum
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_tolerance import drilled_oversize_mm

import pd_vn_transgear_latch_pin_spec as LATCH_PIN
import pd_transgear_arm_geometry as ARM
import pd_vn_transgear_arm_plate_locating_pin_spec as LOCATOR_PIN
import _transgear_arm_plate_locating_interface as LOCATING_PIN
import pd_transgear_pin_spec as PIN
from pd_transgear_arm_geometry import (
    REDUCER_POSITION_DIAMETER,
    PIN_BORE_DIA,
    PIN_STATION,
    PIVOT_BORE_DIA,
    THICKNESS,
    PIN_HOLE_DIA,
    PIN_HOLE_DIA_BAND,
    PIVOT_END_R,
    SPOT_FACE_DIA_GROWTH,
    STOCK_THICKNESS_IN,
    TIP_STATION,
)

# Places each printed dimension carries (contract §3.1 / §12), in inches
# (#290): the hull radius and the end-face width print .XX, rounded from
# their mm models (``pd_transgear_arm_geometry.OUTLINE_PLACES``); the tip
# station is .XX (R9-23, ``pd_transgear_arm_geometry.TIP_STATION``); the
# thickness is the ground stock's, a reference (the stock band governs it,
# ``STOCK_TEXT_PREFIX``); the pivot bore prints its #9 drill's size under
# the DRILLED HOLES row; the latch-pin hole prints under its explicit ream
# band; the pin bore prints the .1260 reamer's size at three places
# with no band (fit audit 2026-11-23); the pin station and the locating sites
# are BASIC under circular position controls; the plate-tap stations print
# as references, the taps being spotted through MHA-PD-19's screw holes at
# assembly (``pd_transgear_arm_geometry.PLATE_TAP_LOCATION_RADIUS_MM``); the
# end-face latch-hole height is an ordinary .XXX row the title block governs
# (coordinator ruling (a), #2019: no tightened band); the pin-hole depth is
# a .XX MIN over a drill point (#3124), the model carrying the MIN.  The
# geometry module judges the walls and the hanger joints at each print's
# reach.
OUTLINE_PLACES = ARM.OUTLINE_PLACES
TIP_STATION_PLACES = ARM.TIP_STATION_PLACES
THICKNESS_PLACES = 4
PIVOT_BORE_PLACES = 3
SPOT_FACE_DIA_PLACES = 3
SPOT_FACE_FLOOR_PLACES = ARM.SPOT_FACE_FLOOR_PLACES
STATION_PLACES = 4
PIN_HOLE_DIA_PLACES = 4
PIN_BORE_DIA_PLACES = 3
PIN_HOLE_DEPTH_PLACES = ARM.PIN_HOLE_DEPTH_PLACES
# The flank's lean to the P-T centreline prints as a reference to one place
# of a degree, 2.4 (owner ruling 2026-11-20 (Pedro), #2424 option B): the
# vise set-up angle; the outline's printed rows govern the edges.
FLANK_ANGLE_PLACES = 1

# Explicit model bands, (upper, lower) deviations where one-sided.
# The counterbore only cuts oversize (drilled-hole row).
SPOT_FACE_DIA_BAND = (SPOT_FACE_DIA_GROWTH, 0.0)
# Floor from the FRONT face: the MHA-PD-VN-63 spring's room under the head (R9-71).
SPOT_FACE_FLOOR_TOLERANCE = ARM.SPOT_FACE_FLOOR_TOLERANCE

# The plate-tap stations are not BASIC: the taps carry no frame (they are
# transferred from MHA-PD-19 at assembly), so the sheet prints their
# stations as references.
BASIC_REDUCER_DIMENSIONS = (("StationReference", "PinStation"),)
BASIC_REDUCER_DIMENSIONS += tuple(
    ("LocatorProfile", name) for name in ("LocatorX1", "LocatorY1", "LocatorX2", "LocatorY2")
)
PART_DATUMS = (
    PartDatum("A", PlanarFace((0.0, 0.0, -1.0), 0.0)),
    PartDatum("B", CylinderFace(PIVOT_BORE_DIA)),
    PartDatum("C", CylinderFace(PIN_BORE_DIA, contains_x_mm=PIN_STATION)),
)
# The frames print in inches (#290). Delegated ruling 2026-11-07 (Main, no
# precedent; owner review #2144): no projected zone anywhere on MHA-PD-18
# (rule 26 bars the modifier). The pin bore S (datum C) takes ⌖ Ø.004 to
# A|B and a plain ⊥ Ø.001 to A over the bore, the reamed-hole row (owner
# ruling 2026-11-08 (Pedro), #2144 item 4.1). The axis it allows, the bonded
# pin leaning in the bore's gap and run on to the chain plane in front of face A, is
# paper_drive_arm_registration.S_AXIS_ZONE_DIAMETER_MM: the meshes and the
# platen air charge it, and MHA-PD-00's collar feeler accepts the collar air
# it closes (pd_cluster_air.ASSEMBLY_ACCEPTED_COLLAR_SOURCES).
GEOMETRIC_TOLERANCES_IN = {"position": ".004", "perpendicularity": ARM.PIN_BORE_PERPENDICULARITY_IN}
GEOMETRIC_TOLERANCES_MM = {key: float(value) * 25.4 for key, value in GEOMETRIC_TOLERANCES_IN.items()}
if GEOMETRIC_TOLERANCES_MM["position"] > REDUCER_POSITION_DIAMETER:
    raise AssertionError("MHA-PD-18 prints a reducer position zone wider than its stacks assume")
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "feed_stud_position", "position", GEOMETRIC_TOLERANCES_IN["position"],
        CylinderFace(PIN_BORE_DIA, contains_x_mm=PIN_STATION),
        ("A", "B"), "diametral",
    ),
    GeometricControl(
        "feed_stud_perpendicularity", "perpendicularity",
        GEOMETRIC_TOLERANCES_IN["perpendicularity"],
        CylinderFace(PIN_BORE_DIA, contains_x_mm=PIN_STATION),
        ("A",), "diametral",
    ),
    # No frame on the rear face (machinist review, rule 5): the precision-
    # ground stock's thickness band carries its parallelism to A
    # (paper_drive_arm_registration.ARM_OPPOSITE_FACE_PARALLELISM_MM). No
    # frame on the plate taps: spotted and drilled through MHA-PD-19's
    # screw holes at assembly, the plate doweled on, PD-19's holes are the
    # master (the tap callout says so).
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


# The press and its proud set are assembly (MHA-PD-00 "arm-plate-located").
# The sheet's callout and its note 2 name the dowel the reamed holes take,
# its press by trial (the dowel does not enter by hand), what the press
# protects (the plate's return to the reducer mesh setting) and what the
# small mouth breaks keep: the dowel's full-diameter grip
# (``pd_transgear_arm_geometry.LOCATOR_FULL_CYLINDER_SPAN_MIN_MM``), with the
# match-drill with the plate and its assembly step.  The range is ANALYSIS,
# not printed: the dowel's catalogue band against what the .1240 set reamer
# is modelled to cut.
LOCATOR_PRESS_INTERFERENCE = (
    LOCATOR_PIN.DIA_LIMITS[0] - ARM.LOCATOR_HOLE_REAMED_LIMITS_MM[1],
    LOCATOR_PIN.DIA_LIMITS[1] - ARM.LOCATOR_HOLE_REAMED_LIMITS_MM[0],
)
if LOCATOR_PRESS_INTERFERENCE[0] <= 0.0:
    raise AssertionError("the MHA-PD-18 locating ream loses MHA-PD-VN-64's press")
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
# The thickness is the stock's: it prints "3/8 (.3750) GROUND STOCK REF",
# prefix and suffix around the imported model value, which the parentheses
# mark as reference, so the title block's rows never apply to it.  A
# supplier size prints untoleranced and the supplier's catalogue tolerance
# governs it (fleet supplier-REF ruling, #2147); the seat tilt and the plate
# screw's engagement are judged at that catalogue tolerance,
# ``pd_transgear_arm_geometry.THICKNESS_BAND`` (codjiflo review of #2015).
STOCK_TEXT_PREFIX = f"{STOCK_THICKNESS_IN} ("
# REF: an as-bought size with the supplier's tolerance (units guidance).
STOCK_TEXT_SUFFIX = ") GROUND STOCK REF"

# --- The MHA-PD-23 pin's bonded slip fit in the reamed bore at S (R9-68) -------
# Fit audit 2026-11-23 (pending owner confirmation): the pin is one diameter
# and is bonded in the bore with LOCTITE 638; nothing presses.  The pin spec
# owns the bond (it imports the arm geometry, so the geometry cannot import
# it back).  The bore stays REAMED and prints the reamer's size with no
# band: its gap is the lean the pin's axis is allowed
# (paper_drive_arm_registration.S_AXIS_TILT_MAX_RAD), and a drilled #30
# (.1285 +.004/0) would open it past what the meshes and the airs clear.
# ``pd_transgear_arm_geometry.PIN_BORE_DIA_BAND`` is the ANALYSIS band the
# set reamer is modelled to cut, not a printed limit.  The acceptance is the
# pin entering with no shake and, as the gap's single upper limit, one pin
# of the .001-step set that must not enter.
# (PIN_BORE_DIA_PLACES above: three places, Ø.126 REAM THRU.)
PIN_BOND_GAP = PIN.BOND_GAP  # modelled (least, greatest) diametral
PIN_BORE_NO_GO_PIN_DIA = 3.2258  # .127, one pin of the .001-step set
PIN_BORE_NO_GO_PLACES = 3
_SET_PIN_UNDER_SIZE_MAX = 0.00508  # .0002, a Class ZZ minus pin
# The widest gap the sheets accept: a bore that just refuses the .127 pin,
# on the pin's smallest modelled shank.
PIN_BOND_GAP_ACCEPTED_MAX = round(PIN_BORE_NO_GO_PIN_DIA - PIN.DIA_MIN, 6)  # .0022
# Rule 23: the bond's clearance as the bore's callout prints it, the least
# the reamer and the pin model to the most the .127 NO-GO accepts.
PIN_BOND_CLEARANCE_PRINTED = (PIN_BOND_GAP[0], PIN_BOND_GAP_ACCEPTED_MAX)  # .0010-.0022
if not 0.0 < PIN_BOND_GAP[0] <= PIN_BOND_GAP[1] <= PIN_BOND_GAP_ACCEPTED_MAX:
    raise AssertionError(
        f"MHA-PD-18 pin bore bond gap on MHA-PD-23 is {PIN_BOND_GAP}, outside "
        f"0..{PIN_BOND_GAP_ACCEPTED_MAX}"
    )
if PIN_BOND_GAP_ACCEPTED_MAX > PIN.LOCTITE_638_GAP_MAX:
    raise AssertionError("the .127 NO-GO accepts a gap over LOCTITE 638's gap fill")
if ARM.PIN_BORE_DIA_MAX >= PIN_BORE_NO_GO_PIN_DIA - _SET_PIN_UNDER_SIZE_MAX:
    raise AssertionError(
        "the smallest .127 set pin enters a pin bore inside the reamer's modelled band"
    )
# The true overall, pivot-end extreme to the square end, prints as a
# reference; a derived reference has no part-side places, so the spec owns
# its digits (three).
OVERALL_LENGTH = PIVOT_END_R + TIP_STATION
DRAWING_REFERENCE_PRECISION = 3

# --- The MHA-PD-VN-58 latch pin's press in the blind ream -------------------------
# (loosest, tightest), ANALYSIS: what the .1240 set reamer is modelled to cut
# against the dowel's catalogue band.  The sheet prints neither a band nor
# this range: the dowel is the gauge, it does not enter by hand.
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
# A dowel that slides in by hand is bonded (MHA-PD-00's bond note) instead of
# a new arm.  Even a hole cut the DRILLED HOLES row over the reamer's size
# keeps the smallest dowel inside LOCTITE 638's gap.
LATCH_PIN_BOND_GAP_MAX = round(
    PIN_HOLE_DIA + drilled_oversize_mm(unit=ARM.UNIT)
    - LATCH_PIN.DIA - min(LATCH_PIN.DIA_BAND),
    6,
)
if LATCH_PIN_BOND_GAP_MAX > LOCATING_PIN.BOND_GAP_LIMIT_MM:
    raise AssertionError("a bonded MHA-PD-VN-58 exceeds the retaining compound's gap")
# The depth MIN's native record (#3124; swTolMIN prints only the model value
# and MIN): its upper deviation is the deepest hole that still holds the wall
# target at the faces, its drill run-off charged, and from its point to the
# pin bore (the latter governs on the 3/8 bar, #2019).
PIN_HOLE_DEPTH_BAND = (
    round(
        min(
            (ARM.WALLS["pin hole to faces"][1] - ARM.WALL_TARGET)
            / math.tan(math.radians(ARM.DRILL_RUN_OFF_DEG)),
            ARM.WALLS["latch-pin hole point to pin bore"][1] - ARM.WALL_TARGET,
        ),
        6,
    ),
    0.0,
)

ISO_VIEW_SCALE = (1, 2)
ISOMETRIC_VIEW_NOTE = f"ISOMETRIC VIEW SCALE {ISO_VIEW_SCALE[0]}:{ISO_VIEW_SCALE[1]}"

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity-policy.md `How the repository implements the guidelines`).  The hole stations live in the blanked
# ``StationReference`` sketch: the Hole Wizard placement sketches that drive
# the taps are not importable, and the pin bore's station prints with them.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArmOutline": {"PivotEndR", "TipStation", "EndWidth", "FlankAngle"},
    "Arm": {"Depth"},
    "PivotBoreProfile": {"PivotBoreDia"},
    "PinBoreProfile": {"PinBoreDia"},
    "PinBoreRearMouthProfile": {"PinMouthChamfer"},
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
        "FlankAngle": FLANK_ANGLE_PLACES,
    },
    "Arm": {"Depth": THICKNESS_PLACES},
    "PivotBoreProfile": {"PivotBoreDia": PIVOT_BORE_PLACES},
    "PinBoreProfile": {"PinBoreDia": PIN_BORE_DIA_PLACES},
    "PinBoreRearMouthProfile": {"PinMouthChamfer": ARM.PIN_MOUTH_CHAMFER_PLACES},
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
