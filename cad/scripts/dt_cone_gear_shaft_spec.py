r"""Pure-data dimensional contract shared by the cone gear shaft and drawing."""

from __future__ import annotations

import math

import cone_line
import dt_cone_pivot_post_spec
import dt_cone_tip_block_spec

from _gtol_spec import CylinderFace
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

from dt_cone_gear_spec import FACE_WIDTH as CONE_GEAR_FACE_WIDTH, SEAT_PITCH, outside_dia_mm
from dt_cone_gear_stack import PITCH_LOCKSTEP_TOLERANCE, face_band
from dt_cone_pivot_post_installation import GEAR_AXIS_SHIFT
from dt_cone_pivot_post_spec import RUNNING_BORE_BAND as POST_JOURNAL_BORE_BAND
from cone_shaft_land_bands import (  # noqa: F401  re-exported for the shaft build
    FLAT_AF_BAND,
    GEAR_SEAT_BAND,
    LAND_DIA_PLACES,
    LAND_AF_PLACES,
    RUNNING_DIA_BAND,
    SECTION_DIA_BANDS,
    SECTION_FLAT_AF,
    TERMINAL_DIA_IN,
    TERMINAL_DIA_PLACES,
    TERMINAL_FLAT_EDGE_BREAK_MAX,
)
from cone_stack_end_play import COLLAR_FEELER, MARGIN_SPARE, SHAFT_END_PLAY
from vn_cone_tip_collar_spec import WIDTH as TIP_COLLAR_WIDTH
from vn_cone_tip_adjuster_spec import CUP_DEPTH
from dt_crank_drive_gear_spec import CENTRE_SHIFT_NORTH as GEAR64_CENTRE_SHIFT_NORTH
from dt_crank_drive_gear_spec import FACE_WIDTH as GEAR64_FACE_WIDTH
from dt_crank_drive_gear_spec import LAYOUT_FACE_WIDTH as GEAR64_LAYOUT_FACE_WIDTH
from dt_crank_drive_gear_spec import SOUTH_FACE_SHIFT_NORTH as GEAR64_SOUTH_FACE_SHIFT_NORTH
from dt_crank_drive_gear_spec import LAYOUT_CENTRE_STATION as GEAR64_LAYOUT_CENTRE_STATION
from gear_seat_fit import flat_bore_af_band, seat_bore_band


MM_PER_IN = 25.4

# The manually rederived v2 pivot post has a Ø12.2808 bearing bore spanning
# 42.011 mm along the cone axis.  The shaft begins 1.0 mm proud of the post's
# front face, so the integral journal is one millimetre longer than the post
# body and runs with 0.05 mm diametral clearance.
JOURNAL_BORE_DIA = dt_cone_pivot_post_spec.BORE_DIA
JOURNAL_CLEARANCE = 0.05
JOURNAL_DIA = JOURNAL_BORE_DIA - JOURNAL_CLEARANCE
# Actual limits for this post/shaft pair, not an intended common clearance.
JOURNAL_DIAMETRAL_CLEARANCE_MM = (
    JOURNAL_BORE_DIA + POST_JOURNAL_BORE_BAND[1] - JOURNAL_DIA - RUNNING_DIA_BAND[0],
    JOURNAL_BORE_DIA + POST_JOURNAL_BORE_BAND[0] - JOURNAL_DIA - RUNNING_DIA_BAND[1],
)
JOURNAL_PROUD = 1.0
JOURNAL_END = dt_cone_pivot_post_spec.CONE_BOSS_LENGTH + JOURNAL_PROUD

# The post's cone station and boss length locate its front face.  The shaft
# end is JOURNAL_PROUD south of that face; the part origin is that end.
# All local stations below follow the same cone-line/post geometry.
FRONT_STUB = (
    -cone_line.POST_STATION
    + dt_cone_pivot_post_spec.CONE_BOSS_LENGTH / 2.0
    + JOURNAL_PROUD
)

# Axial capture (#914, user ruling 2026-09-25).  The tip adjuster pushes the
# shaft south, toward the post; nothing reacted it until the 64T met the post
# boss 1.681 further on.  An integral collar fills that gap: its south face
# bears on the post's north boss face (flush with the journal end) and the
# gear stack is pushed onto its north face (dt_cone_gear_stack).  The collar
# bears on the boss annulus outside the Ø12.2808 bore and inside the Ø17.2
# boss.
#
# The 64T's SOUTH face sits SOUTH_FACE_SHIFT_NORTH north of where the 8.0
# layout face on the 19.9 station put it (#1126), so the collar is the 1.681
# web under that layout face plus the shift: 3.181, above rule 12's 2.0 target
# at its low limit.  The solid stack (user ruling 2026-09-28) grows the 64T
# NORTH from that face to bear on T120, so the collar does not move.  The 64T
# centre is the drive-train's physical 64T station (the shaft tests pin the
# two equal).
GEAR64_SOUTH_FACE_STATION = (
    GEAR64_LAYOUT_CENTRE_STATION
    + GEAR_AXIS_SHIFT
    - GEAR64_LAYOUT_FACE_WIDTH / 2.0
    + GEAR64_SOUTH_FACE_SHIFT_NORTH
)
GEAR64_CENTER_STATION = (
    GEAR64_LAYOUT_CENTRE_STATION + GEAR_AXIS_SHIFT + GEAR64_CENTRE_SHIFT_NORTH
)
GEAR64_NORTH_FACE_STATION = GEAR64_SOUTH_FACE_STATION + GEAR64_FACE_WIDTH
COLLAR_START_STATION = JOURNAL_END
COLLAR_END_STATION = FRONT_STUB + GEAR64_SOUTH_FACE_STATION
COLLAR_THICKNESS = COLLAR_END_STATION - COLLAR_START_STATION
_COLLAR_THICKNESS_UNDER_8_FACE = 1.681218417601599
if (
    abs(GEAR64_CENTER_STATION - GEAR64_FACE_WIDTH / 2.0 - GEAR64_SOUTH_FACE_STATION) > 1e-9
    or abs(
        COLLAR_THICKNESS - (_COLLAR_THICKNESS_UNDER_8_FACE + GEAR64_SOUTH_FACE_SHIFT_NORTH)
    )
    > 1e-9
    or abs(COLLAR_THICKNESS - 3.181) > 5e-4
):
    raise AssertionError(
        f"the collar {COLLAR_THICKNESS:.4f} must stay the #1126 3.181 under the 64T's "
        f"unchanged south face {GEAR64_SOUTH_FACE_STATION:.4f} (user ruling 2026-09-28)"
    )

# The collar's diameter is the 5/8 in cold-finished bar's own, as supplied:
# never turned (user ruling 2026-09-26 on Codex P1 #916).  The turned Ø15.0 it
# replaced printed .X, and at 14.2 it left a 0.96 thrust ring on the boss.
# The shaft is turned from this bar, so the collar is also its largest
# diameter.  ASTM A108 cold-finished rounds take ASTM A29's cold-drawn size
# tolerance: over 1/2 through 1 in, +0 / -0.002 in.
STOCK_DIA = 0.625 * MM_PER_IN
STOCK_DIA_BAND = (0.0, -0.002 * MM_PER_IN)
COLLAR_DIA = STOCK_DIA
# The thrust ring: the collar's south face on the post boss, between the bore
# and the collar OD.  Held to rule 12's 1.5 floor (user ruling 2026-09-26)
# with BOTH bounding edges broken at the worst case: the collar's OD edge and
# the post's bore rim.  The title block's 0.25 break would take the 1.77 ring
# to 1.27, so both edges print a smaller break, derived from
# ring - 2 x break >= floor and rounded DOWN to one printable place (0.1):
# the collar under its stock callout, the post's journal rims in the post
# sheet's journal note (draw_dt_cone_pivot_post.JOURNAL_NOTE).  Sizing the ring
# for two 0.25 breaks instead needs ring >= 2.0, an 11/16 bar, which the
# user's ruling (5/8 bar as supplied) rules out.
THRUST_RING_FLOOR = 1.5
THRUST_RING_MIN = (
    (STOCK_DIA + STOCK_DIA_BAND[1]) - (JOURNAL_BORE_DIA + POST_JOURNAL_BORE_BAND[0])
) / 2.0
THRUST_EDGE_BREAK_MAX = (
    math.floor((THRUST_RING_MIN - THRUST_RING_FLOOR) / 2.0 * 10.0 + 1e-9) / 10.0
)
if THRUST_RING_MIN - 2.0 * THRUST_EDGE_BREAK_MAX < THRUST_RING_FLOOR - 1e-9:
    raise AssertionError(
        f"thrust ring {THRUST_RING_MIN:.3f} less two {THRUST_EDGE_BREAK_MAX} "
        f"breaks is under the {THRUST_RING_FLOOR} floor"
    )
# The callout under the collar's reference diameter: the stock statement in
# the U41 plate's form ("1/4 PLATE AS SUPPLIED"), so the bar size stays out
# of the MATERIAL cell, and the collar's own edge break, tighter than the
# title block's.
COLLAR_STOCK_CALLOUT = (
    f"5/8 BAR AS SUPPLIED\nEDGE BREAK {THRUST_EDGE_BREAK_MAX:.1f} MAX"
)
# The same break on the post's journal rims, the ring's other bounding edge;
# the post sheet prints it with the journal size.
POST_JOURNAL_RIM_BREAK = f"RIMS BREAK {THRUST_EDGE_BREAK_MAX:.1f} MAX"

# Station layout.  Every cone gear station was laid out on a 6.5 reference
# face one exact-tracking seat pitch (dt_cone_gear_spec.SEAT_PITCH) from the next;
# the drive-train assembly owns both, and test_dt_cone_gear_shaft_drawing pins
# the duplicates to it.  The gears are a solid stack (user ruling
# 2026-09-28): each is dt_cone_gear_spec.FACE_WIDTH thick, grown SOUTH from the
# reference north face (centre + 3.25), so every north face -- T006's
# included -- stays where it was, and each gear bears on the one before it.
T006_CENTER_STATION = cone_line.T006_CENTER_STATION
CONE_FACE_STATION_REFERENCE = cone_line.CONE_FACE_STATION_REFERENCE
T006_NORTH_FACE_STATION = cone_line.T006_NORTH_FACE


def gear_faces(j: int) -> tuple[float, float]:
    """(south, north) cone station of seat j's gear faces (pivot end = 0)."""
    north = T006_NORTH_FACE_STATION - (19 - j) * SEAT_PITCH
    return north - CONE_GEAR_FACE_WIDTH, north


# The 64T bears on T120: its north face is T120's south face, the 64T never
# the longer (dt_cone_gear_stack.PITCH_LOCKSTEP_TOLERANCE), so the modelled stack
# closes without interference.
if not (
    -1e-9
    <= gear_faces(0)[0] - GEAR64_NORTH_FACE_STATION
    <= PITCH_LOCKSTEP_TOLERANCE
):
    raise AssertionError(
        f"64T north face {GEAR64_NORTH_FACE_STATION:.6f} must meet T120's south face "
        f"{gear_faces(0)[0]:.6f} within 0..{PITCH_LOCKSTEP_TOLERANCE}"
    )

# The tip end: the custom MHA-VN-016 stack collar is set one COLLAR_FEELER
# north of T006's face and locked on the
# Sec4 D-flat.  The MHA-DT-021 tip block is a straight prism fixed by its
# hold-down: its north face stands TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET south of
# the pivot, itself PIVOT_FROM_T006_NORTH_FACE north of T006's face
# (cone_line's constants).  Rule-12 E11's #10-32 McMaster 94025A164 cup
# adjuster sits ADJUSTER_EMBED (the block spec's) in from that face with its
# apex on the tip.  The vendor Sketch2 profile (Line7, harvested 2026-09-24)
# puts the 45 deg conical cup apex 1.2065 mm beyond the cup rim
# (4.7625 - 3.556), so this spec ends the shaft there; the assembly backs the
# adjuster out by the stub's seat depth on the cup wall. The block, pivot
# and embed stations follow their pure geometry owners.
TIP_COLLAR_START_STATION = T006_NORTH_FACE_STATION + COLLAR_FEELER
TIP_COLLAR_END_STATION = TIP_COLLAR_START_STATION + TIP_COLLAR_WIDTH
TIP_BLOCK_LENGTH = dt_cone_tip_block_spec.BLOCK_Z
PIVOT_FROM_T006_NORTH_FACE = cone_line.PIVOT_STATION - cone_line.T006_NORTH_FACE
TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET = cone_line.TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET
TIP_BLOCK_NORTH_FACE_STATION = cone_line.TIP_BLOCK_NORTH_FACE
TIP_BLOCK_SOUTH_FACE_STATION = TIP_BLOCK_NORTH_FACE_STATION - TIP_BLOCK_LENGTH
ADJUSTER_EMBED = dt_cone_tip_block_spec.ADJUSTER_EMBED
ADJUSTER_CUP_RIM_STATION = TIP_BLOCK_NORTH_FACE_STATION - ADJUSTER_EMBED
T006_TIP_STATION = ADJUSTER_CUP_RIM_STATION + CUP_DEPTH

# Land steps (user ruling 2026-09-28).  The touching gears leave no air gap
# to step in, so each step sits SEAT_STEP_SETBACK SOUTH of the interface where
# a smaller-bore gear first sits -- the north faces of T030 (j = 15), T024
# (j = 16) and T018 (j = 17) -- inside the larger gear's bore.  The larger
# gear then overhangs its land by the setback; the smaller one sits wholly on
# its own land.  The import-time proof below the precision table shows the
# step and its root fillet stay south of the smaller gear at print-worst.
SEAT_STEP_SETBACK = 1.0
SEAT_STEP_GEARS = (15, 16, 17)


def seat_step_station(j: int) -> float:
    """Cone station of the land step behind seat j's north face."""
    return gear_faces(j)[1] - SEAT_STEP_SETBACK


# U40 moved the terminal land start under T018. The cutter-native redesign
# keeps that station and substitutes the authoritative 1/32 in terminal
# diameter, shared by T012, T006 and the stack collar.
TIP_LAND_START_STATION = seat_step_station(17)
TIP_STUB_START_STATION = TIP_LAND_START_STATION
TIP_STUB_LENGTH = T006_TIP_STATION - TIP_STUB_START_STATION

# (diameter in inches, section end station in mm from the front stub end).
# Intermediate seats keep the retained sizes and fit classes. The terminal
# size lives in cone_shaft_land_bands and the gear family checks its web
# against the current cutter-owned printed MIN floors, not an old snapshot.
# Tailstock support remains required for the now more slender terminal land.
# Diameters decrease toward the tip for tip-first assembly.
SECTIONS: tuple[tuple[float, float], ...] = (
    (JOURNAL_DIA / MM_PER_IN, JOURNAL_END),  # integral v2-post bearing journal
    (0.375, FRONT_STUB + seat_step_station(15)),  # 64T + T120..T030 seats
    (0.25, FRONT_STUB + seat_step_station(16)),  # T024 seat
    (0.125, FRONT_STUB + TIP_LAND_START_STATION),  # T018 seat
    (TERMINAL_DIA_IN, FRONT_STUB + T006_TIP_STATION),  # T012/T006, collar, tip
)

SECTION_DIAS = tuple(dia_in * MM_PER_IN for dia_in, _end in SECTIONS)
SECTION_ENDS = tuple(end for _dia_in, end in SECTIONS)
SHAFT_LENGTH = SECTION_ENDS[-1]
def validate_gear_loading_clearances() -> None:
    """Require accepted physical tips before a native shaft build starts.

    Pure layout/fit readers remain importable when a cutter family is refused;
    the accepted outside-dia reader must still refuse at this runtime boundary.
    Tip-first assembly: each small gear passes over no land it cannot clear.
    """
    for teeth, next_bore in ((6, 4), (12, 3), (18, 2), (24, 1)):
        if outside_dia_mm(teeth) <= SECTION_DIAS[next_bore]:
            raise AssertionError(
                f"T{teeth:03d} tip diameter does not exceed the next inboard bore"
            )

# D-flats (user ruling 2026-09-28): every gear land carries one flat with its
# outward normal on the shaft's local +X (the Right plane's normal), across
# flat SECTION_FLAT_AF (flat to the opposite side of the land, the size a
# micrometer reads) with FLAT_AF_BAND.  Each flat runs its whole land, from
# the collar's (or the larger land's) face to the land's end, and the gears'
# D-bores (MHA-DT-003, MHA-DT-007) slide straight on.  The terminal land's flat runs
# out THROUGH THE TIP (user ruling 2026-09-28): T012 and T006 slide on over
# it and MHA-VN-016 is a thrust spacer riding the D, so the end face is a D too.
# FLAT_OFFSETS[i] is the flat's distance from the axis.
FLAT_OFFSETS: tuple[float | None, ...] = tuple(
    None if af is None else af - dia / 2.0
    for af, dia in zip(SECTION_FLAT_AF, SECTION_DIAS)
)
FLAT_LANDS = tuple(i for i, af in enumerate(SECTION_FLAT_AF) if af is not None)
if FLAT_LANDS != (1, 2, 3, 4):
    raise AssertionError(f"every gear land and only those carries a flat: {FLAT_LANDS}")
# Each flat runs off its land's end into air: the next land lies wholly inside
# the flat plane, so milling one flat never touches a smaller land.  And every
# gear, bore at its largest and flat at its shallowest, passes over every land
# north of its own on the way to its seat.
for _land in FLAT_LANDS[:-1]:
    _next_radius_max = (SECTION_DIAS[_land + 1] + SECTION_DIA_BANDS[_land + 1][0]) / 2.0
    _bore_flat_min = (
        SECTION_FLAT_AF[_land]
        + flat_bore_af_band(FLAT_AF_BAND)[1]
        - (SECTION_DIAS[_land] + seat_bore_band(SECTION_DIA_BANDS[_land])[0]) / 2.0
    )
    if FLAT_OFFSETS[_land] < _next_radius_max or _bore_flat_min < _next_radius_max:
        raise AssertionError(
            f"land {_land}'s flat {FLAT_OFFSETS[_land]:.4f} (bore flat "
            f"{_bore_flat_min:.4f}) reaches into land {_land + 1} "
            f"(radius {_next_radius_max:.4f})"
        )

# One length origin (#914 option A, Main ruling 2026-09-25): the collar's
# thrust face, the face the post bears on.  Drawing policy rule 8 allows one
# origin per view, baseline from it.  The journal runs back from it to the
# front stub, and the three land steps and the tip run forward from it.
# Measuring the steps from the same face as the gear stack keeps the
# journal's .X length out from between them.  The tip is a station too (#917
# R5 (a), Main 2026-09-26): the collar is what the tip cup's embed is set
# against, and front-to-tip as the controlling length stacked the journal's
# .X on the overall's, doubling the collar-to-tip band; the front-to-tip
# overall is a reference.  Each land's end plane is offset from
# SECTION_ORIGINS[i] by SECTION_KNOBS[i], the value its SecEnd{i} global
# carries; land 0 is the journal, extruded from the front face.  Each flat is
# cut from the collar face to its land's end by the same knob.
DATUM_STATION = COLLAR_START_STATION
SECTION_ORIGINS = (
    "Front Plane",
    "CollarFace",
    "CollarFace",
    "CollarFace",
    "CollarFace",
)
SECTION_KNOBS = tuple(
    end if origin == "Front Plane" else end - DATUM_STATION
    for end, origin in zip(SECTION_ENDS, SECTION_ORIGINS)
)

# Diameter and across-flat bands, one NAMED class per land, live in
# cone_shaft_land_bands so the gears derive their bores from them without
# importing this spec; build_dt_cone_gear_shaft applies them to the model
# dimensions.

# Step root radius.  Each step sits inside the larger gear's bore, one
# SEAT_STEP_SETBACK behind the smaller gear's south face, so the root can be
# neither a sharp corner (a stress riser at the smallest section of a slender
# shaft) nor a radius that reaches the smaller gear: the fillet stands 0.10
# proud of the smaller land -- more than that gear's radial clearance on
# either the round or the flat -- so its axial run is booked in the setback
# (the proof below).  R0.10 is the standard tool nose radius.  Modelled as
# geometry, round root and flat root alike, and dimensioned once, not written
# as a process note.
FILLET_RADIUS = 0.10
# Three identical land-step roots (the collar's roots stay sharp,
# build_dt_cone_gear_shaft), one fillet feature, one radius dimension.
FILLET_CALLOUT = "3X"

# Surface texture, on the two lands that bear: the Ø12.2308 journal turns in
# the pivot post bore, and the terminal land's round carries the MHA-VN-016
# thrust spacer's round bore and ends in the adjuster's cup.  (It is a D, not
# a running journal, since its flat runs out through the tip.)  The three
# intermediate lands only carry gears, so
# they are left to the title-block process row.
SURFACE_FINISHES = (
    SurfaceFinishControl("pivot_journal", MACHINED_UM, CylinderFace(JOURNAL_DIA)),
    SurfaceFinishControl(
        "tip_land",
        MACHINED_UM,
        CylinderFace(SECTION_DIAS[-1], tolerance_mm=0.01),
    ),
)

# What the native dimensions cannot say (drawing-simplicity policy rule 2: a
# fit requirement names its mate).  The gear seats and their flats name the
# bores they fit (MHA-DT-003's and MHA-DT-007's); why the seat band sits below
# nominal is cone_shaft_land_bands.GEAR_SEAT_BAND's comment, and the fit-up
# lives only at the drive-train assembly step -- rule 6 keeps both off the
# sheet (Main, 2026-09-26).  No check the shop cannot make (codex, 375a122c),
# no digits but the mates' numbers, no method words but one.  Lines stay
# short: the note block starts 58 mm in and the title block begins at 216 mm.
# The tailstock line is that one process word, by user ruling (U40,
# 2026-09-23): the slender terminal land cannot be turned unsupported,
# so the support IS the requirement (rule 6's exception), not a
# method preference.  The parallel line is the flats' relative clock (codex,
# fca59e2b): each land's flat turns every gear on it, so the four must share
# one clock.  No dimension can say it -- the flats stand in four separate
# sections -- and rule 3 keeps a parallelism frame off a shaft, so the
# requirement is the note and its tolerance is the title block's angle,
# which error_budget.yaml books per land as cone_land_clock.
DRAWING_NOTES = "\n".join(
    (
        "GEAR SEATS AND FLATS MATE MHA-DT-003 AND MHA-DT-007 BORES.",
        "ALL FLATS PARALLEL.",
        "TURN THE TIP LAND WITH TAILSTOCK SUPPORT.",
        "TERMINAL MAX BREAK: LONG TORQUE CORNERS ONLY.",
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
    "Sec1FlatProfile": {"Sec1AF"},
    "Sec2FlatProfile": {"Sec2AF"},
    "Sec3FlatProfile": {"Sec3AF"},
    "Sec4FlatProfile": {"Sec4AF"},
    "TerminalFlatEdgeBreak": {"TerminalTorqueEdge"},
    "ShoulderFillets": {"ShoulderR"},
    "CollarProfile": {"CollarDia"},
    "Collar": {"CollarWidth"},
}

# Display precision is a MODEL property (drawing-simplicity policy rule 2):
# the part build stamps it and the sheet only reads it back.
#
# Diameters and across-flats: three places.  Each carries its named band
# (SECTION_DIA_BANDS, FLAT_AF_BAND), so their places are only the number's
# spelling.
#
# Land steps Sec1End..Sec3End: three places, which is the title-block .XXX
# general grade (+-0.13) and no explicit band.  This is a location
# requirement, not a spelling: each step sits SEAT_STEP_SETBACK behind the
# smaller gear's south face, and the proof below books the step's band with
# the collar's, the stack's and the fillet's in that 1.0; the .XX grade
# (+-0.51) alone would take half of it.
#
# Tip station Sec4End (collar face to the tip): two places, the title
# block's .XX grade (+-0.51), by user ruling 2026-09-29.  The tip block is
# fixed by its hold-down, so this band lands on the adjuster's embed;
# build_dt_drive_train_assembly closes that stack by the block's depth and the
# 1.0D adjuster engagement instead of a tighter length.  Journal length
# Sec0End (collar face back to the front stub): one place, the routine grade
# the fleet's plain lengths print; it only sets how far the stub stands proud
# of the post's south face.  Step radius: two places; nothing depends on it
# beyond the setback proof.
#
# Collar (#914): the diameter is the bar's as supplied (STOCK_DIA), so it
# prints as a two-place reference, 15.88, the bar's own size; the web
# prints three places because it is the 64T's station toward MHA-DT-005
# (crank_boss_rim.GEAR64_STATION_TOWARD_POST) and the gear stack's origin:
# at .XX the station term grows from 0.53 to 0.91 and the widest face holding
# the post floor falls from 6.5 to 6.2.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "Sec0Profile": {"Sec0Dia": LAND_DIA_PLACES[0]},
    "Sec1Profile": {"Sec1Dia": LAND_DIA_PLACES[1]},
    "Sec2Profile": {"Sec2Dia": LAND_DIA_PLACES[2]},
    "Sec3Profile": {"Sec3Dia": LAND_DIA_PLACES[3]},
    "Sec4Profile": {"Sec4Dia": LAND_DIA_PLACES[4]},
    "Sec0": {"Sec0End": 1},
    "Sec1": {"Sec1End": 3},
    "Sec2": {"Sec2End": 3},
    "Sec3": {"Sec3End": 3},
    "Sec4": {"Sec4End": 2},
    "Sec1FlatProfile": {"Sec1AF": LAND_AF_PLACES[1]},
    "Sec2FlatProfile": {"Sec2AF": LAND_AF_PLACES[2]},
    "Sec3FlatProfile": {"Sec3AF": LAND_AF_PLACES[3]},
    "Sec4FlatProfile": {"Sec4AF": LAND_AF_PLACES[4]},
    "TerminalFlatEdgeBreak": {"TerminalTorqueEdge": 3},
    "ShoulderFillets": {"ShoulderR": 2},
    "CollarProfile": {"CollarDia": 2},
    "Collar": {"CollarWidth": 3},
}
# The front-to-tip overall (#917 R5 (a)) is the sheet's one reference
# dimension, the read-only sum of the journal and the tip station: one place,
# the grade of the journal it sums.
DRAWING_REFERENCE_PRECISION = 1

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


def printed_band(name: str) -> float:
    """The title-block band a marked length prints at its own places."""
    return printed_band_mm(DRAWING_PRECISION_BY_NAME[name])


# Guaranteed cylindrical support across the ENTIRE retained shaft stroke.
# The integral collar starts seated on the actual post north face; north q
# withdraws the shaft's free end into the bore. Both bore rims and ordinary
# shaft-end break remove support; the shorter COMPLETE overlap controls cock.
JOURNAL_FREE_END_BREAK_MAX_MM = 0.25
JOURNAL_SUPPORT_SPAN_MIN_MM = min(
    dt_cone_pivot_post_spec.CONE_BOSS_LENGTH
    - printed_band_mm(dt_cone_pivot_post_spec.DRAWING_PRECISION_BY_NAME["ConeBossLen"])
    - 2.0 * THRUST_EDGE_BREAK_MAX,
    JOURNAL_END - printed_band("Sec0End")
    - JOURNAL_FREE_END_BREAK_MAX_MM - THRUST_EDGE_BREAK_MAX - SHAFT_END_PLAY[1],
)
if JOURNAL_SUPPORT_SPAN_MIN_MM <= 0.0:
    raise AssertionError("post/shaft pair has no guaranteed cylindrical bearing span")


# The setback proof (user ruling 2026-09-28).  Each step and its root fillet
# must stay south of the smaller gear's south face -- the larger gear's north
# face -- with the stack pushed onto the collar at its shortest: the step at
# the north end of its printed band, the fillet's 0.10 run
# along the smaller land, the collar web's printed band (the stack stands on
# the collar's north face, the steps are measured from its south face), the
# stack's own shortfall up to that face (dt_cone_gear_stack.face_band) and the
# fleet's MARGIN_SPARE.  The fillet runs the same 0.10 along the flat's root
# as along the round's, so the one budget covers the smaller gear's round
# bore and its flat alike.  In service the stack only floats north, off the
# step.
SEAT_STEP_BUDGET: dict[str, dict[str, float]] = {}
for _name, _j, _end in zip(("Sec1End", "Sec2End", "Sec3End"), SEAT_STEP_GEARS, SECTION_ENDS[1:4]):
    if abs(_end - FRONT_STUB - seat_step_station(_j)) > 1e-9:
        raise AssertionError(f"{_name} is not one setback behind gear {_j}'s north face")
    _terms = {
        "step band": printed_band(_name),
        "fillet": FILLET_RADIUS,
        "collar band": printed_band("CollarWidth"),
        "stack": -face_band(_j, "north")[1],
        "spare": MARGIN_SPARE,
    }
    _terms["margin"] = SEAT_STEP_SETBACK - sum(_terms.values())
    SEAT_STEP_BUDGET[_name] = _terms
    if _terms["margin"] < 0.0:
        raise AssertionError(
            f"{_name}: the step and its root reach the smaller gear at print-worst {_terms}"
        )
