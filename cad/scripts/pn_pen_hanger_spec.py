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
The rod line itself (``_recording_geometry.PEN_ROD_X`` / ``PEN_Z_MID``) is never
restated here.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). Lengths stay
physical millimetres, each the exact decimal of the inch value it prints.
Exempt from the grid: the strap and plate bar-stock thickness (as supplied,
REF), the #8 hole (Hole Wizard), and the hole's station, which is the wheel
bar's screw axis (``mg_wheel_bar_geom``) relative to the rod line: it keeps
its value and prints rounded at the title block's .XX (.27, .20), the model
inside that band.
"""

from __future__ import annotations

import math

import _config
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm, printed_deviations
from mg_wheel_bar_geom import WHEEL_BAR_Y
from mg_wheel_bar_geom import BAR_FRONT_Z, BAR_TOP_ABOVE_ROW, HANGER_SCREW_MACHINE_X
from _recording_geometry import PEN_ROD_X, PEN_Z_MID
from _paper_drive_placement import PLATEN_BOTTOM_Y
from pd_platen_spec import PLATE_HEIGHT as PLATEN_HEIGHT
from pn_pen_rod_spec import ROD_SECTION, SECTION_BAND as ROD_SECTION_BAND
from pn_vn_hanger_screw_spec import SHANK_DIA as HANGER_SCREW_DIA
from pn_vn_pen_hanger_nut_spec import ACROSS_FLATS as NUT_ACROSS_FLATS


PEN_ROD_NUMBER = _config.parts("pn-pen-rod")["number"]
# The registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/pn-pen-hanger", _config.parts("pn-pen-hanger"))

# --- Placement: the strap top is flush with the bar top, its back face seats
# on the bar front face, its top-right corner sits on the rod line's x so the
# slots centre on local x 0. ---
HANGER_POS = (PEN_ROD_X, round(WHEEL_BAR_Y + BAR_TOP_ABOVE_ROW, 6), BAR_FRONT_Z)
ROD_AXIS_Z = round(PEN_Z_MID - BAR_FRONT_Z, 6)  # local z of the rod line

# --- Strap (photo: tapers 16 -> 10 mm, black, flat on the bar).  Its foot is
# as wide as the guide plates below (not the photo's narrower foot), so the
# lower plate sits flush with both foot corners (note 1) and needs no lateral
# dimension.
# The strap and both guide plates come from one bar of 1/8 x 3/4 1018
# cold-finish flat, the stock bought for this part (OnlineMetals 4804, the
# 2026-11-03 machine stock order; #2436): the strap's .63 top and the plates'
# .48 width lie across the bar's .75.  The sheet prints the bar's thickness as
# a reference over its stock name, so the stacks below carry the bar's
# commercial band instead of a title-block one (Online Metals, Cold Roll Steel
# Tolerances, https://www.onlinemetals.com/en/cold-roll-steel-tolerances, read
# 2026-11-13: 1018 cold-finish rectangle bar up to .75 wide, +/-.003, the
# width's band governing the thickness too).
FLAT_BAR_T = 3.175  # .125, 1/8
FLAT_BAR_WIDTH = 19.05  # .75, 3/4
FLAT_BAR_T_RANGE = (round((0.125 - 0.003) * 25.4, 6), round((0.125 + 0.003) * 25.4, 6))
STRAP_T = FLAT_BAR_T
STRAP_Z = (-STRAP_T, 0.0)
STRAP_T_STOCK_RANGE = FLAT_BAR_T_RANGE
STRAP_T_STOCK_BAND = (
    round(STRAP_T_STOCK_RANGE[1] - STRAP_T, 6),
    round(STRAP_T_STOCK_RANGE[0] - STRAP_T, 6),
)  # (upper, lower) about the .125 nominal: +/-.003
if not (STRAP_T_STOCK_BAND[1] < 0.0 < STRAP_T_STOCK_BAND[0]):
    raise AssertionError("the strap stock band no longer brackets its bar")
STRAP_TOP_X = (-16.002, 0.0)  # .63 wide at the bar (low)
STRAP_BOT_X = (-6.096, 6.096)  # .48 wide at the foot, centred on the rod (low)
# 6.69 below the bar top: the strap stays flat on the bar plane, which the
# platen and paper also cross (platen z -142.75..-138.9 mm), so its foot stops
# just above the platen top instead of running past the paper top (photo
# ~184 mm below the screw; this is 165, inside the photo's +-15 % parallax).
STRAP_RISE = 169.926  # 6.69
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

# --- Two open U guide plates, brazed across the strap front: plain blanks of
# the strap's 1/8 flat (printed as a reference), slotted after brazing.
# Each plate is a web: its thinnest supplied bar keeps rule 17's .080 target.
GUIDE_PLATE_T = FLAT_BAR_T
GUIDE_PLATE_T_STOCK_RANGE = FLAT_BAR_T_RANGE
if not GUIDE_PLATE_T_STOCK_RANGE[0] < GUIDE_PLATE_T < GUIDE_PLATE_T_STOCK_RANGE[1]:
    raise AssertionError("the guide plate stock band no longer brackets its bar")
if GUIDE_PLATE_T_STOCK_RANGE[0] < WALL_TARGET_MM:
    raise AssertionError("the thinnest supplied guide plate is under the rule 17 target")
# The upper plate's top face below the strap top (printed): the plates'
# pitch follows from it, the rise and the gauge (photo ~42 mm).
UPPER_PLATE_DROP = 127.0  # 5.00
GUIDE_PLATE_YS = (STRAP_BOT_Y, -(UPPER_PLATE_DROP + GUIDE_PLATE_T))  # bottom faces
GUIDE_PITCH = GUIDE_PLATE_YS[1] - GUIDE_PLATE_YS[0]  # lower to upper bottom face
# Each plate's top face below the strap top edge: the extrude's start offset.
GUIDE_PLATE_DROPS = tuple(round(-(y + GUIDE_PLATE_T), 6) for y in GUIDE_PLATE_YS)
# Wide enough that both slot walls keep rule 17's target at the printed worst
# case (guarded with the drawing's places below); as wide as the strap's foot.
GUIDE_PLATE_WIDTH = 12.192  # .48
if not math.isclose(STRAP_BOT_X[1] - STRAP_BOT_X[0], GUIDE_PLATE_WIDTH):
    raise AssertionError(
        "the lower guide plate is no longer flush with both foot corners"
    )
if max(STRAP_TOP_X[1] - STRAP_TOP_X[0], GUIDE_PLATE_WIDTH) > FLAT_BAR_WIDTH:
    raise AssertionError("the strap or a guide plate no longer fits across the 3/4 bar")
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
SLOT_WIDTH = 5.08  # .200
# (upper, lower) deviations, +.002/0 (inch-fit-bands-misc.md §5).  The low
# limit leaves running clearance on the largest rod (pn_pen_rod_spec
# SECTION_BAND); the high limit bounds the lean the two slots allow
# (GUIDE_TILT_MAX).
SLOT_WIDTH_BAND = (0.0508, 0.0)
# The plate's reach (strap front to plate front) and its slot depth, both
# printed from the plate's free end.  The slots are cut after brazing, both in
# one setup (note 2): with the strap's back face on the mill table the cutter
# stands square to the strap and one feed along it slots both plates, so the
# two slots are in line however the braze left the plates, and the .002 slot
# band rides the mill's travel, not the joint.  Deep enough that the printed
# reach and slot depth and the strap's stock band, with the corner radius at
# its printed MAX below, still keep the rod's back corners off the
# slot-corner fillets (guarded below).
PLATE_REACH = 24.638  # .97
SLOT_DEPTH = 10.668  # .42
PLATE_FRONT_Z = round(STRAP_Z[0] - PLATE_REACH, 6)
SLOT_BOTTOM_Z = round(PLATE_FRONT_Z + SLOT_DEPTH, 6)
# The slot bottom from the strap back face (the bar seat): the sketch's anchor.
SLOT_BOTTOM = -SLOT_BOTTOM_Z
# Nominal, largest rod's back face to slot bottom.
SLOT_BOTTOM_GAP = round(SLOT_BOTTOM_Z - (ROD_AXIS_Z + ROD_SECTION / 2.0), 6)
# The plate front edge ahead of the rod axis.
GUIDE_NOSE = round(ROD_AXIS_Z - PLATE_FRONT_Z, 6)
# drawing-guidelines.md rule 16: the slot's two milled internal corners carry
# a radius inside what the rod's corner clearance allows (guarded below),
# printed as the single limit "R.08 MAX" so the shop picks the cutter.
# swTolMAX prints the nominal then MAX, so the modelled radius IS the limit;
# the band runs from sharp up to it.
SLOT_CORNER_R = 2.032  # .08
SLOT_CORNER_R_BAND = (0.0, -SLOT_CORNER_R)  # (upper, lower)
SLOT_CORNER_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "2X R.08 MAX"
ARM_WIDTH = (GUIDE_PLATE_WIDTH - SLOT_WIDTH) / 2.0  # .14

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
# The slot bottom stays behind the rod's back face at the worst case.  The
# rod line is set from the strap back face (the bar seat); the plate's root
# seats on the strap front face, the strap's stock thickness away (a
# reference on the sheet, at its commercial band: the thickest strap pushes
# the plate forward), and the sheet prints the plate's reach and its slot
# depth both .XX from the plate's free end, so the slot bottom carries both
# .XX bands as well.
_XX_BAND = printed_band_mm(2, unit=UNIT)
SLOT_BOTTOM_GAP_MIN = SLOT_BOTTOM_GAP - 2.0 * _XX_BAND - STRAP_T_STOCK_BAND[0]
if SLOT_BOTTOM_GAP_MIN <= 0.0:
    raise AssertionError("guide slot bottom can bear on the pen rod")
# The corner fillets are tangent to the walls SLOT_CORNER_R ahead of the slot
# bottom: with the slot bottom at that worst case and the radius at its printed
# MAX, the rod's back corners still pass the fillets' wall tangency.
SLOT_CORNER_R_MAX = SLOT_CORNER_R
if SLOT_BOTTOM_GAP_MIN < SLOT_CORNER_R_MAX:
    raise AssertionError(
        "guide slot corner fillets can bear on the pen rod's back corners"
    )
# The two fillets leave a flat slot bottom between them, inside the slot depth.
if 2.0 * SLOT_CORNER_R >= SLOT_WIDTH or SLOT_CORNER_R >= SLOT_DEPTH:
    raise AssertionError("guide slot corner radius does not fit the slot")
# The arms still cover the rod's front face with the reach at its .XX limit
# and the thinnest strap stock holding the plate back.
GUIDE_ARM_COVER_MIN = GUIDE_NOSE - _ROD_MAX / 2.0 - _XX_BAND + STRAP_T_STOCK_BAND[1]
if GUIDE_ARM_COVER_MIN <= 0.0:
    raise AssertionError("guide plate arms can stop short of the rod's front face")

# --- M6.10: the selected hanger screw passes through a #8 close-clearance
# Hole Wizard hole near the strap top, on the bar's screw axis, into the
# MHA-PN-VN-54 hex nut on the strap front, the MHA-PN-VN-55 jam nut jammed against
# it (rule 23: the jam nut locks the joint the pen rod's reversing friction
# loads; rule 18: the nuts, not the .125 strap, carry the thread).  The
# Hole Wizard's ANSI-inch #8 close row is the #15 drill (.180) of
# cad/config/tolerances/fastener_clearance.yaml. ---
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
# governs, .197 above the axis): the hole and the bearing nut's flats must
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
# outline (the slot depth and the reach both from the plate's free end), the
# slot-corner radius and the strap stock thickness (the lower plate is
# identical and flush with the strap bottom end -- notes). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {"StrapTopRun", "StrapTaperDx", "StrapRise", "StrapBotWidth"},
    "Strap": {"StrapThick"},
    "ScrewHole": {"ScrewX", "ScrewY"},
    "UpperGuide": {"UpperPlateDrop"},
    "LowerGuide": {"PlateThick"},
    "UpperGuideProfile": {
        "SlotWidth",
        "SlotDepth",
        "ArmWidth",
        "PlateReach",
        "PlateWidth",
    },
    "UpperSlotCorner": {"SlotCornerR"},
}
# Places: every strap, plate and slot size feeds a stack, a wall or the
# plate's flush fit on the strap's foot, so nothing prints .X; the title
# block's .XX, except the banded slot (+.002/0).  The hole station keeps the
# bar's screw axis and prints it rounded at .XX, the model inside the band
# (the wall below is judged about the printed value).  The stock references
# print the bar's three-place decimal.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StrapProfile": {
        "StrapTopRun": 2,
        "StrapTaperDx": 2,
        "StrapRise": 2,
        "StrapBotWidth": 2,
    },
    "Strap": {"StrapThick": 3},
    "ScrewHole": {"ScrewX": 2, "ScrewY": 2},
    "UpperGuide": {"UpperPlateDrop": 2},
    "LowerGuide": {"PlateThick": 3},
    "UpperGuideProfile": {
        "SlotWidth": 3,
        "SlotDepth": 2,
        "ArmWidth": 2,
        "PlateReach": 2,
        "PlateWidth": 2,
    },
    "UpperSlotCorner": {"SlotCornerR": 2},
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


def _printed_limits(
    model: float, name: str, limits: tuple[float, float] | None = None
) -> tuple[float, float]:
    """``(min, max)`` mm an accepted part may show for the named dimension."""
    lower, upper = printed_deviations(
        model, DRAWING_PRECISION_BY_NAME[name], limits, unit=UNIT
    )
    return model + lower, model + upper


# drawing-guidelines.md rule 17: both slot walls keep the .080 target at the
# worst case of the PRINTED bands.  Section A-A prints the plate width, the
# near (+x) arm and the banded slot; the far arm is what that chain leaves.
_plate = _printed_limits(GUIDE_PLATE_WIDTH, "PlateWidth")
_arm = _printed_limits(ARM_WIDTH, "ArmWidth")
_slot = _printed_limits(
    SLOT_WIDTH, "SlotWidth", (SLOT_WIDTH_BAND[1], SLOT_WIDTH_BAND[0])
)
NEAR_ARM_MIN = _arm[0]
FAR_ARM_MIN = _plate[0] - _arm[1] - _slot[1]
if min(NEAR_ARM_MIN, FAR_ARM_MIN) < WALL_TARGET_MM:
    raise AssertionError(
        f"guide slot walls {NEAR_ARM_MIN:.3f}/{FAR_ARM_MIN:.3f} at the printed "
        f"worst case (< {WALL_TARGET_MM})"
    )
# Rule 17: the screw hole's wall to the strap's nearest edge keeps the target
# with the hole at its DRILLED HOLES upper limit and its printed station at
# the far end of its .XX band (about the printed value, not the model's).
_station_offset = max(
    abs(deviation)
    for name, model in zip(("ScrewX", "ScrewY"), SCREW_HOLE_XY, strict=True)
    for deviation in printed_deviations(
        model, DRAWING_PRECISION_BY_NAME[name], unit=UNIT
    )
)
SCREW_HOLE_WALL_MIN = (
    SCREW_HOLE_EDGE_DISTANCE
    - _station_offset
    - (SCREW_HOLE_DIA + drilled_oversize_mm(unit=UNIT)) / 2.0
)
if SCREW_HOLE_WALL_MIN < WALL_TARGET_MM:
    raise AssertionError(
        f"hanger screw hole wall {SCREW_HOLE_WALL_MIN:.3f} at the printed worst "
        f"case (< {WALL_TARGET_MM})"
    )
# Every tight band names its mate on the dimension it governs.  The two
# numbered notes are flagged from the features they govern (rule 7: SEE NOTE
# n puts the note at the callout): note 1, the plates' braze to the strap
# front, from the lower plate's stock callout in the front view (a location
# dimension carries only its value and band, so the upper plate's drop takes
# no flag; #2721 review 20261113T172037696Z); note 2, the slots in line, from
# the slot width.  Rule 7: at most two lines of words under the slot's limits.
BRAZE_NOTE = 1
SLOTS_NOTE = 2
DIMENSION_CALLOUTS: dict[str, str] = {
    "SlotWidth": f"2X SLIDING FIT ON {PEN_ROD_NUMBER}\nSEE NOTE {SLOTS_NOTE}",
    # "2X" counts the two corners of one slot, not the two plates.
    "SlotCornerR": "EACH SLOT",
    # The strap's and the plates' thickness is the bar's as supplied, not a
    # machined size: printed as a reference (parenthesised) with the stock
    # named under it.
    "StrapThick": "1/8 CF FLAT",
    "PlateThick": f"1/8 CF FLAT\nSEE NOTE {BRAZE_NOTE}",
}
# Model dimensions the sheet parenthesises as reference (the stock governs).
REFERENCE_DIMENSIONS: frozenset[str] = frozenset({"StrapThick", "PlateThick"})
# (feature, dimension) -> native prefix.  A custom radius prefix replaces
# SolidWorks' own "R", so it carries it: the section's two slot corners.
DIMENSION_PREFIXES: dict[tuple[str, str], str] = {
    ("UpperSlotCorner", "SlotCornerR"): "2X R",
}

# Note 2 is the slots' fit route (drawing-guidelines.md "What the shop
# holds": two .002-band slots in line across a brazed joint are reached by
# cutting both in one setup after brazing, not by placing pre-cut plates),
# with the rod's free fall as its acceptance.
DRAWING_NOTES = "\n".join(
    (
        f"{BRAZE_NOTE}. TWO GUIDE PLATES BRAZED (BAg-7) TO STRAP FRONT;",
        "   LOWER PLATE FLUSH WITH STRAP END AND BOTH CORNERS.",
        f"{SLOTS_NOTE}. BOTH SLOTS CUT IN ONE SETUP AFTER BRAZING; PEN ROD",
        f"   {PEN_ROD_NUMBER} SLIDES FREELY THROUGH BOTH UNDER ITS OWN WEIGHT.",
    )
)
# The upper plate's lateral station is the lower plate's: both slots sit on
# one centreline the front view draws through them (drawing-guidelines.md
# rule 26: features in line share a drawn centreline), and the lower plate
# is fixed by the strap's foot corners (note 1).  What that station leaves the
# reader to work out (rule 10): the upper plate's +x edge stands past the
# tapered strap's edge at the plate's top face.  Section A-A prints it as a
# reference, measured on the sheet.
UPPER_PLATE_OVERHANG = GUIDE_PLATE_WIDTH / 2.0 - (
    STRAP_TOP_X[1]
    + (STRAP_BOT_X[1] - STRAP_TOP_X[1])
    * (GUIDE_PLATE_YS[1] + GUIDE_PLATE_T)
    / STRAP_BOT_Y
)
DRAWING_REFERENCE_PRECISION = 2
if UPPER_PLATE_OVERHANG <= 0.0:
    raise AssertionError("the upper guide plate no longer overhangs the strap edge")
# The front view is projected and at the sheet's 1:1 (no label, rule 9); the
# one pictorial is named in words, its 1:1 the title block's.
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW"
