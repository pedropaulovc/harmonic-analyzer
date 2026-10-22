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

from _printed_drilled_tolerance import drilled_oversize_mm
from _printed_tolerance import printed_deviations

# Part-owned bore and ear geometry remains separate from the shared seating
# depths, so bar consumers need neither this drawing contract nor that geometry.
from _column_clamp_interface import ARC_DEPTH
from sh_column_clamp_front_geom import (  # noqa: F401
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
    DEPTH_PLACES,
    EAR_HOLE_CALLOUT_PLACES,
    FRONT_EAR_WANDER,
    EAR_HEIGHT_BAND,
    EAR_STATION_BAND,
    NOTE_PLACES,
    SCREW_LINE_SHORTFALL,
    WALL_FLOOR,
    WALL_TARGET,
    stated_max,
    stated_min,
)

BACK_ARC_MATE = "MHA-SH-02"

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  ``build_sh_column_clamp_front`` marks exactly these;
# ``draw_sh_column_clamp_front`` keeps exactly their union across its per-view
# ``keep`` maps (the offline test enforces ``union(marks) == union(keeps)``).
# The block profile carries the depth from the mating face (on the bore axis)
# to the bar face, the overall width and the bore axis to one side face
# (AnchorZ); the ear holes' station from the bore axis prints once for both
# (EarHole1Z, "2X"; EarHole2Z shares its drive); their size ships as a native
# hole callout; their shared height off the bottom face prints once for both
# from the hidden EarHeightReference sketch (_clamp_arc.EAR_HEIGHT_LINE: both
# ear centres hold the centre plane its top end shares). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Depth", "Width", "AnchorZ"},
    "Block": {"Height"},
    "BoreProfile": {"BoreDia"},
    "EarHoles": {"EarHole1Z"},
    "EarHeightReference": {"EarHoleHeight"},
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
# * EarHoleHeight 8.0 +/-0.1 (EAR_HEIGHT_BAND): the clearance holes line up
#   with the back arc's taps across the bar's height too
#   (sh_column_clamp_fit.EAR_SCREW_MISMATCH_MAX); the walls below take it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"Depth": DEPTH_PLACES, "Width": 1, "AnchorZ": 1},
    "Block": {"Height": 1},
    "BoreProfile": {"BoreDia": 1},
    "EarHoles": {"EarHole1Z": 1},
    "EarHeightReference": {"EarHoleHeight": 1},
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
# The ear holes sit at mid-height, located from the bottom face by the
# model's EarHoleHeight at its band.
EAR_HOLE_HEIGHT = ARC_HEIGHT / 2.0
_EAR_HEIGHT_DEV = (-EAR_HEIGHT_BAND, EAR_HEIGHT_BAND)
# The largest accepted clearance hole: the Hole Wizard callout prints its
# diameter at two places (Ø4.98), checked on the DRILLED HOLES row (+0.10/-0).
_EAR_HOLE_R_MAX = (
    EAR_HOLE_DIA
    + printed_deviations(
        EAR_HOLE_DIA, EAR_HOLE_CALLOUT_PLACES, (0.0, drilled_oversize_mm())
    )[1]
) / 2.0
# The hole's reach: its largest radius off its wandered axis (the through
# hole wanders over the arc's deepest printed Depth, sh_column_clamp_fit).
_EAR_REACH = _EAR_HOLE_R_MAX + FRONT_EAR_WANDER
_EAR_IN = EAR_HOLE_Z - EAR_STATION_BAND
_EAR_OUT = EAR_HOLE_Z + EAR_STATION_BAND
WALLS_WORST: dict[str, float] = {
    # Bore to the bar face, through the bore's deepest point.
    "bar-face wall": _DEPTH_MIN - BORE_RADIUS_MAX,
    # Ear hole to the bore.
    "ear to bore": _EAR_IN - _EAR_REACH - BORE_RADIUS_MAX,
    # Ear hole to the near side face (AnchorZ side) and the far one.
    "ear to near side": _ANCHOR_Z + _ANCHOR_DEV[0] - _EAR_OUT - _EAR_REACH,
    "ear to far side": _WIDTH_MIN
    - (_ANCHOR_Z + _ANCHOR_DEV[1])
    - _EAR_OUT
    - _EAR_REACH,
    # Ear hole to the bottom face it is located from, and to the top face.
    "ear to bottom face": EAR_HOLE_HEIGHT + _EAR_HEIGHT_DEV[0] - _EAR_REACH,
    "ear to top face": _HEIGHT_MIN
    - (EAR_HOLE_HEIGHT + _EAR_HEIGHT_DEV[1])
    - _EAR_REACH,
}
if min(WALLS_WORST.values()) < WALL_FLOOR:
    raise AssertionError(
        f"clamp-front walls {WALLS_WORST} under the {WALL_FLOOR} floor"
    )
# drawing-guidelines.md rule 20: walls between the floor and the target.  The
# ear-to-bore web on the largest A513 column with drill wander, ruled at 1.850
# on the 17.9 arc and 1.853 on the 17.4 arc (whose shorter hole wanders
# less), is the only one and the part's least wall: it would need a column of
# at most 25.23 -- under its own nominal -- to reach 2.0.  Owner-ruled
# shortfall, declared as sh-column-clamp-front RV-01
# (cad/config/parts/sh-column-clamp-front.yaml) and stated by EAR_WALL_NOTE;
# any other wall falling short needs its own.
_SHORT_WALLS = {name for name, wall in WALLS_WORST.items() if wall < WALL_TARGET}
if _SHORT_WALLS != {"ear to bore"} or WALLS_WORST["ear to bore"] != min(
    WALLS_WORST.values()
):
    raise AssertionError(
        f"clamp-front walls under {WALL_TARGET}: {sorted(_SHORT_WALLS)}; only the "
        "ear-to-bore web is declared (sh-column-clamp-front RV-01)"
    )
EAR_WALL_MIN = stated_min(WALLS_WORST["ear to bore"])  # 1.85
# sh-column-clamp-front RV-01
EAR_WALL_NOTE = f"MIN EAR WALL {EAR_WALL_MIN:.{NOTE_PLACES}f}"
# The screw line (sh_column_clamp_fit): the worst ear-to-tap offset passes the
# #8 screw's radial clearance in this sheet's hole, rounded up.
SCREW_LINE_SHORT_MAX = stated_max(SCREW_LINE_SHORTFALL)  # 0.06
# sh-column-clamp-front RV-02
SCREW_LINE_NOTE = (
    f"EAR TO {BACK_ARC_MATE} TAP OFFSET UP TO "
    f"{SCREW_LINE_SHORT_MAX:.{NOTE_PLACES}f} OVER #8 SCREW CLEARANCE"
)
DRAWING_NOTES = "\n".join((f"1. {EAR_WALL_NOTE}.", f"2. {SCREW_LINE_NOTE}."))

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
