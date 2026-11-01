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

import _config
from _hole_spec import THREAD_MAJOR_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm, printed_deviations
from sh_column_clamp_back_geom import (  # noqa: F401
    BLOCK_DEPTH,
    DEPTH,
    GRIP_OFFSET,
    HOLE_SPEC,
    TAP_DRILL_DIA,
)
from sh_column_clamp_fit import (  # noqa: F401
    BORE_CLEARANCE_TEXT,
    BORE_DIAMETRAL_CLEARANCE,
    BORE_RADIUS_MAX,
    COLUMN_MATE,
    BACK_EAR_WANDER,
    BACK_DEPTH_PLACES,
    EAR_HOLE_CALLOUT_PLACES,
    EAR_HEIGHT_BAND,
    EAR_STATION_BAND,
    GRIP_GAP_MIN,
    GRIP_OFFSET_BAND,
    WALL_FLOOR,
    WALL_TARGET,
)
from sh_column_clamp_front_geom import (  # noqa: F401
    ARC_HEIGHT,
    ARC_WIDTH,
    COLUMN_BORE,
    EAR_HOLE_Z,
)

UNIT = drawing_unit("parts/sh-column-clamp-back", _config.parts("sh-column-clamp-back"))

FRONT_ARC_MATE = "MHA-SH-01"

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
# * GripOffset .020 +/-.004 (GRIP_OFFSET_BAND): the grip budget in
#   sh_column_clamp_fit; the face gap stays open at its least.
# * Depth .59 at the title block's .XX: the back wall (bore to back face) is
#   GripOffset + Depth less the largest seated bore radius (WALLS_WORST
#   below), and the tap's wander runs its deepest .60.
# * EarHole1Z .689 +/-.004 (EAR_STATION_BAND): the ear stations line up with
#   the front arc's clearance holes (sh_column_clamp_fit.SCREW_FLOAT).
# * BoreDia prints (Ø1.008) as a reference nominal under its matched
#   diametral-clearance acceptance on the column.
# * Width 1.89 and Height .63: outside sizes at the title block's .XX; the
#   walls below take their +/-.01.
# * AnchorZ prints as a reference (.945): half the width, the bore centred on
#   the block.  The walls charge each side face the .XX +/-.01 about it.
# * EarHoleHeight .315 +/-.004 (EAR_HEIGHT_BAND): the taps line up with the
#   front arc's clearance holes across the bar's height too
#   (sh_column_clamp_fit.EAR_SCREW_MISMATCH_MAX); the walls below take it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {
        "Depth": BACK_DEPTH_PLACES,
        "Width": 2,
        "GripOffset": 3,
        "AnchorZ": 3,
    },
    "Block": {"Height": 2},
    "BoreProfile": {"BoreDia": 3},
    "EarHoles": {"EarHole1Z": 3},
    "EarHeightReference": {"EarHoleHeight": 3},
}
# Reference dimensions: the bore's diameter "(Ø1.008)" and the AnchorZ
# distance, a plain "(.945)".
REFERENCE_DIMENSIONS = ("BoreDia",)
LINEAR_REFERENCE_DIMENSIONS = ("AnchorZ",)
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

# Worst-case walls (drawing-guidelines.md rule 17: .080 target, .060 floor).
_DEPTH_MIN = (
    BLOCK_DEPTH
    + printed_deviations(
        BLOCK_DEPTH, DRAWING_PRECISION["BlockProfile"]["Depth"], unit=UNIT
    )[0]
)
_WIDTH_MIN = (
    ARC_WIDTH
    + printed_deviations(
        ARC_WIDTH, DRAWING_PRECISION["BlockProfile"]["Width"], unit=UNIT
    )[0]
)
_ANCHOR_Z = ARC_WIDTH / 2.0
# The reference centre: the side faces stand the title block's .XX band off it.
_ANCHOR_BAND = printed_band_mm(2, unit=UNIT)
_ANCHOR_DEV = (-_ANCHOR_BAND, _ANCHOR_BAND)
_HEIGHT_MIN = (
    ARC_HEIGHT
    + printed_deviations(ARC_HEIGHT, DRAWING_PRECISION["Block"]["Height"], unit=UNIT)[0]
)
# The ear holes sit at mid-height, located from the bottom face by the
# model's EarHoleHeight at its band.
EAR_HOLE_HEIGHT = ARC_HEIGHT / 2.0
_EAR_HEIGHT_DEV = (-EAR_HEIGHT_BAND, EAR_HEIGHT_BAND)
# The tapped ear's thread major envelope, the one rule 17 judges.
THREAD_MAJOR_DIA = THREAD_MAJOR_MM[HOLE_SPEC.size]
# Its reach is the thread major's radius off the tap's wandered axis (the
# through tap wanders over the block's deepest printed Depth,
# sh_column_clamp_fit).
_EAR_REACH = THREAD_MAJOR_DIA / 2.0 + BACK_EAR_WANDER
_EAR_IN = EAR_HOLE_Z - EAR_STATION_BAND
_EAR_OUT = EAR_HOLE_Z + EAR_STATION_BAND
WALLS_WORST: dict[str, float] = {
    # Bore to back face, through the bore's deepest point.
    "back wall": (GRIP_OFFSET - GRIP_OFFSET_BAND) + _DEPTH_MIN - BORE_RADIUS_MAX,
    # Ear thread to the bore (the bore's widest point at the mating face is
    # within its radius of the axis).
    "ear to bore": _EAR_IN - _EAR_REACH - BORE_RADIUS_MAX,
    # Ear thread to the near side face (AnchorZ side) and the far one.
    "ear to near side": _ANCHOR_Z + _ANCHOR_DEV[0] - _EAR_OUT - _EAR_REACH,
    "ear to far side": _WIDTH_MIN
    - (_ANCHOR_Z + _ANCHOR_DEV[1])
    - _EAR_OUT
    - _EAR_REACH,
    # Ear thread to the bottom face it is located from, and to the top face.
    "ear to bottom face": EAR_HOLE_HEIGHT + _EAR_HEIGHT_DEV[0] - _EAR_REACH,
    "ear to top face": _HEIGHT_MIN
    - (EAR_HOLE_HEIGHT + _EAR_HEIGHT_DEV[1])
    - _EAR_REACH,
}
if min(WALLS_WORST.values()) < WALL_FLOOR:
    raise AssertionError(f"clamp-back walls {WALLS_WORST} under the {WALL_FLOOR} floor")
# drawing-guidelines.md rule 20: at the inch bands every wall meets the .080
# target, so the sheet states no shortfall (the back wall's sh-column-clamp-back
# RV-01, 1.9765 mm against the old 2.0, retired with ruling B3, 2026-10-31).
_SHORT_WALLS = {name for name, wall in WALLS_WORST.items() if wall < WALL_TARGET}
if _SHORT_WALLS:
    raise AssertionError(
        f"clamp-back walls under {WALL_TARGET}: {sorted(_SHORT_WALLS)}; none is "
        "declared (cad/config/parts/sh-column-clamp-back.yaml)"
    )

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
