r"""Channel-lever dimensional contract -- the single source of truth shared by
the part build (``build_ch_channel_lever.py``) and its manufacturing drawing
(``draw_ch_channel_lever.py``).

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the pattern).
The drawing-only prose and the marked-dimension contract live in
``ch_channel_lever_notes`` so the assemblies that import this spec never
re-key on a drawing edit.
"""

from __future__ import annotations

import math

import _config
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
)
from _surface_finish import SurfaceFinishControl

# #290: the sheet prints decimal inch (the row's ``drawing_unit``). Lengths
# stay millimetres, each fabricated one the exact decimal of its printed inch
# value; the reach and the hub length are kinematic closures and stay exact.
UNIT = drawing_unit("parts/ch-channel-lever", _config.parts("ch-channel-lever"))


# --- Nominal geometry (DIMENSIONS.md "Chapter 17"). ---
# The spring-hole reach is SET BY THE VERTICAL SPRING AXIS, not by a round 7":
# the channel spring must hang plumb in the saved neutral pose, so the lever's
# spring hole has to sit on the summing-lever anchor's machine X.  Fulcrum
# 199.9 (channel_frame_geom.LEVER_FULCRUM_XY) - anchor 24.85
# (spring_mount_geom.CHANNEL_ANCHOR_XY = knife -15 + sm_summing_lever_spec.HOLE_X
# 39.85) = 175.05.  The neutral lever tilt is -0.00223 deg, so the exact
# projection correction 175.05 / cos(phi) - 175.05 is 1.3e-7 mm -- six orders
# below the +/-0.127 hook-arm allocation (error_budget.yaml), hence the flat
# nominal.  Was 177.8 (7"), which left the spring leaning 2.75 mm off plumb.
LEVER_SPRING_X = 175.05  # fulcrum -> spring-hole c2c, plumb over the anchor
# Bar height from the hub out to the taper start; the end carries the spring hole.
# Owner ruling 2026-11-18 (#3113): the original's depth, the 9.5 photo read
# (dimensions.yaml ch. 17), at the sheet's two places. The 10.9 deepening for
# the retired gray-iron ruling (2026-10-15) is undone. Its lower edge clears
# the bar's top-notch roof (sh_vn_pivot_pin_bar_spec notch_roof_clearance_min)
# and the spring's coil under the tip (build_ch_channel_assembly._assert_spring_mount).
BAR_TALL = 9.398  # .37
# .118: ch_amplitude_bar_spec restates it for the top notch (it follows when
# the bar converts).
LEVER_THICKNESS = 2.9972  # .118
# The fulcrum bore is drilled F, .257 at the title block's DRILLED HOLES row
# (owner ruling 2026-11-24, fit audit question 1, approved as recommended:
# the 44 bores on the two 1/4 in shafts drilled F; was the .2560
# +.0010/.0000 ream of #290 fit table F3). The spring and the bar hold
# the bore's lower wall on the shaft through the whole crank turn, so the
# clearance is a constant offset, not shake. It stays a plain circle cut:
# the sketch dimension prints the drill's size under the drill's callout.
PIVOT_HOLE_SPEC = HoleSpec("drilled_letter", "F")
PIVOT_HOLE_DIA = blind_cut_dia_mm(PIVOT_HOLE_SPEC)  # 6.528, .257
BAR_PIN_X = 127.0  # fulcrum -> bar-pin c2c, 5"
BAR_PIN_HOLE_SPEC = HoleSpec("drilled_number", "#47")
SPRING_EYE_HOLE_SPEC = HoleSpec("drilled_number", "#21")

# The end tapers, as the original's does (#3113; ch17 page001_img01 and the
# squarer page001_img02 side view read the tip at about 0.8 of the depth at
# the bar pin). The bar keeps full depth through the bar pin, where the
# bending moment of this third-class lever peaks, and past the amplitude
# bar's top notch; from the taper start both edges run straight to tangency
# with a full-round tip concentric with the spring hole, as the moment falls
# linearly to nothing at the spring. The taper starts at its own printed
# station (.XX from the fulcrum bore), not on the bar pin's centreline: a
# kink on the hole line could only be named in words (#3113 machinist
# review, 3/3 runs). Owner ruling 2026-11-18 (#3113): the tip radius holds
# the #21 hole's finished wall (both .010 edge breaks charged) at the .060
# floor, under the .080 target (MHA-CH-02 RV-04). The photo ratio (~0.8)
# would have left that wall under the floor; the owner chose the blunter
# R.167. It prints at three places because .17 at two would take the wall
# below the target, and the sheet states the wall it holds.
TAPER_START_X = 139.7  # 5.50: full depth inboard of it
TIP_ARC_CX = LEVER_SPRING_X
TIP_RADIUS = 4.2418  # R.167: tip depth 8.48, 0.90 of BAR_TALL


def taper_tangent_point() -> tuple[float, float]:
    """Upper tangent point of the taper edge on the tip circle (the lower one
    is its mirror): the edge runs from (TAPER_START_X, BAR_TALL / 2)."""
    vx, vy = TAPER_START_X - TIP_ARC_CX, BAR_TALL / 2.0
    reach = math.hypot(vx, vy)
    angle = math.atan2(vy, vx) - math.acos(TIP_RADIUS / reach)
    return TIP_ARC_CX + TIP_RADIUS * math.cos(angle), TIP_RADIUS * math.sin(angle)


# --- Derived spans. ---
NOSE_RADIUS = BAR_TALL / 2.0  # 4.699 fulcrum nose (inside the hub)
TIP_END_X = TIP_ARC_CX + TIP_RADIUS  # 179.29 tip from the fulcrum axis
if not TIP_RADIUS < BAR_TALL / 2.0:
    raise AssertionError("the end must taper toward the tip")

# Integral fulcrum hub (2026-09-02 photo re-derive, ch17 p.40 page002_img03):
# the levers stack hub-to-hub on the fulcrum shaft at the station pitch; the
# 19 `lever-bushing` spacers are retired. OD near the old bushing's O12.
# .48 since the F-drilled bore (the same ruling: the hub O.D. goes .47 to
# .48): at .47 the wall round the drill's largest hole falls under the .080
# target (WALL_MIN below).
HUB_DIA = 12.192  # .48
HUB_LENGTH = 7.62  # == channels.station_pitch_mm (build + lockstep test); .3000
if not BAR_TALL < HUB_DIA:
    raise AssertionError("the arm must stay under the hub")

# --- Bands (upper, lower), native on the model dimensions. ---
# The fulcrum bore's ANALYSIS band: what the F drill cuts, the title block's
# DRILLED HOLES row (the sheet prints the drill and no band of its own). The
# walls and the clearance on the h-band .250 fulcrum shaft (MHA-CH-04) read
# it; the rocker arm's pivot is the same F-drilled bore on its shaft.
PIVOT_HOLE_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)
# The plate is straddled by the amplitude bar's top notch, whose minimum is
# this band's maximum plus the running floor (ch_amplitude_bar_spec, which
# restates it). The band is +/-.002 so the bar's float, with both ledges and
# both plate offsets, leaves the bar-to-bar running gap (owner ruling
# 2026-10-15, #1038 option 2).
LEVER_THICKNESS_TOLERANCE = 0.0508  # +/-.002
# Both transfer arms are drilled holes located from the fulcrum bore the
# lever turns about, so they print plain at the title block's .XXX row
# (+/-.005, drawing-guidelines rule 3), the shop's drilled-hole location row.
# The error budget (error_budget.yaml lever_bar_pin_arm /
# lever_spring_hook_arm) allocates the same band, ~1/6 and ~1/7 of each
# arm's allowable. Delegated ruling 2026-11-07 (Main), no precedent; owner
# review #2144 (Q1-A); confirmed by owner ruling 2026-11-20 (#2351) with
# check:budget passing at these bands.
BAR_PIN_X_TOLERANCE = printed_band_mm(3, unit=UNIT)  # +/-.005
LEVER_SPRING_X_TOLERANCE = printed_band_mm(3, unit=UNIT)  # +/-.005
# The 20 hubs stack face to face between the fulcrum keepers.  A hub may only
# come out long (sh_vn_pivot_pin_bar_spec's bar-to-bar clearance takes the pitch
# at its nominal minimum), and twenty of them at the band's top must still
# leave float at the keeper lugs (test_ch_channel_lever_drawing pins it). The
# pitch prints .300 +.001/.000.
HUB_LENGTH_BAND = (0.0254, 0.0)
# The plate sits central on the hub, located from ONE hub face: each bar rides
# its lever's plate, so the plate's offset in the hub shifts the bar toward its
# neighbour's (sh_vn_pivot_pin_bar_spec's bar-to-bar gap; the stack is #1038).
PLATE_OFFSET = (
    HUB_LENGTH - LEVER_THICKNESS
) / 2.0  # 2.3114 (.091) hub face -> plate face
PLATE_OFFSET_TOLERANCE = 0.0508  # +/-.002

# drawing-guidelines.md rule 17 (walls and webs): every wall the holes leave,
# at the worst case of the printed bands (the bar height and the hub both
# print .XX; drilled holes, the fulcrum bore among them, +.004/0), less the
# title block's edge break at each of its two edges (the hole mouth and the
# outside edge), against the .080 target.
_LINEAR_2PL = printed_band_mm(2, unit=UNIT)
_LINEAR_3PL = printed_band_mm(3, unit=UNIT)
_DRILL_PLUS = drilled_oversize_mm(unit=UNIT)
_EDGE_BREAK = max(edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT))
_SPRING_HOLE_R_MAX = (blind_cut_dia_mm(SPRING_EYE_HOLE_SPEC) + _DRILL_PLUS) / 2.0
_BAR_PIN_HOLE_R_MAX = (blind_cut_dia_mm(BAR_PIN_HOLE_SPEC) + _DRILL_PLUS) / 2.0
WALL_MIN = {
    wall: printed - 2.0 * _EDGE_BREAK
    for wall, printed in {
        "spring hole to tip and edges": TIP_RADIUS - _LINEAR_3PL - _SPRING_HOLE_R_MAX,
        "bar-pin hole to edges": (BAR_TALL - _LINEAR_2PL) / 2.0 - _BAR_PIN_HOLE_R_MAX,
        "fulcrum bore to hub": (HUB_DIA - _LINEAR_2PL) / 2.0
        - (PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0]) / 2.0,
    }.items()
}
# The tapered tip's finished wall is owner-accepted between the floor and the
# target (#3113, MHA-CH-02 RV-04); every other wall meets the target.
WALL_SHORTFALL_ACCEPTED = frozenset({"spring hole to tip and edges"})
for _wall, _value in WALL_MIN.items():
    _limit = WALL_FLOOR_MM if _wall in WALL_SHORTFALL_ACCEPTED else WALL_TARGET_MM
    if _value < _limit - 1e-9:
        raise AssertionError(f"{_wall} wall {_value:.3f} < {_limit} limit")
# Rules 3 and 20: the three-place tip radius states, once, the wall it holds.
_TIP_WALL_IN = (
    math.floor(round(WALL_MIN["spring hole to tip and edges"] / 25.4, 4) * 1000) / 1000
)
TIP_WALL_TEXT = f"HOLDS WALL {_TIP_WALL_IN:.3f}".replace(" 0.", " .") + " MIN"

# drawing-guidelines.md rule 6: no surface carries a roughness symbol. The
# fulcrum bore only rocks a few degrees against one side of its clearance
# under the spring, so it takes none (owner ruling 2026-11-24, fit audit
# question 1: the 63 microinch symbol comes off the 40 pivots).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()
