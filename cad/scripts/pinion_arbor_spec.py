r"""Pure-data dimensional contract for the integral MHA-102 pinion arbor.

The turned head, neck, and long shaft are deliberately one piece.  This is an
approved photo-derived reconstruction choice, not proof of the historical
joint detail.  The exact released external envelope is preserved while the
former socket and unsupported radial retention pin are removed.
"""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_handle_geometry import ROD_DIA

SHAFT_DIA = 8.0
SHAFT_LEN = 226.25  # unchanged origin-to-back-crown-root station
# Only the two short lands that run in the MHA-056 strap bores (REAM_SLIDE)
# carry the ground-shaft band and the Ra 1.6 finish (U39).  Everything else,
# the MHA-002 drum bond zone included, is Ø8 0/-0.10: every bore slides on
# from the back crown, so the upper limit stays 8.00, and the drum's
# +0.10/0 bore then leaves at most a 0.20 Loctite 638 gap.
SHAFT_DIA_BAND = (0.000, -0.100)
JOURNAL_DIA_BAND = SHAFT_H
JOURNAL_LEN = 12.0
# Land stations are printed from the head shoulder at one place, so they are
# chosen exact at one place: each 12 mm land then sits centred on its 9 mm
# MHA-056 strap (front z 50.75-59.75, back z 203.45-212.45), 1.5 each side.
FRONT_JOURNAL_FROM_HEAD_REAR = 50.5
BACK_JOURNAL_FROM_HEAD_REAR = 203.2
BACK_CAP_SAG = 1.2
BACK_CAP_R = (SHAFT_DIA / 2.0) ** 2 / (2.0 * BACK_CAP_SAG) + BACK_CAP_SAG / 2.0

# Former handle-body envelope, turned integrally with the arbor.  Rule 12
# (audit W6, 2026-09-23): the Ø6.005 crossrod hole left 1.50 of wall to each
# face of the 9.0 head at nominal and -0.10 at the printed worst case (HeadLen
# and the hole station both .X).  The head grows to 10.5 about the unchanged
# crossrod station (world z -6.5), and the hole is printed CENTRED on the head
# length rather than located by a .X station, so only the HeadLen band reaches
# the web: (10.5 - 0.8) / 2 - 6.005 / 2 - 0.05 = 1.80 worst case.
HEAD_DIA = 15.0
HEAD_LEN = 10.5
HEAD_CAP_SAG = 3.0
HEAD_CAP_R = ((HEAD_DIA / 2.0) ** 2 + HEAD_CAP_SAG**2) / (2.0 * HEAD_CAP_SAG)
HEAD_CENTER_Z = -6.5  # the released crossrod station
HEAD_REAR_Z = HEAD_CENTER_Z + HEAD_LEN / 2.0
HEAD_FRONT_Z = HEAD_CENTER_Z - HEAD_LEN / 2.0
NECK_DIA = 10.5
NECK_END_Z = 10.0
NECK_LEN = NECK_END_Z - HEAD_REAR_Z
EXPOSED_SHAFT_LEN = SHAFT_LEN - NECK_END_Z
CROSS_HOLE_DIA = 6.005
OVERALL_LEN = SHAFT_LEN + BACK_CAP_SAG - (HEAD_FRONT_Z - HEAD_CAP_SAG)
BACK_RIM_FROM_HEAD_REAR = SHAFT_LEN - HEAD_REAR_Z
FRONT_JOURNAL_Z = HEAD_REAR_Z + FRONT_JOURNAL_FROM_HEAD_REAR
BACK_JOURNAL_Z = HEAD_REAR_Z + BACK_JOURNAL_FROM_HEAD_REAR

# Rule 12 worst-case web from the centred crossrod hole to either head face:
# the .X HeadLen band split over both sides, the hole's own drilled-hole
# allowance on its radius.
HEAD_LEN_BAND = 0.8  # .X title-block row
CROSS_HOLE_WEB_WORST = (
    (HEAD_LEN - HEAD_LEN_BAND) / 2.0 - CROSS_HOLE_DIA / 2.0 - 0.05
)
if CROSS_HOLE_WEB_WORST < 1.5:
    raise AssertionError(
        f"crossrod hole web {CROSS_HOLE_WEB_WORST:.2f} is under the 1.5 floor"
    )
if abs(ROD_DIA - CROSS_HOLE_DIA - 0.0125) > 1e-12:
    raise AssertionError("crossrod/head nominal interference changed")
if min(HEAD_LEN, NECK_LEN, EXPOSED_SHAFT_LEN) <= 0.0:
    raise AssertionError("integral arbor axial spans must be positive")
if not NECK_END_Z < FRONT_JOURNAL_Z < FRONT_JOURNAL_Z + JOURNAL_LEN < BACK_JOURNAL_Z:
    raise AssertionError("front journal land must sit on the exposed shaft")
if BACK_JOURNAL_Z + JOURNAL_LEN >= SHAFT_LEN:
    raise AssertionError("back journal land must end before the back crown")

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
    # Head and neck diameters are the same Front-plane circle pattern as
    # ShaftDia: imported end-on on the donor view and moved onto the 1:1
    # profile (5cc191fb's proven path; a detail silhouette screen pick is
    # seat-dependent and failed on w6).
    "HeadProfile": {"HeadDia"},
    "NeckProfile": {"NeckDia"},
    "Head": {"HeadLen"},
    "Neck": {"NeckLen"},
    "ShaftProfile": {"ShaftDia"},
    "FrontCapProfile": {"HeadCapR", "HeadCapSagDim"},
    "BackCapProfile": {"BackCapR", "BackCapSagDim"},
    "CrossHoleProfile": {"CrossHoleDia"},
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

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HeadProfile": {"HeadDia": 1},
    "NeckProfile": {"NeckDia": 1},
    "Head": {"HeadLen": 1},
    "Neck": {"NeckLen": 2},
    "ShaftProfile": {"ShaftDia": 2},
    "FrontCapProfile": {"HeadCapR": 1, "HeadCapSagDim": 1},
    "BackCapProfile": {"BackCapR": 1, "BackCapSagDim": 1},
    "CrossHoleProfile": {"CrossHoleDia": 1},
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

CROSS_HOLE_CALLOUT = (
    "MATCH-REAM THRU,\n"
    "CENTRED ON HEAD LENGTH,\n"
    "TO MHA-058 GRIP ROD\n"
    "LIGHT ARBOR-PRESS FIT"
)
DRAWING_NOTES = "\n".join(
    (
        "JOURNALS RUN IN MHA-056 REAMED BORES; BOND INTO MHA-002 WITH LOCTITE 638.",
        "INTERNAL SHOULDERS SHARP.",
        "INSTALLED MHA-058 ROD SHALL NOT TURN OR SLIDE BY HAND.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
