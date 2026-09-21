r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations

from _gtol_spec import PlanarFace
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl
from build_cone_tip_adjuster import CUP_DIA as SHAFT_PASSAGE_DIA


# Small black-steel clamp block on the swing platform that carries the axial
# end-play adjuster. See build_cone_tip_block.py for the derivation; this module
# is the drawing's single source of the marked dimensions.
BLOCK_X = 14.0  # plan width across the shaft
BLOCK_Z = 12.0  # plan depth along the shaft
BLOCK_HEIGHT = 40.718  # v2 post cascade: preserve the 1.000-mm crown above slit
ADJUSTER_AXIS_HEIGHT = 33.368  # coaxial with cone-pivot-post-v2 journal
ADJUSTER_THREAD = "5/16-18"  # blind tapped hole from the far (north) face
ADJUSTER_DEPTH = 8.0
# Non-bearing clearance passage from the south face into the adjuster bore. Its
# diameter matches the already-defined adjuster cup, so the shaft tip has one
# continuous envelope without reviving the removed fictional journal fit.
PINCH_THREAD = "#4-40"  # cross-bore tapped hole that squeezes the top slit
PINCH_HEIGHT = 38.918
SLIT_W = 1.2  # top clamp slit width
SLIT_DEPTH = 8.0  # slit cut down from the top face to 32.718
ADJUSTER_BORE_SPEC = HoleSpec(
    "tapped",
    ADJUSTER_THREAD,
    end="blind",
    depth_mm=ADJUSTER_DEPTH,
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

SURFACE_FINISHES = (
    # This face locates the adjuster block on the swing platform. Everything
    # else remains governed by the title-block CAST/MACHINED process row.
    SurfaceFinishControl("foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Depth"},
    "Block": {"BlockHt"},
    "PassageProfile": {"PassageDiaDim", "PassageZ"},
    "PinchBore": {"PinchZ"},
    "SlitProfile": {"SlitW"},
}

# Decimal places carry the general tolerance and therefore live on the model.
# Only the clamp slit needs hundredths to keep useful closing travel; the axis
# and clearance sizes use the ordinary two-place shop grade.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"Width": 1, "Depth": 1},
    "Block": {"BlockHt": 1},
    "PassageProfile": {"PassageDiaDim": 2, "PassageZ": 2},
    "PinchBore": {"PinchZ": 2},
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

DRAWING_NOTES = "\n".join(
    (
        "SHAFT PASSAGE IS CLEARANCE ONLY; NOT A BEARING SURFACE.",
        "PINCH SCREW CLEARS ENTRY JAW AND THREADS OPPOSITE JAW.",
        "ADJUSTER THREAD IS INTERRUPTED BY THE CLAMP SLOT.",
    )
)
