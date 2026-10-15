r"""Column-clamp-back dimensional contract -- the single source of truth shared
by the part build (``build_sh_column_clamp_back.py``) and its manufacturing
drawing (``draw_sh_column_clamp_back.py``).

PURE DATA, no SolidWorks/COM imports.  The geometry is cut by the shared
semi-arc builder (``_clamp_arc.build_arc``); the drawing-free nominals live in
``sh_column_clamp_back_geom`` and the pair's fit budget in
``sh_column_clamp_fit``.  No frames and no datums (drawing-guidelines.md rule
5; clamps are not on the drawing-simplicity-policy.md allowlist): every
location is a +/- from the bore axis or a face, authored on the part.
"""

from __future__ import annotations

from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_deviations
from sh_column_clamp_back_geom import (  # noqa: F401
    BLOCK_DEPTH,
    DEPTH,
    GRIP_OFFSET,
    HOLE_SPEC,
    TAP_DRILL_DIA,
)
from sh_column_clamp_fit import (  # noqa: F401
    BORE_DIAMETRAL_CLEARANCE,
    BORE_RADIUS_MAX,
    COLUMN_MATE,
    EAR_STATION_BAND,
    GRIP_GAP_MIN,
    GRIP_OFFSET_BAND,
)
from sh_column_clamp_front_geom import (  # noqa: F401
    ARC_HEIGHT,
    ARC_WIDTH,
    COLUMN_BORE,
    EAR_HOLE_Z,
)

FRONT_ARC_MATE = "MHA-SH-001"

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  ``build_sh_column_clamp_back`` marks exactly these;
# ``draw_sh_column_clamp_back`` keeps exactly their union across its per-view
# keep maps.  The block profile carries the mating face's offset from the bore
# axis (GripOffset), the block depth from the mating face (Depth), the overall
# width and the bore axis to one side face (AnchorZ); the ear holes' station
# from the bore axis prints once for both (EarHole1Z, "2X"; EarHole2Z shares
# its drive); their size and thread ship as a native hole callout; their
# shared height off the bottom face prints once for both from the hidden
# EarHeightReference sketch (_clamp_arc.EAR_HEIGHT_LINE: both ear centres hold
# the centre plane its top end shares). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Depth", "Width", "GripOffset", "AnchorZ"},
    "Block": {"Height"},
    "BoreProfile": {"BoreDia"},
    "EarHoles": {"EarHole1Z"},
    "EarHeightReference": {"EarHoleHeight"},
}
EAR_STATION_DIMENSIONS = ("EarHole1Z", "EarHole2Z")

# Places and explicit bands on those dimensions.
# * GripOffset 0.5 +/-0.1 (GRIP_OFFSET_BAND): the grip budget in
#   sh_column_clamp_fit; the face gap stays open at its least.
# * Depth .XX: the back wall (bore to back face) is GripOffset + Depth less
#   the largest seated bore radius, BACK_WALL_MIN below.
# * EarHole1Z 17.5 +/-0.1 (EAR_STATION_BAND): the ear stations line up with
#   the front arc's clearance holes (sh_column_clamp_fit.SCREW_FLOAT).
# * BoreDia prints (Ø25.6) as a reference nominal under its matched
#   diametral-clearance acceptance on the column.
# * Width, AnchorZ and Height are outside sizes at .X.
# * EarHoleHeight .XX: the taps line up with the front arc's clearance holes
#   across the bar's height too; the walls below take its printed band.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"Depth": 2, "Width": 1, "GripOffset": 1, "AnchorZ": 1},
    "Block": {"Height": 1},
    "BoreProfile": {"BoreDia": 1},
    "EarHoles": {"EarHole1Z": 1},
    "EarHeightReference": {"EarHoleHeight": 2},
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
    raise AssertionError("every marked clamp-back dimension needs authored places")

# Worst-case walls (drawing-guidelines.md rule 17: 2.0 target, 1.5 floor).
WALL_TARGET = 2.0
_DEPTH_MIN = (
    BLOCK_DEPTH
    + printed_deviations(BLOCK_DEPTH, DRAWING_PRECISION["BlockProfile"]["Depth"])[0]
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
# model's EarHoleHeight at its authored places.
EAR_HOLE_HEIGHT = ARC_HEIGHT / 2.0
_EAR_HEIGHT_DEV = printed_deviations(
    EAR_HOLE_HEIGHT, DRAWING_PRECISION["EarHeightReference"]["EarHoleHeight"]
)
# The tapped ear's thread major envelope, the one rule 17 judges.
THREAD_MAJOR_DIA = THREAD_MAJOR_MM[HOLE_SPEC.size]
_EAR_IN = EAR_HOLE_Z - EAR_STATION_BAND
_EAR_OUT = EAR_HOLE_Z + EAR_STATION_BAND
WALLS_WORST: dict[str, float] = {
    # Bore to back face, through the bore's deepest point.
    "back wall": (GRIP_OFFSET - GRIP_OFFSET_BAND) + _DEPTH_MIN - BORE_RADIUS_MAX,
    # Ear thread to the bore (the bore's widest point at the mating face is
    # within its radius of the axis).
    "ear to bore": _EAR_IN - THREAD_MAJOR_DIA / 2.0 - BORE_RADIUS_MAX,
    # Ear thread to the near side face (AnchorZ side) and the far one.
    "ear to near side": _ANCHOR_Z + _ANCHOR_DEV[0] - _EAR_OUT - THREAD_MAJOR_DIA / 2.0,
    "ear to far side": _WIDTH_MIN
    - (_ANCHOR_Z + _ANCHOR_DEV[1])
    - _EAR_OUT
    - THREAD_MAJOR_DIA / 2.0,
    # Ear thread to the bottom face it is located from, and to the top face.
    "ear to bottom face": EAR_HOLE_HEIGHT + _EAR_HEIGHT_DEV[0] - THREAD_MAJOR_DIA / 2.0,
    "ear to top face": _HEIGHT_MIN
    - (EAR_HOLE_HEIGHT + _EAR_HEIGHT_DEV[1])
    - THREAD_MAJOR_DIA / 2.0,
}
if min(WALLS_WORST.values()) < WALL_TARGET:
    raise AssertionError(f"clamp-back walls {WALLS_WORST} under {WALL_TARGET}")
BACK_WALL_MIN = WALLS_WORST["back wall"]

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
