r"""Summing-lever dimensional contract -- the single source of truth shared by
the part build (``build_sm_summing_lever.py``) and its manufacturing drawing
(``draw_sm_summing_lever.py``).

PURE DATA, no SolidWorks/COM imports (``stock_anchor_geom`` is pure geometry).
A large green-iron casting: a coefficients plate carrying the 20 channel-spring
anchor taps on the +X arm, a solid pivot cylinder with hex knife-edge
trunnions, and a curved summation arm ending in the tapped counter-spring
anchor boss on the -X arm.  Both anchors are purchased eyebolts that thread
straight into those taps -- the lever IS their nut -- so this module owns the
two thread identities and the boss height, and no plain anchor bore exists.
Values MUST match build_sm_summing_lever.py.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``).  Lengths
stay physical millimetres.  The lever's nominals are kinematic closures
(knife ridge, spring stations and pitch), spring/nut seats or values other
subsystems read, so they keep their values and print at the places that
hold them; every check below takes the printed limits.  Only the R MAX
limits (knife-ridge round, rib blends) and the knife-edge side band move to
exact inch values.
"""

from __future__ import annotations

import math

import _config
from _hole_spec import HoleSpec
from _package_units import drawing_unit
from _printed_tolerance import (
    inside_corner_radius_mm,
    printed_band_mm,
    printed_deviations,
)
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1


from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

MM_PER_IN = 25.4
UNIT = drawing_unit("parts/sm-summing-lever", _config.parts("sm-summing-lever"))

# --- Nominal geometry (SummingLever.cs, inches -> mm; DIMENSIONS.md ch. 18). ---
PLATE_W = 1.75 * MM_PER_IN  # 44.45 coefficients-plate width (X)
PLATE_L = 6.0 * MM_PER_IN  # 152.40 plate / pivot length (Z)
COUNTER_WEB_T = 0.2 * MM_PER_IN  # 5.08 negative-X web, centered on Y0
COEFFICIENT_T = 7.0  # uniform positive-X plate; thickened downward only (.276)
COEFFICIENT_TOP_Y = 0.1 * MM_PER_IN  # fixed +2.54 seat, independent of web depth
COEFFICIENT_BOTTOM_Y = COEFFICIENT_TOP_Y - COEFFICIENT_T  # -4.46 nut seats
CYL_R = 0.5 * MM_PER_IN  # 12.70 pivot-cylinder radius
SUM_H = 3.0 * MM_PER_IN  # 76.20 summation reach (-X)
ANCHOR_R = 0.375 * MM_PER_IN  # 9.525 summation-anchor outer radius
ANCHOR_H = 0.75 * MM_PER_IN  # 19.05 summation-anchor boss height (Y)

# hex knife-edge trunnion (vertex-up).  HEX_W was 8.653 (118.6 deg ridge);
# narrowed to 8.080 (115.1 deg ridge) so the trunnion still rocks >= 5.0 deg
# inside the sm-knife-mount Ø12 close bore at the worst case of BOTH parts'
# bands (``build_sm_summing_assembly.KNIFE_FREE_ROCK_WORST_DEG``).  The print
# holds the ridge to each side face and each upper flank to its side face
# (below); the width prints as a reference, the vertex height .XXX at HEX_BAND.
# The hexagon is the knife edge: its mm values stay (#290) and the envelope
# prints at KNIFE_ENVELOPE_PLACES (.318 / .404 / .159).
HEX_W = 8.080
HEX_H = 10.268
KNIFE_ENVELOPE_PLACES = 3
# Title-block .XXX on HEX_H.
HEX_BAND = printed_band_mm(KNIFE_ENVELOPE_PLACES, unit=UNIT)
HEX_DEPTH = 21.717  # .855
# Included angle of the knife-edge ridge (the top vertex of the hexagon).
RIDGE_ANGLE_DEG = 2.0 * math.degrees(math.atan2(HEX_W / 2.0, HEX_H / 4.0))
# Each ridge is truncated by a small round (drawing-guidelines rule 16; owner
# ruling 2026-10-16: the user's ask timed out and the recommended option was
# auto-selected), modelled at its printed limit, R.004 MAX; HEX_H stays the
# theoretical sharp the print dimensions.  KNIFE_RIDGE_TANGENT_XY is the
# (x, y) of the round's +X tangent line on the upper-right face, the visible
# ridge edge the plan picks.
KNIFE_RIDGE_R = 0.1016  # .004
KNIFE_RIDGE_R_PLACES = 3
KNIFE_RIDGE_R_BAND = (0.0, -KNIFE_RIDGE_R)  # (upper, lower)
KNIFE_RIDGE_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.004 MAX"
_RIDGE_HALF = math.radians(RIDGE_ANGLE_DEG) / 2.0
_RIDGE_SETBACK = KNIFE_RIDGE_R / math.tan(_RIDGE_HALF)
KNIFE_RIDGE_TANGENT_XY = (
    _RIDGE_SETBACK * math.sin(_RIDGE_HALF),
    HEX_H / 2.0 - _RIDGE_SETBACK * math.cos(_RIDGE_HALF),
)
# Code review C09 (owner ruling T1, 2026-10-17): the included angle with
# HexWidth and HexHeight left the ridge's position between the sides and each
# flank's own angle free; one flank could take the whole angle band.  Detail D
# instead holds, on both stubs, the ridge sharp RIDGE_FROM_SIDE from EACH side
# face and each upper flank KNIFE_FLANK_TO_SIDE_DEG to its side face, both
# toleranced explicitly; HexWidth becomes a reference.  The worst shoulder is
# the farthest from the ridge with the flattest flank: KNIFE_SHOULDER_X_MAX
# out and KNIFE_SHOULDER_DROP_MIN down, on a flank KNIFE_FLANK_HALF_MAX_DEG
# off the vertical.  The edge's hardness is still unspecified (#1611).
KNIFE_FLANK_TO_SIDE_DEG = round(180.0 - RIDGE_ANGLE_DEG / 2.0, 1)  # 122.4 printed
KNIFE_FLANK_TO_SIDE_TOL_DEG = 0.5
RIDGE_FROM_SIDE = HEX_W / 2.0  # 4.040 from each side face, printed .159
RIDGE_FROM_SIDE_TOL = 0.0508  # +/-.002
# The worst shoulder at the printed limit: .159 + .002 = .161 (4.0894).
KNIFE_SHOULDER_X_MAX = (
    RIDGE_FROM_SIDE
    + printed_deviations(
        RIDGE_FROM_SIDE,
        KNIFE_ENVELOPE_PLACES,
        (-RIDGE_FROM_SIDE_TOL, RIDGE_FROM_SIDE_TOL),
        unit=UNIT,
    )[1]
)
KNIFE_FLANK_HALF_MAX_DEG = 180.0 - (
    KNIFE_FLANK_TO_SIDE_DEG - KNIFE_FLANK_TO_SIDE_TOL_DEG
)
KNIFE_SHOULDER_DROP_MIN = KNIFE_SHOULDER_X_MAX / math.tan(
    math.radians(KNIFE_FLANK_HALF_MAX_DEG)
)
# Between the stubs: both are one prism through the body
# (``build_sm_summing_lever._hex_knife``, read back by
# ``_assert_knife_sides_coplanar``), so each side face of one stub lies in the
# same plane as the other's. The print retains the C09 symmetry-to-sides
# wording for both stubs, not a separate coplanarity requirement.
# Each ridge stands RIDGE_FROM_SIDE +/-RIDGE_FROM_SIDE_TOL from the SAME
# side plane, putting the ridges within KNIFE_STUB_RIDGE_OFFSET_MAX of each
# other. This bound rests on the shared model planes: with independent
# stub sides, symmetry alone would not tie the +Z ridge to datum A on -Z.
# The ridges rest on the knife mounts at the stubs' mid-lengths,
# KNIFE_RIDGE_CONTACT_SPAN apart; their relative offset skews the knife axis
# and spreads the spring hook arms by up to KNIFE_HOOK_ARM_SPREAD_MAX.
KNIFE_STUB_RIDGE_OFFSET_MAX = 2.0 * RIDGE_FROM_SIDE_TOL  # 0.1016
KNIFE_RIDGE_CONTACT_SPAN = PLATE_L + HEX_DEPTH  # 174.117 stub mid to stub mid

# Outward normal and plane offset of the upper-right sloping face of the
# vertex-up hexagon. Its upper endpoint is the +Y knife-edge ridge.
_KNIFE_FACE_SCALE = math.hypot(HEX_H / 4.0, HEX_W / 2.0)
KNIFE_FACE_NORMAL = (
    (HEX_H / 4.0) / _KNIFE_FACE_SCALE,
    (HEX_W / 2.0) / _KNIFE_FACE_SCALE,
    0.0,
)
KNIFE_FACE_OFFSET = KNIFE_FACE_NORMAL[1] * HEX_H / 2.0

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "knife_edge_ridge",
        MACHINED_UM,
        PlanarFace(
            KNIFE_FACE_NORMAL,
            KNIFE_FACE_OFFSET,
            contains_z_mm=(PLATE_L + HEX_DEPTH) / 2.0,
        ),
        display_unit=UNIT,
    ),
    # Both knife edges seat (Detail D's 2X): the -Z ridge carries the same grade.
    SurfaceFinishControl(
        "knife_edge_ridge_minus_z",
        MACHINED_UM,
        PlanarFace(
            KNIFE_FACE_NORMAL,
            KNIFE_FACE_OFFSET,
            contains_z_mm=-(PLATE_L + HEX_DEPTH) / 2.0,
        ),
        display_unit=UNIT,
    ),
)

# The 20 channel-spring lower anchors (McMaster 9489T111, part ``ch-vn-spring-hook``)
# thread DIRECTLY into the coefficient plate -- the supplied nut is discarded
# and each is locked by an MHA-CH-14 jam nut on the plate underside -- so
# each station is a through tap, not a bore:
# one native seed + a linear pattern. The size is the anchor's own thread, so a
# supplier change can never leave the lever tapped for the wrong screw.
HOLE_SPEC = HoleSpec("tapped", ANCHOR_9489T111.thread_size)
HOLE_X = 39.85
HOLE_COUNT = 20
CHANNEL_Z0 = -67.1
CHANNEL_PITCH = 7.0565
# The spring stations sit on the channel arm plane, the cam plane
# (rocker_bank_layout.ARM_MID_DZ = cam_plane.CAM_MID_DZ). Restated,
# like CHANNEL_Z0/CHANNEL_PITCH, not imported: this spec is read by
# _interference_contracts, so an import would put the gear-train and channel
# config into every assembly's closure. test_sm_summing_lever_drawing pins it.
HOLE_Z_OFFSET = -3.52825
# The whole coefficient plate now supplies the spring tap's 1.5D engagement
# at its printed .XX band. Its top and underside remain the
# existing spring-eye and jam-nut seats; there is no separate pad or step.
# All three positive-X rib branches use one tangent wrap/flank/root profile.
RIB_T = 5.08  # every edge/middle rib extrusion, .20 on the ordinary .XX band
RIB_WRAP_R = 0.6 * MM_PER_IN  # R15.24 around the unchanged R12.70 pivot
# 1.41 on the .XX grid; at its printed MAX (36.068) clear of the worst nut
# footprint at X36.449.
RIB_REACH = 35.814  # 1.41 in
# Modeled at the title block's inside-corner ceiling, R.040 MAX.
RIB_BLEND_R = inside_corner_radius_mm(unit=UNIT)
RIB_BLEND_R_PLACES = 3
RIB_BLEND_R_BAND = (0.0, -RIB_BLEND_R)  # (upper, lower), R.040 MAX
RIB_BLEND_R_TOL_TYPE = 6  # swTolType_e.swTolMAX

# The sm-vn-counter-spring lower anchor (McMaster 9490T1, part ``sm-vn-boss-hook``) threads
# DIRECTLY through the summation-anchor boss on the same no-nut rule, authored
# natively AFTER the structural ribs so none of them can refill it.
COUNTER_HOLE_SPEC = HoleSpec("tapped", ANCHOR_9490T1.thread_size)

# --- Derived. ---
CYL_DIA = 2.0 * CYL_R  # 25.4
TIP_X = -SUM_H  # -76.20 summation tip / anchor X
HOLE_Z_FIRST = CHANNEL_Z0 + HOLE_Z_OFFSET
HOLE_Z_LAST = CHANNEL_Z0 + CHANNEL_PITCH * (HOLE_COUNT - 1) + HOLE_Z_OFFSET
HOLE_EDGE_OFFSET = PLATE_W - HOLE_X  # 4.60 from the free +X plate edge
HOLE_END_OFFSET_FIRST = HOLE_Z_FIRST + PLATE_L / 2.0  # from the -Z end
HOLE_END_OFFSET_LAST = PLATE_L / 2.0 - HOLE_Z_LAST  # from the +Z end
HEX_Z_INNER = PLATE_L / 2.0  # trunnion inboard face flush with the body end (76.20)
HEX_Z_OUTER = HEX_Z_INNER + HEX_DEPTH  # outboard face overhangs the body (97.92)
# The between-stub ridge offset's hook-arm spread over the hole column (0.077).
KNIFE_HOOK_ARM_SPREAD_MAX = (
    KNIFE_STUB_RIDGE_OFFSET_MAX
    * (HOLE_Z_LAST - HOLE_Z_FIRST)
    / KNIFE_RIDGE_CONTACT_SPAN
)

# The MODEL owns every printed decimal place (build_sm_summing_lever applies
# this map; the drawing imports it unchanged).  Inch sheet: .XX on the plain
# body sizes, every one of which but the stub length (.86) some wall or
# clearance check reads (none takes the .X row), the plate thickness (.28)
# among them; the knife envelope and R MAX limits at their own places below.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {"PlateWidth": 2, "PlateThickness": 2},
    "CoefficientsPlate": {"PlateLength": 2},
    "CylinderReference": {"CylinderDia": 2},
    "SummationAnchorProfile": {"AnchorOuterDia": 2},
    "SummationAnchor": {"AnchorHeight": 2},
    "SummationPlateProfile": {"SummationArcRadius": 2},
    "SummationPlate": {"WebThickness": 2},
    "EdgeRibFrontProfile": {"EdgeRibFrontArcR": 2, "RibReach": 2},
    "EdgeRibFront": {"EdgeRibThickness": 2},
    "KnifeStubReference": {"KnifeStubLength": 2},
    "KnifeRidgeFillet": {"KnifeRidgeRadius": KNIFE_RIDGE_R_PLACES},
    "KnifeEnvelopeReference": {
        name: KNIFE_ENVELOPE_PLACES
        for name in ("HexWidth", "HexHeight", "RidgeFromLeft", "RidgeFromRight")
    },
}


def _deviations(model: float, feature: str, name: str) -> tuple[float, float]:
    return printed_deviations(model, DRAWING_PRECISION[feature][name], unit=UNIT)


# (lower, upper) mm about the model each printed size admits: the stacks
# (sm_summing_lever_profile, magnifying_bracket_joint_layout, the notes'
# thread engagement) read these, never a bare title-block row.
PLATE_W_DEVIATIONS = _deviations(PLATE_W, "PlateProfile", "PlateWidth")
PLATE_L_DEVIATIONS = _deviations(PLATE_L, "CoefficientsPlate", "PlateLength")
COEFFICIENT_T_DEVIATIONS = _deviations(COEFFICIENT_T, "PlateProfile", "PlateThickness")
RIB_T_DEVIATIONS = _deviations(RIB_T, "EdgeRibFront", "EdgeRibThickness")
RIB_WRAP_R_DEVIATIONS = _deviations(
    RIB_WRAP_R, "EdgeRibFrontProfile", "EdgeRibFrontArcR"
)
RIB_REACH_DEVIATIONS = _deviations(RIB_REACH, "EdgeRibFrontProfile", "RibReach")


# Drawing prose + marked-dimension contract (DRAWING_DIMENSIONS /
# ISOMETRIC_VIEW_NOTE) live in ``sm_summing_lever_notes`` --
# ``build_sm_summing_assembly`` / ``build_sm_knife_mount`` import this module, so
# drawing-only data here would put every notes edit in their rebuild
# closures (codex #354).


# Manufacturing GD&T limits consumed by the part's drawing projection.  The
# inch zones are the source; the drawing prints them, the mm table is derived.
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    # Ø.006 (#290; Ø0.15 before), tightened from Ø0.30 (owner ruling on code
    # review C06): two neighbouring MHA-CH-14 jam nuts stand on adjacent taps,
    # and at Ø0.30 their worst approach leaves no O.D. both the wall floor and
    # the 0.25 neighbour clearance admit (ch_anchor_jam_nut_spec).
    "spring-hole pattern position": ".006",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * MM_PER_IN for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
