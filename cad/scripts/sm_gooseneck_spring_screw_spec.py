"""Pure-data drawing contract for MHA-SM-04, the gooseneck spring screw.

PURE DATA -- no SolidWorks/COM imports.  ``sm_gooseneck_spring_screw_geom``
owns every size and band; this module adds only what the print states: the
marked dimensions, their authored places, the callouts and the notes.

The title block's band for each mark's places governs every size but the
relief diameter and its 45-degree lead.  The relief Ø prints as the native
LIMIT band 2.20/2.00: the die root caps it, and the neck's clamp-torque
strength (derived below) floors it.  The lead prints as a single MAX limit
(the model value is the limit) from the hidden ``LeadReference`` sketch on
the profile's lower silhouette, driven by the profile's ``ReliefLead``.
"""

from __future__ import annotations

import math

import _config
from sm_gooseneck_spring_screw_geom import (
    CROWN_RISE,
    CROWN_RISE_LOWER,
    CROWN_RISE_UPPER,
    HEAD_H,
    HEAD_H_LOWER,
    MAJOR_DIA,
    PITCH,
    RELIEF_DIA_MIN,
    SLOT_DEPTH,
    SLOT_DEPTH_LOWER,
    SLOT_DEPTH_UPPER,
    THREAD,
)

THREAD_CALLOUT = THREAD
CHAMFER_CALLOUT = "X 45 DEG"
# Below-value callouts the PART authors on its dimensions (the drawing only
# reads them back; a drawing-side SetText can write through to the part,
# #1942).  The lead's MAX and the relief's LIMIT band are tighter than the
# title block, so each names what it serves (drawing-guidelines.md rule 4):
# the flat under-head seat that clamps the counter spring's upper loop, and
# the neck's strength under the clamp torque.
COUNTER_SPRING = _config.parts("sm-vn-counter-spring")
COUNTER_SPRING_NUMBER = str(COUNTER_SPRING["number"])
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "LeadReference": {
        "HeadLead": f"{CHAMFER_CALLOUT}\nFLAT SEAT FOR\n{COUNTER_SPRING_NUMBER} LOOP"
    },
    "ShankProfile": {
        "ReliefDia": "MIN FOR\nCLAMP TORQUE",
        "TipChamfer": CHAMFER_CALLOUT,
    },
}
DIMENSION_CALLOUTS_BY_NAME: dict[str, str] = {
    name: text for callouts in DIMENSION_CALLOUTS.values() for name, text in callouts.items()
}

# The relief neck's floor, Ø2.00.  The repo holds no installation torque (user
# ruling 2026-09-21: the fitter tightens until the loop cannot swivel, no
# torque value), so the neck's load is derived from the clamp's job, and the
# assumptions are stated:
#  * The clamp must hold the counter spring's catalog maximum load,
#    MHA-SM-VN-51's ``maximum_load_n`` (69.3 N), by friction alone on the
#    loop's two clamped faces (under-head and plug face).  This is
#    conservative, because the loop also bears on the shank.  ASSUMED dry
#    steel friction 0.15 on the faces and in the thread.  That needs a
#    preload of 69.3 / (2 x 0.15) = 231 N.
#  * The driver turns the head, and the under-head friction reacts at the
#    head, ahead of the neck, so the neck carries the preload plus only the
#    thread's share of the torque: F (d2 / 2) (tan L + mu sec 30) /
#    (1 - mu tan L sec 30) on the basic #6-32 pitch diameter, about 0.090 N-m.
#  * At Ø2.00 that is 73.5 MPa of tension with 57.5 MPa of torsional shear,
#    124 MPa von Mises.  ASSUMED yield of the weaker listed stock, 1018
#    cold-finished: 370 MPa (12L14 cold-drawn is about 415 MPa).  The safety
#    factor is about 3.0.  The floor must keep at least 2.
CLAMP_FRICTION = 0.15  # ASSUMED dry steel, faces and thread
CLAMP_FACES = 2
CLAMP_PRELOAD_N = float(COUNTER_SPRING["maximum_load_n"]) / (
    CLAMP_FACES * CLAMP_FRICTION
)
THREAD_PITCH_DIA = MAJOR_DIA - 0.649519 * PITCH  # basic, ASME B1.1
_TAN_LEAD = PITCH / (math.pi * THREAD_PITCH_DIA)
_SEC_FLANK = 1.0 / math.cos(math.radians(30.0))
NECK_TORQUE_NM = (
    CLAMP_PRELOAD_N
    * THREAD_PITCH_DIA
    / 2000.0
    * (_TAN_LEAD + CLAMP_FRICTION * _SEC_FLANK)
    / (1.0 - CLAMP_FRICTION * _TAN_LEAD * _SEC_FLANK)
)
NECK_TENSION_MPA = CLAMP_PRELOAD_N / (math.pi / 4.0 * RELIEF_DIA_MIN**2)
NECK_SHEAR_MPA = 16.0 * NECK_TORQUE_NM * 1000.0 / (math.pi * RELIEF_DIA_MIN**3)
NECK_VON_MISES_MPA = math.hypot(NECK_TENSION_MPA, math.sqrt(3.0) * NECK_SHEAR_MPA)
NECK_YIELD_MPA = 370.0  # ASSUMED 1018 cold-finished, the weaker listed stock
NECK_SAFETY_FACTOR_MIN = 2.0
NECK_SAFETY_FACTOR = NECK_YIELD_MPA / NECK_VON_MISES_MPA
if NECK_SAFETY_FACTOR < NECK_SAFETY_FACTOR_MIN:
    raise AssertionError("MHA-SM-04 relief floor cannot carry the clamp torque")

# drawing-guidelines.md rule 17 (walls and webs): the head left under the slot floor, at the shortest head,
# the deepest slot and a full under-head edge break, stays above the 2.0
# wall target (7.00 - 0.51 - 3.51 - 0.25 = 2.73).
EDGE_BREAK_MAX = float(_config.title_block("edge_break")["chamfer_max_mm"])
SLOT_WEB_TARGET = 2.0
SLOT_WEB_MIN = round(
    HEAD_H + HEAD_H_LOWER - (SLOT_DEPTH + SLOT_DEPTH_UPPER) - EDGE_BREAK_MAX, 6
)
if SLOT_WEB_MIN < SLOT_WEB_TARGET:
    raise AssertionError("spring-screw slot leaves under the drawing-guidelines.md rule 17 (walls and webs) head web")

# The crown rise is the only printed size that fixes the dome (the head Ø and
# height do not), so it controls at the .XX band.  Across that band the dome
# must stay a usable fillister head: the shallowest slot still cuts through
# the cylindrical rim under the tallest crown, so a full-width blade bears on
# both slot walls, and the tallest crown on the shortest head still leaves a
# cylindrical side after a full edge break.
CROWN_RISE_MIN = CROWN_RISE + CROWN_RISE_LOWER
CROWN_RISE_MAX = CROWN_RISE + CROWN_RISE_UPPER
SLOT_RIM_CUT_MIN = round(SLOT_DEPTH + SLOT_DEPTH_LOWER - CROWN_RISE_MAX, 6)
HEAD_SIDE_MIN = round(HEAD_H + HEAD_H_LOWER - CROWN_RISE_MAX - EDGE_BREAK_MAX, 6)
if CROWN_RISE_MIN <= 0.0 or SLOT_RIM_CUT_MIN <= 0.0 or HEAD_SIDE_MIN <= 0.0:
    raise AssertionError("spring-screw crown band does not leave a fillister head")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia", "HeadHeight", "CrownRise"},
    "ShankProfile": {"UnderHeadLength", "ReliefDia", "ReliefWidth", "TipChamfer"},
    "SlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
    "StationReference": {"OverallLength"},
    "LeadReference": {"HeadLead"},
}
# Chamfers never need extra places (drawing-guidelines.md rule 3): the tip
# chamfer rides the title block's .X band and the lead's single MAX limit
# prints at one place too.  Every other mark prints at two.
ONE_PLACE_DIMENSIONS = frozenset({"TipChamfer", "HeadLead"})
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {
        name: 1 if name in ONE_PLACE_DIMENSIONS else 2 for name in sorted(names)
    }
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
# The overall length is the stock cut-off, a restatement of the head height
# and under-head length; the crown rise is NOT a reference (see above).
REFERENCE_DIMENSIONS = frozenset({"OverallLength"})

# The fitter's clamp step (user ruling 2026-09-21: no torque value, no
# threadlocker) prints on the summing assembly sheet as MHA-SM-00 step 8,
# not here: a part sheet carries no assembly instruction (machinist review
# 2026-10-23).
DRAWING_NOTES = "\n".join(
    (
        "1. CROWN SPHERICAL THROUGH RIM AND APEX.",
        "2. THREAD MATES THE TAPPED END PLUG OF MHA-SM-01.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
