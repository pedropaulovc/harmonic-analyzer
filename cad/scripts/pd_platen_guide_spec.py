"""Pure-data manufacturing contract for the platen guide.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``); bands and
limits stay physical millimetres, each the exact decimal of its inch value.
"""

import math

import _config
from _gtol_planar import PlanarFace
from _hole_spec import HoleSpec
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

UNIT = drawing_unit("parts/pd-platen-guide", _config.parts("pd-platen-guide"))

# R9-64: the guide screws' front receivers are #4-40 tapped THROUGH the rail,
# as R9-48 made the rear row. A blind tap cannot hold full thread to the
# screw's 5.42 reach and keep a bottoming tap's lead above the drill bottom
# without the drill point breaking through the rail's back under a lock, so the hole has
# no thread or drill depth to stack. The tips stop inside the rail
# (build_pd_platen_guide asserts the reach).
TAPPED_HOLE_SPEC = HoleSpec("tapped", "#4-40")

# The guide-lock screws' rear receivers (R9-48): #4-40 tapped THROUGH the
# rail, so the full depth carries thread and no depth band can starve
# the 3/8 in MHA-PD-VN-60 screws (pd_vn_guide_lock_screw_spec.ENGAGEMENT_WORST). The
# tips stop inside the rail (build_pd_platen_guide asserts the reach).
LOCK_TAP_SPEC = HoleSpec("tapped", "#4-40")

# Owner ruling 2026-11-01 (option B2): the rail is .29 tall and both tap rows
# stand .140 above the bottom face (local y 0). Since the owner rulings of
# 2026-11-13 (#2410) this part is the top rail only; the bottom rail is
# MHA-PD-27 (pd_platen_bottom_guide_spec), which keeps this section's depth.
#
# Owner ruling 2026-11-08 (Pedro, #2144 item 2.3: "these are noncritical
# holes, why use GD&T in the first place"): the 9X #4-40 taps print plain
# coordinates, no position frame or datums. Their stations print .XXX at the
# title block's ±.005 (TAP_STATION_PLACES). The tap row prints .140 ±.005
# (TAP_Y_BAND), the shop's drilled-hole location row, with no fit route
# (integration review 20261109T062834910Z: ±.004 was narrower than that row).
# At it each tap major's finished wall to the bottom and top faces at the
# height's .XX minimum is .059, .001 under the .060 floor: Delegated ruling
# 2026-11-09 (Main), pending owner confirmation; owner review #2144 item 2.3
# (RV-01; build_pd_platen_guide asserts both walls). The platen screws float
# in MHA-PD-02's .144 holes over both patterns' coordinate bands
# (test_pd_platen_refit); MHA-PD-12's .125 holes, with only .013 of float,
# are transferred from the lock taps at assembly.
GUIDE_HEIGHT = 7.366  # .29
TAP_Y = 3.556  # .140
TAP_Y_BAND = 0.127  # ±.005
TAP_STATION_PLACES = 3
TAP_STATION_BAND = printed_band_mm(TAP_STATION_PLACES, unit=UNIT)  # ±.005
# The farthest one tap's axis stands from its nominal: both coordinate bands
# at once (a square zone's corner).
TAP_POSITION_RADIAL = math.hypot(TAP_STATION_BAND, TAP_Y_BAND)
# The tap row's band, printed on every hole-table Y LOC; note 1 states the
# taps' finished wall to the edges (TAP_EDGE_WALL_TEXT in the builder).
TAP_Y_BAND_TEXT = f"{TAP_Y / 25.4:.3f} ±{TAP_Y_BAND / 25.4:.3f}".replace("0.", ".")

# The rail's depth (``build_pd_platen_guide.GUIDE_DEPTH``) sets how far behind the
# bar's back face the lock plates ride: the lock gap, which is the platen's
# float toward the 150T disc. The depth carries an explicit one-sided band,
# native on Depth@Guide, that holds the gap inside MHA-PD-00 step 7's leaf
# check on every bar MHA-PD-07 allows, so no seat is ever milled (owner ruling
# 2026-11-24, audit part 2 question C4: "(b) Rails .387 +.000/-.007; check
# "A .004 LEAF ENTERS AND A .017 LEAF DOES NOT". Air 0.067 mm at the widest
# gap; no seat is ever milled."; build_pd_platen_guide asserts it). It retires
# R9-47's faced seats and the .40 +.00/-.01 rail. It prints .XXX.
GUIDE_DEPTH_BAND = (0.0, -0.1778)  # (upper, lower): +.000/-.007
GUIDE_DEPTH_PLACES = 3
# The height keeps .XX (the lock-station sweep reads it so).
GUIDE_HEIGHT_PLACES = 2
# The one-sided band's function, printed at the depth (rule 7's short label):
# both limits are the lock gap's on the support bar.
GUIDE_DEPTH_CALLOUT = (
    f"SETS LOCK GAP\nON {_config.parts('pd-support-bar')['number']}"
)

# The print's dimensions, by owning feature (the build marks exactly these and
# the sheet imports only these), and the places each carries, authored on the
# model (drawing-simplicity-policy.md `How the repository implements the guidelines`). The height prints .XX
# (the lock-station sweep reads it so). The length prints .XX: the rail ends meet
# the platen's edges, which the platen sheet prints at .XX; the holes locate
# from the left end at basic stations, so no stack reads its band.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GuideProfile": {"Length", "Height"},
    "Guide": {"Depth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GuideProfile": {"Length": 2, "Height": GUIDE_HEIGHT_PLACES},
    "Guide": {"Depth": GUIDE_DEPTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {f: set(d) for f, d in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked platen-guide dimension needs native precision")

# The lock gap, lock-plate front face to the bar's back face, as MHA-PD-00
# step 7 accepts it (owner ruling 2026-11-24, audit part 2 question C4): a
# .004 leaf enters and a .017 leaf does not. It is the platen's float: (min,
# max). Its max bounds how far the platen can come forward toward the disc
# (build_pd_paper_drive_assembly.PLATEN_AIR). The as-made gap, the rail's
# depth less the bar's, always lies inside it (build_pd_platen_guide asserts
# it), so nothing is faced.
LOCK_GAP_FIT = (0.1016, 0.4318)  # the .004 and .017 leaves

# The one running surface (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)): the platen HANGS by the top rail's
# bottom face (local y 0) on the support bar's top edge and slides
# along it across the feed. Every other face is cast/machined per the title
# block. The symbol names the bar it slides on.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bar_slide",
        MACHINED_UM,
        PlanarFace((0, -1, 0), 0.0),
        production_method=f"SLIDES ON {_config.parts('pd-support-bar')['number']}",
        display_unit=UNIT,
    ),
)
