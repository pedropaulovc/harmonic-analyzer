r"""Pure-data dimensional contract for the rocker pivot bracket (MHA-CH-008).

PURE DATA, no SolidWorks/COM imports: ``build_ch_pivot_bracket`` builds from it,
and ``rocker_bank_layout`` / the channel assembly read the ear and foot from
it without importing a COM build script.

Part frame: seat face at y = 0, origin under the bore on the seat plane. The
foot runs FOOT_Z0 along +Z (the ear end at -EAR_T/2, the free end outboard
once placed, toward the support's end face); the ear is EAR_W wide (X) by
EAR_T thick (Z), centred on the origin, rising from the foot top and ARCHED
with radius EAR_W/2 over the O BORE_DIA cross-bore, its apex EAR_TOP_Y over
the seat (the arch's centre ARCH_LIFT above the bore axis). The ear is as
wide as the foot, so their sides are one flat each side. Each ear's inner
face bears on a MHA-VN-070 thrust washer: hub 19's at the north ear (the
bank's datum), the preload spring's at the south one (``rocker_bank_layout``).

One MHA-VN-034 #4-40 cup-point set screw drops through the arch apex, on the
ear's mid-plane, into the bore and onto the pivot shaft's flat (user,
2026-10-10). EAR_T is 8.0 (was 6.0) so the tap keeps its walls to both ear
faces; the apex stands 35.00 over the seat, 9.80 over the bore (was the R8
half-round's 8.00), so the tap keeps 1.5D of full thread with both heights
at the title block's band (#1371).

The foot's end and its one hold-down hole must suit both ends of the support,
so ``ch_pivot_bracket_sides`` derives them from the bank layout (which
imports this module for the ear, so the derivation cannot live here) and
checks them with the ligament functions below.
"""

from __future__ import annotations

from math import sqrt

from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm

FOOT_W = 16.0  # X, across the support apex (16.933 wide; 0.47 margin each side)
FOOT_H = 6.0
EAR_W = FOOT_W  # X: the ear's sides run flush with the foot's
EAR_T = 8.0  # Z; the ear's Z band is the bore's (z -4..+4)
FOOT_Z0 = -EAR_T / 2.0  # foot starts at the ear's inboard face
BORE_H = 25.2  # shaft axis above the seat: the rocker pivot stays at machine
# y 253.8 on the 228.6 support apex
BORE_DIA = 6.5  # O6.35 shaft, 0.15 diametral clearance
EAR_ARCH_R = EAR_W / 2.0  # the ear's top is a half-round, tangent to its sides
# Every height runs from the seat (drawing-guidelines.md rule 10, #1371 r1
# review): the bore axis and the arch apex, each at the title block's .XX.
# The apex tap's wall over the bore is their difference, so it loses both
# bands; the R8 half-round about the bore left the tap 1.08D of full thread,
# and lifting the arch's centre 1.80 over the bore gives it 1.5D at that
# worst case (owner policy: geometry, not a ruling). The arch stays the ear's
# own half-round, its sides run 1.80 further up.
EAR_TOP_Y = 35.0  # the overall height, seat to apex
HEIGHT_BAND = 0.508  # title-block .XX: the overall and the bore heights
APEX_ABOVE_BORE = EAR_TOP_Y - BORE_H  # 9.80
ARCH_LIFT = APEX_ABOVE_BORE - EAR_ARCH_R  # 1.80: the arch centre over the bore
BORE_LIGAMENT = APEX_ABOVE_BORE - BORE_DIA / 2.0  # 6.55: drawing-guidelines.md rule 17 (walls and webs) web over the bore
# The MHA-VN-071 hold-down passes here: #8 close clearance, the hole MHA-DT-002
# gives its #8-32 fillister of the same head. The old #19 (0.025 radial over the thread major)
# caught the screw's under-head junction fillet on its mouth (r743-3C).
HOLD_DOWN_HOLE_SPEC = HoleSpec("clearance", "#8", fit="close")
HOLE_DIA = blind_cut_dia_mm(HOLD_DOWN_HOLE_SPEC)

# One hold-down hole per bracket, on x = 0 in the foot's free run (from the
# ear's outboard face to the foot end), its station given from the ear's
# INBOARD face -- the face fit-up sets (the north datum, the south blade-set
# face), so the hole lands on the support's transferred seat without the foot
# length's band (user, 2026-10-10, option ii). Worst case is each term at its
# OWN band (Codex #936 PRRT_kwDOPHDy386mV3AN). The foot length and the hole
# station both ride the title block's .XX: the foot is long enough to keep the
# 2.0 wall to its end, the screw head clear of the ear and the support seat's
# 2.0 end wall at those bands (user ruling 2026-10-14, #954 machinist review:
# fix the wall with geometry, not a band; #1371 review: the station's +/-0.10
# went the same way; ``ch_pivot_bracket_sides`` sizes the support, and so the
# foot, for it). The ear thickness keeps its +/-0.10 for the thrust faces and
# the tap's walls. Across the foot its sides stay at .XX (the band
# rocker_bracket_seat_layout carries this foot at) and the hole's centring on
# x = 0 at .XX; a drilled hole grows by the title block's +0.10/0.
# build_ch_pivot_bracket carries the +/-0.10 band on the model's own
# dimension.
FOOT_LEN_BAND = 0.508  # title-block .XX
EAR_T_BAND = 0.10
STATION_BAND = 0.508  # title-block .XX
EDGE_BAND = 0.508  # title-block .XX: the foot's sides
HOLE_X_BAND = 0.508  # title-block .XX: the hole's centring across the foot
DRILL_GROWTH = 0.10  # title-block drilled hole, +0.10/0 on the diameter
LIGAMENT_FLOOR = 1.5
LIGAMENT_TARGET = 2.0


def hole_ligaments_min(hole_z: float, foot_z1: float) -> dict[str, float]:
    """Worst-case ligaments round a hold-down hole at station hole_z.

    The foot end loses the station's band and the foot length's (both run
    from the ear's inboard face), plus half the drill growth. The ear face is
    no free edge (the foot runs on under the ear), so the hole's run-side
    limit is the screw head's clearance to it, not a ligament: see
    ``head_to_ear_face_min``.
    """
    return {
        "foot end": foot_z1
        - hole_z
        - HOLE_DIA / 2.0
        - (FOOT_LEN_BAND + STATION_BAND + DRILL_GROWTH / 2.0),
        "foot side": (FOOT_W - HOLE_DIA) / 2.0
        - (EDGE_BAND + HOLE_X_BAND + DRILL_GROWTH / 2.0),
    }


def head_to_ear_face_min(hole_z: float, head_dia: float) -> float:
    """Worst-case gap from the hold-down screw's head to the ear's outboard face.

    The station and the ear thickness both run from the ear's inboard face,
    so the outboard face closes on the head by those two bands.
    """
    return hole_z - head_dia / 2.0 - EAR_T / 2.0 - (EAR_T_BAND + STATION_BAND)


if BORE_LIGAMENT < LIGAMENT_TARGET:
    raise AssertionError("ear arch leaves less than the 2.0 web over the bore")

# The arch's radius rides the title block's .XX (the two heights' band is
# HEIGHT_BAND); the bore grows by the drilled hole's +0.10/0.
ARCH_R_BAND = 0.508
BORE_RADIUS_MAX = (BORE_DIA + DRILL_GROWTH) / 2.0

# --- apex set screw (user, 2026-10-10) ----------------------------------------
# One MHA-VN-034 #4-40 x 1/4 cup-point set screw drops radially through the
# arch apex on the ear's mid-plane, onto the pivot shaft's flat. The tap runs
# THROUGH to the bore and stops there (through-next), the arbor pedestal's
# idiom (dt_arbor_pedestal_spec), never into the ear below the bore.
SET_SCREW_THREAD = "#4-40"
SET_SCREW_PITCH = 25.4 / 40.0
SET_SCREW_HOLE_SPEC = HoleSpec("tapped", SET_SCREW_THREAD, end="through_next")
SET_SCREW_MAJOR_DIA = THREAD_MAJOR_MM[SET_SCREW_THREAD]
# The cup end the flat must take: the vendor's 45 deg x one-pitch point
# chamfer off the major (vn_arbor_set_screw_spec.POINT_LENGTH).
SET_SCREW_POINT_DIA = SET_SCREW_MAJOR_DIA - 2.0 * SET_SCREW_PITCH  # 1.575
# The tap sits on the ear's mid-plane, held +/-0.10 from the inboard face;
# that face's mid-plane is itself half the thickness band off, so the tap
# may stand this far off nominal along the shaft.
SET_SCREW_STATION_BAND = 0.10
SET_SCREW_OFF_MID_MAX = SET_SCREW_STATION_BAND + EAR_T_BAND / 2.0
# The thread's wall to each ear face at the worst case (target 2.0): the
# inboard face at the tap's far limit, the outboard face also losing the
# thickness band.
SET_SCREW_WALLS_MIN = {
    "inboard face": EAR_T / 2.0 - SET_SCREW_OFF_MID_MAX - SET_SCREW_MAJOR_DIA / 2.0,
    "outboard face": EAR_T / 2.0
    - EAR_T_BAND
    - SET_SCREW_OFF_MID_MAX
    - SET_SCREW_MAJOR_DIA / 2.0,
}  # 2.43, 2.33
if min(SET_SCREW_WALLS_MIN.values()) < LIGAMENT_TARGET:
    raise AssertionError(
        f"the apex tap leaves {SET_SCREW_WALLS_MIN} to the ear faces at worst"
        f" case, under the {LIGAMENT_TARGET} wall"
    )


def _sag(radius: float) -> float:
    """A circle's sag across the thread's major diameter."""
    return radius - sqrt(radius**2 - (SET_SCREW_MAJOR_DIA / 2.0) ** 2)


# Full thread in the arch wall at the worst case (dt_arbor_pedestal_spec's
# terms): the thread is full only where its major circle lies wholly in
# metal, so the arch's and the bore's sags across the hole are lost, and so
# is the one-pitch entry chamfer. The apex sits at its lowest over the bore
# (the overall height low, the bore high), the arch at its smallest radius
# (its largest sag).
SET_SCREW_WALL_TERMS = {
    "apex over the bore at its minimum": APEX_ABOVE_BORE - 2.0 * HEIGHT_BAND,
    "bore radius at its maximum": -BORE_RADIUS_MAX,
    "arch sag across the thread": -_sag(EAR_ARCH_R - ARCH_R_BAND),
    "bore sag across the thread": -_sag(BORE_RADIUS_MAX),
    "one-pitch entry chamfer": -SET_SCREW_PITCH,
}
SET_SCREW_FULL_THREAD_MIN = sum(SET_SCREW_WALL_TERMS.values())  # 4.39
SET_SCREW_ENGAGEMENT_D = SET_SCREW_FULL_THREAD_MIN / SET_SCREW_MAJOR_DIA  # 1.543D
SET_SCREW_ENGAGEMENT_PRINTED = int(SET_SCREW_ENGAGEMENT_D * 100.0) / 100.0
SET_SCREW_MIN_ENGAGEMENT_D = 1.5  # drawing-guidelines.md rule 18 (thread engagement)
if SET_SCREW_ENGAGEMENT_D < SET_SCREW_MIN_ENGAGEMENT_D:
    raise AssertionError(
        f"MHA-CH-008 apex set screw keeps {SET_SCREW_ENGAGEMENT_D:.2f}D of full"
        f" thread, under {SET_SCREW_MIN_ENGAGEMENT_D}D"
    )
# The engagement as a plain fact. The bracket sheet no longer prints it (it
# meets rule 18); the channel assembly's set-screw step still quotes it until
# that sheet's own pass drops the quote.
SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT = (
    f"#4-40 ENGAGEMENT {SET_SCREW_FULL_THREAD_MIN:.2f} MIN "
    f"({SET_SCREW_ENGAGEMENT_PRINTED:.2f}D)."
)
