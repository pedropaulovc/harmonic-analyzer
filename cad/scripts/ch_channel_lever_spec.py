r"""Channel-lever dimensional contract -- the single source of truth shared by
the part build (``build_ch_channel_lever.py``) and its manufacturing drawing
(``draw_ch_channel_lever.py``).

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the pattern).
The drawing-only prose and the marked-dimension contract live in
``ch_channel_lever_notes`` so the assemblies that import this spec never
re-key on a drawing edit.
"""

from __future__ import annotations

from _gtol_cylinder import CylinderFace
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl


# --- Nominal geometry (DIMENSIONS.md "Chapter 17"). ---
# The spring-hole reach is SET BY THE VERTICAL SPRING AXIS, not by a round 7":
# the channel spring must hang plumb in the saved neutral pose, so the lever's
# spring hole has to sit on the summing-lever anchor's machine X.  Fulcrum
# 199.9 (channel_frame_geom.LEVER_FULCRUM_XY) - anchor 24.85
# (spring_mount_geom.CHANNEL_ANCHOR_XY = knife -15 + sm_summing_lever_spec.HOLE_X
# 39.85) = 175.05.  The neutral lever tilt is -0.00223 deg, so the exact
# projection correction 175.05 / cos(phi) - 175.05 is 1.3e-7 mm -- six orders
# below the +/-0.10 hook-arm allocation (error_budget.yaml), hence the flat
# nominal.  Was 177.8 (7"), which left the spring leaning 2.75 mm off plumb.
LEVER_SPRING_X = 175.05  # fulcrum -> spring-hole c2c, plumb over the anchor
# Bar height, full length; the end carries the spring hole. The lever is
# gray cast iron (owner ruling 2026-10-15: "device levers are clearly cast
# iron"), so the arm is deepened in its own plane from 9.5 for strength while
# staying under the O12.0 hub. Its lower edge clears the bar's top-notch roof
# (ch_bar_pivot_pin_spec notch_roof_clearance_min) and the spring's coil
# under the full-round tip (build_ch_channel_assembly._assert_spring_mount).
BAR_TALL = 11.0
LEVER_THICKNESS = 3.0
PIVOT_HOLE_DIA = 6.5  # fulcrum bore riding the 6.35 fulcrum shaft
BAR_PIN_X = 127.0  # fulcrum -> bar-pin c2c, 5"
BAR_PIN_HOLE_SPEC = HoleSpec("drilled_number", "#47")
SPRING_EYE_HOLE_SPEC = HoleSpec("drilled_number", "#21")

# The end is the full-height bar with a full-round tip about the spring hole
# (ch17 p.39 close-up, page001_img01: the bar runs full height to a rounded
# end with the hook hole in it).  The former 6.0-tall stepped tab left
# (6.0 - 4.04) / 2 = 0.98 of wall beside the #21 hole (baseline machinist
# review, drawing-guidelines.md rule 17); concentric with the full round the
# wall is BAR_TALL / 2 - r all the way round.
TIP_ARC_CX = LEVER_SPRING_X
TIP_RADIUS = BAR_TALL / 2.0  # 5.50: full round, tangent to both bar edges

# --- Derived spans. ---
NOSE_RADIUS = BAR_TALL / 2.0  # 5.50 fulcrum nose (inside the hub)
TIP_END_X = TIP_ARC_CX + TIP_RADIUS  # 180.55 tip from the fulcrum axis

# Integral fulcrum hub (2026-09-02 photo re-derive, ch17 p.40 page002_img03):
# the levers stack hub-to-hub on the fulcrum shaft at the station pitch; the
# 19 `lever-bushing` spacers are retired. OD = the old bushing's O12.
HUB_DIA = 12.0
HUB_LENGTH = 7.0565  # == machine channels.station_pitch_mm (asserted by the build)
if not BAR_TALL < HUB_DIA:
    raise AssertionError("the arm must stay under the hub")

# --- Bands (upper, lower), native on the model dimensions. ---
# The fulcrum bore is reamed: it runs on the h-band 6.35 fulcrum shaft
# (MHA-CH-004), the same O6.5 +0.03/0 pivot the rocker arm runs on its shaft.
PIVOT_HOLE_BAND = (0.03, 0.0)
# The plate is straddled by the amplitude bar's top notch, whose 3.15 minimum
# is this band's maximum plus the running floor (ch_amplitude_bar_spec). The
# band is +/-0.05 so the bar's float, with both ledges and both plate offsets,
# leaves the bar-to-bar running gap (owner ruling 2026-10-15, #1038 option 2).
LEVER_THICKNESS_TOLERANCE = 0.05
# Both transfer arms carry the error budget's +/-0.10 gain allocation
# (error_budget.yaml lever_bar_pin_arm / lever_spring_hook_arm), measured from
# the fulcrum bore that the lever turns about.
BAR_PIN_X_TOLERANCE = 0.10
LEVER_SPRING_X_TOLERANCE = 0.10
# The 20 hubs stack face to face between the fulcrum keepers.  A hub may only
# come out long (ch_bar_pivot_pin_spec's bar-to-bar clearance takes the pitch
# at its nominal minimum), and twenty of them at the band's top must still
# leave float at the keeper lugs (test_ch_channel_lever_drawing pins it).
HUB_LENGTH_BAND = (0.03, 0.0)
# The plate sits central on the hub, located from ONE hub face: each bar rides
# its lever's plate, so the plate's offset in the hub shifts the bar toward its
# neighbour's (ch_bar_pivot_pin_spec's bar-to-bar gap; the stack is #1038).
PLATE_OFFSET = (HUB_LENGTH - LEVER_THICKNESS) / 2.0  # 2.028 hub face -> plate face
PLATE_OFFSET_TOLERANCE = 0.05

# drawing-guidelines.md rule 17 (walls and webs): every wall the holes leave,
# at the worst case of the printed bands (the bar height and the hub both
# print at one place, title-block +/-0.8; drilled holes +0.10/0; the reamed
# bore at its top).
WALL_FLOOR = 2.0
_LINEAR_1PL = 0.8
_DRILL_PLUS = 0.10
_SPRING_HOLE_R_MAX = (blind_cut_dia_mm(SPRING_EYE_HOLE_SPEC) + _DRILL_PLUS) / 2.0
_BAR_PIN_HOLE_R_MAX = (blind_cut_dia_mm(BAR_PIN_HOLE_SPEC) + _DRILL_PLUS) / 2.0
WALL_MIN = {
    "spring hole to tip and edges": (BAR_TALL - _LINEAR_1PL) / 2.0 - _SPRING_HOLE_R_MAX,
    "bar-pin hole to edges": (BAR_TALL - _LINEAR_1PL) / 2.0 - _BAR_PIN_HOLE_R_MAX,
    "fulcrum bore to hub": (HUB_DIA - _LINEAR_1PL) / 2.0
    - (PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0]) / 2.0,
}
for _wall, _value in WALL_MIN.items():
    if _value < WALL_FLOOR:
        raise AssertionError(f"{_wall} wall {_value:.2f} < {WALL_FLOOR} floor")

# drawing-guidelines.md rule 6: the fulcrum bore is the one running surface.
SURFACE_FINISHES = (
    SurfaceFinishControl("fulcrum_bore", MACHINED_UM, CylinderFace(PIVOT_HOLE_DIA)),
)
