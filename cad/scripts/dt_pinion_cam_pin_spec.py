r"""Pure-data dimensional contract shared by the pinion cam-follower pin and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A short drill-rod stud bonded into the
swing strap's west edge, riding on the eccentric cam collar.  The nominals drive
the part's named equation globals AND the drawing's coordinate math; the
marked-dimension map keeps the part marks and drawing keeps in lockstep
(``test_dt_pinion_cam_pin_drawing.py``).
"""

from __future__ import annotations

import _config
from _gtol_cylinder import CylinderFace
from _package_units import drawing_unit
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from dt_pinion_bracket_geometry import PIN_BORE as SEAT_DIA
from dt_pinion_cam_pin_geometry import (
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    PIN_DIA as PIN_DIA,
    PIN_LEN as PIN_LEN,
    SEAT_LEN as SEAT_LEN,
)
# The strap's seat band (dt_pinion_bracket_spec.PIN_SEAT_DIA_BAND), restated
# so this closure stays off the strap spec; the drawing test pins the two
# equal.  Owner ruling 2026-11-23, tool audit Q8: .157 +.003/0.
SEAT_BAND = (0.0762, 0.0)

# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/dt-pinion-cam-pin", _config.parts("dt-pinion-cam-pin"))

# U27 (Main, 2026-09-23): no press.  The stud is stock drill rod slipped into
# the MHA-DT-14 strap's follower seat and bonded with LOCTITE 638, inside the
# 0.25 mm bond gap the 638 data sheet allows (the U6 drum-to-arbor
# precedent).  A novice cannot hold the old +/-0.004 press band.  #290: 5/32
# O1 drill rod at the supplier's .1563 +/-.0005 in, in the .157 +.003/.000
# end-milled seat (owner ruling 2026-11-23, tool audit Q8).
PIN_DIA_BAND = (0.0127, -0.0127)  # (upper, lower): +/-.0005 in, the drill rod's
SEAT_NUMBER = "MHA-DT-14"
RETAINING_COMPOUND = "LOCTITE 638"
RETAINING_COMPOUND_MAX_GAP_MM = 0.25
# The length and the crown radius set nothing: the cam rides the shank about
# 15 from the seated end, 5 short of the crown root (build_dt_drive_train_assembly
# _FPIN_S0/_S_CAM), and no part reaches the crown.  Their two places take the
# title block's .XX band (drawing-guidelines.md rule 3 (decimal places carry
# the tolerance)); the old +/-0.05 bands named no mate (machinist review r1 of
# #1009).

# drawing-guidelines.md rule 11 (turned parts read like the lathe) (turned parts): the shank is a Right-plane half-profile, so its
# diameter prints on the side view beside the length, not on the end view
# (machinist review of 7f7fc1717).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "Depth"},
    "CapProfile": {"CapR"},
}
# Decimal places ARE the tolerance statement (drawing-guidelines.md rule 3 (decimal places carry the tolerance)): the drill
# rod's REF size prints its catalogue .1563 at four, and the length and crown
# radius take the .XX band.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 4, "Depth": 2},
    "CapProfile": {"CapR": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked dimension must state its decimal places")

# The shank is the drill rod as bought and never cut, so it prints the stock,
# not limits of size (drawing-guidelines.md rule 4: "a diameter that is
# bought to size and never cut prints the stock"): the size REF, "(Ø.1563)",
# and "5/32 DRILL ROD, AS SUPPLIED" under it, with the bonded fit by its
# standard name and LOCTITE grade.  Machinist review r1 (farm run
# 20261124T110807008Z, over-specification): the ±.0005 banded a bought
# diameter.  Fit audit F22's "keep" carries no owner ruling, so the stock
# form stands (drawing-guidelines rule 4, form 4's bought-to-size clause).  PIN_DIA_BAND stays
# the supplier's catalogue band, the input to BOND_CLEARANCE_MIN/MAX; it
# prints nowhere.  The fraction is the registry row's (its Material cell).
STOCK = _config.parts("dt-pinion-cam-pin")["material"]
if "drill rod, 5/32 in" not in STOCK.lower():
    raise AssertionError(f"the bonded slip fit assumes 5/32 drill rod, not {STOCK!r}")
PIN_DIA_CALLOUT = (
    "5/32 DRILL ROD, AS SUPPLIED; BONDED FIT IN\n"
    f"{SEAT_NUMBER} FOLLOWER SEAT, {RETAINING_COMPOUND}"
)
DEPTH_CALLOUT = "SEATED FLAT END\nTO CROWN ROOT"
CAP_RADIUS_CALLOUT = "OUTER CROWN"

# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs,
# slides or locates): the cam rides the shank, a cam-follower contact, so
# the shank carries Ra 63 uin (ground drill rod meets it as received; Codex P2 on
# #1687).  Name both the function and its physical surface so the free crown
# cannot be mistaken for the contact (epoch4 review of #1687).  This remains
# the existing whole cylindrical-face control, not a localized contact band.
# The crown touches nothing and carries no symbol (machinist review r1).
SHANK_FINISH_TARGET = "CAM CONTACT - SHANK OD"
SURFACE_FINISHES = (
    SurfaceFinishControl(
        key="shank",
        roughness_um=MACHINED_UM,
        face=CylinderFace(diameter_mm=PIN_DIA),
        production_method=SHANK_FINISH_TARGET,
        display_unit=UNIT,
    ),
)

# The bond gap between the stud's and the seat's printed limits (the seat's
# band is the strap spec's).
BOND_CLEARANCE_MIN = round(SEAT_DIA + SEAT_BAND[1] - (PIN_DIA + PIN_DIA_BAND[0]), 6)
BOND_CLEARANCE_MAX = round(SEAT_DIA + SEAT_BAND[0] - (PIN_DIA + PIN_DIA_BAND[1]), 6)
if BOND_CLEARANCE_MIN < 0.0 or BOND_CLEARANCE_MAX > RETAINING_COMPOUND_MAX_GAP_MM:
    raise AssertionError(
        f"bonded pin gap {BOND_CLEARANCE_MIN}-{BOND_CLEARANCE_MAX} is outside the"
        f" 0-{RETAINING_COMPOUND_MAX_GAP_MM} {RETAINING_COMPOUND} window"
    )

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): assembly requirements belong on the feature callout or the
# assembly step, never in a part's general notes.  ASSEMBLY_STEP is the
# pinion fit-up step text (pinion_rig_fitup) that owns this joint.  The sheet
# has no general notes: the crown root takes the title block's edge break like
# every other edge (machinist review r1 of #1009).
# One pin per strap: the count prints, or a fitter bonds one and stops.
_PIN = _config.parts("dt-pinion-cam-pin")
ASSEMBLY_STEP = (
    f"BOND {_PIN['quantity']}X {_PIN['number']}, ONE INTO EACH {SEAT_NUMBER} "
    f"FOLLOWER SEAT WITH {RETAINING_COMPOUND}."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"
# The overall (seated end to crown apex) is a pure reference restatement;
# its places are specification (drawing-guidelines.md rule 3 (decimal places carry the tolerance)).
DRAWING_REFERENCE_PRECISION = 2
