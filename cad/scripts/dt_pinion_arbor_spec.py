r"""Pure-data dimensional contract for the integral MHA-DT-22 pinion arbor.

The turned head, neck, and long shaft are deliberately one piece.  This is an
approved photo-derived reconstruction choice, not proof of the historical
joint detail.  The exact released external envelope is preserved while the
former socket and unsupported radial retention pin are removed.

The geometry -- envelope, drum station and journal-land stack -- lives in
``dt_pinion_arbor_geometry`` and is re-exported here; this module adds the
drawing contract (marks, precision, finishes, notes).
"""

from __future__ import annotations

from _gtol_cylinder import CylinderFace
from _printed_tolerance import edge_break_radius_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from dt_pinion_arbor_geometry import (
    BACK_CAP_R as BACK_CAP_R,
    BACK_CAP_SAG as BACK_CAP_SAG,
    BACK_JOURNAL_FROM_HEAD_REAR as BACK_JOURNAL_FROM_HEAD_REAR,
    BACK_JOURNAL_Z as BACK_JOURNAL_Z,
    BACK_RIM_FROM_HEAD_REAR as BACK_RIM_FROM_HEAD_REAR,
    BOND_ZONE_DIA_FROM_HEAD_REAR as BOND_ZONE_DIA_FROM_HEAD_REAR,
    BOND_ZONE_DIA_Z as BOND_ZONE_DIA_Z,
    BOND_ZONE_LAND_CLEARANCE as BOND_ZONE_LAND_CLEARANCE,
    CROSS_HOLE_DIA as CROSS_HOLE_DIA,
    CROSS_HOLE_DIA_BAND as CROSS_HOLE_DIA_BAND,
    CROSS_HOLE_FRONT_WEB_WORST as CROSS_HOLE_FRONT_WEB_WORST,
    CROSS_HOLE_REAR_WEB_WORST as CROSS_HOLE_REAR_WEB_WORST,
    CROSS_HOLE_STATION as CROSS_HOLE_STATION,
    CROSS_HOLE_STATION_BAND as CROSS_HOLE_STATION_BAND,
    CROSS_HOLE_STATION_PLACES as CROSS_HOLE_STATION_PLACES,
    CROSS_HOLE_WEB_TARGET as CROSS_HOLE_WEB_TARGET,
    CROSS_HOLE_WEB_WORST as CROSS_HOLE_WEB_WORST,
    CROSSROD_MAX_CLEARANCE as CROSSROD_MAX_CLEARANCE,
    CROSSROD_MIN_CLEARANCE as CROSSROD_MIN_CLEARANCE,
    DRUM_AFT_SHIFT as DRUM_AFT_SHIFT,
    DRUM_FRONT_Z_AS_BUILT as DRUM_FRONT_Z_AS_BUILT,
    DRUM_LEN as DRUM_LEN,
    DRUM_LEN_BAND as DRUM_LEN_BAND,
    DRUM_STATION as DRUM_STATION,
    DRUM_STATION_AS_BUILT as DRUM_STATION_AS_BUILT,
    DRUM_STATION_BAND as DRUM_STATION_BAND,
    drum_total_air as drum_total_air,
    END_PLAY as END_PLAY,
    END_PLAY_SET_ERROR as END_PLAY_SET_ERROR,
    EXPOSED_SHAFT_LEN as EXPOSED_SHAFT_LEN,
    FRONT_JOURNAL_FROM_HEAD_REAR as FRONT_JOURNAL_FROM_HEAD_REAR,
    FRONT_JOURNAL_Z as FRONT_JOURNAL_Z,
    HEAD_CAP_R as HEAD_CAP_R,
    HEAD_CAP_SAG as HEAD_CAP_SAG,
    HEAD_CENTER_Z as HEAD_CENTER_Z,
    HEAD_DIA as HEAD_DIA,
    HEAD_FRONT_Z as HEAD_FRONT_Z,
    HEAD_LEN as HEAD_LEN,
    HEAD_CAP_SAG_PLACES as HEAD_CAP_SAG_PLACES,
    HEAD_LEN_BAND as HEAD_LEN_BAND,
    HEAD_LEN_PLACES as HEAD_LEN_PLACES,
    HEAD_REAR_Z as HEAD_REAR_Z,
    JOURNAL_DIA_BAND as JOURNAL_DIA_BAND,
    JOURNAL_LEN as JOURNAL_LEN,
    LAND_ENDS as LAND_ENDS,
    LAND_FINISH_RUNOUT as LAND_FINISH_RUNOUT,
    land_margin_slack as land_margin_slack,
    LAND_MARGINS_AT_STOPS as LAND_MARGINS_AT_STOPS,
    LAND_OVER_STRAP_REQUIRED as LAND_OVER_STRAP_REQUIRED,
    land_stations as land_stations,
    LINEAR_XX_BAND as LINEAR_XX_BAND,
    MIN_END_PLAY as MIN_END_PLAY,
    MIN_LAND_OVER_STRAP as MIN_LAND_OVER_STRAP,
    NECK_DIA as NECK_DIA,
    NECK_END_Z as NECK_END_Z,
    NECK_LEN as NECK_LEN,
    NECK_LEN_PLACES as NECK_LEN_PLACES,
    OVERALL_LEN as OVERALL_LEN,
    PIN_STATION_BAND as PIN_STATION_BAND,
    PIN_STATION_FROM_HEAD_REAR as PIN_STATION_FROM_HEAD_REAR,
    PIN_Z as PIN_Z,
    RELEASED_ARBOR_ROOT_Z as RELEASED_ARBOR_ROOT_Z,
    RELEASED_DRUM_FRONT_Z as RELEASED_DRUM_FRONT_Z,
    RETAINING_COMPOUND as RETAINING_COMPOUND,
    RETAINING_COMPOUND_MAX_GAP_MM as RETAINING_COMPOUND_MAX_GAP_MM,
    SHAFT_DIA as SHAFT_DIA,
    SHAFT_DIA_BAND as SHAFT_DIA_BAND,
    SHAFT_LEN as SHAFT_LEN,
    STOPS as STOPS,
    STRAP_AXIAL_LOCATION as STRAP_AXIAL_LOCATION,
    UNIT as UNIT,
    worst_land_margins as worst_land_margins,
)

SURFACE_FINISHES = tuple(
    SurfaceFinishControl(
        key,
        MACHINED_UM,
        CylinderFace(SHAFT_DIA, contains_z_mm=station + JOURNAL_LEN / 2.0),
        display_unit=UNIT,
    )
    for key, station in (
        ("front_journal", FRONT_JOURNAL_Z),
        ("back_journal", BACK_JOURNAL_Z),
    )
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    # Head and neck diameters are Front-plane circles: imported end-on on the
    # donor view and moved onto the 1:1 profile (5cc191fb's proven path; a
    # detail silhouette screen pick is seat-dependent and failed on w6).  The
    # Ø5/16 is not: its circle's witnesses crossed the neck face, so the bond
    # zone carries its own flank diameter (BondZoneReference).
    "HeadProfile": {"HeadDia"},
    "NeckProfile": {"NeckDia"},
    "Head": {"HeadLen"},
    "Neck": {"NeckLen"},
    "BondZoneReference": {"BondZoneDia"},
    # Where the MHA-DT-01 drum's front end is bonded, from the head rear face
    # at the .XX band (ruling A); an assembly station, not a turned feature,
    # so the note names it and the sheet dimensions it.
    "DrumStationReference": {"DrumStationFromHeadRear"},
    "FrontCapProfile": {"HeadCapR", "HeadCapSagDim"},
    "BackCapProfile": {"BackCapR", "BackCapSagDim"},
    "CrossHoleProfile": {"CrossHoleDia"},
    # Machinist review r1/r3 of #1685 (clarity): the hole was located only by
    # "CENTRED ON Ø15 CYLINDER LENGTH", with no datum face and no band.  It
    # prints as an ordinary .XX station from the head rear face, the face
    # every other station runs from; at title-block bands both webs hold the
    # .080 in target (CROSS_HOLE_WEB_WORST).
    "CrossHoleStationReference": {"CrossHoleFromHeadRear"},
    # R1a: the collar's spring-pin hole, from the same head rear face.
    "PinHoleProfile": {"PinHoleDia"},
    "PinStationReference": {"PinStationFromHeadRear"},
    "BackRimReference": {"BackRimFromHeadRear"},
    "OverallReference": {"OverallLen"},
    "FrontJournalReference": {
        "FrontJournalFromHeadRear",
        "FrontJournalLen",
        "FrontJournalDia",
    },
    "BackJournalReference": {
        "BackJournalFromHeadRear",
        "BackJournalLen",
        "BackJournalDia",
    },
}

# The construction-only sketches that carry printed dimensions: the part saves
# them hidden (#880) and the drawing shows them per view
# (_drawing_hidden_sketches).
REFERENCE_SKETCHES = (
    "FrontJournalReference",
    "BackJournalReference",
    "BackRimReference",
    "BondZoneReference",
    "DrumStationReference",
    "PinStationReference",
    "CrossHoleStationReference",
    "OverallReference",
)

# #290 decimal-inch places.  Four on the 5/16 lands and bond zone (their
# sub-.001 bands print exactly), the reamed cross hole (.250 +.0015/+.0010)
# and the 1/16 pin hole (.0625 +.0025/.0000); two (.XX) on every other
# length, station, diameter and crown radius, because the land, drum, pin,
# web and run-out stacks read them.  The crown sags and the overall are REFs;
# the overall prints one place, (9.6), because its rounded chain (.05 + 8.93 +
# .48 + (.12)) sums to 9.58 and a two-place (9.57) read as a mismatch.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HeadProfile": {"HeadDia": 2},
    "NeckProfile": {"NeckDia": 2},
    "Head": {"HeadLen": HEAD_LEN_PLACES},
    "Neck": {"NeckLen": NECK_LEN_PLACES},
    "BondZoneReference": {"BondZoneDia": 4},
    "DrumStationReference": {"DrumStationFromHeadRear": 2},
    "FrontCapProfile": {"HeadCapR": 2, "HeadCapSagDim": HEAD_CAP_SAG_PLACES},
    "BackCapProfile": {"BackCapR": 2, "BackCapSagDim": 2},
    "CrossHoleProfile": {"CrossHoleDia": 4},
    "CrossHoleStationReference": {"CrossHoleFromHeadRear": CROSS_HOLE_STATION_PLACES},
    "PinHoleProfile": {"PinHoleDia": 4},
    "PinStationReference": {"PinStationFromHeadRear": 2},
    "BackRimReference": {"BackRimFromHeadRear": 2},
    "OverallReference": {"OverallLen": 1},
    "FrontJournalReference": {
        "FrontJournalFromHeadRear": 2,
        "FrontJournalLen": 2,
        "FrontJournalDia": 4,
    },
    "BackJournalReference": {
        "BackJournalFromHeadRear": 2,
        "BackJournalLen": 2,
        "BackJournalDia": 4,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked integral-arbor dimension needs authored places")

# The cross hole's station from the head rear face, printed at .XX (see
# DRAWING_DIMENSIONS); the model hole sits on it.
CROSS_HOLE_FROM_HEAD_REAR = HEAD_REAR_Z - HEAD_CENTER_Z
if abs(CROSS_HOLE_FROM_HEAD_REAR - CROSS_HOLE_STATION) > 1e-9:
    raise AssertionError("the model crossrod hole left its printed station")

# Mating parts the callouts name (drawing-guidelines.md rule 4: every tight
# band names its mate and fit).
CROSSROD_NUMBER = "MHA-DT-15"
STRAP_NUMBER = "MHA-DT-14"
DRUM_NUMBER = "MHA-DT-01"

# Machinist review of 7f7fc1717 (blocker): "HEAD LENGTH" did not say whether
# it meant the straight Ø15 cylinder or the whole crowned head, which put the
# hole in two places.  It names the cylinder the HeadLen dimension measures.
# Machinist review r1 of #1685 (blocker): the +0.1/0.0 band named no mate, so
# the callout names the bonded MHA-DT-15 crossrod.  Machinist review r3: the
# hole's station is a toleranced dimension (CrossHoleFromHeadRear), so the
# callout no longer says CENTRED.
CROSS_HOLE_CALLOUT = f"REAM THRU, BONDED FIT\nON {CROSSROD_NUMBER} CROSSROD"
# Machinist review r1 of #1685 (clarity): each land's callout names the bore
# it runs in, where the general note used to.
JOURNAL_CALLOUT = f"JOURNAL,\nRUNS IN {STRAP_NUMBER}"
# Machinist review r1 of #1685 (blocker): the -0.01/-0.10 band named no mate,
# and the Ø5/16 spans either side of the lands carried no diameter (owner,
# 2026-10-12).  One callout covers every Ø5/16 surface but the two lands and
# names the drum bonded on it.  Machinist review r3 (blocker): the 61.05
# drum station falls on the front journal, which read as the drum confined
# to the non-journal Ø8.  The lands run past the straps' inner faces to hold
# them through the drum's float (LAND_MARGINS_AT_STOPS), so each drum end
# rests on its land's inner end at every limit; the callout says so.
# The callout rides the BondZoneDia dimension, which prints the size itself.
BOND_ZONE_CALLOUT = (
    f"ALL EXCEPT JOURNALS;\n{DRUM_NUMBER} BOND ZONE,\nDRUM ENDS ON JOURNALS"
)
# Smallest overlap of each drum end on its land's inner end, every printed
# band at its limit: the front land's inner end from its .XX station and .XX
# length, the back land's from its .XX station, the drum from its .XX station
# and its own sheet's length band.
DRUM_FRONT_END_ON_JOURNAL_MIN = (
    FRONT_JOURNAL_FROM_HEAD_REAR - LINEAR_XX_BAND + JOURNAL_LEN - LINEAR_XX_BAND
) - (DRUM_STATION + DRUM_STATION_BAND)
DRUM_BACK_END_ON_JOURNAL_MIN = (
    DRUM_STATION - DRUM_STATION_BAND + DRUM_LEN + DRUM_LEN_BAND[1]
) - (BACK_JOURNAL_FROM_HEAD_REAR + LINEAR_XX_BAND)
if min(DRUM_FRONT_END_ON_JOURNAL_MIN, DRUM_BACK_END_ON_JOURNAL_MIN) <= 0.0:
    raise AssertionError("a drum end can leave its journal; BOND_ZONE_CALLOUT lies")
# Notes never carry dimensions (Codex P1 on #814): the drum station is the
# model's DrumStationFromHeadRear, printed on the profile with its .XX band.
# Machinist review r1 of #1685 (clarity): it ended on no feature of this part,
# so its callout names what it locates -- the MHA-DT-01 drum's front end,
# set when the drum is bonded on (drawing-guidelines.md rule 19).
DRUM_STATION_CALLOUT = f"DRUM STATION:\n{DRUM_NUMBER} FRONT END,\nSET AT ASSEMBLY"
# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): assembly requirements belong on the feature callout or the
# assembly step, never in a part's general notes.  ASSEMBLY_STEP is the
# pinion fit-up step text (pinion_rig_fitup) that owns this joint.
# The drum joint's one step covers MHA-DT-01 too (dt_alignment_pinion_spec).
# The journals' bore moved onto their callouts (JOURNAL_CALLOUT), so the one
# note is the inside-corner ceiling at the Ø5/16-Ø.41 and Ø.41/Ø.59 shoulders
# (machinist review r1 of #1685; the dt-crankshaft precedent: the title
# block's edge-break radius, until #1625 puts the default in the title block).
INSIDE_CORNER_R_MAX = edge_break_radius_mm(unit=UNIT)  # R.010
DRAWING_NOTES = f"INSIDE CORNERS R{INSIDE_CORNER_R_MAX / 25.4:.3f} MAX.".replace(
    "R0.", "R."
)
ASSEMBLY_STEP = (
    f"SLIDE MHA-DT-22 INTO MHA-DT-01 AND BOND WITH {RETAINING_COMPOUND}, DRUM FRONT "
    "END AT MHA-DT-22 DRUM STATION; WIPE SQUEEZE-OUT OFF JOURNAL LANDS."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
