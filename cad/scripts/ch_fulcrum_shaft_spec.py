r"""Pure-data dimensional contract shared by the fulcrum shaft, its drawing and
the channel assembly that places it.

The plain Ø6.35 steel shaft the top levers rock on. It runs full length at
one diameter (no journals, shoulders or steps) through the reamed bores of the
two end keepers (MHA-CH-007, ``ch_fulcrum_keeper_spec``); each end stands
END_PROUD past its keeper lug's outer face and finishes in a hemispherical
dome (the bright dome of the ch. 17 p. 40 photo). One set-screw flat per end,
both on +Y, sits under the keeper's crown tap on the lug mid-plane: the two
cup-point set screws (MHA-VN-055) bearing on them are the shaft's only axial
and rotational location.

Part frame: axis along Z, centred on z = 0 (the assembly places the origin at
ch_fulcrum_keeper_spec.FULCRUM_KEEPER_CENTRE_Z); the flats face +Y.
"""

from __future__ import annotations

from math import sqrt

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from ch_fulcrum_keeper_spec import (
    BORE_DIA,
    BORE_DIA_BAND,
    CROWN_DIA,
    KEEPER_Z_OFF,
    LUG_HALF_T,
    SET_SCREW_MIN_ENGAGEMENT_D,
    SET_SCREW_PITCH,
)
from vn_fulcrum_set_screw_spec import CUP_DIA as SET_SCREW_CUP_DIA
from vn_fulcrum_set_screw_spec import LENGTH as SET_SCREW_LENGTH
from vn_fulcrum_set_screw_spec import MAJOR_DIA as SET_SCREW_MAJOR_DIA
from vn_fulcrum_set_screw_spec import POINT_LENGTH as SET_SCREW_POINT_LENGTH

MM_PER_IN = 25.4

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_DIA_BAND = SHAFT_H
if SHAFT_DIA != BORE_DIA:
    raise AssertionError("fulcrum shaft and keeper bore nominals differ")
SHAFT_R = SHAFT_DIA / 2.0

# --- Length: cylindrical to END_PROUD past each keeper lug's outer face, then
# a full hemisphere (radius = shaft radius). ---
END_PROUD = 0.5
CYLINDER_HALF = KEEPER_Z_OFF + LUG_HALF_T + END_PROUD  # 77.5
DOME_R = SHAFT_R
SHAFT_LENGTH = 2.0 * (CYLINDER_HALF + DOME_R)  # 161.35 tip to tip

# --- Set-screw flats: one per end on +Y, centred on the keeper lug mid-plane
# (z = +-KEEPER_Z_OFF), so the crown tap's cup point lands mid-flat. ---
FLAT_PITCH = 2.0 * KEEPER_Z_OFF  # 148.0 like-edge to like-edge
FLAT_LENGTH = 3.5
FLAT_DEPTH = 0.3
ACROSS_FLAT = SHAFT_DIA - FLAT_DEPTH  # 6.05: the printed size
FLAT_HEIGHT = SHAFT_R - FLAT_DEPTH  # 2.875: the set screw's cup seat above the axis

# --- Worst case of the printed bands (policy rule 12; DRAWING_PRECISION
# below). ---
_BAND_BY_PLACES = {1: 0.8, 2: 0.51, 3: 0.13}
_FLAT_LENGTH_MIN = FLAT_LENGTH - _BAND_BY_PLACES[1]
_FLAT_DEPTH_MIN = FLAT_DEPTH - _BAND_BY_PLACES[3]  # AcrossFlat at its maximum
_SHAFT_R_MIN = (SHAFT_DIA + SHAFT_DIA_BAND[1]) / 2.0
# The shallowest flat must still be wider than the set screw's thread, so its
# cup burr lands on the flat and the shaft withdraws past the bore.
FLAT_CHORD_MIN = 2.0 * sqrt(2.0 * _SHAFT_R_MIN * _FLAT_DEPTH_MIN - _FLAT_DEPTH_MIN**2)
if FLAT_CHORD_MIN <= SET_SCREW_MAJOR_DIA:
    raise AssertionError(
        f"shallowest flat is {FLAT_CHORD_MIN:.3f} wide, under the set screw's "
        f"{SET_SCREW_MAJOR_DIA} major"
    )
# Axial play each cup may take from its flat centre and still bear wholly on
# the flat, at the shortest printed flat; the two keepers' tap spacing and
# FlatPitch together may use twice this.
FLAT_CUP_CAPTURE = (_FLAT_LENGTH_MIN - SET_SCREW_CUP_DIA) / 2.0
if FLAT_CUP_CAPTURE < _BAND_BY_PLACES[2]:
    raise AssertionError("the shortest flat cannot absorb the FlatPitch band")
# The longest flat stays inside its keeper lug, so a lever hub never rides it.
if FLAT_LENGTH + _BAND_BY_PLACES[1] > 2.0 * LUG_HALF_T:
    raise AssertionError("the longest set-screw flat runs out of the keeper lug")
if KEEPER_Z_OFF + FLAT_LENGTH / 2.0 >= CYLINDER_HALF:
    raise AssertionError("set-screw flat runs onto the domed end")

# Installed set screw (policy rule 12: >= 1.5D of FULL thread at the worst
# case). Heights are above the keeper bore axis: the set screw pulls the shaft
# down onto the bore wall, so its flat sits AcrossFlat - bore radius up. The
# tap's full thread runs from the bore top (plus the keeper spec's
# conservative bore sag) to the crown's least radius less its sag and one
# entry-chamfer pitch; the screw's full thread starts one cup chamfer above
# its seat on the flat.
_SCREW_HALF_MAJOR = SET_SCREW_MAJOR_DIA / 2.0


def _sag(radius: float) -> float:
    return radius - sqrt(radius**2 - _SCREW_HALF_MAJOR**2)


_CROWN_LEAST_R = (CROWN_DIA - _BAND_BY_PLACES[1]) / 2.0
_BORE_R_MAX = (BORE_DIA + BORE_DIA_BAND[0]) / 2.0
_BORE_R_MIN = (BORE_DIA + BORE_DIA_BAND[1]) / 2.0
_TAP_FULL_TOP = _CROWN_LEAST_R - _sag(_CROWN_LEAST_R) - SET_SCREW_PITCH
_TAP_FULL_BOTTOM = _BORE_R_MAX + _sag(_BORE_R_MAX)
_SEAT_LOW = ACROSS_FLAT - _BAND_BY_PLACES[3] - _BORE_R_MAX
_SEAT_HIGH = ACROSS_FLAT + _BAND_BY_PLACES[3] - _BORE_R_MIN
SET_SCREW_ENGAGEMENT_MM = min(
    min(_TAP_FULL_TOP, seat + SET_SCREW_LENGTH)
    - max(_TAP_FULL_BOTTOM, seat + SET_SCREW_POINT_LENGTH)
    for seat in (_SEAT_LOW, _SEAT_HIGH)
)
SET_SCREW_ENGAGEMENT_D = SET_SCREW_ENGAGEMENT_MM / SET_SCREW_MAJOR_DIA
if SET_SCREW_ENGAGEMENT_D < SET_SCREW_MIN_ENGAGEMENT_D:
    raise AssertionError(
        f"installed set screw engages {SET_SCREW_ENGAGEMENT_D:.2f}D of full "
        f"thread at the worst case (< {SET_SCREW_MIN_ENGAGEMENT_D}D)"
    )
# Socket face above the crown apex: below it at nominal, proud in free air at
# the worst case (Main ruling A, 2026-10-10; vn_fulcrum_set_screw_spec).
SET_SCREW_PROUD_NOMINAL = FLAT_HEIGHT + SET_SCREW_LENGTH - CROWN_DIA / 2.0
SET_SCREW_PROUD_WORST = _SEAT_HIGH + SET_SCREW_LENGTH - _CROWN_LEAST_R
if SET_SCREW_PROUD_NOMINAL >= 0.0 or SET_SCREW_PROUD_WORST > 0.4:
    raise AssertionError("set screw stands proud of the keeper crown past the ruling")

SURFACE_FINISHES = (
    SurfaceFinishControl("bearing", MACHINED_UM, CylinderFace(SHAFT_DIA)),
)

# One revolved half-profile carries the diameter and the tip-to-tip length;
# the flats' cut sketch carries their length, their like-edge pitch and the
# across-flat size (a construction line from the flat to the far O.D.).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia", "OverallLength"},
    "FlatProfile": {"FlatLength", "FlatPitch", "AcrossFlat"},
}
# Decimal places are the tolerance statement (policy rule 2); the model owns
# them. ShaftDia carries its SHAFT_H band natively; AcrossFlat at .XXX holds
# FLAT_CHORD_MIN above the set screw's major.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDia": 3, "OverallLength": 2},
    "FlatProfile": {"FlatLength": 1, "FlatPitch": 2, "AcrossFlat": 3},
}
if {
    feature: set(names) for feature, names in DRAWING_PRECISION.items()
} != DRAWING_DIMENSIONS:
    raise AssertionError(
        "DRAWING_PRECISION and DRAWING_DIMENSIONS must name the same dims"
    )

DRAWING_NOTES = "\n".join(
    (
        "BOTH ENDS FULL HEMISPHERE (R = SHAFT RADIUS).",
        "CENTRE MARKS 1.0 DEEP MAX.",
        "FLATS SEAT MHA-VN-055 SET SCREWS IN MHA-CH-007 KEEPERS.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
# The isometric renders at ISO_SCALE (1, 2) while the sheet/title block reads
# 1:1, so without this the pictorial is silently half scale -- the sheet's own
# title block would misstate it. Mirrors cylinder-gear-shaft, whose identical
# 1:2 iso carries the same note (codex #334).
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
