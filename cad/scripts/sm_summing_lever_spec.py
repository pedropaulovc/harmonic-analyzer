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
"""

from __future__ import annotations

from sm_knife_contact import (
    KNIFE_FACE_NORMAL,
    KNIFE_FACE_OFFSET,
    KNIFE_STUB_RIDGE_OFFSET_MAX,
)
from _hole_spec import HoleSpec
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1


from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

MM_PER_IN = 25.4

# --- Nominal geometry (SummingLever.cs, inches -> mm; DIMENSIONS.md ch. 18). ---
PLATE_W = 1.75 * MM_PER_IN  # 44.45 coefficients-plate width (X)
PLATE_L = 6.0 * MM_PER_IN  # 152.40 plate / pivot length (Z)
COUNTER_WEB_T = 0.2 * MM_PER_IN  # 5.08 negative-X web, centered on Y0
COEFFICIENT_T = 7.0  # uniform positive-X plate; thickened downward only
COEFFICIENT_TOP_Y = 0.1 * MM_PER_IN  # fixed +2.54 seat, independent of web depth
COEFFICIENT_BOTTOM_Y = COEFFICIENT_TOP_Y - COEFFICIENT_T  # -4.46 nut seats
CYL_R = 0.5 * MM_PER_IN  # 12.70 pivot-cylinder radius
SUM_H = 3.0 * MM_PER_IN  # 76.20 summation reach (-X)
ANCHOR_R = 0.375 * MM_PER_IN  # 9.525 summation-anchor outer radius
ANCHOR_H = 0.75 * MM_PER_IN  # 19.05 summation-anchor boss height (Y)

HEX_DEPTH = 21.717  # axial length each stub protrudes past the body end
# Between the stubs: both are one prism through the body
# (``build_sm_summing_lever._hex_knife``, read back by
# ``_assert_knife_sides_coplanar``), so each side face of one stub lies in the
# same plane as the other's. The print retains the C09 symmetry-to-sides
# wording for both stubs, not a separate coplanarity requirement.
# Each ridge stands sm_knife_contact.RIDGE_FROM_SIDE
# +/-sm_knife_contact.RIDGE_FROM_SIDE_TOL from the SAME side plane, putting
# the ridges within sm_knife_contact.KNIFE_STUB_RIDGE_OFFSET_MAX of each
# other. This bound rests on the shared model planes: with independent
# stub sides, symmetry alone would not tie the +Z ridge to datum A on -Z.
# The ridges rest on the knife mounts at the stubs' mid-lengths,
# KNIFE_RIDGE_CONTACT_SPAN apart; their relative offset skews the knife axis
# and spreads the spring hook arms by up to KNIFE_HOOK_ARM_SPREAD_MAX.
KNIFE_RIDGE_CONTACT_SPAN = PLATE_L + HEX_DEPTH  # 174.117 stub mid to stub mid

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "knife_edge_ridge",
        MACHINED_UM,
        PlanarFace(
            KNIFE_FACE_NORMAL,
            KNIFE_FACE_OFFSET,
            contains_z_mm=(PLATE_L + HEX_DEPTH) / 2.0,
        ),
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
# at the title block's ordinary .XX band. Its top and underside remain the
# existing spring-eye and jam-nut seats; there is no separate pad or step.
# All three positive-X rib branches use one tangent wrap/flank/root profile.
RIB_WRAP_R = 0.6 * MM_PER_IN  # R15.24 around the unchanged R12.70 pivot
RIB_REACH = HOLE_X - 4.1  # 35.75; clear of the worst nut footprint at X36.45
RIB_BLEND_R = 1.0  # modeled at the R1.0 MAX internal blend limit
RIB_BLEND_R_BAND = (0.0, -RIB_BLEND_R)  # (upper, lower), R1.0 MAX
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

# Noncritical body-end length uses the ordinary .X ±0.8 mm title-block band.
# Author its places on the part; the drawing must import them unchanged.
# This changes no nominal geometry or entry-relative receiver depth/location.
DRAWING_PRECISION = {"CoefficientsPlate": {"PlateLength": 1}}


# Drawing prose + marked-dimension contract (DRAWING_DIMENSIONS /
# ISOMETRIC_VIEW_NOTE) live in ``sm_summing_lever_notes`` --
# drawing-only data here would put every anchor and assembly consumer in their
# rebuild closures (codex #354).


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    # Ø0.15, tightened from 0.30 (owner ruling on code review
    # C06): two neighbouring MHA-CH-14 jam nuts stand on adjacent taps, and
    # at Ø0.30 their worst approach leaves no O.D. both the wall floor and the
    # 0.25 neighbour clearance admit (ch_anchor_jam_nut_spec).
    "spring-hole pattern position": "0.15",
}
