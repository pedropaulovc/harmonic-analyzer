r"""Pure-data dimensional contract shared by the arbor-pedestal part and drawing.

The marked-dimension map lives here so a change rebuilds both the SLDPRT and the
SLDDRW recipes from one source (see build_arbor_pedestal.py for the geometry).
"""

from __future__ import annotations
from math import sqrt

from _hole_spec import HoleSpec, blind_cut_dia_mm
from _gtol_spec import CylinderFace, PlanarFace
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl


MM_PER_IN = 25.4

# Black japanned gray-iron bearing post that clamps one end of the
# stationary cylinder arbor: a low rectangular foot flange, a tapered strap
# rising to a semicircular dome around the arbor clamp bore, and one #8
# hold-down hole through the outboard ledge (U34c: ch12 p.18 img09 shows a
# single slotted fillister centred on a flange about 18 long outboard of the
# strap root).
FOOT_WIDTH = 24.0  # X plan width of the foot flange
FOOT_DEPTH = 28.0  # Z plan depth of the foot flange: 10 strap + 18 ledge
FOOT_HEIGHT = 5.0  # low flange height under the strap
STRAP_T = 10.0  # strap depth; far face is coplanar with the foot far face
# Local Z stations. The part origin sits in the strap band, and the band never
# moved when U34c grew the foot outboard, so every station hangs off the
# strap's INNER face -- the one the end disc runs against and the foot's far
# face is flush with. The drive train anchors each pedestal on that face.
STRAP_INNER_Z = 8.0  # strap inner face = foot far face (local +Z)
STRAP_ROOT_Z = STRAP_INNER_Z - STRAP_T  # strap outer face / ledge root, -2
FOOT_NEAR_Z = STRAP_INNER_Z - FOOT_DEPTH  # outboard end of the ledge, -20
FOOT_MID_Z = (STRAP_INNER_Z + FOOT_NEAR_Z) / 2.0  # plan centre of the foot, -6
LEDGE_DEPTH = FOOT_DEPTH - STRAP_T  # exposed hold-down ledge, 18
TOP_RADIUS = 10.0  # dome radius = strap half-width at the top
BORE_DIA = 9.55  # finished running bore for the 3/8 in cylinder-arbor journal
BORE_DIA_BAND = (0.03, 0.0)  # 9.550–9.580 mm running-bore limits
BORE_HEIGHT = 39.718  # v2 post journal axis: 6.35 platform + 33.368 boss height
_ROOT_HALF_WIDTH = FOOT_WIDTH / 2.0
_CENTER_RISE = BORE_HEIGHT - FOOT_HEIGHT
_TANGENT_DISC = sqrt(_ROOT_HALF_WIDTH**2 + _CENTER_RISE**2 - TOP_RADIUS**2)
_TANGENT_DENOM = _ROOT_HALF_WIDTH**2 + _CENTER_RISE**2
TAPER_TANGENT_X = (
    TOP_RADIUS**2 * _ROOT_HALF_WIDTH + TOP_RADIUS * _CENTER_RISE * _TANGENT_DISC
) / _TANGENT_DENOM
TAPER_TANGENT_Y = (
    BORE_HEIGHT
    + (-(TOP_RADIUS**2) * _CENTER_RISE + TOP_RADIUS * _ROOT_HALF_WIDTH * _TANGENT_DISC)
    / _TANGENT_DENOM
)
# #8 close clearance (Ø4.572, 0.180 in) for the MHA-143 #8-32 fillister. The
# base seat is transfer-punched through this hole at assembly, so the close
# fit keeps an 11/64 punch centred to about 0.1 while the Ø6.86 head still
# bears on a 1.1 annulus.
SCREW_HOLE_SPEC = HoleSpec("clearance", "#8", fit="close")
SCREW_HOLE_DIA = blind_cut_dia_mm(SCREW_HOLE_SPEC)
# Hold-down hole centre, local z: centred on the 18 ledge, 9 outboard of the
# strap root (machine -91.652 south / +94.202 north). Shared, because the
# plan view dimensions the hole from the strap inner face and must not
# restate the number.
SCREW_Z = STRAP_ROOT_Z - LEDGE_DEPTH / 2.0

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "arbor_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=BORE_HEIGHT),
    ),
    # The foot seat mates the pedestal to harmonic-base: on a part that may be
    # left as-cast elsewhere, the one face that MUST be cut says so.
    SurfaceFinishControl("foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
)

# Hidden reference sketches (#810 Codex l4afp, policy rule 2): the strap band,
# the hold-down hole's station off the foot's far face and both lateral
# locations off the west side face are manufacturing dimensions under the
# .X band, yet no feature dimension measures them -- the strap band is an
# offset extrude, the hole is placed from the origin in the strap band and the
# profiles are X-centred. Each therefore gets a one-line construction sketch,
# lying on the part outline so it prints no line of its own, whose single
# driving dimension IS the value, equation-bound to the same globals the
# features use. The part saves them blanked; the drawing shows each in the one
# view that dimensions it (_drawing_hidden_sketches.curate_view_dimensions).
REFERENCE_SKETCHES = (
    "StrapDepthReference",
    "HoldDownReference",
    "HoleLateralReference",
    "BoreLateralReference",
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FootProfile": {"Width", "Depth"},
    "Foot": {"FootHt"},
    # BoreHeight plus a concentric R10 crown and tangent sides defines the
    # complete upright profile without redundant endpoint widths.
    "BoreProfile": {"BoreDia", "BoreHeight"},
    "StrapDepthReference": {"StrapDepth"},
    "HoldDownReference": {"HoldDownLocation"},
    "HoleLateralReference": {"HoleLateral"},
    "BoreLateralReference": {"BoreLateral"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity policy rule
# 2), so the MODEL owns them: build_arbor_pedestal applies this map to the
# .SLDPRT and draw_arbor_pedestal only reads it back.  The foot envelope and
# flange height are round nominals under the title block's general .X band.
# The bore takes two places for two different reasons: its diameter carries
# its OWN running-fit band (BORE_DIA_BAND), and the journal-axis height is a
# derived 39.718 that one place would misstate by 0.018 mm.  Neither is a
# third decimal: cad/docs/tolerance-policy.md reserves those for the size
# limits of a mating bore/shaft pair, and this post's axis height perturbs no
# transfer quantity, so it stays on the general grade with no band of its own.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FootProfile": {"Width": 1, "Depth": 1},
    "Foot": {"FootHt": 1},
    "BoreProfile": {"BoreDia": 2, "BoreHeight": 2},
    "StrapDepthReference": {"StrapDepth": 1},
    # One place (.X, ±0.8): the base seat is transferred from this hole at
    # assembly, so its location only has to keep the webs, and the U27 worst
    # case at ±0.8 still leaves 5.0 to the strap root and to the ledge end.
    "HoldDownReference": {"HoldDownLocation": 1},
    # Both lateral locations run off the foot's west side face (policy rule 7:
    # an origin is a feature, not the symmetry axis). One place: the drum x is
    # set with the arbor itself at assembly (DRO edge-find), so neither hole's
    # side offset feeds a fit, and the crown is concentric with the bore.
    "HoleLateralReference": {"HoleLateral": 1},
    "BoreLateralReference": {"BoreLateral": 1},
}

# Places for the two dimensions the SHEET still derives, keyed by the recipe's
# own label: the parenthesised overall height (a band-free restatement of the
# axis height plus the crown) and the crown radius, which restates the dome
# boss's model diameter as the radius a print gives an arc.  Those places are
# still specification, so the spec owns the digit and the sheet passes it
# through instead of writing a literal.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    # Two places, like the axis height it is the sum of: a one-place (49.7)
    # next to 39.72 + R10.0 reads as an arithmetic error on the print.
    "overall height": 2,
    "crown radius": 1,
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
if any(
    name not in {name for names in DRAWING_PRECISION.values() for name in names}
    for names in DRAWING_DIMENSIONS.values()
    for name in names
):
    raise AssertionError("a marked dimension prints without part-authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")
