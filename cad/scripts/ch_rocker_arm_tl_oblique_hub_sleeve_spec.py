r"""MHA-CH-06-TL-34: oblique-trammel hub sleeve, dimensional contract.

PURE DATA, no SolidWorks/COM and no drawing imports.  Shop fixture tooling
(cad/docs/subsystem-identities.md): the loose turned steel sleeve on the TL-33
hub stud's shank inside the TL-24 riser's HUB clearance.  It carries the
MHA-CH-13 strap under the TL-35 washer, where the riser's 9/16 self-cut has
removed the riser around the hub, so the hub screw's clamp lands on steel on
the carrier, not on the strap's unsupported span.

It goes on after the riser is self-cut (the cutter's band reaches inside its
O.D.); flush with the riser top so the strap seats on both, it is a matched
length (rule 4): its thickness is faced to the actual riser's, flush to .002
below.  The bore is reamed .4000 (REAM_H7, the shop's queued .4000 reamer,
``tools.reamers-inch-purchases``) over the stud's .3990-.3995 shank.

Part frame: sleeve axis +Z through the origin (``Axis1``, Top Plane x Right
Plane); the carrier-side face on the Front Plane (z = 0), the strap-side face
at z = LENGTH.
"""

from __future__ import annotations

import _config
import ch_rocker_arm_tl_oblique_hub_stud_spec as stud
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _fit_ream_h7 import REAM_H7
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from ch_rocker_arm_spec import inch_text

STEM = "ch-rocker-arm-tl-oblique-hub-sleeve"
UNIT = drawing_unit(f"parts/{STEM}", _config.parts("ch-rocker-arm-tl-oblique-hub-sleeve"))
NUMBER = _config.parts("ch-rocker-arm-tl-oblique-hub-sleeve")["number"]
QUANTITY = 1

# The O.D. keeps the .XXX row: the jig's holding proof charges its printed
# maximum against the 3/8 strap cutter's flank (with the carrier's HUB stack,
# the stud's slip and this sleeve's float), and the final correlated stack
# leaves .054 mm there; the .XX row's extra .127 mm on the diameter
# (.0635 radial) would close it.  The sheet states that function.
OD = 14.732  # .580
OD_PLACES = 3
ID = 10.16  # .4000, the reamer's size
ID_BAND = REAM_H7
ID_PLACES = 4
LENGTH = trammel.RISER_THICK  # .24, matched to the actual riser
LENGTH_PLACES = 2
# Matched fit at assembly: flush to .002 below the riser's top.
FLUSH_BELOW_MAX = 0.0508  # .002

_OD_MIN = OD - printed_band_mm(OD_PLACES, unit=UNIT)
_ID_MAX = ID + ID_BAND[0]
WALL_MIN = (_OD_MIN - _ID_MAX) / 2.0
# Radial float on the stud shank, at the fit's loosest.
SHANK_FLOAT_MAX = (_ID_MAX - (stud.SHANK_DIA + stud.SHANK_DIA_BAND[1])) / 2.0
SHANK_CLEARANCE_MIN = ID + ID_BAND[1] - (stud.SHANK_DIA + stud.SHANK_DIA_BAND[0])
if WALL_MIN < WALL_TARGET_MM:
    raise AssertionError("the hub sleeve wall breaks rule 17's .080 target")
if SHANK_CLEARANCE_MIN <= 0.0:
    raise AssertionError("the hub sleeve does not slip over the stud shank")
if OD >= stud.FLANGE_DIA:
    raise AssertionError("the hub sleeve overhangs the stud flange's footprint")

# Marked model dimensions and the places the part authors on them.  The end
# view's O.D. moves onto the side view with the length (rule 11); the reamed
# bore stays in the end view with its REAM callout.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SleeveProfile": {"SleeveOd", "SleeveBore"},
    "Sleeve": {"SleeveLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "SleeveProfile": {"SleeveOd": OD_PLACES, "SleeveBore": ID_PLACES},
    "Sleeve": {"SleeveLength": LENGTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for names in DRAWING_PRECISION.values() for name, places in names.items()
}
# (feature, dimension) -> (upper, lower) native band.
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("SleeveProfile", "SleeveBore"): ID_BAND,
}

RISER_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-riser")["number"]
# The jig assembly's drawing number (ch_rocker_arm_tl_oblique_jig_assembly_spec
# .DRAWING_NUMBER, not imported: that module imports this one).
JIG_NUMBER = "MHA-CH-06-TL-00"
# Rule 12: the bore says ream and names its mate (rule 4); the O.D. says what
# its .XXX row protects; the length is the matched fit, naming the riser and
# the feature it matches, with its acceptance.
DIMENSION_CALLOUTS: dict[str, str] = {
    "SleeveBore": f"REAM\nSLIP ON HUB STUD\n{stud.NUMBER} SHANK",
    "SleeveOd": f"MAX CLEARS 3/8 STRAP\nCUTTER SWEEP ON JIG\n{JIG_NUMBER}",
    "SleeveLength": (
        f"MATCH RISER {RISER_NUMBER}\nTHICKNESS AT HUB: FLUSH\n"
        f"TO {inch_text(FLUSH_BELOW_MAX, 3)} BELOW ITS TOP"
    ),
}
