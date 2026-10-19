r"""Pure-data contract for the pen hanger: geometry, fit and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_pn_pen_hanger`` models this
geometry and applies the bands and places below to its model dimensions;
``draw_pn_pen_hanger`` keeps exactly ``DRAWING_DIMENSIONS`` across its two
per-view keep maps; ``build_pn_pen_assembly`` places the part at
``HANGER_POS`` and checks the rod's travel against ``GUIDE_SPAN_Y``.

Frame: origin at the strap's top-right BACK corner -- on the wheel bar's front
face, level with the bar top, on the rod line's x.  The part is authored
MACHINE-handed and placed IDENTITY, so local axes are machine axes: the strap
occupies y -170..0, z -3..0; the rod axis is local (0, ., ``ROD_AXIS_Z``).
The rod line itself (``paper_drive_geom.PEN_ROD_X`` / ``PEN_Z_MID``) is never
restated here.
"""

from __future__ import annotations

import math

import _config
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from mg_vn_lever_wire_geom import WHEEL_BAR_Y
from mg_wheel_bar_geom import BAR_FRONT_Z, BAR_SIDE, HANGER_SCREW_MACHINE_X
from paper_drive_geom import PEN_ROD_X, PEN_Z_MID, PLATEN_BOTTOM_Y
from pd_platen_spec import PLATE_HEIGHT as PLATEN_HEIGHT
from pn_pen_rod_spec import ROD_SECTION, SECTION_BAND as ROD_SECTION_BAND
from pn_vn_hanger_screw_spec import SHANK_DIA as HANGER_SCREW_DIA
from pn_vn_pen_hanger_nut_spec import ACROSS_FLATS as NUT_ACROSS_FLATS


PEN_ROD_NUMBER = _config.parts("pn-pen-rod")["number"]

# --- Placement: the strap top is flush with the bar top, its back face seats
# on the bar front face, its top-right corner sits on the rod line's x so the
# slots centre on local x 0. ---
HANGER_POS = (PEN_ROD_X, round(WHEEL_BAR_Y + BAR_SIDE / 2.0, 6), BAR_FRONT_Z)
ROD_AXIS_Z = round(PEN_Z_MID - BAR_FRONT_Z, 6)  # local z of the rod line

# --- Strap (photo: tapers 16 -> 10, black, flat on the bar).  Its foot is as
# wide as the guide plates below (12, not the photo's 10), so the lower plate
# sits flush with both foot corners (note 1) and needs no lateral dimension.
STRAP_T = 3.0
STRAP_Z = (-STRAP_T, 0.0)
STRAP_TOP_X = (-16.0, 0.0)  # 16 wide at the bar (low)
STRAP_BOT_X = (-6.0, 6.0)  # 12 wide at the foot, centred on the rod (low)
# 170 below the bar top: the strap stays flat on the bar plane, which the
# platen and paper also cross (platen z -142.75..-138.9), so its foot stops
# just above the platen top instead of running past the paper top (photo
# ~184 below the screw; this is 165, inside the photo's +-15 % parallax).
STRAP_RISE = 170.0
STRAP_BOT_Y = -STRAP_RISE
STRAP_OUTLINE = (
    (STRAP_TOP_X[1], 0.0),
    (STRAP_TOP_X[0], 0.0),
    (STRAP_BOT_X[0], STRAP_BOT_Y),
    (STRAP_BOT_X[1], STRAP_BOT_Y),
)  # counter-clockwise from the origin corner
PLATEN_TOP_CLEARANCE_MIN = 2.0
PLATEN_TOP_CLEARANCE = HANGER_POS[1] + STRAP_BOT_Y - (PLATEN_BOTTOM_Y + PLATEN_HEIGHT)
if PLATEN_TOP_CLEARANCE < PLATEN_TOP_CLEARANCE_MIN:
    raise AssertionError(
        f"hanger foot {PLATEN_TOP_CLEARANCE:.3f} above the platen top "
        f"(< {PLATEN_TOP_CLEARANCE_MIN})"
    )

# --- Two open U guide plates (1.5 sheet), brazed across the strap front. ---
GUIDE_PLATE_T = 1.5
GUIDE_PITCH = 40.0  # lower-plate bottom to upper-plate bottom (photo ~42)
GUIDE_PLATE_YS = (STRAP_BOT_Y, STRAP_BOT_Y + GUIDE_PITCH)  # bottom faces, local
# Each plate's top face below the strap top edge: the extrude's start offset.
GUIDE_PLATE_DROPS = tuple(-(y + GUIDE_PLATE_T) for y in GUIDE_PLATE_YS)
# Wide enough that both slot walls keep rule 17's floor at the .X worst case
# (guarded with the drawing's places below); as wide as the strap's foot.
GUIDE_PLATE_WIDTH = 12.0
if not math.isclose(STRAP_BOT_X[1] - STRAP_BOT_X[0], GUIDE_PLATE_WIDTH):
    raise AssertionError(
        "the lower guide plate is no longer flush with both foot corners"
    )
GUIDE_SPAN_Y = (
    round(HANGER_POS[1] + GUIDE_PLATE_YS[0], 6),
    round(HANGER_POS[1] + GUIDE_PLATE_YS[1] + GUIDE_PLATE_T, 6),
)  # machine y: lower-plate bottom .. upper-plate top
# The rod's square section must pass both plates by this much at both travel
# extremes (pn_pen_carriage_geom; asserted by the hanger test and the pen
# assembly).
GUIDE_ENGAGE_MARGIN = 3.0

# --- Slot: the rod's only lateral guide.  Width on the rod, bottom just behind
# the rod's back face, the plate's front arms past the rod's front face. ---
SLOT_WIDTH = 5.05
# (upper, lower) deviations.  The low limit leaves running clearance on the
# largest rod (pn_pen_rod_spec 0/-0.05); the high limit bounds the lean the two
# slots allow (GUIDE_TILT_MAX).
SLOT_WIDTH_BAND = (0.05, 0.0)
# Nominal, largest rod's back face to slot bottom.  Open enough that the
# title-block .X band on the slot bottom AND on the corner radius below still
# keeps the rod's back corners off the slot-corner fillets (guarded below),
# so the slot bottom needs no tight band.
SLOT_BOTTOM_GAP = 4.0
SLOT_BOTTOM_Z = round(ROD_AXIS_Z + ROD_SECTION / 2.0 + SLOT_BOTTOM_GAP, 6)
# Printed from the strap back face (the bar seat), the one face that fixes the
# rod line relative to the slot.
SLOT_BOTTOM = -SLOT_BOTTOM_Z
# drawing-guidelines.md rule 16: the slot's two milled internal corners carry
# the largest radius the rod's corner clearance allows.
SLOT_CORNER_R = 2.0
GUIDE_NOSE = 4.0  # plate front edge ahead of the rod axis
PLATE_FRONT_Z = round(ROD_AXIS_Z - GUIDE_NOSE, 6)
PLATE_REACH = round(STRAP_Z[0] - PLATE_FRONT_Z, 6)  # strap front to plate front
SLOT_DEPTH = round(SLOT_BOTTOM_Z - PLATE_FRONT_Z, 6)
ARM_WIDTH = (GUIDE_PLATE_WIDTH - SLOT_WIDTH) / 2.0

_ROD_MAX = ROD_SECTION + ROD_SECTION_BAND[0]
_ROD_MIN = ROD_SECTION + ROD_SECTION_BAND[1]
SLOT_CLEARANCE = (
    SLOT_WIDTH + SLOT_WIDTH_BAND[1] - _ROD_MAX,
    SLOT_WIDTH + SLOT_WIDTH_BAND[0] - _ROD_MIN,
)  # (tightest, loosest) side-to-side
if SLOT_CLEARANCE[0] <= 0.0:
    raise AssertionError("guide slot binds the largest pen rod")
# Worst lean of the rod between the two slots' outer faces (radians).
GUIDE_TILT_MAX = math.atan(SLOT_CLEARANCE[1] / (GUIDE_PITCH + GUIDE_PLATE_T))
if math.degrees(GUIDE_TILT_MAX) > 0.25:
    raise AssertionError("guide slots let the pen rod lean over 0.25 deg")
# The slot bottom stays behind the rod's back face at its .X limit.
SLOT_BOTTOM_GAP_MIN = SLOT_BOTTOM_GAP - printed_band_mm(1)
if SLOT_BOTTOM_GAP_MIN <= 0.0:
    raise AssertionError("guide slot bottom can bear on the pen rod")
# The corner fillets are tangent to the walls SLOT_CORNER_R ahead of the slot
# bottom: with the slot bottom AND the radius both at their .X limits, the
# rod's back corners still pass the fillets' wall tangency.
SLOT_CORNER_R_MAX = SLOT_CORNER_R + printed_band_mm(1)
if SLOT_BOTTOM_GAP_MIN < SLOT_CORNER_R_MAX:
    raise AssertionError(
        "guide slot corner fillets can bear on the pen rod's back corners"
    )
# The two fillets leave a flat slot bottom between them, inside the slot depth.
if 2.0 * SLOT_CORNER_R >= SLOT_WIDTH or SLOT_CORNER_R >= SLOT_DEPTH:
    raise AssertionError("guide slot corner radius does not fit the slot")
# The arms still cover the rod's front face with the reach at its .X limit.
GUIDE_ARM_COVER_MIN = GUIDE_NOSE - _ROD_MAX / 2.0 - printed_band_mm(1)
if GUIDE_ARM_COVER_MIN <= 0.0:
    raise AssertionError("guide plate arms can stop short of the rod's front face")

# --- M6.10: the selected hanger screw passes through a #8 close-clearance
# Hole Wizard hole near the strap top, on the bar's screw axis, into the
# MHA-PN-VN-54 hex nut on the strap front, the MHA-PN-VN-55 jam nut jammed against
# it (rule 23: the jam nut locks the joint the pen rod's reversing friction
# loads; rule 18: the nuts, not the 3.0 strap, carry the thread). ---
SCREW_HOLE_SPEC = HoleSpec("clearance", "#8", fit="close")
SCREW_HOLE_DIA = blind_cut_dia_mm(SCREW_HOLE_SPEC)
if SCREW_HOLE_DIA <= HANGER_SCREW_DIA:
    raise AssertionError("hanger screw hole does not clear the #8 thread")
SCREW_HOLE_XY = (
    round(HANGER_SCREW_MACHINE_X - HANGER_POS[0], 6),
    round(WHEEL_BAR_Y - HANGER_POS[1], 6),
)


def _edge_distance(start: tuple[float, float], end: tuple[float, float]) -> float:
    """Signed distance from the hole axis to one outline edge (+ inside)."""
    (x1, y1), (x2, y2) = start, end
    px, py = SCREW_HOLE_XY
    return ((x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)) / math.hypot(
        x2 - x1, y2 - y1
    )


# Perpendicular distances to all four straight strap edges (the top edge
# governs, 5.0 above the axis): the hole and the bearing nut's flats must
# both sit inside the whole tapered outline.  The wall is judged at the printed
# worst case below, once the station's places are authored.
SCREW_HOLE_EDGE_DISTANCE = min(
    _edge_distance(a, b)
    for a, b in zip(STRAP_OUTLINE, STRAP_OUTLINE[1:] + STRAP_OUTLINE[:1])
)
if NUT_ACROSS_FLATS / 2.0 >= SCREW_HOLE_EDGE_DISTANCE:
    raise AssertionError("hanger nut flats overhang the strap edge")

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Front view (looking at the plates): the strap outline, the
# screw-hole station, the upper plate's drop and the (alike) lower plate's
# thickness.
# Section A-A just above the upper plate, looking down onto it: its U
# outline, the slot-corner radius and the strap stock thickness (the lower
# plate is identical and flush with the strap bottom end -- notes). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {"StrapTopRun", "StrapTaperDx", "StrapRise", "StrapBotWidth"},
    "Strap": {"StrapThick"},
    "ScrewHole": {"ScrewX", "ScrewY"},
    "UpperGuide": {"UpperPlateDrop"},
    "LowerGuide": {"PlateThick"},
    "UpperGuideProfile": {
        "SlotWidth",
        "SlotBottom",
        "ArmWidth",
        "PlateReach",
        "PlateWidth",
    },
    "UpperSlotCorner": {"SlotCornerR"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StrapProfile": {
        "StrapTopRun": 1,
        "StrapTaperDx": 1,
        "StrapRise": 1,
        "StrapBotWidth": 1,
    },
    "Strap": {"StrapThick": 1},
    "ScrewHole": {"ScrewX": 1, "ScrewY": 1},
    "UpperGuide": {"UpperPlateDrop": 1},
    "LowerGuide": {"PlateThick": 1},
    "UpperGuideProfile": {
        "SlotWidth": 2,
        "SlotBottom": 1,
        "ArmWidth": 1,
        "PlateReach": 1,
        "PlateWidth": 1,
    },
    "UpperSlotCorner": {"SlotCornerR": 1},
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
    raise AssertionError("every marked pen-hanger dimension needs authored places")
# (feature, dimension) -> (upper, lower) native band.
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("UpperGuideProfile", "SlotWidth"): SLOT_WIDTH_BAND,
}
# drawing-guidelines.md rule 17: both slot walls keep the 1.5 floor at the
# worst case of the PRINTED bands.  Section A-A prints the plate width, the
# near (+x) arm and the banded slot; the far arm is what that chain leaves.
SLOT_WALL_FLOOR = 1.5
_plate = round(GUIDE_PLATE_WIDTH, DRAWING_PRECISION_BY_NAME["PlateWidth"])
_plate_band = printed_band_mm(DRAWING_PRECISION_BY_NAME["PlateWidth"])
_arm = round(ARM_WIDTH, DRAWING_PRECISION_BY_NAME["ArmWidth"])
_arm_band = printed_band_mm(DRAWING_PRECISION_BY_NAME["ArmWidth"])
_slot = round(SLOT_WIDTH, DRAWING_PRECISION_BY_NAME["SlotWidth"])
NEAR_ARM_MIN = _arm - _arm_band
FAR_ARM_MIN = (_plate - _plate_band) - (_arm + _arm_band) - (_slot + SLOT_WIDTH_BAND[0])
if min(NEAR_ARM_MIN, FAR_ARM_MIN) < SLOT_WALL_FLOOR:
    raise AssertionError(
        f"guide slot walls {NEAR_ARM_MIN:.2f}/{FAR_ARM_MIN:.2f} at the printed "
        f"worst case (< {SLOT_WALL_FLOOR})"
    )
# Rule 17: the screw hole's wall to the strap's nearest edge keeps the floor
# with the hole at its DRILLED HOLES upper limit and its printed station at
# the far end of its .X band.
_station_band = max(
    printed_band_mm(DRAWING_PRECISION_BY_NAME[name]) for name in ("ScrewX", "ScrewY")
)
SCREW_HOLE_WALL_MIN = (
    SCREW_HOLE_EDGE_DISTANCE
    - _station_band
    - (SCREW_HOLE_DIA + drilled_oversize_mm()) / 2.0
)
if SCREW_HOLE_WALL_MIN < SLOT_WALL_FLOOR:
    raise AssertionError(
        f"hanger screw hole wall {SCREW_HOLE_WALL_MIN:.2f} at the printed worst "
        f"case (< {SLOT_WALL_FLOOR})"
    )
# Every tight band names its mate on the dimension it governs.
DIMENSION_CALLOUTS: dict[str, str] = {
    "SlotWidth": f"2X SLIDING FIT ON\nPEN ROD {PEN_ROD_NUMBER}",
    # "2X" counts the two corners of one slot, not the two plates.
    "SlotCornerR": "EACH SLOT",
    # The plates' thickness is the sheet's as supplied, not a machined size:
    # printed as a reference (parenthesised) with the stock named under it.
    "PlateThick": "SHEET STOCK",
}
# Model dimensions the sheet parenthesises as reference (the stock governs).
REFERENCE_DIMENSIONS: frozenset[str] = frozenset({"PlateThick"})
# (feature, dimension) -> native prefix.  A custom radius prefix replaces
# SolidWorks' own "R", so it carries it: the section's two slot corners.
DIMENSION_PREFIXES: dict[tuple[str, str], str] = {
    ("UpperSlotCorner", "SlotCornerR"): "2X R",
}

DRAWING_NOTES = "\n".join(
    (
        "1. TWO GUIDE PLATES ALIKE, SILVER-BRAZED (BAg-7) TO STRAP",
        "   FRONT FACE; LOWER PLATE FLUSH WITH STRAP BOTTOM END",
        "   AND BOTH ITS CORNERS.",
        f"2. SLOTS IN LINE: PEN ROD {PEN_ROD_NUMBER} SLIDES FREELY",
        "   THROUGH BOTH UNDER ITS OWN WEIGHT.",
    )
)
# Leadered on the upper plate in section A-A: its lateral station is the
# lower plate's (both centred on the rod line), which the strap's foot
# corners fix (note 1).
UPPER_PLATE_LOCATION_CALLOUT = "IN LINE WITH\nLOWER PLATE"
# What that station leaves the reader to work out (rule 10): the upper
# plate's +x edge stands past the tapered strap's edge at the plate's top
# face.  Section A-A prints it as a reference, measured on the sheet.
UPPER_PLATE_OVERHANG = GUIDE_PLATE_WIDTH / 2.0 - (
    STRAP_TOP_X[1]
    + (STRAP_BOT_X[1] - STRAP_TOP_X[1])
    * (GUIDE_PLATE_YS[1] + GUIDE_PLATE_T)
    / STRAP_BOT_Y
)
DRAWING_REFERENCE_PRECISION = 1
if UPPER_PLATE_OVERHANG <= 0.0:
    raise AssertionError("the upper guide plate no longer overhangs the strap edge")
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 1:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
