r"""Pure-data dimensional contract for the rocker pivot bracket (MHA-CH-008).

PURE DATA, no SolidWorks/COM imports: ``build_ch_pivot_bracket`` builds from it,
and ``rocker_bank_layout`` / the channel assembly read the ear and foot from
it without importing a COM build script.

Part frame: seat face at y = 0, origin under the bore on the seat plane. The
foot runs FOOT_Z0 along +Z (the ear end at -EAR_T/2, the free end outboard
once placed, flush with the support's end face); the ear is EAR_W wide (X) by
EAR_T thick (Z), centred on the origin, rising from the foot top and ARCHED
with radius EAR_W/2 about the O BORE_DIA cross-bore. The ear is as wide as
the foot, so their sides are one flat each side. Each ear's inner face bears
on a MHA-CH-009 thrust washer: hub 19's at the north ear (the bank's datum),
the preload spring's at the south one (``rocker_bank_layout``).

One MHA-VN-034 #4-40 cup-point set screw drops through the arch apex, on the
ear's mid-plane, into the bore and onto the pivot shaft's flat (user,
2026-10-10). EAR_T is 8.0 (was 6.0) so the tap keeps its walls to both ear
faces.

The foot's end and its one hold-down hole depend on which end of the support
the bracket sits at, so they are per configuration: ``ch_pivot_bracket_sides``
derives them from the bank layout (which imports this module for the ear, so
the derivation cannot live here) and checks them with the ligament functions
below.
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
EAR_ARCH_R = EAR_W / 2.0  # the ear's top is a half-round about the bore
EAR_TOP_Y = BORE_H + EAR_ARCH_R  # 33.2
BORE_LIGAMENT = EAR_ARCH_R - BORE_DIA / 2.0  # 4.75: rule 12 web over the bore
# The MHA-VN-032 hold-down passes here: #8 close clearance, the hole MHA-DT-002
# gives the same screw. The old #19 (0.025 radial over the thread major)
# caught the screw's under-head junction fillet on its mouth (r743-3C).
HOLD_DOWN_HOLE_SPEC = HoleSpec("clearance", "#8", fit="close")
HOLE_DIA = blind_cut_dia_mm(HOLD_DOWN_HOLE_SPEC)

# One hold-down hole per bracket, on x = 0 in the foot's free run (from the
# ear's outboard face to the foot end), its station given from the ear's
# INBOARD face -- the face fit-up sets (the north datum, the south blade-set
# face), so the hole lands on the support's transferred seat without the foot
# length's band (user, 2026-10-10, option ii). Worst case is each term at its
# OWN band (Codex #936 PRRT_kwDOPHDy386mV3AN). Along the foot the south
# bracket's short run leaves no room for title-block .XX, so three lengths
# carry +/-0.10 (Codex P2 on 2026-10-09's flip, user option A): the foot
# length and the hole station, both from the inboard ear face, and the ear
# thickness. Across the foot its sides stay at .XX (the band
# rocker_bracket_seat_layout carries this foot at) and the hole's centring on
# x = 0 at .XX; a drilled hole grows by the title block's +0.10/0.
# build_ch_pivot_bracket carries the +/-0.10 bands on the model's own
# dimensions.
FOOT_LEN_BAND = 0.10
EAR_T_BAND = 0.10
STATION_BAND = 0.10
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


if BORE_LIGAMENT < 2.0:
    raise AssertionError("ear arch leaves less than the 2.0 web over the bore")

# The arch's radius rides the title block's .XX; the bore grows by the drilled
# hole's +0.10/0.
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
# is the one-pitch entry chamfer.
SET_SCREW_WALL_TERMS = {
    "arch radius at its minimum": EAR_ARCH_R - ARCH_R_BAND,
    "bore radius at its maximum": -BORE_RADIUS_MAX,
    "arch sag across the thread": -_sag(EAR_ARCH_R - ARCH_R_BAND),
    "bore sag across the thread": -_sag(BORE_RADIUS_MAX),
    "one-pitch entry chamfer": -SET_SCREW_PITCH,
}
SET_SCREW_FULL_THREAD_MIN = sum(SET_SCREW_WALL_TERMS.values())  # 3.10
SET_SCREW_ENGAGEMENT_D = SET_SCREW_FULL_THREAD_MIN / SET_SCREW_MAJOR_DIA  # 1.09D
SET_SCREW_ENGAGEMENT_PRINTED = int(SET_SCREW_ENGAGEMENT_D * 100.0) / 100.0
# The ruled floor: the R8 arch over the bore is all the thread there is, short
# of rule 12's 1.5D. It must not fall further without a new ruling.
if SET_SCREW_ENGAGEMENT_PRINTED < 1.08:
    raise AssertionError("MHA-CH-008 apex set-screw engagement fell below 1.08D")
# The channel assembly's set-screw step states the shortfall as a plain fact.
# Named exception: MHA-CH-008 set-screw engagement (drawing-simplicity-policy.md, "Named exceptions").
SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT = (
    f"#4-40 ENGAGEMENT {SET_SCREW_FULL_THREAD_MIN:.2f} MIN "
    f"({SET_SCREW_ENGAGEMENT_PRINTED:.2f}D)."
)
