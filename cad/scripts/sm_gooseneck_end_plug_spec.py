r"""Pure-data print contract for MHA-SM-05, the gooseneck end plug.

PURE DATA, no SolidWorks/COM imports.  ``sm_gooseneck_geom`` owns every size
and ``sm_gooseneck_spring_joint`` the plug's bond clearance, tap and wall
budgets; this module adds what the print states: the marked model
dimensions, their places and callouts, the tap's callout rows and the notes.
``build_sm_gooseneck_end_plug`` marks and authors them on the part;
``draw_sm_gooseneck_end_plug`` places exactly ``DRAWING_DIMENSIONS``.

Design (owner rulings 2026-11-08 (Pedro), #2315).  The plug is its own part,
with its own drawing and MHA-SM-00 BOM row (not ``component_of``): a solid
AISI 1018 Ø.500 head, flush with MHA-SM-01's tube, PLUG_HEAD_LENGTH from the
end face to the tube's faced end, then a spigot turned to the measured tube
bore at the joint's diametral clearance, bonded into MHA-SM-01 with LOCTITE
638 at MHA-SM-00.  It is tapped #10-24 UNC-2B blind BEFORE bonding, for the
purchased MHA-SM-VN-56 shoulder screw (owner ruling 2026-11-08 (Pedro), #2144
item 11.4: plain tap, no counterbore, frames or datums).  Bare, no plating.

Every size is a native model dimension of ``EndPlugProfile``: the head Ø and
length, the spigot Ø (a reference: the fit governs, note 1) and the overall
length; the spigot length is their difference and prints no value of its
own.  The end view's native blind-tap callout names the screw and states its
full-thread engagement (rule 20, owner minor sm-gooseneck-end-plug RV-01).

Decimal-inch sheet (#290): every size prints at the places the joint's
budgets charge (sm_gooseneck_spring_joint).
"""

from __future__ import annotations

import math

import _config
import sm_gooseneck_geom as geom
import sm_gooseneck_spring_joint as joint
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations
from sm_vn_gooseneck_shoulder_screw_spec import MAJOR_DIA as SCREW_MAJOR_DIA

# Frozen Numbers (cad/docs/subsystem-identities.md); the drawing test checks
# each against its registry row.
NUMBER = "MHA-SM-05"
TUBE_NUMBER = "MHA-SM-01"
ASSEMBLY_NUMBER = "MHA-SM-00"
SCREW_NUMBER = "MHA-SM-VN-56"

# #290: the registry row's drawing_unit (in) is this sheet's unit; the joint
# charges the geometry module's SHEET_UNIT, so the two must agree.
UNIT = drawing_unit(
    "parts/sm-gooseneck-end-plug", _config.parts("sm-gooseneck-end-plug")
)
if UNIT != geom.SHEET_UNIT:
    raise AssertionError("MHA-SM-05's registry unit is not its geometry's SHEET_UNIT")

# The shoulder screw's engagement under rule 18's 1.5D stands only on owner
# minor RV-01 (sm_gooseneck_spring_joint.owner_minor).
if joint.ENGAGEMENT_MIN < joint.ENGAGEMENT_MIN_D * SCREW_MAJOR_DIA:
    joint.owner_minor(
        _config.parts("sm-gooseneck-end-plug"), "RV-01", "sm_gooseneck_end_plug"
    )

# Flush, no step: the head is the tube's own Ø (owner rulings 2026-10-27,
# #1951), and the spigot stands clear inside the tube's bore.
if not math.isclose(geom.PLUG_DIA, geom.TUBE_DIA, abs_tol=1e-9):
    raise AssertionError("gooseneck end plug's head is not flush with the tube OD")
if not joint.TAP_DRILL_DIA < joint.PLUG_SHANK_DIA < geom.TUBE_BORE_DIA:
    raise AssertionError("gooseneck end plug's spigot does not sit clear in the bore")
if not math.isclose(
    geom.PLUG_LENGTH, geom.PLUG_HEAD_LENGTH + geom.PLUG_SHANK_LENGTH, abs_tol=1e-9
):
    raise AssertionError("gooseneck end plug's length is not its head plus spigot")


def _inch(value_mm: float, places: int) -> str:
    """``value_mm`` as the sheet prints it: inches at ``places``, no leading
    zero."""
    return f"{value_mm / geom.MM_PER_IN:.{places}f}".removeprefix("0")


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  EndPlugProfile is the revolve's half-section on the Front
# plane: the head Ø and length, the spigot Ø and the overall length. ---
PROFILE = "EndPlugProfile"
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    PROFILE: {"PlugDia", "PlugHeadLength", "PlugShankDia", "PlugLength"},
}
# The spigot is turned to the measured MHA-SM-01 bore (note 1): its nominal
# is a reference and the clearance governs (round 2 of the SM-01 sheet,
# 20261107T110808280Z: a plain .363 beside the fit note was a second
# controlling value, rule 7).
REFERENCE_DIMENSIONS: dict[str, frozenset[str]] = {
    PROFILE: frozenset({"PlugShankDia"}),
}
# Inch places (#290): the head Ø and length and the overall length at the
# title block's .XX (the joint charges PLUG_DIA_DEVIATIONS and
# PLUG_HEAD_LENGTH_DEVIATIONS there); the spigot Ø at .XXX
# (PLUG_SHANK_DIA_DEVIATIONS).
THREE_PLACE_DIMENSIONS = frozenset({"PlugShankDia"})


def places(name: str) -> int:
    return 3 if name in THREE_PLACE_DIMENSIONS else 2


DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: places(name) for name in sorted(names)}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
# The joint's walls and drill envelopes are charged at exactly these places.
for _name, _mm, _deviations in (
    ("PlugDia", geom.PLUG_DIA, joint.PLUG_DIA_DEVIATIONS),
    ("PlugHeadLength", geom.PLUG_HEAD_LENGTH, joint.PLUG_HEAD_LENGTH_DEVIATIONS),
    ("PlugShankDia", joint.PLUG_SHANK_DIA, joint.PLUG_SHANK_DIA_DEVIATIONS),
):
    if printed_deviations(_mm, DRAWING_PRECISION_BY_NAME[_name], unit=UNIT) != (
        _deviations
    ):
        raise AssertionError(
            f"gooseneck end plug {_name} prints at other places than the joint charges"
        )

# The spigot's length is the overall less the head, each at the title block's
# .XX: its shortest still holds the shoulder screw's removal torque at the
# joint's margin (the bond's capacity scales with its length), and its
# longest stays short of the bend's exit tangent inside MHA-SM-01.
_OVERALL_DEVIATIONS = printed_deviations(geom.PLUG_LENGTH, 2, unit=UNIT)
SPIGOT_LENGTH_MIN = (
    geom.PLUG_LENGTH
    + _OVERALL_DEVIATIONS[0]
    - (geom.PLUG_HEAD_LENGTH + joint.PLUG_HEAD_LENGTH_DEVIATIONS[1])
)
SPIGOT_LENGTH_MAX = (
    geom.PLUG_LENGTH
    + _OVERALL_DEVIATIONS[1]
    - (geom.PLUG_HEAD_LENGTH + joint.PLUG_HEAD_LENGTH_DEVIATIONS[0])
)
BOND_TORQUE_CAPACITY_MIN = (
    joint.BOND_TORQUE_CAPACITY * SPIGOT_LENGTH_MIN / geom.PLUG_SHANK_LENGTH
)
if BOND_TORQUE_CAPACITY_MIN < joint.BOND_TORQUE_MARGIN_MIN * joint.SCREW_REMOVAL_TORQUE:
    raise AssertionError(
        "gooseneck end plug's shortest spigot does not hold the screw's removal torque"
    )
if SPIGOT_LENGTH_MAX >= geom.TUBE_STRAIGHT:
    raise AssertionError("gooseneck end plug's longest spigot reaches the bend")

# The bond window (sm_gooseneck_spring_joint.BOND_CLEARANCE_MIN/MAX), printed
# in inches rounded inward at three places, plain inch steps (machinist review
# of fanout/integration 8fb7fb46f7 on the SM-01 shank window: .0040-.0098 read
# as converted millimetres): the acceptance of a matched fit (fan-out policy
# 1; machinist review 20261107T102825912Z: as REF beside a .XXX spigot it set
# no limit), the spigot turned to the measured bore.
BOND_WINDOW = "-".join(
    f"{inches:.3f}".removeprefix("0")
    for inches in (
        math.ceil(round(joint.BOND_CLEARANCE_MIN / geom.MM_PER_IN * 1e3, 6)) / 1e3,
        math.floor(round(joint.BOND_CLEARANCE_MAX / geom.MM_PER_IN * 1e3, 6)) / 1e3,
    )
)

# Callouts the PART authors on its dimensions, below the value (the drawing
# imports and reads them back; a drawing-side SetText can write through to
# the part, #1942).  The spigot Ø names its fit once, on note 1 (rule 4).
FIT_NOTE = 1
SHANK_FIT_CALLOUT = f"SEE NOTE {FIT_NOTE}"
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    PROFILE: {"PlugShankDia": SHANK_FIT_CALLOUT},
}
DIMENSION_CALLOUTS_BY_NAME: dict[str, str] = {
    name: text
    for callouts in DIMENSION_CALLOUTS.values()
    for name, text in callouts.items()
}
if set(DIMENSION_CALLOUTS_BY_NAME) - set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("a gooseneck end plug callout names an unmarked dimension")

# The native blind-tap callout (end view): the title block's THREADS row owns
# the 2B class (drawing-guidelines.md rule 2), the tap's two depths print at
# the places their band is read at (sm_gooseneck_spring_joint.TAP_DEPTH_BAND),
# from the end face, the Hole Wizard start face.  Under the native rows: the
# screw it takes and, as a plain manufacturing fact (rule 20), its full-thread
# engagement under 1.5D (owner minor RV-01), floored to .001 and .01D.  Four
# rows in all (the layout audit's tall-block limit).  The drill Ø at .XXX
# (#25, .1495), the depths at .XX.
TAP_CALLOUT_PRECISION = {"hw-tapdrldia": 3, "hw-threaddepth": 2, "hw-tapdrldepth": 2}
ENGAGEMENT_STATEMENT = (
    f"ENGAGEMENT {f'{joint.ENGAGEMENT_CALLOUT_MIN:.3f}'.removeprefix('0')} MIN "
    f"({joint.ENGAGEMENT_CALLOUT_D:.2f}D)"
)
TAP_CALLOUT_BELOW = f"FOR {SCREW_NUMBER}\n{ENGAGEMENT_STATEMENT}"

# Two lines (drawing-guidelines.md rule 7), each ending left of the title
# block: the spigot's matched fit in the tube (linked from the spigot Ø), and
# the joint it makes, named once.  The sheet shows the plug alone, so it
# leaves the bench tapped and needs no order note; the bond itself is
# MHA-SM-00 STEP 8 (GoosePlug, relaying owner rulings 2026-11-08 (Pedro),
# #2315: no sequence note, no RV-02).  Material and finish are the title
# block's (registry row: AISI 1018 cold-drawn round; bare, no plating).
DRAWING_NOTES = "\n".join(
    (
        f"{FIT_NOTE}. TURN SPIGOT TO MEASURED {TUBE_NUMBER} BORE, "
        f"CLEARANCE {BOND_WINDOW}",
        f"2. BONDED INTO {TUBE_NUMBER} WITH LOCTITE 638 AT {ASSEMBLY_NUMBER}",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
