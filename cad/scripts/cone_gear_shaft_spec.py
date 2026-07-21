r"""Pure-data dimensional contract shared by the cone gear shaft and drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

# The 3/8" big end runs FRONT_STUB past the legacy pivot-end origin, through
# the pivot post's journal (see build_cone_gear_shaft.py). The part origin is
# that FRONT END face; every station below is measured from it.
FRONT_STUB = 12.3

# (diameter in inches, section end station in mm from the front stub end).
# Diameters mirror build_cone_gear.bore_dia_in (snug perpendicular gear seats).
# WARNING the 1/32" (0.79 mm) tip journal is mechanically marginal -- it
# follows from the 62.2 OD anchor (ch13, low confidence) and is flagged for
# Phase 3 rebuild validation. It is drawn faithfully, not "fixed" here.
SECTIONS: tuple[tuple[float, float], ...] = (
    (0.375, FRONT_STUB + 141.9),  # front stub + pivot journal + 64T + T120..T024
    (0.25, FRONT_STUB + 148.8),  # T018 seat
    (0.125, FRONT_STUB + 155.7),  # T012 seat
    (0.03125, FRONT_STUB + 190.0),  # T006 seat + thin-tip journal
)

SECTION_DIAS = tuple(dia_in * MM_PER_IN for dia_in, _end in SECTIONS)
SECTION_ENDS = tuple(end for _dia_in, end in SECTIONS)
SHAFT_LENGTH = SECTION_ENDS[-1]

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "Sec0Profile": {"Sec0Dia"},
    "Sec1Profile": {"Sec1Dia"},
    "Sec2Profile": {"Sec2Dia"},
    "Sec3Profile": {"Sec3Dia"},
    "Sec0": {"Sec0End"},
    "Sec1": {"Sec1End"},
    "Sec2": {"Sec2End"},
    "Sec3": {"Sec3End"},
}

# Kept to short lines so the block sits clear of the bottom-right title block
# (a single ~130-char line reached x~0.33 m and overlapped it -- Codex/layout
# audit). Substrings the test pins (CENTRE MARKS / LARGE-END FACE / FOLLOWER-REST
# / FRAGILE BY DESIGN) each stay intact on one line.
DRAWING_NOTES = "\n".join(
    (
        "CENTRE MARKS AT BOTH ENDS, 1.0 DEEP MAX, MAY REMAIN.",
        "STEP STATIONS ARE MEASURED FROM THE LARGE-END FACE.",
        "STEP DIAMETERS ARE GEAR SEATS AND BEARING JOURNALS:",
        "TURN OR GRIND TO SIZE; NO FLATS OR KEYSEATS.",
        "ALL STEP DIAMETERS RUN WITHIN 0.05 TIR TO DATUM A.",
        "TURN FROM OVERSIZE 3/8 IN STOCK BETWEEN CENTRES; FINISH-TURN",
        "THE DIA 0.79 TIP LAST WITH FOLLOWER-REST SUPPORT --",
        "SECTION IS FRAGILE BY DESIGN.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
