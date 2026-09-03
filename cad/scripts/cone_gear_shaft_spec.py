r"""Pure-data dimensional contract shared by the cone gear shaft and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace, GeometricControl, PartDatum
from _surface_finish import MACHINED_UM, SurfaceFinishControl

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

# Every turned section is a ground-shaft h fit: the cone gear, the cylinder
# gear and the bearing bushings all slide onto these lands.  ONE shared class,
# applied to the model dimension by build_cone_gear_shaft -- not five copies of
# "+0.00/-0.02" typed as sheet callout text.
SECTION_DIA_BAND = SHAFT_H

# No geometric controls (cad/docs/drawing-simplicity-policy.md rule 3): a
# shaft is not on the GD&T allowlist -- every land is a size tolerance on its
# model dimension.  The typed tuples stay empty so build_cone_gear_shaft's
# author_part_pmi call keeps its shape.
PART_DATUMS: tuple[PartDatum, ...] = ()
GEOMETRIC_CONTROLS: tuple[GeometricControl, ...] = ()
# One roughness symbol, on the bearing journal that turns in the pivot post
# (rule 5).  The 1/32 in tip is finish-turned last under a follower rest;
# a symbol on it would change nothing the note does not already force.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_journal", MACHINED_UM, CylinderFace(JOURNAL_DIA)
    ),
)

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

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  Short lines keep the
# block clear of the bottom-right title block.
DRAWING_NOTES = "\n".join(
    (
        "12.5 MIN ROUND BAR. TURN BETWEEN CENTRES ON TEMPORARY EXTENSIONS;",
        "PART OFF TO LENGTH: NO CENTRE HOLE MAY REMAIN ON EITHER END.",
        "SHOULDER ROOTS R0.10 MAX OR UNDERCUT 0.20 X 0.20 MAX.",
        f"TURN THE DIA {SECTION_DIAS[-1]:.3f} TIP LAST UNDER A FOLLOWER REST; FRAGILE BY DESIGN.",
    )
)
# No end view: every diameter reads on its own land of the side view (the
# three tip lands in DETAIL A), so the sheet carries no end-view label.
