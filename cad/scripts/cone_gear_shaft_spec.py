r"""Pure-data dimensional contract shared by the cone gear shaft and drawing."""

from __future__ import annotations

from cone_pivot_post_installation import GEAR_AXIS_SHIFT


MM_PER_IN = 25.4

# The manually rederived v2 pivot post has a Ø12.2808 bearing bore spanning
# 42.011 mm along the cone axis.  The shaft begins 1.0 mm proud of the post's
# front face, so the integral journal is one millimetre longer than the post
# body and runs with 0.05 mm diametral clearance.
JOURNAL_BORE_DIA = 12.2808
JOURNAL_CLEARANCE = 0.05
JOURNAL_DIA = JOURNAL_BORE_DIA - JOURNAL_CLEARANCE
JOURNAL_END = 43.011

# The final coupled-layout post centre is cone station -39.90136099793.  Its
# 42.011 mm axial body therefore has its front face at -60.9068609979; another
# 1.0 mm makes the shaft end proud at -61.9068609979.  The part origin is that front end and all
# stations below are measured from it.
FRONT_STUB = 61.9068609979

# T006's north face is followed by the 4 mm bushing, a 2 mm half-bushing
# clearance, and the 12 mm tip block. Keep 5 mm of the tip in the adjuster cup.
T006_TIP_STATION = 126.02232594770454 + 6.5 / 2.0 + 4.0 + 2.0 + 12.0 / 2.0 + 5.0

# (diameter in inches, section end station in mm from the front stub end).
# Diameters mirror build_cone_gear.bore_dia_in (snug perpendicular gear seats).
# WARNING the 1/32" (0.79 mm) tip journal is mechanically marginal -- it
# follows from the 62.2 OD anchor (ch13, low confidence) and is flagged for
# Phase 3 rebuild validation. It is drawn faithfully, not "fixed" here.
SECTIONS: tuple[tuple[float, float], ...] = (
    (JOURNAL_DIA / MM_PER_IN, JOURNAL_END),  # integral v2-post bearing journal
    (0.375, FRONT_STUB + 141.9 + GEAR_AXIS_SHIFT),
    (0.25, FRONT_STUB + 148.8 + GEAR_AXIS_SHIFT),
    (0.125, FRONT_STUB + 155.7 + GEAR_AXIS_SHIFT),
    (0.03125, FRONT_STUB + T006_TIP_STATION),  # shortened tip journal
)

SECTION_DIAS = tuple(dia_in * MM_PER_IN for dia_in, _end in SECTIONS)
SECTION_ENDS = tuple(end for _dia_in, end in SECTIONS)
SHAFT_LENGTH = SECTION_ENDS[-1]

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "Sec0Profile": {"Sec0Dia"},
    "Sec1Profile": {"Sec1Dia"},
    "Sec2Profile": {"Sec2Dia"},
    "Sec3Profile": {"Sec3Dia"},
    "Sec4Profile": {"Sec4Dia"},
    "Sec0": {"Sec0End"},
    "Sec1": {"Sec1End"},
    "Sec2": {"Sec2End"},
    "Sec3": {"Sec3End"},
    "Sec4": {"Sec4End"},
}

# Kept to short lines so the block sits clear of the bottom-right title block
# (a single ~130-char line reached x~0.33 m and overlapped it -- Codex/layout
# audit). Substrings the test pins (CENTRE MARKS / LARGE-END FACE / FOLLOWER-REST
# / FRAGILE BY DESIGN) each stay intact on one line.
DRAWING_NOTES = "\n".join(
    (
        "ALL AXIAL STATION DIMENSIONS +/-0.25.",
        "STEP STATIONS ARE MEASURED FROM THE LARGE-END FACE.",
        f"DIA {JOURNAL_DIA:.4f} BEARING JOURNAL IS DATUM A.",
        f"RUNNING FIT IN DIA {JOURNAL_BORE_DIA:.4f} POST BORE: "
        f"{JOURNAL_CLEARANCE:.2f} DIAMETRAL CLEARANCE.",
        f"DIA {SECTION_DIAS[1]:.3f}, {SECTION_DIAS[2]:.3f}, "
        f"{SECTION_DIAS[3]:.3f}, AND {SECTION_DIAS[4]:.3f}",
        "GEAR-SEAT CYLINDERS HAVE CIRCULAR RUNOUT 0.05 MAX TO A",
        "AT EVERY CROSS SECTION.",
        "SHOULDER ROOTS R0.10 MAX OR RELIEF 0.20 WIDE X 0.20 DEEP MAX.",
        "START FROM DIA 12.5 MIN ROUND BAR; TURN BETWEEN TEMPORARY",
        "CENTRE EXTENSIONS, THEN REMOVE THEM TO FINISHED LENGTH.",
        "NO CENTRE HOLE MAY REMAIN ON EITHER FINISHED END.",
        f"FINISH-TURN THE DIA {SECTION_DIAS[-1]:.3f} TIP LAST "
        "WITH FOLLOWER-REST SUPPORT --",
        "SECTION IS FRAGILE BY DESIGN.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
