r"""Pure-data dimensional contract shared by the arbor-pedestal part and drawing.

The marked-dimension map lives here so a change rebuilds both the SLDPRT and the
SLDDRW recipes from one source (see build_dt_arbor_pedestal.py for the geometry).
"""

from __future__ import annotations
from math import sqrt

import _config
from _fit_ream_slide import REAM_SLIDE
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _hole_spec import HoleSpec, THREAD_MAJOR_MM, blind_cut_dia_mm
from _printed_tolerance import printed_band_mm
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl
from sh_vn_arbor_set_screw_spec import THREAD as SET_SCREW_THREAD
from _cone_axis_constants import CONE_AXIS_HEIGHT_MM, PLATFORM_THICKNESS_MM


MM_PER_IN = 25.4
# #290: the registry row's drawing_unit (in) is this sheet's unit.  Every
# printed nominal below is the exact millimetre value of its inch print.
UNIT = drawing_unit("parts/dt-arbor-pedestal", _config.parts("dt-arbor-pedestal"))

# Black japanned gray-iron bearing post that clamps one end of the
# stationary cylinder arbor: a low rectangular foot flange, a tapered strap
# rising to a semicircular dome around the arbor clamp bore, and one #8
# hold-down hole through the outboard ledge (U34c: ch12 p.18 img09 shows a
# single slotted fillister centred on a flange about 18 long outboard of the
# strap root).
FOOT_WIDTH = 23.876  # .94, X plan width of the foot flange
FOOT_DEPTH = 27.94  # 1.10, Z plan depth of the foot flange: .40 strap + .70 ledge
FOOT_HEIGHT = 5.08  # .20, low flange height under the strap
STRAP_T = 10.16  # .40, strap depth; far face is coplanar with the foot far face
# Local Z stations. The part origin sits in the strap band, and the band never
# moved when U34c grew the foot outboard, so every station hangs off the
# strap's INNER face -- the one the end disc runs against and the foot's far
# face is flush with. The drive train anchors each pedestal on that face.
STRAP_INNER_Z = 8.0  # strap inner face = foot far face (local +Z)
STRAP_ROOT_Z = STRAP_INNER_Z - STRAP_T  # strap outer face / ledge root, -2
FOOT_NEAR_Z = STRAP_INNER_Z - FOOT_DEPTH  # outboard end of the ledge
FOOT_MID_Z = (STRAP_INNER_Z + FOOT_NEAR_Z) / 2.0  # plan centre of the foot
LEDGE_DEPTH = FOOT_DEPTH - STRAP_T  # exposed hold-down ledge, .70
# Dome radius = strap half-width at the top. R.43, not the photographed R10:
# the crown carries the MHA-DT-VN-64 apex set screw (#743, below), and only
# about R11 leaves it 1.5D of full thread at the printed worst case.
TOP_RADIUS = 10.922  # .43
# Finished running bore for the 3/8 in cylinder-arbor journal: REAM_SLIDE,
# .3760-.3765 in, cut by the owned .3760 over reamer.
BORE_DIA = 9.525
BORE_DIA_BAND = REAM_SLIDE
BORE_HEIGHT = PLATFORM_THICKNESS_MM + CONE_AXIS_HEIGHT_MM
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
# #8 close clearance (Ø.180) for the MHA-DT-VN-62 #8-32 fillister. The base
# seat is transfer-punched through this hole at assembly, so the close fit
# keeps an 11/64 punch centred to about .004 while the Ø.270 head still bears
# on a .045 annulus.
SCREW_HOLE_SPEC = HoleSpec("clearance", "#8", fit="close")
SCREW_HOLE_DIA = blind_cut_dia_mm(SCREW_HOLE_SPEC)
# Hold-down hole centre, local z: centred on the .70 ledge, .35 outboard of
# the strap root (.75 from the strap inner face). Shared, because the plan view dimensions the hole from the
# strap inner face and must not restate the number.
SCREW_Z = STRAP_ROOT_Z - LEDGE_DEPTH / 2.0

# --- apex set screw (#743, user ruling Q3: "set screw located at apex of
# straps") ---------------------------------------------------------------
# One #4-40 x 1/4 cup-point set screw (MHA-DT-VN-64) drops radially through the
# crown apex onto the arbor, at the strap's mid-depth. The back pedestal's
# screw fixes the arbor; the front one is tightened after the bank's end-play
# leaf is set. The cup bears in a spot drilled into the arbor at fit-up
# through this tapped hole with the #43 tap drill, so the arbor print keeps
# "no flats". The tap runs THROUGH to the bore and stops there
# (through-next), never into the strap below it.
SET_SCREW_HOLE_SPEC = HoleSpec("tapped", SET_SCREW_THREAD, end="through_next")
SET_SCREW_Z = STRAP_INNER_Z - STRAP_T / 2.0  # .20 off the inner face: strap mid-depth
SET_SCREW_PITCH = 25.4 / 40.0
SET_SCREW_MIN_ENGAGEMENT_D = 1.5  # drawing-guidelines.md rule 18 (thread engagement): >= 1.5D of full thread

# Full thread in the crown wall at the printed worst case. The crown radius
# prints at two places (title block .XX, +-.01) and the bore at its own running
# band; the thread is only full where its major-diameter circle lies wholly
# in metal, so the crown's sag across the hole and the bore's sag across it
# are lost, and so is the one-pitch entry chamfer.
_CROWN_BAND_MM = printed_band_mm(2, unit=UNIT)  # "crown radius" prints at .XX
_BORE_MAX_RADIUS = (BORE_DIA + BORE_DIA_BAND[0]) / 2.0
_THREAD_HALF_MAJOR = THREAD_MAJOR_MM[SET_SCREW_THREAD] / 2.0


def _sag(radius: float) -> float:
    return radius - sqrt(radius**2 - _THREAD_HALF_MAJOR**2)


def set_screw_wall_terms(top_radius: float) -> dict[str, float]:
    """Named terms of the apex tap's worst-case full-thread length (mm): the
    crown at its least radius, less the metal the thread cannot use."""
    least_crown = top_radius - _CROWN_BAND_MM
    return {
        "crown radius at .XX minimum": least_crown,
        "bore radius at its maximum": -_BORE_MAX_RADIUS,
        "crown sag across the thread": -_sag(least_crown),
        "bore sag across the thread": -_sag(_BORE_MAX_RADIUS),
        "one-pitch entry chamfer": -SET_SCREW_PITCH,
    }


def set_screw_engagement_d(top_radius: float) -> float:
    """Worst-case full thread in the crown, in thread diameters."""
    full = sum(set_screw_wall_terms(top_radius).values())
    return full / THREAD_MAJOR_MM[SET_SCREW_THREAD]


# At the mm sheet's .X band R10 (the photographed crown) left 1.21D and failed;
# R.43 at .XX leaves about 1.8D.
SET_SCREW_FULL_THREAD_MM = sum(set_screw_wall_terms(TOP_RADIUS).values())
SET_SCREW_ENGAGEMENT_D = set_screw_engagement_d(TOP_RADIUS)
if SET_SCREW_ENGAGEMENT_D < SET_SCREW_MIN_ENGAGEMENT_D:
    raise AssertionError(
        f"apex set screw keeps {SET_SCREW_ENGAGEMENT_D:.2f}D of full thread "
        f"at the printed worst case (< {SET_SCREW_MIN_ENGAGEMENT_D}D)"
    )
# Web between the tap and each strap face (z). The strap depth and the screw
# location (from the strap inner face) both print at .XX (below), so the
# outer web loses both bands. Target .080 in (drawing-guidelines.md rule 17
# (walls and webs)).
_STRAP_DEPTH_BAND_MM = printed_band_mm(2, unit=UNIT)
_SET_SCREW_LOCATION_BAND_MM = printed_band_mm(2, unit=UNIT)
SET_SCREW_WEB_MM = min(
    (STRAP_INNER_Z - SET_SCREW_Z) - _SET_SCREW_LOCATION_BAND_MM - _THREAD_HALF_MAJOR,
    (STRAP_T - _STRAP_DEPTH_BAND_MM)
    - (STRAP_INNER_Z - SET_SCREW_Z + _SET_SCREW_LOCATION_BAND_MM)
    - _THREAD_HALF_MAJOR,
)
if SET_SCREW_WEB_MM < WALL_TARGET_MM:
    raise AssertionError(f"apex tap web {SET_SCREW_WEB_MM:.3f} mm < .080 in target")

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "arbor_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=BORE_HEIGHT),
        display_unit=UNIT,
    ),
    # The foot seat mates the pedestal to harmonic-base: on a part that may be
    # left as-cast elsewhere, the one face that MUST be cut says so.
    SurfaceFinishControl(
        "foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0), display_unit=UNIT
    ),
)

# Hidden reference sketches (#810 Codex l4afp, drawing-simplicity-policy.md `How the repository implements the guidelines`): the strap band,
# the hold-down hole's station off the foot's far face and both lateral
# locations off the west side face are manufacturing dimensions under the
# general bands, yet no feature dimension measures them -- the strap band is an
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
    "SetScrewReference",
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FootProfile": {"Width", "Depth"},
    "Foot": {"FootHt"},
    # BoreHeight plus a concentric crown and tangent sides defines the
    # complete upright profile without redundant endpoint widths.
    "BoreProfile": {"BoreDia", "BoreHeight"},
    # The crown: the dome boss's own RADIUS dimension, printed as modelled.
    "DomeProfile": {"DomeRadius"},
    "StrapDepthReference": {"StrapDepth"},
    "HoldDownReference": {"HoldDownLocation"},
    "HoleLateralReference": {"HoleLateral"},
    "BoreLateralReference": {"BoreLateral"},
    "SetScrewReference": {"SetScrewLocation"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`
# ), so the MODEL owns them: build_dt_arbor_pedestal applies this map to the
# .SLDPRT and draw_dt_arbor_pedestal only reads it back.  Inch sheet (#290):
# every size and location prints .XX (+-.01).  None can take the .X row: its
# +-.1 would cost the apex set screw its thread (crown), the tap its webs
# (strap depth, station), and move the hold-down and foot past what the base
# seat and drive-train checks read; their nominals sit on the .01 grid.  The
# reamed bore prints four places, for its own REAM_SLIDE band.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FootProfile": {"Width": 2, "Depth": 2},
    "Foot": {"FootHt": 2},
    "BoreProfile": {"BoreDia": 4, "BoreHeight": 2},
    # The apex set screw's full thread is sized at this band's least radius
    # (set_screw_wall_terms).
    "DomeProfile": {"DomeRadius": 2},
    "StrapDepthReference": {"StrapDepth": 2},
    # The base seat is transferred from this hole at assembly, so its
    # location only has to keep the webs.
    "HoldDownReference": {"HoldDownLocation": 2},
    # The apex set-screw tap's station off the strap inner face: the strap's
    # outer web under the tap loses this band (SET_SCREW_WEB_MM).
    "SetScrewReference": {"SetScrewLocation": 2},
    # Both lateral locations run off the foot's west side face (drawing-guidelines.md rule 10 (dimension from a real feature):
    # an origin is a feature, not the symmetry axis). The drum x is set with
    # the arbor itself at assembly (DRO edge-find), so neither hole's side
    # offset feeds a fit, and the crown is concentric with the bore.
    "HoleLateralReference": {"HoleLateral": 2},
    "BoreLateralReference": {"BoreLateral": 2},
}

# Places for the one dimension the SHEET still derives, keyed by the recipe's
# own label: the parenthesised overall height, a band-free restatement of the
# axis height plus the crown.  Its places are still specification, so the
# spec owns the digit and the sheet passes it through instead of writing a
# literal.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    # Two places, like the axis height and crown it is the sum of (2.18).
    "overall height": 2,
}

# The apex tap's and the hold-down hole's native Hole Wizard drill sizes
# print .XXX (draw_dt_arbor_pedestal sets them on the callouts).
HOLE_CALLOUT_PRECISION = 3

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
