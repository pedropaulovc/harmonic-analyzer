r"""Pure-data dimensional contract shared by the cone gear shaft and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
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

# T006's north face starts the 4 mm bushing, followed by 2 mm clearance and
# the 12 mm tip block.  McMaster 94025A150 is threaded 6 mm into the block's
# north face, placing its stock cup rim at station 141.27232594770454.  The
# vendor Sketch2 profile puts the conical cup apex 1.98755 mm beyond that rim
# (6.35 - 4.36245), so the terminal shaft endpoint contacts that apex rather
# than extending through it as the former nominal 5 mm insertion did.
T006_CENTER_STATION = 126.02232594770454
T006_FACE_WIDTH = 6.5
TIP_BUSHING_LENGTH = 4.0
TIP_BLOCK_CLEARANCE = 2.0
TIP_BLOCK_LENGTH = 12.0
T006_NORTH_FACE_STATION = T006_CENTER_STATION + T006_FACE_WIDTH / 2.0
TIP_BUSHING_START_STATION = T006_NORTH_FACE_STATION
TIP_BUSHING_END_STATION = TIP_BUSHING_START_STATION + TIP_BUSHING_LENGTH
TIP_BLOCK_NORTH_FACE_STATION = (
    TIP_BUSHING_END_STATION + TIP_BLOCK_CLEARANCE + TIP_BLOCK_LENGTH
)
ADJUSTER_EMBED = 6.0
ADJUSTER_CUP_RIM_STATION = TIP_BLOCK_NORTH_FACE_STATION - ADJUSTER_EMBED
MCM_94025A150_CUP_DEPTH = 1.98755
T006_TIP_STATION = ADJUSTER_CUP_RIM_STATION + MCM_94025A150_CUP_DEPTH
TIP_STUB_START_STATION = 155.7 + GEAR_AXIS_SHIFT
TIP_STUB_LENGTH = T006_TIP_STATION - TIP_STUB_START_STATION

# (diameter in inches, section end station in mm from the front stub end).
# Diameters mirror build_cone_gear.bore_dia_in (snug perpendicular gear seats).
# The terminal land is 1/16 in, not the 1/32 in a literal "bore = shaft
# section at the seat" first produced.  At DP 49.82 / PA 14.5 a 6-tooth gear
# is cut as involute flanks closed by a chord on the base circle -- the
# project's own DXF profile, cut with a self-made form cutter -- so T006's
# minimum-material radius is 1.3365 mm and its tooth depth 0.703 mm.  A
# 1/16 in bore still leaves a 0.543 mm rim under that root (0.77x tooth
# depth) on a soldered, keyless, near-torque-free gear, and in exchange the
# 20.675 mm terminal journal goes from L/D 26 to 13 -- 16x the bending
# stiffness, the difference between a land a manual lathe can turn and one
# that whips off the tool.  It is also the largest step that keeps the shaft
# monotonically decreasing: the cone is assembled tip-first, and every gear
# OD exceeds the next inboard gear's bore (T006 4.08 > T012 bore 3.175;
# T012 7.14 > T018 6.35; T018 10.20 > T024 9.525), so no single gear can be
# made integral with the shaft unless all twenty are.
SECTIONS: tuple[tuple[float, float], ...] = (
    (JOURNAL_DIA / MM_PER_IN, JOURNAL_END),  # integral v2-post bearing journal
    (0.375, FRONT_STUB + 141.9 + GEAR_AXIS_SHIFT),
    (0.25, FRONT_STUB + 148.8 + GEAR_AXIS_SHIFT),
    (0.125, FRONT_STUB + 155.7 + GEAR_AXIS_SHIFT),
    (0.0625, FRONT_STUB + T006_TIP_STATION),  # T006 seat + tip journal
)

SECTION_DIAS = tuple(dia_in * MM_PER_IN for dia_in, _end in SECTIONS)
SECTION_ENDS = tuple(end for _dia_in, end in SECTIONS)
SHAFT_LENGTH = SECTION_ENDS[-1]

# Every turned section is a ground-shaft h fit: the cone gear, the cylinder
# gear and the bearing bushings all slide onto these lands.  ONE shared class,
# applied to the model dimension by build_cone_gear_shaft -- not five copies of
# "+0.00/-0.02" typed as sheet callout text.
SECTION_DIA_BAND = SHAFT_H

# Shoulder root radius.  Each step sits in the ~0.39 mm axial air gap between
# two neighbouring gear faces (~0.19 mm per side), so the root can be neither
# a sharp corner (a stress riser at the smallest section of a slender shaft)
# nor a radius big enough to touch a gear face: R0.10 is the largest standard
# tool nose radius that clears.  Modelled as geometry and dimensioned once,
# not written as a process note.
FILLET_RADIUS = 0.10
# Four identical shoulder roots, one fillet feature, one radius dimension.
FILLET_CALLOUT = "4X"

# Surface texture, on the two lands that RUN: the Ø12.2308 journal turns in
# the pivot post bore and the terminal land turns in the cone tip bushing.
# The three intermediate lands only carry soldered gears, so they are left to
# the title-block process row.
SURFACE_FINISHES = (
    SurfaceFinishControl("pivot_journal", MACHINED_UM, CylinderFace(JOURNAL_DIA)),
    SurfaceFinishControl(
        "tip_journal",
        MACHINED_UM,
        CylinderFace(SECTION_DIAS[-1], tolerance_mm=0.01),
    ),
)

# The one thing the native dimensions cannot say: WHY three shoulder stations
# print three places (drawing-simplicity policy rule 2: a location requirement
# names its mate).  The note explains, it does not add a check: acceptance is
# the title-block .XXX grade on those dimensions, and a note that asked the
# shop to verify gear faces it has no positions for would be uncheckable
# (codex, 375a122c).  No digits, no method words.  Lines stay short: the
# note block starts 58 mm in and the title block begins at 216 mm.
DRAWING_NOTES = "\n".join(
    (
        "THREE-PLACE SHOULDER STATIONS LOCATE",
        "THE SOLDERED CONE GEAR SEATS.",
    )
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
    "ShoulderFillets": {"ShoulderR"},
}

# Display precision is a MODEL property (drawing-simplicity policy rule 2):
# the part build stamps it and the sheet only reads it back.
#
# Diameters: three places.  All five carry the shared h band, so their places
# are only the number's spelling.
#
# Gear-seat shoulders Sec1End..Sec3End: three places, which is the title-block
# .XXX general grade (+-0.13) and no explicit band.  This is a location
# requirement, not a spelling: gears are soldered at the 6.8889 mm seat pitch
# with 6.5 mm faces, and each of these three steps has to fall inside the
# ~0.39 mm air gap between two neighbouring gear faces (T024 north 141.72 |
# step 141.9 | T018 south 142.11, and so on), 0.18..0.21 from either face.
# +-0.13 keeps the step in the gap; the .XX grade (+-0.51) would let the
# larger land run up to 0.3 mm under the small-bore gear's face, so that gear
# could not pass the land to reach its pitch station.  The R0.10 root radius
# eats a further 0.10 of the outboard margin, which a bore edge break covers.
#
# Journal length Sec0End and overall length Sec4End: one place, the routine
# grade the fleet's plain lengths print.  The journal is 1.0 mm proud of the
# post front face, the post bore ends flush with its shoulder, and the 64T
# crank-drive gear beside that shoulder is soldered with ~1.7 mm of air to the
# step, so +-0.8 on the length touches nothing; the tip end meets an
# adjustable cup-point screw that takes up any length error.  Shoulder
# radius: two places; nothing depends on it beyond clearing the gear faces.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "Sec0Profile": {"Sec0Dia": 3},
    "Sec1Profile": {"Sec1Dia": 3},
    "Sec2Profile": {"Sec2Dia": 3},
    "Sec3Profile": {"Sec3Dia": 3},
    "Sec4Profile": {"Sec4Dia": 3},
    "Sec0": {"Sec0End": 1},
    "Sec1": {"Sec1End": 3},
    "Sec2": {"Sec2End": 3},
    "Sec3": {"Sec3End": 3},
    "Sec4": {"Sec4End": 1},
    "ShoulderFillets": {"ShoulderR": 2},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")
