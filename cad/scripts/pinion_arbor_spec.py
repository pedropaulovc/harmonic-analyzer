r"""Pure-data dimensional contract for the integral MHA-102 pinion arbor.

The turned head, neck, and long shaft are deliberately one piece.  This is an
approved photo-derived reconstruction choice, not proof of the historical
joint detail.  The exact released external envelope is preserved while the
former socket and unsupported radial retention pin are removed.

The geometry -- envelope, drum station and journal-land stack -- lives in
``pinion_arbor_geometry`` and is re-exported here; this module adds the
drawing contract (marks, precision, finishes, notes).
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_arbor_geometry import (
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
    CROSS_HOLE_WEB_TARGET as CROSS_HOLE_WEB_TARGET,
    CROSS_HOLE_WEB_WORST as CROSS_HOLE_WEB_WORST,
    CROSSROD_MAX_CLEARANCE as CROSSROD_MAX_CLEARANCE,
    CROSSROD_MIN_CLEARANCE as CROSSROD_MIN_CLEARANCE,
    DRUM_AFT_SHIFT as DRUM_AFT_SHIFT,
    DRUM_FRONT_Z_AS_BUILT as DRUM_FRONT_Z_AS_BUILT,
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
    LINEAR_X_BAND as LINEAR_X_BAND,
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
    worst_land_margins as worst_land_margins,
)

SURFACE_FINISHES = tuple(
    SurfaceFinishControl(
        key,
        MACHINED_UM,
        CylinderFace(SHAFT_DIA, contains_z_mm=station + JOURNAL_LEN / 2.0),
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
    # Ø8 is not: its circle's witnesses crossed the neck face, so the bond
    # zone carries its own flank diameter (BondZoneReference).
    "HeadProfile": {"HeadDia"},
    "NeckProfile": {"NeckDia"},
    "Head": {"HeadLen"},
    "Neck": {"NeckLen"},
    "BondZoneReference": {"BondZoneDia"},
    # Where the MHA-002 drum's front end is bonded, from the Ø15 head rear
    # face at the general .X band (ruling A); an assembly station, not a
    # turned feature, so the note names it and the sheet dimensions it.
    "DrumStationReference": {"DrumStationFromHeadRear"},
    "FrontCapProfile": {"HeadCapR", "HeadCapSagDim"},
    "BackCapProfile": {"BackCapR", "BackCapSagDim"},
    "CrossHoleProfile": {"CrossHoleDia"},
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
    "OverallReference",
)

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HeadProfile": {"HeadDia": 1},
    "NeckProfile": {"NeckDia": 1},
    "Head": {"HeadLen": HEAD_LEN_PLACES},
    "Neck": {"NeckLen": NECK_LEN_PLACES},
    "BondZoneReference": {"BondZoneDia": 2},
    "DrumStationReference": {"DrumStationFromHeadRear": 2},
    "FrontCapProfile": {"HeadCapR": 1, "HeadCapSagDim": HEAD_CAP_SAG_PLACES},
    "BackCapProfile": {"BackCapR": 1, "BackCapSagDim": 1},
    "CrossHoleProfile": {"CrossHoleDia": 2},
    "PinHoleProfile": {"PinHoleDia": 2},
    "PinStationReference": {"PinStationFromHeadRear": 1},
    "BackRimReference": {"BackRimFromHeadRear": 1},
    "OverallReference": {"OverallLen": 1},
    "FrontJournalReference": {
        "FrontJournalFromHeadRear": 1,
        "FrontJournalLen": 1,
        "FrontJournalDia": 2,
    },
    "BackJournalReference": {
        "BackJournalFromHeadRear": 1,
        "BackJournalLen": 1,
        "BackJournalDia": 2,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked integral-arbor dimension needs authored places")

# Machinist review of 7f7fc1717 (blocker): "HEAD LENGTH" did not say whether
# it meant the straight Ø15 cylinder or the whole crowned head, which put the
# hole in two places.  It names the cylinder the HeadLen dimension measures.
# <MOD-DIAM> carries its own leading gap, so no space before it.
CROSS_HOLE_CALLOUT = (
    "REAM THRU,\n"
    f"CENTRED ON<MOD-DIAM>{HEAD_DIA:.0f} CYLINDER LENGTH"
)
# Notes never carry dimensions (Codex P1 on #814): the drum station is the
# model's DrumStationFromHeadRear, printed on the profile as "DRUM STATION"
# with its .X band, and the note only names it.
# Rule 6: assembly requirements belong on the feature callout or the
# assembly step, never in a part's general notes.  ASSEMBLY_STEP is the
# pinion fit-up step text (pinion_rig_fitup) that owns this joint.
# The drum joint's one step covers MHA-002 too (alignment_pinion_spec).
DRAWING_NOTES = "JOURNALS RUN IN MHA-056 REAMED BORES."
ASSEMBLY_STEP = (
    f"SLIDE MHA-102 INTO MHA-002 AND BOND WITH {RETAINING_COMPOUND}, DRUM FRONT "
    "END AT MHA-102 DRUM STATION; WIPE SQUEEZE-OUT OFF JOURNAL LANDS."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
