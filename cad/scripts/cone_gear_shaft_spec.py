r"""Pure-data dimensional contract shared by the cone gear shaft and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

from cone_pivot_post_installation import GEAR_AXIS_SHIFT
from cone_gear_spec import FACE_WIDTH as CONE_GEAR_FACE_WIDTH
from crank_drive_gear_spec import FACE_WIDTH as GEAR64_FACE_WIDTH


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

# Axial capture (#914, user ruling 2026-09-25).  The tip adjuster pushes the
# shaft south, toward the post; nothing reacted it until the 64T met the post
# boss 1.681 further on.  An integral collar now fills that gap: its south
# face bears on the post's north boss face (flush with the journal end) and
# the 64T is soldered against its north face, so no station moves.  The web is
# the gap, 1.681 -- above the 1.5 floor, accepted by the user rather than
# moving the 64T.  Ø15.0 bears on the boss annulus outside the Ø12.2808 bore
# and inside the Ø17.2 boss; it is the largest diameter, so the shaft turns
# from 5/8 in bar.  The 64T centre is the drive-train's GEAR64_STATION (the
# shaft tests pin the two equal).
GEAR64_CENTER_STATION = 19.9 + GEAR_AXIS_SHIFT
COLLAR_DIA = 15.0
COLLAR_START_STATION = JOURNAL_END
COLLAR_END_STATION = FRONT_STUB + GEAR64_CENTER_STATION - GEAR64_FACE_WIDTH / 2.0
COLLAR_THICKNESS = COLLAR_END_STATION - COLLAR_START_STATION
STOCK_DIA = 0.625 * MM_PER_IN

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
# U40 (option S1, 2026-09-23): every small-shaft land moves one gear station
# toward the big end, so the 1/16 in terminal land now starts in the air gap
# between T018 and T012 (legacy station 148.8, formerly 155.7 between T012
# and T006).  One constant feeds both the 1/8 in section end and the tip stub
# start, so they cannot drift apart.
TIP_LAND_START_STATION = 148.8 + GEAR_AXIS_SHIFT
TIP_STUB_START_STATION = TIP_LAND_START_STATION
TIP_STUB_LENGTH = T006_TIP_STATION - TIP_STUB_START_STATION

# (diameter in inches, section end station in mm from the front stub end).
# Diameters are typed here in inches and must agree with
# build_cone_gear.bore_dia_in (snug perpendicular gear seats), which U40
# moved one station toward the big end together with this shaft: 3/8 in
# T030..T120, 1/4 in T024, 1/8 in T018, 1/16 in T012 and T006.  Each shoulder
# therefore sits one 6.9 seat pitch nearer the big end than before (legacy
# stations 135.0 / 141.9 / 148.8, formerly 141.9 / 148.8 / 155.7), still in
# the air gap between two gear faces; the overall length is unchanged.
#
# The terminal land is 1/16 in, not the 1/32 in a literal "bore = shaft
# section at the seat" first produced.  At DP 49.82 / PA 14.5 a 6-tooth gear
# is cut as involute flanks closed by a chord on the base circle -- the
# project's own DXF profile, cut with a self-made form cutter -- so T006's
# minimum-material radius is 1.3365 mm and its tooth depth 0.703 mm.  A
# 1/16 in bore still leaves a 0.543 mm rim under that root (0.77x tooth
# depth) on a soldered, keyless, near-torque-free gear.  Since U40 the land
# carries T012 as well, so it runs 23.293 mm at L/D 14.7 up to the E11 cup
# apex (it was 17.775 at L/D 11 before U40; at 1/32 in it would be L/D 29).  A manual lathe turns that only with
# the tip held on a tailstock centre -- unsupported, it whips off the tool --
# which is why the tailstock note below is a requirement (U40), not a method.
# The shaft still decreases monotonically toward the tip: the cone is
# assembled tip-first, and every gear OD exceeds the next inboard gear's bore
# (T006 OD 4.08 > T012 bore 1.5875; T012 7.14 > T018 3.175; T018 10.20 >
# T024 6.35; T024 13.26 > T030 9.525), so no single gear can be made integral
# with the shaft unless all twenty are.
SECTIONS: tuple[tuple[float, float], ...] = (
    (JOURNAL_DIA / MM_PER_IN, JOURNAL_END),  # integral v2-post bearing journal
    (0.375, FRONT_STUB + 135.0 + GEAR_AXIS_SHIFT),  # 64T + T120..T030 seats
    (0.25, FRONT_STUB + 141.9 + GEAR_AXIS_SHIFT),  # T024 seat
    (0.125, FRONT_STUB + TIP_LAND_START_STATION),  # T018 seat
    (0.0625, FRONT_STUB + T006_TIP_STATION),  # T012 + T006 seats, tip journal
)

SECTION_DIAS = tuple(dia_in * MM_PER_IN for dia_in, _end in SECTIONS)
SECTION_ENDS = tuple(end for _dia_in, end in SECTIONS)
SHAFT_LENGTH = SECTION_ENDS[-1]

# One length origin (#914 option A, Main ruling 2026-09-25): the collar's
# thrust face, the face the post bears on.  Drawing policy rule 8 allows one
# origin per view, baseline from it.  The journal runs back from it to the
# front stub, the three gear-seat shoulders and the solder stations run
# forward from it, and the overall length stays the conspicuous front-to-tip
# dimension.  Measuring shoulders and gears from the same face keeps the
# journal's .X length out from between them.  Each land's end plane is offset
# from SECTION_ORIGINS[i] by SECTION_KNOBS[i], the value its SecEnd{i} global
# carries; land 0 is the journal, extruded from the front face.
DATUM_STATION = COLLAR_START_STATION
SECTION_ORIGINS = (
    "Front Plane",
    "CollarFace",
    "CollarFace",
    "CollarFace",
    "Front Plane",
)
SECTION_KNOBS = tuple(
    end if origin == "Front Plane" else end - DATUM_STATION
    for end, origin in zip(SECTION_ENDS, SECTION_ORIGINS)
)

# Solder stations (#914 user ruling: +-0.13 from the collar face).  #834
# narrows each cone gear from its SOUTH face only, so the north faces stay on
# the 6.5 reference face and a station is the gear's south face, the face a
# spacer set on the collar meets.  The twenty seats are equally spaced at the
# exact-tracking seat pitch, so the print gives the first and the last with
# "20X EQ SP".  T120's reference centre is the drive train's
# SHAFT_T120_STATION (the shaft tests pin the two equal).
CONE_FACE_REFERENCE = T006_FACE_WIDTH
T120_CENTER_STATION = 28.25 + GEAR_AXIS_SHIFT
SOLDER_STATION_COUNT = 20
SOLDER_T120_STATION = (
    FRONT_STUB
    + T120_CENTER_STATION
    + CONE_FACE_REFERENCE / 2.0
    - CONE_GEAR_FACE_WIDTH
    - DATUM_STATION
)
SOLDER_T006_STATION = (
    FRONT_STUB
    + T006_CENTER_STATION
    + CONE_FACE_REFERENCE / 2.0
    - CONE_GEAR_FACE_WIDTH
    - DATUM_STATION
)

# Diameter bands, one NAMED class per land, applied to the model dimension
# by build_cone_gear_shaft -- never "+0.00/-0.02" typed as sheet callout text.
#
# The two lands that RUN keep the shared ground-shaft h band: the Ø12.231
# journal turns in the pivot post's Ø12.2808 bore (0.05 nominal clearance),
# and the Ø1.588 tip land -- the T012 and T006 seats AND the journal -- turns
# in the cone tip bushing's 1.5875 +0.05/0 bore, 0..0.07 running clearance.
RUNNING_DIA_BAND = SHAFT_H
# GEAR_SEAT_BAND (U27, 2026-09-23): the three intermediate lands only carry
# soldered gears.  The upper limit stays at nominal, so every gear still
# passes down its land to its pitch station; the -0.05 lower limit is the
# soft-solder capillary gap, and holds the gear within 0.025 radially -- a
# small fraction of the ~0.51 mm module, so mesh runout does not suffer.
# 2.5x the h band, which a micrometer holds on a manual lathe; -0.10 would
# allow ~20% of the module in runout on hand-cut teeth.  Spec-local on
# purpose: _fit_limits is imported fleet-wide.
GEAR_SEAT_BAND = (0.000, -0.050)
SECTION_DIA_BANDS: tuple[tuple[float, float], ...] = (
    RUNNING_DIA_BAND,  # Sec0: pivot journal
    GEAR_SEAT_BAND,  # Sec1: T030-T120 seats
    GEAR_SEAT_BAND,  # Sec2: T024 seat
    GEAR_SEAT_BAND,  # Sec3: T018 seat
    RUNNING_DIA_BAND,  # Sec4: T012 + T006 seats + tip journal
)

# Shoulder root radius.  Each step sits in the ~0.39 mm axial air gap between
# two neighbouring gear faces (~0.19 mm per side), so the root can be neither
# a sharp corner (a stress riser at the smallest section of a slender shaft)
# nor a radius big enough to touch a gear face: R0.10 is the largest standard
# tool nose radius that clears.  Modelled as geometry and dimensioned once,
# not written as a process note.
FILLET_RADIUS = 0.10
# Three identical gear-seat shoulder roots (the collar's roots stay sharp,
# build_cone_gear_shaft), one fillet feature, one radius dimension.
FILLET_CALLOUT = "3X"

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
# one process word, by user ruling (U40, 2026-09-23): the 23.293 mm
# Ø1.588 terminal land (L/D 14.7) cannot be turned unsupported, so the
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
    "CollarProfile": {"CollarDia"},
    "Collar": {"CollarWidth"},
    "SolderStations": {"T120Station", "T006Station"},
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
# with 6.5 mm faces, and each of these three steps has to fall inside the
# ~0.39 mm air gap between two neighbouring gear faces (U40, legacy stations:
# T030 north 134.83 | step 135.0 | T024 south 135.22, then T024|T018 and
# T018|T012 one pitch on), 0.17..0.22 from either face.
# +-0.13 keeps the step in the gap; the .XX grade (+-0.51) would let the
# larger land run up to 0.3 mm under the small-bore gear's face, so that gear
# could not pass the land to reach its pitch station.  The R0.10 root radius
# eats a further 0.10 of the outboard margin, which a bore edge break covers.
#
# Journal length Sec0End (collar face back to the front stub) and overall
# length Sec4End: one place, the routine grade the fleet's plain lengths
# print.  The journal only sets how far the stub stands proud of the post's
# south face (the collar face bears on its north face), and the tip end meets
# an adjustable cup-point screw that takes up any length error.  Shoulder
# radius: two places; nothing depends on it beyond clearing the gear faces.
#
# Collar (#914): the diameter prints one place (.X leaves a 1.0 mm minimum
# bearing ring outside the post bore, and the 5/8 bar caps the top); the web
# prints three places, because at .XX the 1.681 web could fall to 1.17, under
# the 1.5 floor the user accepted it against.  Solder stations: three places,
# the +-0.13 the user ruled.
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
    "CollarProfile": {"CollarDia": 1},
    "Collar": {"CollarWidth": 3},
    "SolderStations": {"T120Station": 3, "T006Station": 3},
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
