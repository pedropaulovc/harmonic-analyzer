r"""Pure-data dimensional contract shared by the cone gear shaft and drawing."""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

from cone_gear_spec import DEEPENED_MESH_MM, FACE_WIDTH as CONE_GEAR_FACE_WIDTH
from cone_shaft_land_bands import (  # noqa: F401  re-exported for the shaft build
    GEAR_SEAT_BAND,
    RUNNING_DIA_BAND,
    SECTION_DIA_BANDS,
)


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
# the 12 mm tip block.  Rule-12 E11 replaced the 5/16-18 94025A150 with the
# #10-32 McMaster 94025A164, threaded ADJUSTER_EMBED (9.5, the block spec's
# fit-up setting) into the block's north face, which places its cup rim at
# station 137.77232594770454.  The vendor Sketch2 profile (Line7, harvested
# 2026-09-24) puts the 45 deg conical cup apex 1.2065 mm beyond that rim
# (4.7625 - 3.556), so the terminal shaft endpoint contacts that apex.
# Both constants duplicate the block spec and the replica so this spec
# imports no build module; the drive-train assembly asserts tip == apex.
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
ADJUSTER_EMBED = 9.5
ADJUSTER_CUP_RIM_STATION = TIP_BLOCK_NORTH_FACE_STATION - ADJUSTER_EMBED
MCM_94025A164_CUP_DEPTH = 1.2065
T006_TIP_STATION = ADJUSTER_CUP_RIM_STATION + MCM_94025A164_CUP_DEPTH

# Gear faces along the shaft.  Seat j (T120 at j = 0 .. T006 at j = 19) sits
# one exact-tracking seat pitch from the next; the drive-train assembly owns
# the pitch and the 6.5 reference face every station was laid out on, and
# test_cone_gear_shaft_drawing pins both duplicates to it.  U27 narrowed each
# gear to cone_gear_spec.FACE_WIDTH from its SOUTH face only, so every north
# face stays on the reference and each gear centre moves half the narrowing
# north (the assembly's seed placement).
CONE_SEAT_PITCH = 6.888787817263312
CONE_FACE_STATION_REFERENCE = T006_FACE_WIDTH


def gear_faces(j: int) -> tuple[float, float]:
    """(south, north) cone station of seat j's gear faces (pivot end = 0)."""
    reference_centre = T006_CENTER_STATION - (19 - j) * CONE_SEAT_PITCH
    north = reference_centre + CONE_FACE_STATION_REFERENCE / 2.0
    return north - CONE_GEAR_FACE_WIDTH, north


def seat_gap_midpoint(j: int) -> float:
    """Station centred in the air gap between seat j's gear and seat j + 1's."""
    return (gear_faces(j)[1] + gear_faces(j + 1)[0]) / 2.0


# Every land step sits at the centre of its air gap (Main, 2026-09-25): the
# old 135.0 / 141.9 / 148.8 legacy stations were laid out for 6.5 faces and
# left the step 0.17 from the inboard face once U27 moved the gaps north.
# Centred, each step has SEAT_STEP_AIR to both faces.
SEAT_STEP_AIR = (CONE_SEAT_PITCH - CONE_GEAR_FACE_WIDTH) / 2.0
# U40 (option S1, 2026-09-23): every small-shaft land moves one gear station
# toward the big end, so the 1/16 in terminal land now starts in the air gap
# between T018 (j = 17) and T012 (formerly between T012 and T006).  One
# constant feeds both the 1/8 in section end and the tip stub start, so they
# cannot drift apart.
TIP_LAND_START_STATION = seat_gap_midpoint(17)
TIP_STUB_START_STATION = TIP_LAND_START_STATION
TIP_STUB_LENGTH = T006_TIP_STATION - TIP_STUB_START_STATION

# (diameter in inches, section end station in mm from the front stub end).
# Diameters are typed here in inches and must agree with
# build_cone_gear.bore_dia_in (snug perpendicular gear seats), which U40
# moved one station toward the big end together with this shaft: 3/8 in
# T030..T120, 1/4 in T024, 1/8 in T018, 1/16 in T012 and T006.  Each shoulder
# therefore sits one seat pitch nearer the big end than before, centred in the
# air gap between two gear faces (seat_gap_midpoint); the overall length is
# unchanged.
#
# The terminal land is 1/16 in, not the 1/32 in a literal "bore = shaft
# section at the seat" first produced.  At DP 49.82 / PA 14.5 a 6-tooth gear
# is cut as involute flanks closed by a chord on the base circle -- the
# project's own DXF profile, cut with a self-made form cutter.  T006's gap
# floor is printed at 2.880 mm MIN diameter (U40), so a 1/16 in bore leaves a
# 0.646 mm nominal web, 0.621 mm at maximum bore -- the one named web
# exception (cone_gear_spec.WEB_EXCEPTIONS_MM) -- on a soldered, keyless,
# near-torque-free gear.  Since U40 the land
# carries T012 as well, so it runs 23.04 mm at L/D 14.5 up to the E11 cup
# apex (it was 17.775 at L/D 11 before U40; at 1/32 in it would be L/D 29).  A manual lathe turns that only with
# the tip held on a tailstock centre -- unsupported, it whips off the tool --
# which is why the tailstock note below is a requirement (U40), not a method.
# The shaft still decreases monotonically toward the tip: the cone is
# assembled tip-first, and every gear's tip diameter exceeds the next inboard
# gear's bore (T006 4.28 > T012 bore 1.5875; T012 7.55 > T018 3.175; T018
# 10.74 > T024 6.35; T024 13.90 > T030 9.525; asserted below from
# cone_gear_spec.DEEPENED_MESH_MM), so no single gear can be made integral
# with the shaft unless all twenty are.
SECTIONS: tuple[tuple[float, float], ...] = (
    (JOURNAL_DIA / MM_PER_IN, JOURNAL_END),  # integral v2-post bearing journal
    (0.375, FRONT_STUB + seat_gap_midpoint(15)),  # 64T + T120..T030 seats
    (0.25, FRONT_STUB + seat_gap_midpoint(16)),  # T024 seat
    (0.125, FRONT_STUB + TIP_LAND_START_STATION),  # T018 seat
    (0.0625, FRONT_STUB + T006_TIP_STATION),  # T012 + T006 seats, tip journal
)

SECTION_DIAS = tuple(dia_in * MM_PER_IN for dia_in, _end in SECTIONS)
SECTION_ENDS = tuple(end for _dia_in, end in SECTIONS)
SHAFT_LENGTH = SECTION_ENDS[-1]
# Tip-first assembly: each small gear passes over no land it cannot clear.
# T006..T024 sit on SECTIONS[4..2] (T006/T012 share the terminal land); the
# next inboard gear's bore is the land under it.
for _teeth, _next_bore in ((6, 4), (12, 3), (18, 2), (24, 1)):
    if DEEPENED_MESH_MM[_teeth][0] <= SECTION_DIAS[_next_bore]:
        raise AssertionError(
            f"T{_teeth:03d} tip diameter does not exceed the next inboard bore"
        )

# Diameter bands, one NAMED class per land, live in cone_shaft_land_bands so
# the cone gears derive their bonded bores from them without importing
# this spec; build_cone_gear_shaft applies them to the model dimensions.

# Shoulder root radius.  Each step sits mid-gap between two neighbouring gear
# faces (SEAT_STEP_AIR, 0.444 mm per side), so the root can be neither
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

# What the native dimensions cannot say (drawing-simplicity policy rule 2: a
# fit requirement names its mate).  The gear-seat limits are what leaves the
# solder gap in the cone gears' bores; the printed limits govern, so the note
# is a reason, not a fitting instruction (review 2026-09-23).  The old lines
# explaining the three-place stations went: the places already say it.  No
# check the shop cannot make (codex, 375a122c), no digits but the mate's
# number, no method words but one.  Lines stay short: the note block starts
# 58 mm in and the title block begins at 216 mm.  The tailstock line is that
# one process word, by user ruling (U40, 2026-09-23): the 23.04 mm
# Ø1.588 terminal land (L/D 14.5) cannot be turned unsupported, so the
# support IS the requirement (rule 6's exception), not a method preference.
DRAWING_NOTES = "\n".join(
    (
        "GEAR SEAT LIMITS LEAVE A SOLDER GAP",
        "IN THE CONE GEAR BORES, MHA-013.",
        "TURN THE TIP JOURNAL WITH TAILSTOCK SUPPORT.",
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
# Diameters: three places.  Each carries its named band (SECTION_DIA_BANDS),
# so their places are only the number's spelling.
#
# Gear-seat shoulders Sec1End..Sec3End: three places, which is the title-block
# .XXX general grade (+-0.13) and no explicit band.  This is a location
# requirement, not a spelling: gears are soldered at the 6.8889 mm seat pitch
# with 6.0 mm faces (U27), and each of these three steps has to fall inside
# the ~0.89 mm air gap between two neighbouring gear faces (U40, legacy
# stations: T030 north 134.83 | step 135.28 | T024 south 135.72, then
# T024|T018 and T018|T012 one pitch on), centred 0.444 from either face.
# +-0.13 keeps the step in the gap; the .XX grade (+-0.51) would let the
# larger land run up to 0.07 mm under the small-bore gear's face, so that gear
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
