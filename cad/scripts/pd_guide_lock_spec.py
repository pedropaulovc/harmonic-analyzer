r"""Guide-lock dimensional contract -- the single source of truth shared by the
part build (``build_pd_guide_lock.py``) and its manufacturing drawing
(``draw_pd_guide_lock.py``).

PURE DATA, no SolidWorks/COM imports: the nominal geometry (the "editable
knobs"), the hole layout the drawing needs for its view math, and the
marked-dimension -> kept-dimension NAME map. Keeping this in ONE module means a
rename or a nominal change is a single edit that reaches both scripts, so the
part-side ``mark_dimensions_for_drawing`` set and the drawing-side ``keep``
maps cannot silently drift apart (see ``dt_crank_arm_spec.py`` for the pattern's
build-graph rationale).

The offline lockstep test (``test_pd_guide_lock_drawing.py``) asserts the part
marks and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS`` -- the drift alarm,
run without SolidWorks in ~1 s.
"""

from __future__ import annotations

import _config
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_deviations

# #290: the sheet prints decimal inch; every nominal below is the exact
# millimetre decimal of its printed inch value.
UNIT = drawing_unit("parts/pd-guide-lock", _config.parts("pd-guide-lock"))

# --- Nominal geometry (book ch. 22, pp. 54-55; see build_pd_guide_lock.py for the
# bottom-station height derivation). These drive the part's named equation
# globals AND the drawing's coordinate math. ---
# .89 along +X with the holes .157 and .709 from the left edge, so the
# plate overhangs its hole pattern further on the right: the right-end wall
# then reaches the .080 target at the printed worst case (machinist review
# ENFORCE, PR #1897). The assembly centres the hole pattern, not the plate,
# on each lock station.
LOCK_WIDTH = 22.606  # .89, along +X
# R9-59: the plate laps past the rail's outer edge. Its screw holes sit on the
# rail's tap row, .140 above the rail's datum B (pd_platen_guide_spec.TAP_Y):
# that is the bottom rail's outer edge and .150 below the top rail's, so at
# .155 from the guide-side edge the plate laps .015 past the bottom rail and
# .005 past the top one, and the holes keep the .080 wall target at the
# printed worst case (PR #1897).
HOLE_Y = 3.937  # .155
# .45 along +Y; y = 0 is the guide-side edge. One plate serves both rails
# (user ruling 2026-10-11): lip + .29 rail + bar overlap. The bar fills the
# channel to a running clearance over the bottom rail
# (pd_support_bar_spec.BAR_HEIGHT), so the plate overlaps the bar ~3.9 at the
# top rail (which hangs on it) and ~2.7 at the bottom rail. The height
# prints .XX: its least size still overlaps the bar over the 0.5 retention
# floor with the lifted top plates, its largest clears the latch hook and
# pivot spacer (build_pd_paper_drive_assembly's lock-station sweep).
LOCK_HEIGHT = 11.43  # .45
# 2026-10-11 (user): 1/16 in steel sheet, thickness as supplied, e.g. A36
# precision-ground sheet, McMaster-Carr 1388K196, 1/16 in -.005 to +.005 in
# (read live 2026-10-11; the family's +/-.003 and +/-.001 grades sit inside
# that band). The band is the requirement, so the title block names the
# low-carbon steel family, not the grade or ground form (rule 2).
# It replaced R9-31's machined 2.0 strip, whose slotted pan heads
# (MHA-PD-VN-60) stood too proud for the arm plate, and a 0.25 head spot face,
# which left no wall at the 3.5-from-edge holes. #290: stock fractions print
# as reference, the supplier's band governs, so the sheet prints the
# thickness as a 1/16 REF and the registry row's material specification
# states the band, which the lock-station sweep and the screw's engagement
# spend.
LOCK_THICK = 1.5875  # 1/16, extruded +Z
LOCK_THICK_BAND = 0.127  # +/-.005: the sheet's mill tolerance, supplier's
LOCK_STOCK_SKU = "1388K196"
# One line: SolidWorks keeps a line-broken above-callout but never prints it
# (draw_pd_transgear_drive_collar; farm run 20261012T002237965Z here).
LOCK_STOCK_CALLOUT = "SHEET AS SUPPLIED"
# 2026-10-11 (user): the four plan corners are rounded, as the ch22 back photo
# (page001_img01) shows them: at its 3.60 px/mm platen scale (269.64 = 970 px)
# each plate's corner arcs span ~6.3 px, R ~1.75 (an upper bound: the JPEG's
# blur only widens them). R.07 prints .XX; with R under the holes' offsets
# from every edge, each hole sits outside its corner's R x R square, so its
# edge distances still run to the straight edges.
CORNER_R = 1.778  # .07
# Screw-hole layout on the guide-side band (matches the guide's hole pitch:
# the two stations sit x +-.276 about the hole pattern's centre, the lock
# station, on the rail's tap row past the lip). R9-49: 1/8 DRILL
# (.125) over the #4-40 majors carries this plate's coordinate bands and
# the rail taps' Ø.008 position (pd_vn_guide_lock_screw_spec.LOCK_SET_OFFSET);
# the #4 close .120 left too little.
HOLE_XY = ((3.9878, HOLE_Y), (18.0086, HOLE_Y))  # .157, .709
# Plate-frame x of the hole pattern's centre: the assembly puts it on the
# lock station (the plate's own centre stands right of it).
HOLE_PATTERN_X = (HOLE_XY[0][0] + HOLE_XY[1][0]) / 2.0
HOLE_SPEC = HoleSpec("drilled_fractional", "1/8")
# ± on each printed hole coordinate (drawing-guidelines.md rule 5 (avoid excessive GD&T): no frame on this plate). Its
# radial reach, hypot(.001, .001), is what the set window spends.
HOLE_LOCATION_BAND = 0.0254  # ±.001
HOLE_LOCATION_PLACES = 3

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_pd_guide_lock`` marks exactly these; ``draw_pd_guide_lock``
# keeps exactly their union across its per-view ``keep`` maps. The screw
# holes' size ships as a native hole callout; their placement-sketch
# coordinates from the plate's corner print here (both holes share Hole1Y). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LockProfile": {"Width", "Height"},
    "Lock": {"Depth"},
    "ScrewHoles": {"Hole1X", "Hole2X", "Hole1Y"},
    "Corners": {"CornerR"},
}
HOLE_LOCATION_DIMENSIONS = DRAWING_DIMENSIONS["ScrewHoles"]

# Places and explicit bands the print carries on those dimensions, the ones the
# paper-drive lock-station sweep judges the plate at (drawing-guidelines.md rule 17 (walls and webs)). The
# thickness is the 1/16 sheet's, printed as a fraction REF: the supplier's
# ±.005 (LOCK_THICK_BAND) governs it; the model carries four places (.0625).
# The height prints .XX: its least size still overlaps the bar
# (build_pd_paper_drive_assembly._assert_lock_retention) and its largest
# clears the latch hook and pivot spacer. The width prints .XX: its +.01
# lengthens the overhang the skew swings
# (pd_vn_guide_lock_screw_spec.CORNER_OVERHANG_MAX), and the title block's .X
# ±.1 would leave the right-end wall under the target. The corner radius
# prints .XX, shared by all four (4X): at .X it could reach the holes.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LockProfile": {"Width": 2, "Height": 2},
    "Lock": {"Depth": 4},
    "ScrewHoles": {name: HOLE_LOCATION_PLACES for name in HOLE_LOCATION_DIMENSIONS},
    "Corners": {"CornerR": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if DRAWING_PRECISION.keys() != DRAWING_DIMENSIONS.keys() or any(
    set(DRAWING_PRECISION[feature]) != names
    for feature, names in DRAWING_DIMENSIONS.items()
):
    raise AssertionError("every marked guide-lock dimension needs authored places")

# Edge ligaments of the screw holes at the printed worst case: the largest
# drilled hole, its coordinate band, and the plate's printed outline bands.
# The holes locate from the plate's corner (x from the left edge, y from the
# guide-side edge), so the right and far ligaments also spend the outline's.
# Rule 17's target: every hole wall reaches it at the printed worst case, so
# the sheet states no shortfall.
_HOLE_R_MAX = (blind_cut_dia_mm(HOLE_SPEC) + drilled_oversize_mm(unit=UNIT)) / 2.0
_WIDTH_MIN = (
    LOCK_WIDTH
    + printed_deviations(
        LOCK_WIDTH, DRAWING_PRECISION["LockProfile"]["Width"], unit=UNIT
    )[0]
)
_HEIGHT_MIN = (
    LOCK_HEIGHT
    + printed_deviations(
        LOCK_HEIGHT, DRAWING_PRECISION["LockProfile"]["Height"], unit=UNIT
    )[0]
)
HOLE_LIGAMENTS_WORST: dict[str, float] = {
    "guide-side edge": min(y for _, y in HOLE_XY) - HOLE_LOCATION_BAND - _HOLE_R_MAX,
    "far edge": _HEIGHT_MIN
    - max(y for _, y in HOLE_XY)
    - HOLE_LOCATION_BAND
    - _HOLE_R_MAX,
    "left edge": min(x for x, _ in HOLE_XY) - HOLE_LOCATION_BAND - _HOLE_R_MAX,
    "right edge": _WIDTH_MIN
    - max(x for x, _ in HOLE_XY)
    - HOLE_LOCATION_BAND
    - _HOLE_R_MAX,
}
if min(HOLE_LIGAMENTS_WORST.values()) < WALL_TARGET_MM:
    raise AssertionError(
        f"guide-lock screw-hole ligaments {HOLE_LIGAMENTS_WORST} under {WALL_TARGET_MM}"
    )

# The rounded corners must not reach the holes: with each hole centre (at its
# printed worst case, from the nearest edges at their printed worst case)
# outside its corner's R x R square at the largest printed radius, the
# nearest boundary to every hole is a straight edge, so the ligaments above
# hold unchanged.
_, _CORNER_R_UPPER = printed_deviations(
    CORNER_R, DRAWING_PRECISION["Corners"]["CornerR"], unit=UNIT
)
_CORNER_R_MAX = CORNER_R + _CORNER_R_UPPER
_HOLE_EDGE_OFFSETS_MIN = (
    min(x for x, _ in HOLE_XY) - HOLE_LOCATION_BAND,
    _WIDTH_MIN - max(x for x, _ in HOLE_XY) - HOLE_LOCATION_BAND,
)
if min(_HOLE_EDGE_OFFSETS_MIN) <= _CORNER_R_MAX:
    raise AssertionError(
        f"guide-lock corner radius {_CORNER_R_MAX} reaches a screw hole "
        f"(edge offsets {_HOLE_EDGE_OFFSETS_MIN})"
    )

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
