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
# R9-61: 15.65 along +Y; y = 0 is the guide-side edge. The 2026-09-02 user
# re-read of ch22 p.54 gives a LOW lock (1 lip + 5 rail + 7 channel + 3 bar
# overlap = 16); only the spacer-side edge came in, by 0.35, so the set and
# skewed plate clears the floating pivot spacer, and the bottom station
# overlaps the bar 2.65 (2.15 at the -0.50 band).
LOCK_HEIGHT = 15.65
LOCK_THICK = 2.0  # extruded +Z

# Screw-hole layout on the guide-side band (matches the guide's hole pitch:
# the two stations sit x +-7 about the plate centre, on the rail's 2.5
# mid-line past the lip). R9-49: 1/8 DRILL (Ø3.175) over the #4-40 majors
# carries this plate's coordinate bands and the rail taps' Ø0.20 position
# (vn_guide_lock_screw_spec.LOCK_SET_OFFSET); the #4 close Ø3.048 left too little.
HOLE_XY = ((4.0, RAIL_EDGE_LIP + 2.5), (18.0, RAIL_EDGE_LIP + 2.5))
HOLE_SPEC = HoleSpec("drilled_fractional", "1/8")
# ± on each printed hole coordinate (rule 3: no frame on this plate). Its
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
}
HOLE_LOCATION_DIMENSIONS = DRAWING_DIMENSIONS["ScrewHoles"]

# Places and explicit bands the print carries on those dimensions, the ones the
# paper-drive lock-station sweep judges the plate at (policy rule 12). Each
# plate's far edge passes 0.142 from the floating pivot spacer, set and skewed
# on its screws (R9-61), and its back face carries the button heads past the
# hanger arm and arm plate. So the height never runs over 15.65 (+0/-0.50),
# and the strip thickness prints .XXX (±0.13; at .XX the heads reach the arm
# plate). The width prints .X: its +0.8 lengthens the overhang the skew swings
# (vn_guide_lock_screw_spec.CORNER_OVERHANG_MAX).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LockProfile": {"Width": 1, "Height": 2},
    "Lock": {"Depth": 3},
    "ScrewHoles": {name: HOLE_LOCATION_PLACES for name in HOLE_LOCATION_DIMENSIONS},
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
LOCK_HEIGHT_BAND = (0.0, -0.50)  # (upper, lower), native on Height

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
_HEIGHT_MIN = LOCK_HEIGHT + LOCK_HEIGHT_BAND[1]
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

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
