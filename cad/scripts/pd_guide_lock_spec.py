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
from _inch import inch
from pd_platen_guide_spec import GUIDE_HEIGHT, LOCK_SCREW_DX
from _printed_tolerance import drilled_oversize_mm, printed_deviations

# --- Nominal geometry (book ch. 22, pp. 54-55; see build_pd_guide_lock.py for the
# bottom-station height derivation). These drive the part's named equation
# globals AND the drawing's coordinate math. ---
LOCK_WIDTH = inch(7, 8)  # along +X
# R9-59: the plate laps RAIL_EDGE_LIP past the rail's outer edge, so its screw
# holes, on the rail's mid-line, stand lip + 3/32 from the guide-side edge and
# keep the 1.5 ligament at the printed worst case (2.5 left 0.81). 1/32: the
# 1/16 grid moves this sub-1/4 lip 59%; at 1/32 the guide-side ligament is
# 1.5025 against the 1.5 floor.
RAIL_EDGE_LIP = inch(1, 32)
# Along +Y; y = 0 is the guide-side edge. One plate serves both rails
# (user ruling 2026-10-11): 1/32 lip + 3/16 rail + bar overlap. The 1-1/8
# bar fills the channel to a 1/32 running clearance over the bottom rail
# (pd_support_bar_spec.BAR_HEIGHT), so the plate overlaps the bar 5/32 at the
# top rail (which hangs on it) and 1/8 at the bottom rail. It prints at the
# general .X, as 9.6 did (Codex P1 on #1353: a tighter .XX needed a
# design-intent note, which drawing-guidelines.md rule 7 (notes: few,
# flagged, never a method) bars). The 15.65 plate (R9-61) spanned the old 7
# channel and stood 9.65 over the bar at the top rail, toward the latch hook.
LOCK_HEIGHT = inch(3, 8)
# 2026-10-11 (user): steel sheet, thickness as supplied, under the
# tight-tolerance low-carbon sheet's -0.005 to +0.005 in band (McMaster-Carr
# 1388K196 was the 1/16 in sheet, read live 2026-10-11).  It replaced R9-31's
# machined 2.0 strip, whose slotted pan heads (MHA-VN-046) stood too proud for
# the arm plate, and a 0.25 head spot face, which left no wall at the
# 3.5-from-edge holes.  All-inch: .040 in, not 1/16: the 7/16 rail behind the
# 3/8 bar stands the plates 0.3125 farther back, and on 1/16 sheet the
# slotted pan heads sweep into the hanger arm plate (lock-station sweep).
# The .040 sheet's SKU is not yet selected (no live catalogue read).  The
# thickness prints .XXX under the sheet's own band, which the lock-station
# sweep and the screw's engagement spend, with LOCK_STOCK_CALLOUT above it.
LOCK_THICK = inch(0.040)  # extruded +Z
LOCK_THICK_BAND = 0.127  # +/-, native on Depth@Lock: the sheet's mill tolerance
LOCK_STOCK_SKU = None  # .040 tight-tolerance sheet: SKU not yet selected
# One line: SolidWorks keeps a line-broken above-callout but never prints it
# (draw_pd_transgear_drive_collar; farm run 20261012T002237965Z here).
LOCK_STOCK_CALLOUT = ".040 SHEET AS SUPPLIED"
# 2026-10-11 (user): the four plan corners are rounded, as the ch22 back photo
# (page001_img01) shows them: at its 3.60 px/mm platen scale (269.64 = 970 px)
# each plate's corner arcs span ~6.3 px, R ~1.75 (an upper bound: the JPEG's
# blur only widens them). R1/16 prints .X; with R under the holes' offset
# from every edge, each hole sits outside its corner's R x R square, so its
# edge distances still run to the straight edges.
CORNER_R = inch(1, 16)

# Screw-hole layout on the guide-side band (matches the guide's hole pitch:
# the two stations sit x +-LOCK_SCREW_DX (1/4) about the plate centre, on the
# rail's mid-line past the lip): 3/16 from each side edge. R9-49: 1/8 DRILL
# (Ø3.175) over the #4-40 majors carries this plate's coordinate bands and
# the rail taps' Ø0.20 position (vn_guide_lock_screw_spec.LOCK_SET_OFFSET);
# the #4 close Ø3.048 left too little.
_HOLE_Y = RAIL_EDGE_LIP + GUIDE_HEIGHT / 2.0
HOLE_XY = (
    (LOCK_WIDTH / 2.0 - LOCK_SCREW_DX, _HOLE_Y),
    (LOCK_WIDTH / 2.0 + LOCK_SCREW_DX, _HOLE_Y),
)
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
# (vn_guide_lock_screw_spec.CORNER_OVERHANG_MAX). The corner radius prints .X
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
