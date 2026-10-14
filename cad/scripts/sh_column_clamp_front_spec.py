r"""Column-clamp-front dimensional contract -- the single source of truth shared
by the part build (``build_sh_column_clamp_front.py``) and its manufacturing
drawing (``draw_sh_column_clamp_front.py``).

PURE DATA, no SolidWorks/COM imports (the ``<part>_spec.py`` split -- see
``dt_crank_arm_spec.py`` for the pattern rationale).  The geometry itself is cut by
the SHARED semi-arc builder (``_clamp_arc.build_arc``), while the part-owned
hole contract lives in ``sh_column_clamp_front_geom`` for reuse without drawing
dependencies, and the pair's fit budget in ``sh_column_clamp_fit``.  No frames
and no datums (drawing-guidelines.md rule 5; clamps are not on the
drawing-simplicity-policy.md allowlist): every location is a +/- from the bore
axis or a face, authored on the part.
"""

from __future__ import annotations

from _printed_tolerance import drilled_oversize_mm, printed_deviations

# Nominal geometry lives in the drawing-FREE ``sh_column_clamp_front_geom`` module so
# the assemblies can import ``ARC_DEPTH`` without pulling this file's drawing
# contract (marked-dimension map / places) into their build-recipe closure.
# Re-exported here unchanged for the drawing-side consumers and the lockstep test.
from sh_column_clamp_front_geom import (  # noqa: F401
    ARC_DEPTH,
    ARC_HEIGHT,
    ARC_WIDTH,
    BORE_RADIUS,
    COLUMN_BORE,
    EAR_HOLE_DIA,
    EAR_HOLE_SPEC,
    EAR_HOLE_Z,
    EAR_SPACING,
)
from sh_column_clamp_fit import (  # noqa: F401
    BORE_DIAMETRAL_CLEARANCE,
    BORE_RADIUS_MAX,
    COLUMN_MATE,
    EAR_STATION_BAND,
)

BACK_ARC_MATE = "MHA-SH-002"

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  ``build_sh_column_clamp_front`` marks exactly these;
# ``draw_sh_column_clamp_front`` keeps exactly their union across its per-view
# ``keep`` maps (the offline test enforces ``union(marks) == union(keeps)``).
# The block profile carries the depth from the mating face (on the bore axis)
# to the bar face, the overall width and the bore axis to one side face
# (AnchorZ); the ear holes' station from the bore axis prints once for both
# (EarHole1Z, "2X"; EarHole2Z shares its drive); their size ships as a native
# hole callout. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Depth", "Width", "AnchorZ"},
    "Block": {"Height"},
    "BoreProfile": {"BoreDia"},
    "EarHoles": {"EarHole1Z"},
}
EAR_STATION_DIMENSIONS = ("EarHole1Z", "EarHole2Z")

# Places and explicit bands on those dimensions.
# * Depth .XX: the bar face's station from the column axis sets the clamp
#   screws' thread engagement in the back arc (build_pd_paper_drive_assembly's
#   clamp stack).
# * EarHole1Z 17.5 +/-0.1 (EAR_STATION_BAND): the clearance holes line up
#   with the back arc's taps (sh_column_clamp_fit.SCREW_FLOAT).
# * BoreDia prints (Ø25.6) as a reference nominal under its matched
#   diametral-clearance acceptance on the column (sh_column_clamp_fit: the
#   grip budget spends at most 0.30 per bore).
# * Width, AnchorZ and Height are outside sizes at .X.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"Depth": 2, "Width": 1, "AnchorZ": 1},
    "Block": {"Height": 1},
    "BoreProfile": {"BoreDia": 1},
    "EarHoles": {"EarHole1Z": 1},
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
    raise AssertionError("every marked clamp-front dimension needs authored places")

# Worst-case walls (drawing-guidelines.md rule 17: 2.0 target, 1.5 floor).
WALL_TARGET = 2.0
_DEPTH_MIN = (
    ARC_DEPTH
    + printed_deviations(ARC_DEPTH, DRAWING_PRECISION["BlockProfile"]["Depth"])[0]
)
_WIDTH_MIN = (
    ARC_WIDTH
    + printed_deviations(ARC_WIDTH, DRAWING_PRECISION["BlockProfile"]["Width"])[0]
)
_ANCHOR_Z = ARC_WIDTH / 2.0
_ANCHOR_DEV = printed_deviations(
    _ANCHOR_Z, DRAWING_PRECISION["BlockProfile"]["AnchorZ"]
)
_HEIGHT_MIN = (
    ARC_HEIGHT + printed_deviations(ARC_HEIGHT, DRAWING_PRECISION["Block"]["Height"])[0]
)
# The ear holes sit at mid-height. The sheet locates them from the bottom face
# with a drawing dimension at the sheet's default two places (the placement
# sketch ties them to the bar's centre plane, which carries no dimension).
EAR_HOLE_HEIGHT = ARC_HEIGHT / 2.0
EAR_HOLE_HEIGHT_PLACES = 2
_EAR_HEIGHT_DEV = printed_deviations(EAR_HOLE_HEIGHT, EAR_HOLE_HEIGHT_PLACES)
# The largest accepted clearance hole (DRILLED HOLES row: +oversize / -0).
_EAR_HOLE_R_MAX = (EAR_HOLE_DIA + drilled_oversize_mm()) / 2.0
_EAR_IN = EAR_HOLE_Z - EAR_STATION_BAND
_EAR_OUT = EAR_HOLE_Z + EAR_STATION_BAND
WALLS_WORST: dict[str, float] = {
    # Bore to the bar face, through the bore's deepest point.
    "bar-face wall": _DEPTH_MIN - BORE_RADIUS_MAX,
    # Ear hole to the bore.
    "ear to bore": _EAR_IN - _EAR_HOLE_R_MAX - BORE_RADIUS_MAX,
    # Ear hole to the near side face (AnchorZ side) and the far one.
    "ear to near side": _ANCHOR_Z + _ANCHOR_DEV[0] - _EAR_OUT - _EAR_HOLE_R_MAX,
    "ear to far side": _WIDTH_MIN
    - (_ANCHOR_Z + _ANCHOR_DEV[1])
    - _EAR_OUT
    - _EAR_HOLE_R_MAX,
    # Ear hole to the bottom face it is located from, and to the top face.
    "ear to bottom face": EAR_HOLE_HEIGHT + _EAR_HEIGHT_DEV[0] - _EAR_HOLE_R_MAX,
    "ear to top face": _HEIGHT_MIN
    - (EAR_HOLE_HEIGHT + _EAR_HEIGHT_DEV[1])
    - _EAR_HOLE_R_MAX,
}
if min(WALLS_WORST.values()) < WALL_TARGET:
    raise AssertionError(f"clamp-front walls {WALLS_WORST} under {WALL_TARGET}")

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
