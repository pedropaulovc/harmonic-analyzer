r"""Pure-data dimensional contract shared by the cone gear shaft and drawing."""

from __future__ import annotations

import math

import cone_line
import dt_cone_pivot_post_spec
import dt_cone_tip_block_spec

from _fit_deviations import deviations
from _gtol_cylinder import CylinderFace
from _inch_wall_limits import WALL_FLOOR_MM
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm, printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl

from dt_cone_gear_spec import FACE_WIDTH as CONE_GEAR_FACE_WIDTH, SEAT_PITCH, outside_dia_mm
from dt_cone_gear_stack import PITCH_LOCKSTEP_TOLERANCE, face_band
from _cone_axis_constants import GEAR_AXIS_SHIFT
from dt_cone_pivot_post_spec import JOURNAL_BORE_BAND as POST_JOURNAL_BORE_BAND
from cone_shaft_land_bands import (  # noqa: F401  re-exported for the shaft build
    FLAT_AF_BAND,
    GEAR_SEAT_BAND,
    LAND_DIA_PLACES,
    LAND_AF_PLACES,
    RUNNING_DIA_BAND,
    SECTION_CONE_GEAR_TEETH,
    SECTION_DIA_BANDS,
    SECTION_FLAT_AF,
    TERMINAL_DIA_IN,
    TERMINAL_DIA_MM,
    TERMINAL_DIA_PLACES,
    TERMINAL_FLAT_EDGE_BREAK_MAX,
    UNIT,
)
from cone_stack_end_play import COLLAR_FEELER, MARGIN_SPARE, SHAFT_END_PLAY
from dt_vn_cone_tip_collar_spec import WIDTH as TIP_COLLAR_WIDTH
from _mcmaster_94025a164 import CUP_DEPTH
from dt_crank_drive_gear_spec import CENTRE_SHIFT_NORTH as GEAR64_CENTRE_SHIFT_NORTH
from dt_crank_drive_gear_spec import FACE_WIDTH as GEAR64_FACE_WIDTH
from dt_crank_drive_gear_spec import LAYOUT_FACE_WIDTH as GEAR64_LAYOUT_FACE_WIDTH
from dt_crank_drive_gear_spec import SOUTH_FACE_SHIFT_NORTH as GEAR64_SOUTH_FACE_SHIFT_NORTH
from dt_crank_drive_gear_spec import LAYOUT_CENTRE_STATION as GEAR64_LAYOUT_CENTRE_STATION
from gear_seat_fit import FLAT_AF_CLEARANCE, flat_bore_af_band, seat_bore_band


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

# Axial capture (#914, user ruling 2026-09-25).  The tip adjuster pushes the
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
# The terminal flat's two long torque corners stay sharp in the model; their
# break limit is a drawing requirement, printed above the terminal across-flat
# (draw_dt_cone_gear_shaft).  cone_shaft_land_bands derives the number.  One
# line: SolidWorks stores an above callout's line break but prints none of it
# (run 20261010T071427837Z).  No process word: the limit is the requirement
# (machinist review r1).
TORQUE_CORNER_CALLOUT = f"CORNERS {inch_text(TERMINAL_FLAT_EDGE_BREAK_MAX, 3)} MAX"


def _gear(teeth: int) -> str:
    return f"T{teeth:03d}"


# Each tight band names its mate and fit route (drawing-guidelines.md rule
# 4).  The journal's .0008 band is under the turned-diameter row, so it is a
# matched running fit to the MHA-DT-05 bore, the form the reviewer accepted
# on MHA-DT-19's pivot shaft, its clearance the printed limits'
# (JOURNAL_DIAMETRAL_CLEARANCE_MM).  Every gear land and its flat slide in
# the bores of the gears it carries; those mates (MHA-DT-03, MHA-DT-07 on
# land 1, MHA-DT-VN-54 on the terminal land) and the flats' matched fit are
# flag note LAND_NOTE, linked from each land's diameter and across-flat: the
# stepped tip's texts climb over each other and have no room for the names.
LAND_NOTE = 1
LAND_FLAG = f"SEE NOTE {LAND_NOTE}"
JOURNAL_FIT_CALLOUT = (
    "RUNNING FIT, MATCHED TO MHA-DT-05\n"
    f"BORE (CLEARANCE {inch_text(JOURNAL_DIAMETRAL_CLEARANCE_MM[0], 4)}"
    f"-{inch_text(JOURNAL_DIAMETRAL_CLEARANCE_MM[1], 4)})"
)
SEAT_MATE_CALLOUTS = {
    "Sec0Dia": JOURNAL_FIT_CALLOUT,
    "Sec1Dia": LAND_FLAG,
}
# The terminal land's band also carries the MHA-DT-VN-54 collar, whose bore
# clearance is derived from this diameter (dt_vn_cone_tip_collar_spec; codex
# review of #1644 at fd9aa2df7); LAND_NOTE names it with D-D's gears.
TERMINAL_LAND = 4
SEAT_MATE_SUFFIXES = {f"Sec{land}Dia": f" {LAND_FLAG}" for land in (2, 3, TERMINAL_LAND)}
# An across-flat line is centred on its section; with "SEE" B-B's would
# overrun the sheet border by 0.6 mm, so the flats carry the bare flag.
FLAT_MATE_SUFFIXES = {f"Sec{land}AF": f" NOTE {LAND_NOTE}" for land in (1, 2, 3, 4)}
# Every D-bore's across-flat band is gear_seat_fit.flat_bore_af_band of the
# land's (the 64T's too), so one clearance serves all four flats.
FLAT_AF_CLEARANCE_TEXT = (
    f"{inch_text(FLAT_AF_CLEARANCE[0], 4)}-{inch_text(FLAT_AF_CLEARANCE[1], 4)}"
)

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

# The tip end: the custom MHA-DT-VN-54 stack collar is set one COLLAR_FEELER
# north of T006's face and locked on the
# Sec4 D-flat.  The MHA-DT-21 tip block is a straight prism fixed by its
# hold-down: its north face stands TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET south of
# the pivot, itself PIVOT_FROM_T006_NORTH_FACE north of T006's face
# (cone_line's constants).  drawing-guidelines.md rule 18 (thread engagement) E11's #10-32 McMaster 94025A164 cup
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
TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET = dt_cone_tip_block_spec.TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET
TIP_BLOCK_NORTH_FACE_STATION = dt_cone_tip_block_spec.TIP_BLOCK_NORTH_FACE
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
# keeps that station and substitutes the authoritative .031 in terminal
# diameter, shared by T012, T006 and the stack collar.
TIP_LAND_START_STATION = seat_step_station(17)
TIP_STUB_START_STATION = TIP_LAND_START_STATION
TIP_STUB_LENGTH = T006_TIP_STATION - TIP_STUB_START_STATION

# (diameter in inches, section end station in mm from the front stub end).
# Intermediate seats keep the retained sizes and fit classes. The terminal
# size lives in cone_shaft_land_bands and the gear family checks its web
# against the current cutter-owned printed MIN floors, not an old snapshot.
# Tailstock support remains required for the now more slender terminal land.
# Diameters decrease toward the tip for tip-first assembly.  The stations
# are the gear stack's (closures): only the journal's end is a fabricated
# length, snapped above.
SECTION_DIAS: tuple[float, ...] = (
    JOURNAL_DIA,  # integral v2-post bearing journal, .4825
    9.525,  # 3/8: 64T + T120..T030 seats
    6.35,  # 1/4: T024 seat
    3.175,  # 1/8: T018 seat
    TERMINAL_DIA_MM,  # .031: T012/T006, collar, tip
)
SECTION_ENDS: tuple[float, ...] = (
    JOURNAL_END,
    FRONT_STUB + seat_step_station(15),
    FRONT_STUB + seat_step_station(16),
    FRONT_STUB + TIP_LAND_START_STATION,
    FRONT_STUB + T006_TIP_STATION,
)
SECTIONS: tuple[tuple[float, float], ...] = tuple(
    (dia / MM_PER_IN, end) for dia, end in zip(SECTION_DIAS, SECTION_ENDS, strict=True)
)
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
# D-bores (MHA-DT-03, MHA-DT-07) slide straight on.  The terminal land's flat runs
# out THROUGH THE TIP (user ruling 2026-09-28): T012 and T006 slide on over
# it and MHA-DT-VN-54 is a thrust spacer riding the D, so the end face is a D too.
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
# thrust face, the face the post bears on.  drawing-guidelines.md rule 14 (keep text off the part) allows one
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
# SEAT_STEP_SETBACK behind the smaller gear's south face, so the root's
# radius must not reach the smaller gear: the fillet stands .004 proud of the
# smaller land -- more than that gear's radial clearance on either the round
# or the flat -- so its axial run is booked in the setback (the proof below).
# R.004 is the standard tool nose radius.  Modelled as geometry, round root
# and flat root alike, and dimensioned once, not written as a process note.
FILLET_RADIUS = 0.1016  # .004
# The setback books the root's run at its printed maximum, so the radius
# prints as the single limit R.004 MAX (swTolMAX prints the model value, then
# MAX): the title block's +-.005 would let a .009 root reach the smaller gear
# (Codjiflo P2 on #2107).  Any root from sharp up to .004 is good.  The
# stacked +.000/-.002 band this replaced named no mate at its callout and had
# no room to (machinist review of the final7 render, 20261102T152513202Z).
FILLET_R_BAND = (0.0, -FILLET_RADIUS)  # (upper, lower): any root up to the MAX
FILLET_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.004 MAX"
# Three identical land-step roots (the collar's roots stay sharp,
# build_dt_cone_gear_shaft), one fillet feature, one radius dimension.
FILLET_CALLOUT = "3X"

# Surface texture, on the one land that runs: the .4825 journal turns in
# the pivot post bore.  Every other land only carries parts locked to the
# shaft -- the gears slide on and are driven by the flats, the MHA-DT-VN-54
# collar is screwed to the terminal flat -- and the tip bears on the
# adjuster's cup with its end, not its round, so they are left to the
# title-block process row (drawing-guidelines.md rule 6; machinist review
# r5, 20261018T080102803Z, which found the tip land's Ra 1.6 unexplained).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_journal", MACHINED_UM, CylinderFace(JOURNAL_DIA), display_unit=UNIT
    ),
)

# The sheet's numbered flag notes, four lines (drawing-guidelines.md rule 7:
# few, flagged, never a method).  Note LAND_NOTE is linked from every land's
# diameter and across-flat: it names each land's mates once by drawing number
# (rule 4; sections A-A to D-D cut lands 1 to 4), and gives the flats' .0004
# bands, under the milled-width row, their fit route: each flat is milled
# matched to its gears' measured D-bores, with the acceptance and the
# printed limits' across-flat clearance as REF.  The flats' common clock is
# the aligned sections' and the title block's angle (error_budget.yaml books
# it per land as cone_land_clock).  Note STACK_NOTE names, once, the stack the
# three-place lengths set (rule 4): each step stands SEAT_STEP_SETBACK behind
# the smaller gear's south face (the proof below) and the collar web is the
# MHA-DT-07 station and the stack's origin.  The tailstock line is the one
# process word, by user ruling (U40, 2026-09-23): the slender terminal land
# cannot be turned unsupported, so the support IS the requirement (exception
# RV-02 in cad/config/parts/dt-cone-gear-shaft.yaml).  Lines stay short: the
# note block starts 20 mm in and the title block begins at 216 mm.
STACK_NOTE = 2
TAILSTOCK_NOTE = 3
# The printed step lengths (from the collar's thrust face, the journal end)
# and the collar web, as their dimensions print them.
STACK_LENGTHS_TEXT = ", ".join(
    inch_text(SECTION_ENDS[land] - SECTION_ENDS[0], 3) for land in (1, 2, 3)
) + f" AND {inch_text(COLLAR_THICKNESS, 3)}"
DRAWING_NOTES = "\n".join(
    (
        f"{LAND_NOTE}. SLIDING FIT IN MHA-DT-03, A-A ALSO MHA-DT-07, D-D ALSO MHA-DT-VN-54;",
        "   MILL FLATS TO MEASURED D-BORES: NO ROCK "
        f"(CLEARANCE {FLAT_AF_CLEARANCE_TEXT} REF).",
        f"{STACK_NOTE}. {STACK_LENGTHS_TEXT} SET THE MHA-DT-07 AND MHA-DT-03 STACK.",
        f"{TAILSTOCK_NOTE}. TURN THE TIP LAND WITH TAILSTOCK SUPPORT.",
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
    "ShoulderFillets": {"ShoulderR"},
    "CollarProfile": {"CollarDia"},
    "Collar": {"CollarWidth"},
}

# Display precision is a MODEL property (drawing-simplicity-policy.md `How the repository implements the guidelines`):
# the part build stamps it and the sheet only reads it back.  Decimal inch
# (#290).
#
# Diameters and across-flats: four places.  Each carries its named band
# (SECTION_DIA_BANDS, FLAT_AF_BAND), so their places are only the number's
# spelling.
#
# Land steps Sec1End..Sec3End: three places, which is the title-block .XXX
# general grade (+-.005) and no explicit band.  This is a location
# requirement, not a spelling: each step sits SEAT_STEP_SETBACK behind the
# smaller gear's south face, and the proof below books the step's printed
# limit with the collar's, the stack's and the fillet's in that 1.0 mm; the
# .XX grade (+-.01) alone would take half of it.
#
# Tip station Sec4End (collar face to the tip): two places, the title
# block's .XX grade (+-.01), by user ruling 2026-09-29.  The tip block is
# fixed by its hold-down, so this band lands on the adjuster's embed;
# build_dt_drive_train_assembly closes that stack by the block's depth and the
# 1.0D adjuster engagement instead of a tighter length.  Journal length
# Sec0End (collar face back to the front stub): two places, the .XX grade,
# since the journal's guaranteed bearing span below reads it (never .X).
# Step radius: three places; nothing depends on it beyond the setback proof.
#
# Collar (#914): the diameter is the bar's as supplied (STOCK_DIA), so it
# prints as the 5/8 fraction reference, the bar's own size; the web prints
# three places because it is the 64T's station toward MHA-DT-05
# (crank_boss_rim.GEAR64_STATION_TOWARD_POST) and the gear stack's origin.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "Sec0Profile": {"Sec0Dia": LAND_DIA_PLACES[0]},
    "Sec1Profile": {"Sec1Dia": LAND_DIA_PLACES[1]},
    "Sec2Profile": {"Sec2Dia": LAND_DIA_PLACES[2]},
    "Sec3Profile": {"Sec3Dia": LAND_DIA_PLACES[3]},
    "Sec4Profile": {"Sec4Dia": LAND_DIA_PLACES[4]},
    "Sec0": {"Sec0End": 2},
    "Sec1": {"Sec1End": 3},
    "Sec2": {"Sec2End": 3},
    "Sec3": {"Sec3End": 3},
    "Sec4": {"Sec4End": 2},
    "Sec1FlatProfile": {"Sec1AF": LAND_AF_PLACES[1]},
    "Sec2FlatProfile": {"Sec2AF": LAND_AF_PLACES[2]},
    "Sec3FlatProfile": {"Sec3AF": LAND_AF_PLACES[3]},
    "Sec4FlatProfile": {"Sec4AF": LAND_AF_PLACES[4]},
    "ShoulderFillets": {"ShoulderR": 3},
    "CollarProfile": {"CollarDia": 3},
    "Collar": {"CollarWidth": 3},
}
# The collar's stock reference prints as the bar's fraction.
COLLAR_DIA_FRACTION_DENOMINATOR = 8
# The front-to-tip overall (#917 R5 (a)) is the sheet's one reference
# dimension, the read-only sum of the journal and the tip station: two
# places, the grade of the lengths it sums.
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
}


def printed_length_deviations(name: str) -> tuple[float, float]:
    """(lower, upper) mm about the model of a marked length's printed limits:
    the inch value the sheet prints, with its own band (the step roots) or the
    title block's."""
    if name == "ShoulderR":
        return printed_deviations(
            FILLET_RADIUS, DRAWING_PRECISION_BY_NAME[name], deviations(FILLET_R_BAND), unit=UNIT
        )
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


# The setback proof (user ruling 2026-09-28).  Each step and its root fillet
# must stay south of the smaller gear's south face -- the larger gear's north
# face -- with the stack pushed onto the collar at its shortest: the step at
# the north end of its printed limits, the fillet's R.004 +.000 run
# along the smaller land, the collar web's printed short limit (the stack
# stands on the collar's north face, the steps are measured from its south
# face), the stack's own shortfall up to that face
# (dt_cone_gear_stack.face_band) and the fleet's MARGIN_SPARE.  The fillet
# runs the same .004 along the flat's root
# as along the round's, so the one budget covers the smaller gear's round
# bore and its flat alike.  In service the stack only floats north, off the
# step.
SEAT_STEP_BUDGET: dict[str, dict[str, float]] = {}
for _name, _j, _end in zip(("Sec1End", "Sec2End", "Sec3End"), SEAT_STEP_GEARS, SECTION_ENDS[1:4]):
    if abs(_end - FRONT_STUB - seat_step_station(_j)) > 1e-9:
        raise AssertionError(f"{_name} is not one setback behind gear {_j}'s north face")
    _terms = {
        "step band": printed_length_deviations(_name)[1],
        "fillet": FILLET_RADIUS + printed_length_deviations("ShoulderR")[1],
        "collar band": -printed_length_deviations("CollarWidth")[0],
        "stack": -face_band(_j, "north")[1],
        "spare": MARGIN_SPARE,
    }
    _terms["margin"] = SEAT_STEP_SETBACK - sum(_terms.values())
    SEAT_STEP_BUDGET[_name] = _terms
    if _terms["margin"] < 0.0:
        raise AssertionError(
            f"{_name}: the step and its root reach the smaller gear at print-worst {_terms}"
        )
