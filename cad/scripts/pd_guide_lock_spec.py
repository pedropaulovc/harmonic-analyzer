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

from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_deviations

# --- Nominal geometry (book ch. 22, pp. 54-55; see build_pd_guide_lock.py for the
# bottom-station height derivation). These drive the part's named equation
# globals AND the drawing's coordinate math. ---
LOCK_WIDTH = 22.0  # along +X
# R9-59: the plate laps RAIL_EDGE_LIP past the rail's outer edge, so its screw
# holes, on the rail's mid-line, stand 3.5 from the guide-side edge and keep
# the 1.5 ligament at the printed worst case (2.5 left 0.81).
RAIL_EDGE_LIP = 1.0
# 9.6 along +Y; y = 0 is the guide-side edge. One plate serves both rails
# (user ruling 2026-10-11): 1 lip + 5 rail + ~3 bar overlap. The 28-tall bar
# fills the channel to a 1.0 running clearance over the bottom rail
# (pd_support_bar_spec.BAR_HEIGHT), so the plate overlaps the bar 3.6 at the
# top rail (which hangs on it) and 2.6 at the bottom rail. 9.6, not 9.5, so
# the height prints at the general .X (Codex P1 on #1353: a tighter .XX
# needed a design-intent note, which drawing-guidelines.md rule 7 (notes: few, flagged, never a method) bars); at 9.5 - 0.8 the lifted
# top plates would lap the bar under the 0.5 retention floor. The 15.65 plate
# (R9-61) spanned the old 7 channel and stood 9.65 over the bar at the top
# rail, toward the latch hook.
LOCK_HEIGHT = 9.6
# 2026-10-11 (user): 1/16 in steel sheet, thickness as supplied: A36
# precision-ground sheet, McMaster-Carr 1388K196, 1/16 in -0.005 to +0.005 in
# (read live 2026-10-11; the family's +/-0.003 and +/-0.001 grades sit inside
# that band).  It replaced R9-31's machined 2.0 strip, whose slotted pan heads
# (MHA-PD-VN-60) stood too proud for the arm plate, and a 0.25 head spot face,
# which left no wall at the 3.5-from-edge holes.  The thickness prints .XXX
# under the sheet's own band, which the lock-station sweep and the screw's
# engagement spend, with LOCK_STOCK_CALLOUT above it.
LOCK_THICK = 1.5875  # extruded +Z
LOCK_THICK_BAND = 0.127  # +/-, native on Depth@Lock: the sheet's mill tolerance
LOCK_STOCK_SKU = "1388K196"
# One line: SolidWorks keeps a line-broken above-callout but never prints it
# (draw_pd_transgear_drive_collar; farm run 20261012T002237965Z here).
LOCK_STOCK_CALLOUT = "1/16 SHEET AS SUPPLIED"
# 2026-10-11 (user): the four plan corners are rounded, as the ch22 back photo
# (page001_img01) shows them: at its 3.60 px/mm platen scale (269.64 = 970 px)
# each plate's corner arcs span ~6.3 px, R ~1.75 (an upper bound: the JPEG's
# blur only widens them). R1.8 prints .X; with R under the holes' 3.5 offset
# from every edge, each hole sits outside its corner's R x R square, so its
# edge distances still run to the straight edges.
CORNER_R = 1.8

# Screw-hole layout on the guide-side band (matches the guide's hole pitch:
# the two stations sit x +-7 about the plate centre, on the rail's 2.5
# mid-line past the lip). R9-49: 1/8 DRILL (Ø3.175) over the #4-40 majors
# carries this plate's coordinate bands and the rail taps' Ø0.20 position
# (pd_vn_guide_lock_screw_spec.LOCK_SET_OFFSET); the #4 close Ø3.048 left too little.
HOLE_XY = ((4.0, RAIL_EDGE_LIP + 2.5), (18.0, RAIL_EDGE_LIP + 2.5))
HOLE_SPEC = HoleSpec("drilled_fractional", "1/8")
# ± on each printed hole coordinate (drawing-guidelines.md rule 5 (avoid excessive GD&T): no frame on this plate). Its
# radial reach, hypot(0.035, 0.035) = 0.0495, is what the set window spends.
HOLE_LOCATION_BAND = 0.035
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
# plate's back face carries the slotted pan heads past the hanger arm and arm
# plate, so the sheet's thickness prints .XXX under its ±0.127 mill band
# (LOCK_THICK_BAND). The height prints .X (±0.8): its least size still
# overlaps the bar (build_pd_paper_drive_assembly._assert_lock_retention) and
# its largest clears the latch hook and pivot spacer. The width prints .X:
# its +0.8 lengthens the overhang the skew swings
# (pd_vn_guide_lock_screw_spec.CORNER_OVERHANG_MAX). The corner radius prints .X
# (±0.8), shared by all four (4X).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LockProfile": {"Width": 1, "Height": 1},
    "Lock": {"Depth": 3},
    "ScrewHoles": {name: HOLE_LOCATION_PLACES for name in HOLE_LOCATION_DIMENSIONS},
    "Corners": {"CornerR": 1},
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
LIGAMENT_FLOOR = 1.5
_HOLE_R_MAX = (blind_cut_dia_mm(HOLE_SPEC) + drilled_oversize_mm()) / 2.0
_WIDTH_MIN = (
    LOCK_WIDTH
    + printed_deviations(LOCK_WIDTH, DRAWING_PRECISION["LockProfile"]["Width"])[0]
)
_HEIGHT_MIN = (
    LOCK_HEIGHT
    + printed_deviations(LOCK_HEIGHT, DRAWING_PRECISION["LockProfile"]["Height"])[0]
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
if min(HOLE_LIGAMENTS_WORST.values()) < LIGAMENT_FLOOR:
    raise AssertionError(
        f"guide-lock screw-hole ligaments {HOLE_LIGAMENTS_WORST} under {LIGAMENT_FLOOR}"
    )

# The rounded corners must not reach the holes: with each hole centre (at its
# printed worst case, from the nearest edges at their printed worst case)
# outside its corner's R x R square at the largest printed radius, the
# nearest boundary to every hole is a straight edge, so the ligaments above
# hold unchanged.
_CORNER_R_MAX = (
    CORNER_R + printed_deviations(CORNER_R, DRAWING_PRECISION["Corners"]["CornerR"])[1]
)
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
