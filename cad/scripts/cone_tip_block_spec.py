r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations

import _config
from _gtol_spec import PlanarFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl
from build_cone_tip_adjuster import CUP_DIA as SHAFT_PASSAGE_DIA


# Small black-steel clamp block on the swing platform that carries the axial
# end-play adjuster. See build_cone_tip_block.py for the derivation; this module
# is the drawing's single source of the marked dimensions.
BLOCK_X = 14.0  # plan width across the shaft
BLOCK_Z = 12.0  # plan depth along the shaft
# User-approved 2026-09-21 DFM correction: add only free material above the
# unchanged slit floor, and locate the pinch screw from the adjuster axis.
BLOCK_HEIGHT = 42.818
ADJUSTER_AXIS_HEIGHT = 33.368  # unchanged cone-shaft / adjuster axis
PINCH_RISE = 5.850
PINCH_RISE_TOLERANCE_MM = 0.05
PINCH_HEIGHT = ADJUSTER_AXIS_HEIGHT + PINCH_RISE
SLIT_FLOOR = 32.718
SLIT_W = 1.2
SLIT_DEPTH = BLOCK_HEIGHT - SLIT_FLOOR
ADJUSTER_THREAD = "5/16-18"  # blind tapped hole from the far (north) face
ADJUSTER_THREAD_DEPTH = 6.0  # full-form thread; leaves lead beyond usable thread
ADJUSTER_DEPTH = 8.0  # tap-drill shoulder
# Non-bearing clearance passage from the south face into the adjuster bore. Its
# diameter matches the already-defined adjuster cup, so the shaft tip has one
# continuous envelope without reviving the removed fictional journal fit.
PINCH_THREAD = "#4-40"  # cross-bore tapped hole that squeezes the top slit
ADJUSTER_BORE_SPEC = HoleSpec(
    "tapped",
    ADJUSTER_THREAD,
    end="blind",
    depth_mm=ADJUSTER_DEPTH,
    overrides_mm={"ThreadDepth": ADJUSTER_THREAD_DEPTH},
)
ADJUSTER_BORE_DIA = blind_cut_dia_mm(ADJUSTER_BORE_SPEC)
PINCH_BORE_SPEC = HoleSpec("tapped", PINCH_THREAD)
PINCH_BORE_DIA = blind_cut_dia_mm(PINCH_BORE_SPEC)
PINCH_CLEARANCE_SPEC = HoleSpec(
    "clearance",
    "#4",
    fit="normal",
    end="blind",
    depth_mm=(BLOCK_X - SLIT_W) / 2.0,
)
PINCH_CLEARANCE_DIA = blind_cut_dia_mm(PINCH_CLEARANCE_SPEC)

# Prove the approved stack against what the PRINT permits, not just nominal CAD.
# The title-block rows are the source of the absolute-height and drilled-hole
# bands; the functional inter-axis spacing carries its own native ±0.05 band.
_GENERAL_1PL_MM = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
_GENERAL_2PL_MM = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
_DRILLED_HOLE_PLUS_MM = float(
    str(_config.title_block("drilled_hole")["display_plus"]).lstrip("+")
)
MIN_TOP_LIGAMENT_MM = 0.50
MIN_CLEARANCE_TO_ADJUSTER_MM = 0.15
_worst_pinch_rise = round(PINCH_RISE, 2) - PINCH_RISE_TOLERANCE_MM
_worst_clearance_radius = (
    round(PINCH_CLEARANCE_DIA, 2) + _DRILLED_HOLE_PLUS_MM
) / 2.0
_adjuster_major_radius = THREAD_MAJOR_MM[ADJUSTER_THREAD] / 2.0
_pinch_major_radius = THREAD_MAJOR_MM[PINCH_THREAD] / 2.0
WORST_CLEARANCE_TO_ADJUSTER_MM = (
    _worst_pinch_rise - _worst_clearance_radius - _adjuster_major_radius
)
WORST_SCREW_ENVELOPE_GAP_MM = (
    _worst_pinch_rise - _pinch_major_radius - _adjuster_major_radius
)
_worst_pinch_height = (
    round(ADJUSTER_AXIS_HEIGHT, 2)
    + _GENERAL_2PL_MM
    + round(PINCH_RISE, 2)
    + PINCH_RISE_TOLERANCE_MM
)
WORST_TOP_LIGAMENT_MM = (
    round(BLOCK_HEIGHT, 1)
    - _GENERAL_1PL_MM
    - _worst_pinch_height
    - _worst_clearance_radius
)
_worst_adjuster_side_ligament = (
    round(BLOCK_X, 1)
    - _GENERAL_1PL_MM
    - (round(BLOCK_X / 2.0, 1) + _GENERAL_1PL_MM)
    - _adjuster_major_radius
)
_worst_pinch_depth_ligament = (
    round(BLOCK_Z, 1)
    - _GENERAL_1PL_MM
    - (round(BLOCK_Z / 2.0, 1) + _GENERAL_1PL_MM)
    - _worst_clearance_radius
)
MIN_SIDE_LIGAMENT_MM = 0.50
WORST_ADJUSTER_SIDE_LIGAMENT_MM = _worst_adjuster_side_ligament
WORST_PINCH_DEPTH_LIGAMENT_MM = _worst_pinch_depth_ligament
if WORST_CLEARANCE_TO_ADJUSTER_MM < MIN_CLEARANCE_TO_ADJUSTER_MM:
    raise AssertionError("pinch clearance envelope can cut the adjuster thread")
if WORST_SCREW_ENVELOPE_GAP_MM <= 0.0:
    raise AssertionError("pinch screw can collide with the installed adjuster")
if WORST_TOP_LIGAMENT_MM < MIN_TOP_LIGAMENT_MM:
    raise AssertionError("pinch clearance can break through the block top")
if WORST_ADJUSTER_SIDE_LIGAMENT_MM < MIN_SIDE_LIGAMENT_MM:
    raise AssertionError("general passage-centre band can break out an adjuster side")
if WORST_PINCH_DEPTH_LIGAMENT_MM < MIN_SIDE_LIGAMENT_MM:
    raise AssertionError("general pinch-depth band can break out a block side")

SURFACE_FINISHES = (
    # This face locates the adjuster block on the swing platform. Everything
    # else remains governed by the title-block CAST/MACHINED process row.
    SurfaceFinishControl("foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Depth"},
    "Block": {"BlockHt"},
    "PassageProfile": {"PassageDiaDim", "PassageZ"},
    "PassageCenterReference": {"PassageCenter"},
    "PinchDepthReference": {"PinchDepthCenter"},
    "PinchRiseReference": {"PinchRise"},
    "SlitProfile": {"SlitW"},
}

# Decimal places carry the general tolerance and therefore live on the model.
# PinchRise is the one critical locating interface and also carries a native
# explicit ±0.05 band; unrelated envelope dimensions retain loose grades.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"Width": 1, "Depth": 1},
    "Block": {"BlockHt": 1},
    "PassageProfile": {"PassageDiaDim": 2, "PassageZ": 2},
    "PassageCenterReference": {"PassageCenter": 1},
    "PinchDepthReference": {"PinchDepthCenter": 1},
    "PinchRiseReference": {"PinchRise": 2},
    "SlitProfile": {"SlitW": 2},
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a cone-tip-block drawing dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"DRAWING_PRECISION names unmarked {_feature} dimensions: {_unmarked}"
        )

DRAWING_NOTES = ""
