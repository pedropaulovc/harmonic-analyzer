r"""Pure-data dimensional contract shared by the cone gear shaft and drawing."""

from __future__ import annotations

import math

import cone_land_key
import cone_line
import cone_tip_cluster
import dt_cone_pivot_post_spec

from _fit_deviations import deviations
from _gtol_cylinder import CylinderFace
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm, printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl

from dt_cone_gear_spec import FACE_WIDTH as CONE_GEAR_FACE_WIDTH, SEAT_PITCH, outside_dia_mm
from dt_cone_gear_spec import FACE_WIDTH_BAND as CONE_GEAR_FACE_WIDTH_BAND
from dt_cone_gear_stack import PITCH_LOCKSTEP_TOLERANCE, face_band
from _cone_axis_constants import GEAR_AXIS_SHIFT
from dt_cone_pivot_post_spec import JOURNAL_BORE_BAND as POST_JOURNAL_BORE_BAND
from cone_shaft_land_bands import (  # noqa: F401  re-exported for the shaft build
    GEAR_SEAT_BAND,
    LAND_DIA_PLACES,
    RUNNING_DIA_BAND,
    SECTION_CONE_GEAR_TEETH,
    SECTION_DIA_BANDS,
    UNIT,
    land_finished_dia_limits_mm,
)
from cone_stack_end_play import MARGIN_SPARE, SHAFT_END_PLAY, STACK_FEELER_BAND
from dt_crank_drive_gear_spec import CENTRE_SHIFT_NORTH as GEAR64_CENTRE_SHIFT_NORTH
from dt_crank_drive_gear_spec import FACE_WIDTH as GEAR64_FACE_WIDTH
from dt_crank_drive_gear_spec import LAYOUT_FACE_WIDTH as GEAR64_LAYOUT_FACE_WIDTH
from dt_crank_drive_gear_spec import SOUTH_FACE_SHIFT_NORTH as GEAR64_SOUTH_FACE_SHIFT_NORTH
from dt_crank_drive_gear_spec import LAYOUT_CENTRE_STATION as GEAR64_LAYOUT_CENTRE_STATION
from gear_seat_fit import seat_bore_band

MM_PER_IN = 25.4


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.004``, ``1.69``."""
    text = f"{value_mm / MM_PER_IN:.{places}f}"
    return text[1:] if text.startswith("0.") else text


# The manually rederived v2 pivot post has a .483 in bearing bore spanning
# 42.011 mm along the cone axis.  The shaft begins just proud of the post's
# front face: the integral journal is turned 1.70 in long (#290: the old
# 1.0 mm-proud 43.011 snapped up to the printed .XX grid, so the stub still
# stands the assembly's 1.0 mm proud), JOURNAL_PROUD longer
# than the post body.  It is turned .0005 in under the bore nominal (.4825
# in), so the bore's +.0010/+.0005 band closes the shaft_in_bushing class on
# its SHAFT_H band.
JOURNAL_BORE_DIA = dt_cone_pivot_post_spec.BORE_DIA
JOURNAL_CLEARANCE = 0.0127
JOURNAL_DIA = JOURNAL_BORE_DIA - JOURNAL_CLEARANCE
# Actual limits for this post/shaft pair, not an intended common clearance.
JOURNAL_DIAMETRAL_CLEARANCE_MM = (
    JOURNAL_BORE_DIA + POST_JOURNAL_BORE_BAND[1] - JOURNAL_DIA - RUNNING_DIA_BAND[0],
    JOURNAL_BORE_DIA + POST_JOURNAL_BORE_BAND[0] - JOURNAL_DIA - RUNNING_DIA_BAND[1],
)
JOURNAL_END = 43.18  # 1.70
JOURNAL_PROUD = JOURNAL_END - dt_cone_pivot_post_spec.CONE_BOSS_LENGTH
if not 1.0 <= JOURNAL_PROUD <= 1.5:
    raise AssertionError(
        f"the journal stands {JOURNAL_PROUD:.3f} proud of the post body, outside 1.0..1.5"
    )

# The post's cone station and boss length locate its front face.  The shaft
# end is JOURNAL_PROUD south of that face; the part origin is that end.
# All local stations below follow the same cone-line/post geometry.
FRONT_STUB = (
    -cone_line.POST_STATION
    + dt_cone_pivot_post_spec.CONE_BOSS_LENGTH / 2.0
    + JOURNAL_PROUD
)

# Axial capture (#914, user ruling 2026-09-25).  The tip end screw pushes the
# shaft south, toward the post; nothing reacted it until the 64T met the post
# boss 1.681 further on.  An integral collar fills that gap: its south face
# bears on the post's north boss face (flush with the journal end) and the
# gear stack is pushed onto its north face (dt_cone_gear_stack).  The collar
# bears on the boss annulus outside the .483 in bore and inside the Ø17.2
# boss.
#
# The 64T's SOUTH face sits SOUTH_FACE_SHIFT_NORTH north of where the 8.0
# layout face on the 19.9 station put it (#1126), so the collar is the 1.681
# web under that layout face plus the shift: 3.181 (a stack closure, printed
# .125 at .XXX), above drawing-guidelines.md rule 17 (walls and webs)'s .080 in target
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
STOCK_DIA = 15.875  # 5/8
STOCK_DIA_BAND = (0.0, -0.0508)  # +0/-.002 in
COLLAR_DIA = STOCK_DIA
# The thrust ring: the collar's south face on the post boss, between the bore
# and the collar OD.  Held to drawing-guidelines.md rule 17 (walls and webs)'s
# .060 in floor (user ruling 2026-09-26; #290 inch floor) with BOTH bounding
# edges broken at the worst case: the collar's OD edge and the post's bore
# rim.  The title block's .010 break would take the .070 ring to .050, so both
# edges print a smaller break, derived from ring - 2 x break >= floor and
# rounded DOWN to the printed .001 in grid: the collar under its stock
# callout, the post's journal rims in the post sheet's journal note
# (draw_dt_cone_pivot_post.JOURNAL_NOTE).  Sizing the ring for two .010
# breaks instead needs a larger bar, which the user's ruling (5/8 bar as
# supplied) rules out.
THRUST_RING_FLOOR = WALL_FLOOR_MM
THRUST_RING_MIN = (
    (STOCK_DIA + STOCK_DIA_BAND[1]) - (JOURNAL_BORE_DIA + POST_JOURNAL_BORE_BAND[0])
) / 2.0
THRUST_EDGE_BREAK_MAX = round(
    math.floor((THRUST_RING_MIN - THRUST_RING_FLOOR) / 2.0 / MM_PER_IN * 1e3 + 1e-9)
    / 1e3 * MM_PER_IN,
    9,
)
if THRUST_RING_MIN - 2.0 * THRUST_EDGE_BREAK_MAX < THRUST_RING_FLOOR - 1e-9:
    raise AssertionError(
        f"thrust ring {THRUST_RING_MIN:.3f} less two {THRUST_EDGE_BREAK_MAX} "
        f"breaks is under the {THRUST_RING_FLOOR} floor"
    )
# The collar's two roots stay sharp in the model (#914): its south face seats
# on the MHA-DT-05 boss round the journal rim, its north face carries the
# 64T.  The 64T clears any root under its 1.0 bore chamfer; the post's rim
# break has no minimum, so the root's limit is the one a sharp rim still
# seats against: an R.002 root stands a sharp rim off the face by under
# .0004 at the journal's mean clearance.  A hand-ground tool nose holds it.
COLLAR_ROOT_RADIUS_MAX = 0.0508  # .002
# The callout under the collar's reference diameter: the stock statement in
# the U41 plate's form ("1/4 PLATE AS SUPPLIED"), so the bar size stays out
# of the MATERIAL cell, with the collar's two limits tighter than the title
# block at the feature they govern (rule 3: never in a note) and their one
# reason naming both faces' mates once by drawing number.  The OD edge break
# keeps the MHA-DT-05 thrust ring above its floor (above); the sharp roots
# let both faces seat.  Two lines of words (rule 7).
COLLAR_STOCK_CALLOUT = "\n".join(
    (
        f"5/8 BAR AS SUPPLIED, EDGE BREAK {inch_text(THRUST_EDGE_BREAK_MAX, 3)} MAX",
        f"ROOTS R{inch_text(COLLAR_ROOT_RADIUS_MAX, 3)} MAX, SEATS MHA-DT-05 AND MHA-DT-07",
    )
)
# The same break on the post's journal rims, the ring's other bounding edge;
# the post sheet prints it with the journal size.
POST_JOURNAL_RIM_BREAK = f"RIMS BREAK {inch_text(THRUST_EDGE_BREAK_MAX, 3)} MAX"
def _gear(teeth: int) -> str:
    return f"T{teeth:03d}"


# Each tight band names its mate and fit route (drawing-guidelines.md rule
# 4).  The journal's .0008 band is under the turned-diameter row, so it is a
# matched running fit to the MHA-DT-05 bore, the form the reviewer accepted
# on MHA-DT-19's pivot shaft, its clearance the printed limits'
# (JOURNAL_DIAMETRAL_CLEARANCE_MM) as a REF row of its own: two lines of
# words (rule 7) narrow enough to stand between the faced end and section
# A-A (round 3's 33-character line crowded section A's letter).  Land 1
# slides in the bores of the gears it carries (MHA-DT-03, MHA-DT-07 and the
# MHA-DT-VN-71 key): flag note LAND_NOTE, linked from its diameter and the
# keyseat.  Land 2 and the socket are bonded fits (owner decision C1 keyed,
# 2026-11-09, PR #1992; cone_tip_cluster): flag note BOND_NOTE names their
# mates, linked from land 2's diameter and the socket's.  The compound is
# named on the assembly sheet, where the joint is made (rule 23).
LAND_NOTE = 1
BOND_NOTE = 2
LAND_FLAG = f"SEE NOTE {LAND_NOTE}"
BOND_FLAG = f"SEE NOTE {BOND_NOTE}"
JOURNAL_FIT_CALLOUT = (
    "RUNNING FIT, MATCHED\n"
    "TO MHA-DT-05 BORE\n"
    f"(CLEARANCE {inch_text(JOURNAL_DIAMETRAL_CLEARANCE_MM[0], 4)}"
    f"-{inch_text(JOURNAL_DIAMETRAL_CLEARANCE_MM[1], 4)})"
)
SEAT_MATE_CALLOUTS = {
    "Sec0Dia": JOURNAL_FIT_CALLOUT,
    "Sec1Dia": LAND_FLAG,
}
SEAT_MATE_SUFFIXES = {"Sec2Dia": f" {BOND_FLAG}"}
# The keyseat width is centred on its section; it carries the bare flag.
KEYSEAT_MATE_SUFFIXES = {"Sec1KeyseatWidth": f" NOTE {LAND_NOTE}"}

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
    """(south, north) cone station of seat j's gear faces at their layout
    stations (pivot end = 0)."""
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

# Land step (user ruling 2026-09-28).  The touching gears leave no air gap
# to step in, so the land-1 to land-2 step sits SEAT_STEP_SETBACK SOUTH of
# T030's north face (j = 15), inside T030's bore.  T030 then overhangs land 1
# by the setback; T024 sits wholly on land 2.  The import-time proof below
# the precision table shows the step and its root fillet stay south of T024
# at print-worst.
SEAT_STEP_SETBACK = 1.0
SEAT_STEP_GEAR = 15


def seat_step_station(j: int) -> float:
    """Cone station of the land step behind seat j's north face."""
    return gear_faces(j)[1] - SEAT_STEP_SETBACK


# The tip (owner decision C1 keyed, 2026-11-09, PR #1992; cone_tip_cluster).
# T024 (seat j = 16) is bonded on land 2 one STACK_FEELER off T030's north
# face, so in the model it sits TIP_SET_SHIFT_MM north of its layout
# station; the shaft ends TIP_END_RECESS_MM inside T024's bore, so T018
# always butts T024's north face.  The reamed socket for T006's spigot runs
# SOCKET_DEPTH_MM into that end.
T024_SEAT = 16
T024_NORTH_FACE_STATION = gear_faces(T024_SEAT)[1] + cone_tip_cluster.TIP_SET_SHIFT_MM
TIP_END_STATION = T024_NORTH_FACE_STATION - cone_tip_cluster.TIP_END_RECESS_MM
SOCKET_DIA = cone_tip_cluster.STEM_BORE_DIA_MM
SOCKET_DIA_BAND = cone_tip_cluster.STEM_BORE_BAND
SOCKET_DEPTH = cone_tip_cluster.SOCKET_DEPTH_MM
SOCKET_FLOOR_STATION = TIP_END_STATION - SOCKET_DEPTH
# A standard blind ream is fully defined by its callout (drawing-guidelines.md
# rules 9 and 12): the imported SocketDia over "REAM <depth> .20", the depth
# at the title block's .XX, its flag after it -- dt_cone_tip_block's dowel
# hole recipe.  The depth is not a marked dimension: it would dimension to a
# hidden line on the side view.
SOCKET_DEPTH_PLACES = 2
SOCKET_CALLOUT = "\n".join(
    (
        f"REAM <HOLE-DEPTH> {inch_text(SOCKET_DEPTH, SOCKET_DEPTH_PLACES)}",
        BOND_FLAG,
    )
)

# (diameter in inches, section end station in mm from the front stub end).
# Diameters decrease toward the tip for tip-first assembly.  The land-1 end
# is a gear-stack closure and land 2's end the tip cluster's; only the
# journal's end is a fabricated length, snapped above.
SECTION_DIAS: tuple[float, ...] = (
    JOURNAL_DIA,  # integral v2-post bearing journal, .4825
    cone_land_key.LAND_DIA_MM,  # 3/8: 64T + T120..T030 seats, keyed
    6.35,  # 1/4: T024, bonded; the socket in its end
)
SECTION_ENDS: tuple[float, ...] = (
    JOURNAL_END,
    FRONT_STUB + seat_step_station(SEAT_STEP_GEAR),
    FRONT_STUB + TIP_END_STATION,
)
SECTIONS: tuple[tuple[float, float], ...] = tuple(
    (dia / MM_PER_IN, end) for dia, end in zip(SECTION_DIAS, SECTION_ENDS, strict=True)
)
SHAFT_LENGTH = SECTION_ENDS[-1]


def validate_gear_loading_clearances() -> None:
    """Require accepted physical tips before a native shaft build starts.

    Pure layout/fit readers remain importable when a cutter family is refused;
    the accepted outside-dia reader must still refuse at this runtime boundary.
    Tip-first assembly: T024, the first gear on, is the smallest gear that
    passes a shaft land, and its tips clear the keyed land it stops short of.
    """
    if outside_dia_mm(24) <= SECTION_DIAS[1]:
        raise AssertionError("T024 tip diameter does not exceed the keyed land")


# Land 1 is round and keyed (owner decision 2026-11-09, C1 keyed, PR #1992):
# the 1/16 keyseat (cone_land_key) on the shaft's local +X runs the land, from
# the collar's tip-side face to the land's end.  No D-flat remains on the
# shaft.
KEYED_LAND = 1
if SECTION_DIAS[KEYED_LAND] != cone_land_key.LAND_DIA_MM:
    raise AssertionError("land 1 is the keyed Ø.375 land")
# The keyseat runs off its land's end into air: land 2 lies wholly inside the
# keyseat floor, so milling it never touches land 2.  And every land-1 gear,
# bore at its largest and keyway top at its shallowest, passes over land 2.
_LAND2_RADIUS_MAX = (SECTION_DIAS[2] + SECTION_DIA_BANDS[2][0]) / 2.0
_KEYSEAT_FLOOR_OFFSET_MIN = (
    cone_land_key.limits(cone_land_key.KEYSEAT_S_MM, cone_land_key.KEYSEAT_S_BAND)[0]
    - (SECTION_DIAS[KEYED_LAND] + SECTION_DIA_BANDS[KEYED_LAND][0]) / 2.0
)
_KEYWAY_TOP_OFFSET_MIN = (
    cone_land_key.limits(cone_land_key.KEYWAY_T_MM, cone_land_key.KEYWAY_T_BAND)[0]
    - (SECTION_DIAS[KEYED_LAND] + seat_bore_band(SECTION_DIA_BANDS[KEYED_LAND])[0])
    / 2.0
)
if min(_KEYSEAT_FLOOR_OFFSET_MIN, _KEYWAY_TOP_OFFSET_MIN) < _LAND2_RADIUS_MAX:
    raise AssertionError(
        f"land 1's keyseat floor {_KEYSEAT_FLOOR_OFFSET_MIN:.4f} (keyway top "
        f"{_KEYWAY_TOP_OFFSET_MIN:.4f}) reaches into land 2 (radius {_LAND2_RADIUS_MAX:.4f})"
    )

# Two length origins, one per chucking (drawing-guidelines.md rule 11; Main's
# delegated ruling (b), 2026-11-07, round 6).  The journal-side chucking faces
# the collar's thrust face, the face the post bears on: the journal runs back
# from it to the front stub and the collar web forward to the collar's
# tip-side face.  The tip-side chucking faces that tip-side face, the seat the
# gear stack is pushed onto (MHA-DT-07 first): the land step and the tip run
# forward from it, so the step and the gear it stands behind share one face
# and the collar web never enters between them.  The journal (1.70) and the
# web (.125) chain the two origins and the front stub to the tip; the
# front-to-tip overall is a reference.  Each land's end plane is offset from
# SECTION_ORIGINS[i] by SECTION_KNOBS[i], the value its SecEnd{i} global
# carries; land 0 is the journal, extruded from the front face.  The keyseat
# is cut back from land 1's end plane over the land, the socket from land
# 2's end plane.
DATUM_STATION = COLLAR_END_STATION
SECTION_ORIGINS = (
    "Front Plane",
    "CollarEndPlane",
    "CollarEndPlane",
)
SECTION_KNOBS = tuple(
    end if origin == "Front Plane" else end - DATUM_STATION
    for end, origin in zip(SECTION_ENDS, SECTION_ORIGINS)
)

# Diameter bands, one NAMED class per land, live in cone_shaft_land_bands so
# the gears derive their bores from them without importing this spec;
# build_dt_cone_gear_shaft applies them to the model dimensions.

# Step root radius.  The step sits inside T030's bore, one SEAT_STEP_SETBACK
# behind T024's south face, so the root's radius must not reach T024: the
# fillet stands .004 proud of land 2 -- more than T024's radial clearance --
# so its axial run is booked in the setback (the proof below).  R.004 is the
# standard tool nose radius.  Modelled as geometry and dimensioned once, not
# written as a process note.
FILLET_RADIUS = 0.1016  # .004
# The setback books the root's run at its printed maximum, so the radius
# prints as the single limit R.004 MAX (swTolMAX prints the model value, then
# MAX): the title block's +-.005 would let a .009 root reach T024 (Codjiflo
# P2 on #2107).  Any root from sharp up to .004 is good.
FILLET_R_BAND = (0.0, -FILLET_RADIUS)  # (upper, lower): any root up to the MAX
FILLET_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.004 MAX"

# Surface texture, on the one land that runs: the .4825 journal turns in
# the pivot post bore.  The gear lands and the socket only carry parts fixed
# to the shaft -- the land-1 gears are driven by the key, T024 and T006's
# spigot are bonded -- so they are left to the title-block process row
# (drawing-guidelines.md rule 6).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_journal", MACHINED_UM, CylinderFace(JOURNAL_DIA), display_unit=UNIT
    ),
)

# The sheet's numbered flag notes (drawing-guidelines.md rule 7: few,
# flagged, never a method).  Note LAND_NOTE names land 1's mates once by
# drawing number (rule 4; section A-A cuts the keyed land, owner decision
# 2026-11-09, PR #1992); the keyseat and its clock are the section's and the
# title block's angle (error_budget.yaml books it as cone_flat_clock).  Note
# BOND_NOTE names the bonded mates of land 2 and the socket.  Note STACK_NOTE
# names, once, the stack the three-place lengths set (rule 4): the step
# stands SEAT_STEP_SETBACK behind T024's south face (the proof below), the
# tip station keeps the end inside T024's bore so T018 butts T024 (the
# recess proof below), and the collar web is the MHA-DT-07 station and the
# stack's origin.  The
# 2026-09-28 flats' matched-fit line and U40's tailstock line went with the
# flats and the tip land (C1 keyed supersedes both).
STACK_NOTE = 3
DRAWING_NOTES = "\n".join(
    (
        f"{LAND_NOTE}. SLIDING FIT: MHA-DT-03 30T-120T GEARS, MHA-DT-07, KEY MHA-DT-VN-71.",
        f"{BOND_NOTE}. BONDED FIT: LAND MHA-DT-03 24T GEAR; SOCKET MHA-DT-37 SPIGOT.",
        f"{STACK_NOTE}. FLAGGED LENGTHS SET THE MHA-DT-07 AND MHA-DT-03 STACK.",
    )
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "Sec0Profile": {"Sec0Dia"},
    "Sec1Profile": {"Sec1Dia"},
    "Sec2Profile": {"Sec2Dia"},
    "Sec0": {"Sec0End"},
    "Sec1": {"Sec1End"},
    "Sec2": {"Sec2End"},
    "Sec1KeyseatProfile": {"Sec1KeyseatWidth", "Sec1KeyseatS"},
    "SocketProfile": {"SocketDia"},
    "Sec1KeyseatEndProfile": {"Sec1KeyseatEndSet"},
    "ShoulderFillets": {"ShoulderR"},
    "CollarProfile": {"CollarDia"},
    "Collar": {"CollarWidth"},
}

# Display precision is a MODEL property (drawing-simplicity-policy.md `How the repository implements the guidelines`):
# the part build stamps it and the sheet only reads it back.  Decimal inch
# (#290).
#
# Diameters: four places.  Each carries its named band (SECTION_DIA_BANDS,
# the socket's REAM_H7), so their places are only the number's spelling.
# Land 1's keyseat width and S print at cone_land_key's places with its
# bands.
#
# Land step Sec1End (from the collar's tip-side face): three places, the
# title-block .XXX general grade (+-.005) and no explicit band.  This is a
# location requirement, not a spelling: the step sits SEAT_STEP_SETBACK
# behind T024's south face, and the proof below books the step's printed
# limit with the stack's and the fillet's in that 1.0 mm; the .XX grade
# (+-.01) alone would take half of it.
#
# Tip Sec2End (collar's tip-side face to the end): three places, the .XXX
# grade, booked in the recess proof below (the end stays inside T024's bore
# at every limit).  Journal length Sec0End (collar thrust face back to the
# front stub): two places, the .XX grade, since the journal's guaranteed
# bearing span below reads it (never .X).  The socket's depth prints in its
# callout at SOCKET_DEPTH_PLACES, the .XX grade, booked in the spigot proof
# below.  Step radius: three places;
# nothing depends on it beyond the setback proof.
#
# Keyseat end (machinist review of 06460fb: the mill stop): the end radius's
# centre from the collar's tip-side face, two places, the title block's .XX
# grade, at .05 (cone_land_key.KEY_END_SET_MM).  At its printed low limit the
# widest end mill still stands clear of that face, the 64T's seat
# (KEYSEAT_END_COLLAR_CLEARANCE_MIN_MM below; Codjiflo #2331 4521933063:
# .03, tangent in the model, let it sink .011 in).  The key's square south
# end comes to rest on that centre line, so the band moves the key, never
# into the end; KEY_NORTH_MARGIN_MM below keeps its north end short of T024
# at the printed limits of both lengths.
#
# Collar (#914): the diameter is the bar's as supplied (STOCK_DIA), so it
# prints as the 5/8 fraction reference, the bar's own size; the web prints
# three places because it is the 64T's station toward MHA-DT-05
# (crank_boss_rim.GEAR64_STATION_TOWARD_POST) and the gear stack's origin.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "Sec0Profile": {"Sec0Dia": LAND_DIA_PLACES[0]},
    "Sec1Profile": {"Sec1Dia": LAND_DIA_PLACES[1]},
    "Sec2Profile": {"Sec2Dia": LAND_DIA_PLACES[2]},
    "Sec0": {"Sec0End": 2},
    "Sec1": {"Sec1End": 3},
    "Sec2": {"Sec2End": 3},
    "Sec1KeyseatProfile": {
        "Sec1KeyseatWidth": cone_land_key.KEYSEAT_PLACES,
        "Sec1KeyseatS": cone_land_key.KEYSEAT_PLACES,
    },
    "SocketProfile": {"SocketDia": cone_tip_cluster.STEM_PLACES},
    "Sec1KeyseatEndProfile": {"Sec1KeyseatEndSet": cone_land_key.KEY_END_SET_PLACES},
    "ShoulderFillets": {"ShoulderR": 3},
    "CollarProfile": {"CollarDia": 3},
    "Collar": {"CollarWidth": 3},
}
# The collar's stock reference prints as the bar's fraction.
COLLAR_DIA_FRACTION_DENOMINATOR = 8
# The front-to-tip overall (#917 R5 (a)) is the sheet's one reference
# dimension, the read-only sum of the journal, the web and the tip: two
# places.
DRAWING_REFERENCE_PRECISION = 2

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


_LENGTH_NOMINALS = {
    **{f"Sec{i}End": knob for i, knob in enumerate(SECTION_KNOBS)},
    "CollarWidth": COLLAR_THICKNESS,
    "ShoulderR": FILLET_RADIUS,
    "Sec1KeyseatEndSet": cone_land_key.KEY_END_SET_MM,
}


def printed_length_deviations(name: str) -> tuple[float, float]:
    """(lower, upper) mm about the model of a marked length's printed limits:
    the inch value the sheet prints (the socket depth in its callout), with
    its own band (the step root) or the title block's."""
    if name == "ShoulderR":
        return printed_deviations(
            FILLET_RADIUS, DRAWING_PRECISION_BY_NAME[name], deviations(FILLET_R_BAND), unit=UNIT
        )
    if name == "SocketDepth":
        return printed_deviations(SOCKET_DEPTH, SOCKET_DEPTH_PLACES, unit=UNIT)
    return printed_deviations(
        _LENGTH_NOMINALS[name], DRAWING_PRECISION_BY_NAME[name], unit=UNIT
    )


def printed_band(name: str) -> float:
    """The farther printed limit of a marked length from its model value: the
    title-block band plus the inch rounding of the printed nominal."""
    return max(abs(deviation) for deviation in printed_length_deviations(name))


# Guaranteed cylindrical support across the ENTIRE retained shaft stroke.
# The integral collar starts seated on the actual post north face; north q
# withdraws the shaft's free end into the bore. Both bore rims and ordinary
# shaft-end break remove support; the shorter COMPLETE overlap controls cock.
JOURNAL_FREE_END_BREAK_MAX_MM = edge_break_chamfer_mm(unit=UNIT)
JOURNAL_SUPPORT_SPAN_MIN_MM = min(
    dt_cone_pivot_post_spec.CONE_BOSS_LENGTH
    - printed_band_mm(dt_cone_pivot_post_spec.DRAWING_PRECISION_BY_NAME["ConeBossLen"], unit=dt_cone_pivot_post_spec.UNIT)
    - 2.0 * THRUST_EDGE_BREAK_MAX,
    JOURNAL_END + printed_length_deviations("Sec0End")[0]
    - JOURNAL_FREE_END_BREAK_MAX_MM - THRUST_EDGE_BREAK_MAX - SHAFT_END_PLAY[1],
)
if JOURNAL_SUPPORT_SPAN_MIN_MM <= 0.0:
    raise AssertionError("post/shaft pair has no guaranteed cylindrical bearing span")


# The setback proof (user ruling 2026-09-28).  The step and its root fillet
# must stay south of T024's south face -- T030's north face -- with the stack
# pushed onto the collar at its shortest: the step at the north end of its
# printed limits, the fillet's R.004 +.000 run along land 2, the stack's own
# shortfall up to that face (dt_cone_gear_stack.face_band) and the fleet's
# MARGIN_SPARE.  The step and the stack share the collar's tip-side face
# (round 6), so the collar web no longer stands between them; its printed
# short limit is still charged, as a second spare, so the re-datum loosens no
# proof (FoDtFab4's condition).  T024 sits one feeler further north still;
# that only adds air.
if abs(SECTION_ENDS[1] - FRONT_STUB - seat_step_station(SEAT_STEP_GEAR)) > 1e-9:
    raise AssertionError("Sec1End is not one setback behind T030's north face")
SEAT_STEP_BUDGET: dict[str, float] = {
    "step band": printed_length_deviations("Sec1End")[1],
    "fillet": FILLET_RADIUS + printed_length_deviations("ShoulderR")[1],
    "collar band": -printed_length_deviations("CollarWidth")[0],
    "stack": -face_band(SEAT_STEP_GEAR, "north")[1],
    "spare": MARGIN_SPARE,
}
SEAT_STEP_BUDGET["margin"] = SEAT_STEP_SETBACK - sum(SEAT_STEP_BUDGET.values())
if SEAT_STEP_BUDGET["margin"] < 0.0:
    raise AssertionError(
        f"Sec1End: the step and its root reach T024 at print-worst {SEAT_STEP_BUDGET}"
    )


def _limits(nominal: float, band: tuple[float, float]) -> tuple[float, float]:
    """(minimum, maximum) of ``nominal`` under (upper, lower) deviations."""
    return nominal + min(band), nominal + max(band)


# The recess proof (cone_tip_cluster.TIP_END_RECESS_MM).  The shaft's end must
# stand inside T024's bore at every limit, so T018 always butts T024's north
# face, and short of T024's south face, so T024 is bonded on land 2.  T024's
# north face deviates from its model station as T030's north face does with
# the stack pushed onto the collar (dt_cone_gear_stack.face_band), plus the
# feeler set's STACK_FEELER_BAND either way and T024's own face width band;
# the end deviates by Sec2End's printed limits.  Both run from the collar's
# tip-side face, so the collar web does not enter.
_T030_NORTH_BAND = face_band(SEAT_STEP_GEAR, "north")
T024_NORTH_FACE_DEVIATION_MM = (
    _T030_NORTH_BAND[1] - STACK_FEELER_BAND + CONE_GEAR_FACE_WIDTH_BAND[1],
    _T030_NORTH_BAND[0] + STACK_FEELER_BAND + CONE_GEAR_FACE_WIDTH_BAND[0],
)
_END_DEVIATION = printed_length_deviations("Sec2End")
TIP_END_RECESS_LIMITS_MM = (
    cone_tip_cluster.TIP_END_RECESS_MM
    + T024_NORTH_FACE_DEVIATION_MM[0]
    - _END_DEVIATION[1],
    cone_tip_cluster.TIP_END_RECESS_MM
    + T024_NORTH_FACE_DEVIATION_MM[1]
    - _END_DEVIATION[0],
)
_FACE_WIDTH_LIMITS = _limits(CONE_GEAR_FACE_WIDTH, CONE_GEAR_FACE_WIDTH_BAND)
# T024's bonded length on land 2 at its least.
T024_BOND_LENGTH_MIN_MM = _FACE_WIDTH_LIMITS[0] - TIP_END_RECESS_LIMITS_MM[1]
if TIP_END_RECESS_LIMITS_MM[0] <= 0.0 or T024_BOND_LENGTH_MIN_MM <= 0.0:
    raise AssertionError(
        f"the shaft end leaves T024's bore: recess {TIP_END_RECESS_LIMITS_MM}, "
        f"bond length {T024_BOND_LENGTH_MIN_MM:.4f} mm"
    )

# The spigot proof.  T006's spigot runs SPIGOT_LENGTH_MM south of T006's
# leaves, through T012 and T018 (two face widths, butted on T024's north
# face) into the socket.  Over the recess range above, with the spigot (.XX,
# on the T006 sheet in this unit) and the socket depth (.XX) at their limits
# and both face widths at theirs, the spigot keeps air at the socket floor
# and at least SPIGOT_SOCKET_ENGAGEMENT_MIN_MM in the socket.
_SPIGOT_LIMITS = _limits(
    cone_tip_cluster.SPIGOT_LENGTH_MM,
    printed_deviations(cone_tip_cluster.SPIGOT_LENGTH_MM, 2, unit=UNIT),
)
_SOCKET_DEPTH_LIMITS = _limits(SOCKET_DEPTH, printed_length_deviations("SocketDepth"))
SPIGOT_FLOOR_AIR_MIN_MM = (
    TIP_END_RECESS_LIMITS_MM[0]
    + 2.0 * _FACE_WIDTH_LIMITS[0]
    - _SPIGOT_LIMITS[1]
    + _SOCKET_DEPTH_LIMITS[0]
)
SPIGOT_ENGAGEMENT_MIN_MM = (
    _SPIGOT_LIMITS[0] - 2.0 * _FACE_WIDTH_LIMITS[1] - TIP_END_RECESS_LIMITS_MM[1]
)
if (
    SPIGOT_FLOOR_AIR_MIN_MM <= 0.0
    or SPIGOT_ENGAGEMENT_MIN_MM < cone_tip_cluster.SPIGOT_SOCKET_ENGAGEMENT_MIN_MM
):
    raise AssertionError(
        f"T006's spigot: floor air {SPIGOT_FLOOR_AIR_MIN_MM:.4f} mm, engagement "
        f"{SPIGOT_ENGAGEMENT_MIN_MM:.4f} mm (needs "
        f"{cone_tip_cluster.SPIGOT_SOCKET_ENGAGEMENT_MIN_MM:.4f})"
    )

# The socket's wall (drawing-guidelines.md rule 17's .080 target): land 2 at
# its least printed diameter round the socket at its largest.
SOCKET_WALL_MIN_MM = (
    land_finished_dia_limits_mm(SECTION_DIAS[2], 2)[0]
    - _limits(SOCKET_DIA, SOCKET_DIA_BAND)[1]
) / 2.0
if SOCKET_WALL_MIN_MM < WALL_TARGET_MM:
    raise AssertionError(
        f"socket wall {SOCKET_WALL_MIN_MM:.4f} mm under rule 17's .080"
    )

# The key's north end at the far printed limits of the keyseat end's .XX
# location and the key's .XX length stays south of T024 (gear 16), bonded on
# land 2 one feeler north of T030: the key sits between the keyseat's end and
# T024.
KEY_NORTH_MARGIN_MM = (
    FRONT_STUB
    + gear_faces(16)[0]
    - (
        COLLAR_END_STATION
        + cone_land_key.KEY_END_SET_MM
        + printed_length_deviations("Sec1KeyseatEndSet")[1]
        + cone_land_key.KEY_LENGTH_MM
        + printed_band_mm(cone_land_key.KEY_LENGTH_PLACES, unit=UNIT)
    )
)
if KEY_NORTH_MARGIN_MM <= 0.0:
    raise AssertionError(
        f"the key reaches T024 at print-worst ({KEY_NORTH_MARGIN_MM} mm)"
    )

# The keyseat's end at its printed low limit, cut by the widest end mill
# (the keyseat's upper width), keeps KEYSEAT_END_COLLAR_MARGIN_MM of the
# collar's tip-side face, the 64T's seat and the stack's origin, uncut.
KEYSEAT_END_COLLAR_MARGIN_MM = 0.1
KEYSEAT_END_COLLAR_CLEARANCE_MIN_MM = (
    cone_land_key.KEY_END_SET_MM
    + printed_length_deviations("Sec1KeyseatEndSet")[0]
    - cone_land_key.limits(
        cone_land_key.KEYSEAT_WIDTH_MM, cone_land_key.KEYSEAT_WIDTH_BAND
    )[1]
    / 2.0
)
if KEYSEAT_END_COLLAR_CLEARANCE_MIN_MM < KEYSEAT_END_COLLAR_MARGIN_MM:
    raise AssertionError(
        "the keyseat's end mill reaches the collar's 64T seat at print-worst "
        f"({KEYSEAT_END_COLLAR_CLEARANCE_MIN_MM:.4f} mm clear)"
    )
