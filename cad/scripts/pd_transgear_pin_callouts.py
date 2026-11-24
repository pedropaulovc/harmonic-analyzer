"""Dimension text the MHA-PD-23 part authors on its marked dimensions.

The part builder writes every lane below on its source dimension; the
drawing imports them verbatim and only reads them back.  Setting dimension
text from the drawing writes through to the imported source dimension, and
the drawing's native save then saves the dirtied part outside its own recipe
(``cad/docs/pipeline/evidence/vm2-datum-placement/source-hash-cause.md``,
fleet issue #1942).  Kept out of ``pd_transgear_pin_spec``, which the cluster
fit, the bushings and the paper-drive assembly import.
"""

from __future__ import annotations

import _config
import pd_vn_transgear_retaining_ring_spec as RING
from pd_rack_pinion_spec import inch_ceil_mm, inch_floor_mm, inch_text
from pd_transgear_pin_spec import (
    ARM_NUMBER,
    BOND_CLEARANCE_PRINTED,
    FRONT_BUSHING_NUMBER,
    RETAINING_COMPOUND,
    RING_NUMBER,
    RUNNING_MATES,
    SEAT_FILLET_SUFFIX,
)

# The sheet's notes, the part's Manufacturing Notes property.  The bond into
# the arm is the MHA-PD-00 assembly's pin step; the part sheet gives the fit
# (rule 23).  Numbered note 1, linked from the shank's reference Ø by SEE
# NOTE 1, gives the shank's two fits (the bond: owner ruling 2026-11-24, fit
# audit question 4; rule 4, made to fit): it is turned last to its three mates'
# reamed bores and accepted by feel, a bought shim sliding on (the shims'
# smallest bore is the shank's ceiling); and it is bonded in the arm,
# accepted by sliding in by hand.  This sheet is the one acceptance of all
# four pairs, the pin being made last: the three running bores and the
# arm's bore print their REAM, that this pin is turned to them and what the
# REAM protects, and no acceptance of their own.  The note gives no reason:
# a reference size made to its mates carries no band to answer for, and
# machinist review r1 of the fit batch read "KEEPS DISC OFF MHA-PD-22"
# here as design rationale (rule 7); the bores' callouts answer rule 4's
# necessity test for their REAMs.  The bond's diametral clearance prints
# here and nowhere else (rule 23; fit batch review r2: the arm's sheet
# carried it, so the member made last printed no range): the least the
# reamer and the shank model to the most the arm traveler's .127 set pin
# accepts (pd_transgear_pin_spec.BOND_CLEARANCE_PRINTED), inside the
# compound's gap.  The ring groove's Ø and width
# name their ring once, in note 2 (rule 4).  Kept here, not in the widely
# imported spec, so the wording re-keys only this part.
SHANK_FIT_NOTE = 1
RING_GROOVE_NOTE = 2
SHIM_NUMBER = _config.parts("pd-vn-transgear-cluster-shim")["number"]
SHANK_ACCEPTANCE = "EACH TURNS FREE, NO SHAKE"
BOND_ACCEPTANCE = "SLIDES IN BY HAND"
BOND_CLEARANCE_TEXT = (
    f"{inch_text(inch_floor_mm(min(BOND_CLEARANCE_PRINTED), 4), 4)}-"
    f"{inch_text(inch_ceil_mm(max(BOND_CLEARANCE_PRINTED), 4), 4)}"
)
DRAWING_NOTES = "\n".join((
    f"{SHANK_FIT_NOTE}. SHANK: TURN LAST TO BORES OF {', '.join(RUNNING_MATES)}:",
    f"    {SHANK_ACCEPTANCE}; SHIM {SHIM_NUMBER} SLIDES ON.",
    f"    BONDED IN {ARM_NUMBER}, {RETAINING_COMPOUND}, CLEARANCE {BOND_CLEARANCE_TEXT}:",
    f"    {BOND_ACCEPTANCE}.",
    f"{RING_GROOVE_NOTE}. RING GROOVE Ø AND WIDTH: FOR RING {RING_NUMBER}",
    f"    (McMASTER {RING.SKU}).",
    "1/4 IN BAR STOCK OK.",
))

TEXT_PREFIX = 1  # swDimensionTextPrefix
TEXT_SUFFIX = 2  # swDimensionTextSuffix
CALLOUT_ABOVE = 3  # swDimensionTextCalloutAbove
CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

# The ring the groove takes is named once, in note 2, which both of the
# groove's catalogue bands, Ø and width, link to (rule 4: one feature with
# several tight dimensions names its mate once, on one note linked to all).
GROOVE_CALLOUT = f"SEE NOTE {RING_GROOVE_NOTE}"
# The shank's reference Ø links its fits in numbered note 1 (rule 7: a
# callout carries at most two lines of words; the fit route is the note's).
SHANK_CALLOUT = f"SEE NOTE {SHANK_FIT_NOTE}"
# The +/-.001 station names the stack it sets once, by drawing number (rule
# 4): the groove's load wall holds the ring that stops the front bushing and
# the sleeve (``transgear_cluster_fit.SLEEVE_REAR_FORWARD_CHAIN``); the end
# float is shimmed at assembly.
GROOVE_STATION_CALLOUT = f"SETS STACK OF MHA-PD-10 AND {FRONT_BUSHING_NUMBER}"

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    CALLOUT_ABOVE: {("PinProfile", "GrooveDia"): GROOVE_CALLOUT},
    CALLOUT_BELOW: {
        ("PinProfile", "ShankDia"): SHANK_CALLOUT,
        ("PinProfile", "GrooveStation"): GROOVE_STATION_CALLOUT,
        ("PinProfile", "GrooveWidth"): GROOVE_CALLOUT,
    },
    # The root radius is a single limit, its own one-line "R.005 MAX" (a
    # local MAX under the title block's inside corner needs no reason): the
    # modelled size IS the max, and the part authors the MAX (SolidWorks'
    # native swTolMAX prints "max.").
    TEXT_SUFFIX: {("SeatFillet", "SeatRadius"): SEAT_FILLET_SUFFIX},
}
if any("\n" in text for text in CALLOUTS[CALLOUT_ABOVE].values()):
    raise AssertionError("an above-callout with a line break never prints")

# The dome heights follow from each radius on its land's Ø, and the land
# ahead of the groove from the tip apex's station, the load wall's and the
# tip dome: all three print as REFERENCES, "(.03)", "(.04)", "(.12)"
# (rules 10 and 11: the land ends at the dome's junction, which the shop
# cannot pick up).  The shank's Ø is a reference too, "(Ø.125)": it is made
# to fit its mates' reamed bores (note 1), and the fit is the requirement.
REFERENCE_TEXT: dict[tuple[str, str], dict[int, str]] = {
    ("HeadDomeProfile", "HeadDomeSagDim"): {TEXT_PREFIX: "(", TEXT_SUFFIX: ")"},
    ("TipDomeProfile", "TipDomeSagDim"): {TEXT_PREFIX: "(", TEXT_SUFFIX: ")"},
    ("PinProfile", "FrontLand"): {TEXT_PREFIX: "(", TEXT_SUFFIX: ")"},
    ("PinProfile", "ShankDia"): {TEXT_PREFIX: "(<MOD-DIAM>", TEXT_SUFFIX: ")"},
}


def authored_text() -> dict[str, dict[str, dict[int, str]]]:
    """feature -> dimension -> lane -> text: everything the part writes."""
    authored: dict[str, dict[str, dict[int, str]]] = {}
    for lane, rows in CALLOUTS.items():
        for (feature, name), text in rows.items():
            authored.setdefault(feature, {}).setdefault(name, {})[lane] = text
    for (feature, name), lanes in REFERENCE_TEXT.items():
        authored.setdefault(feature, {}).setdefault(name, {}).update(lanes)
    return authored


def authored_by_name() -> dict[str, dict[int, str]]:
    """dimension name -> lane -> text (the drawing's identity is the name)."""
    return {
        name: lanes
        for by_name in authored_text().values()
        for name, lanes in by_name.items()
    }


def callout_rows(text: str) -> tuple[str, ...]:
    """A callout's rows, independent of CRLF."""
    return tuple(row.strip() for row in text.replace("\r", "").split("\n"))


def callouts_by_lane(lane: int) -> dict[str, str]:
    """One lane's rows keyed by dimension name (the drawing's identity)."""
    return {name: text for (_feature, name), text in CALLOUTS[lane].items()}
