"""Pure-data manufacturing contract for the MHA-PD-27 platen bottom guide.

Owner rulings 2026-11-13 (#2410): the platen's bottom guide rail is
MHA-PD-11's .40-deep section grown downward until its underside seats the
MHA-PD-26 feed rack's flat top; its top stays where the bottom MHA-PD-11
rail's top was (0.98 under the support bar), and the rack is screwed to its
underside. MHA-PD-11 is now the top rail only.

Local frame: length along +X from the left end, height along +Y from the
underside (y 0), depth extruded -Z from the platen-mating front face (z 0),
as MHA-PD-11. Three hole families:

* four #4-40 lock taps, THROUGH from the rear face, at MHA-PD-11's lock
  stations and the same height above the platen as before, printed;
* five #4-40 platen-screw taps, THROUGH from the front face, transferred
  from MHA-PD-02's lower row at MHA-PD-00 with the rack already on and its
  crests set: the platen-screw float cannot absorb the crest set, so the
  holes follow it;
* four stepped rack-screw holes from the top face, #51 through and a
  Ø.110 counterbore, struck from the rack's taps at MHA-PD-00 with a
  transfer screw.

Both transfers: delegated ruling 2026-11-14 (Main), pending owner
confirmation; owner review #2144 (#2410); precedent R9-9, the disc's taps
spotted through MHA-PD-17's holes at assembly.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``); bands and
limits stay physical millimetres, each the exact decimal of its inch value.
"""

from __future__ import annotations

import math

import _config
from _hole_spec import NUMBER_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _inch_wall_limits import WALL_FLOOR_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
)
import _mcmaster_91794a055 as _screw
import pd_feed_rack_spec as rack
import pd_platen_guide_spec as top_rail
from pd_platen_spec import DRAWING_PRECISION_BY_NAME as PLATEN_PRECISION
from pd_platen_spec import GUIDE_HOLE_DIA, GUIDE_HOLE_X, GUIDE_HOLE_Y, PLATE_WIDTH
from pd_platen_spec import UNIT as PLATEN_UNIT

UNIT = drawing_unit(
    "parts/pd-platen-bottom-guide", _config.parts("pd-platen-bottom-guide")
)
MM_PER_IN = 25.4
PLACES = 3
BAND = printed_band_mm(PLACES, unit=UNIT)  # +/-.005
EDGE_BREAK = max(edge_break_chamfer_mm(unit=UNIT), edge_break_radius_mm(unit=UNIT))

GUIDE_LENGTH = PLATE_WIDTH
GUIDE_DEPTH = 10.16  # .40, MHA-PD-11's section
GUIDE_DEPTH_BAND = top_rail.GUIDE_DEPTH_BAND
GUIDE_DEPTH_PLACES = top_rail.GUIDE_DEPTH_PLACES
GUIDE_DEPTH_CALLOUT = top_rail.GUIDE_DEPTH_CALLOUT
LOCK_TAP_SPEC = top_rail.LOCK_TAP_SPEC
PLATEN_TAP_SPEC = top_rail.TAPPED_HOLE_SPEC
_TAP_MAJOR = THREAD_MAJOR_MM[PLATEN_TAP_SPEC.size]
# The title block's .010 tap mouth break, as MHA-PD-11's rows pay it.
TAP_MOUTH_BREAK = EDGE_BREAK

# --- Where it sits (in the platen's frame, from its bottom edge) -------------
# The rack's crests stand .100 below the platen's bottom edge, set by height
# gauge to +/-.002 (CREST_SET_BAND, pd_paper_drive_assembly_steps'
# RACK_CREST_TOL); the strip's flat top, so this rail's underside, stands the
# strip's height above them: 2.228 above the platen's bottom edge, where the
# bottom MHA-PD-11 rail's underside stood 10.5 (build_pd_paper_drive_assembly
# asserts both against the frame).
UNDERSIDE_ABOVE_PLATEN_BOTTOM = 2.22819
FORMER_TOP_ABOVE_PLATEN_BOTTOM = 10.5 + top_rail.GUIDE_HEIGHT
CREST_SET_BAND = 0.0508  # +/-.002
# The strip's height varies by its receiving room, which moves the rail.
_STRIP_HEIGHT_ROOM = rack.PURCHASED_RACK_HEIGHT_MAX_MM - rack.RACK_HEIGHT

# --- The platen-screw taps, transferred from MHA-PD-02 -----------------------
# On MHA-PD-02's lower guide-hole row; their row on this rail follows the
# platen's hole (its .XXX row), the strip's height, the crest set and the
# spot: MHA-PD-00 spots them with the largest 1/64 transfer punch that enters
# the platen's Ø.144 holes (draw_pd_paper_drive_assembly.GUIDE_SPOT_PUNCH),
# which floats in a hole drilled to its oversize
# (rocker_bracket_seat_layout.PUNCH_FLOAT's premise).
PLATEN_TAP_X = GUIDE_HOLE_X
PLATEN_TAP_Y = GUIDE_HOLE_Y[0] - UNDERSIDE_ABOVE_PLATEN_BOTTOM  # .466
HOLE_TRANSFER_BAND = 0.0254  # .001 per axis, a transfer screw in its own tap
PLATEN_SPOT_PUNCH_64THS = math.floor(GUIDE_HOLE_DIA / MM_PER_IN * 64.0)  # 9/64
PLATEN_SPOT_PUNCH_FLOAT = (
    GUIDE_HOLE_DIA
    + drilled_oversize_mm(unit=PLATEN_UNIT)
    - PLATEN_SPOT_PUNCH_64THS / 64.0 * MM_PER_IN
) / 2.0
PLATEN_TAP_Y_BAND = (
    printed_band_mm(PLATEN_PRECISION["Guide1Y"], unit=PLATEN_UNIT)
    + _STRIP_HEIGHT_ROOM
    + CREST_SET_BAND
    + PLATEN_SPOT_PUNCH_FLOAT
)

# --- The lock taps, printed --------------------------------------------------
# MHA-PD-11's two lock stations (30% and 70% across), a screw .276 either side
# of each; their row stands at the same height above the platen as the bottom
# MHA-PD-11 rail's did, so the lock plates and the lock-station sweep keep
# their geometry. Printed from the underside at .XXX.
LOCK_SCREW_DX = 7.0104  # .276, build_pd_platen_guide.LOCK_SCREW_DX
LOCK_STATION_X = (GUIDE_HOLE_X[1], GUIDE_HOLE_X[3])
LOCK_TAP_X = tuple(s + d for s in LOCK_STATION_X for d in (-LOCK_SCREW_DX, LOCK_SCREW_DX))
LOCK_TAP_Y = 0.466 * MM_PER_IN
LOCK_TAP_Y_BAND = BAND
if abs(LOCK_TAP_Y - PLATEN_TAP_Y) > BAND:
    raise AssertionError("the lock-tap row left the platen-screw row")

# --- Height: the platen-screw taps' wall to the top face (rule 17) -----------
# The transferred row at its worst band, the tap major, the title block's
# .010 outside edge break and .010 tap mouth break, and the height's .XXX band:
# the least .001 height that keeps the .060 floor.
_TAP_REACH = _TAP_MAJOR / 2.0 + EDGE_BREAK + TAP_MOUTH_BREAK
GUIDE_HEIGHT = (
    math.ceil(
        round(
            (PLATEN_TAP_Y + PLATEN_TAP_Y_BAND + _TAP_REACH + WALL_FLOOR_MM + BAND)
            / MM_PER_IN
            * 1000.0,
            6,
        )
    )
    / 1000.0
    * MM_PER_IN
)  # .624
TOP_ABOVE_PLATEN_BOTTOM = UNDERSIDE_ABOVE_PLATEN_BOTTOM + GUIDE_HEIGHT
# How far the top rose over the former bottom rail's: the 0.98 running room
# under the support bar pays it (build_pd_paper_drive_assembly asserts).
TOP_RISE = TOP_ABOVE_PLATEN_BOTTOM - FORMER_TOP_ABOVE_PLATEN_BOTTOM
PLATEN_TAP_TOP_WALL_MIN = (
    GUIDE_HEIGHT - BAND - (PLATEN_TAP_Y + PLATEN_TAP_Y_BAND) - _TAP_REACH
)
PLATEN_TAP_BOTTOM_WALL_MIN = PLATEN_TAP_Y - PLATEN_TAP_Y_BAND - _TAP_REACH
LOCK_TAP_TOP_WALL_MIN = GUIDE_HEIGHT - BAND - (LOCK_TAP_Y + LOCK_TAP_Y_BAND) - _TAP_REACH
if min(PLATEN_TAP_TOP_WALL_MIN, PLATEN_TAP_BOTTOM_WALL_MIN, LOCK_TAP_TOP_WALL_MIN) < (
    WALL_FLOOR_MM - 1e-9
):
    raise AssertionError("a bottom-guide tap's wall to a face is under the .060 floor")

# --- The rack-screw holes, struck from MHA-PD-26 -----------------------------
# Over the rack's taps (the strip lies flush with the rail's ends), on the
# strip's centreline: FRONT_BEHIND_PLATEN plus half the strip's face width
# from the front face. #51 through (close to the .060 screw), counterbored
# Ø.110 from the top to the rack spec's floor (rail height less the
# counterbore depth: the height's .XXX and the depth's own ±.005,
# pd_feed_rack_spec.SCREW_FLOOR_BAND).
# The rail is placed Ry180 (its native Front on the platen, as MHA-PD-11), so
# its local x runs from the platen's +X end while the strip's runs from its
# -X end: the stations mirror about the rail's length.
SCREW_HOLE_X = tuple(sorted(GUIDE_LENGTH - x for x in rack.TAP_X))
SCREW_HOLE_Z = rack.FRONT_BEHIND_PLATEN + rack.TAP_Z  # from the front face
SCREW_HOLE_DIA = NUMBER_DRILL_MM["#51"]  # .067
SCREW_CBORE_DIA = 0.110 * MM_PER_IN  # #35
SCREW_CBORE_DEPTH = GUIDE_HEIGHT - rack.SCREW_FLOOR  # .469
# The counterbore's printed bands, (upper, lower) in mm: owner ruling
# 2026-11-25 (#3620), "b: Ø.110 +.004/−0 and depth .469 ±.005". With no band of
# its own each would be a Hole Wizard pocket at the .XX grade, ±.01 (rule 3,
# _wizard_pocket_band), and at ±.01 the Ø.096 #0 head can hang on a Ø.100
# pocket (SCREW_HEAD_ENTRY_MIN -.003), the longest screw on the thinnest floor
# runs .005 into the rack tap's lead (pd_feed_rack_spec.SCREW_TIP_REACH_MAX),
# the engagement falls to .0275 under MHA-PD-26's printed .032 MIN
# (ENGAGEMENT_WORST) and the front wall to .0417 under the printed .044 MIN
# (SCREW_CBORE_FRONT_WALL_MIN). The part puts both bands on the RackScrewHoles
# Hole Wizard feature (build_pd_platen_bottom_guide._band_rack_screw_counterbores)
# so the native callout displays them.
SCREW_CBORE_DIA_BAND = (0.1016, 0.0)  # Ø.110 +.004/-.000
SCREW_CBORE_DEPTH_BAND = (0.127, -0.127)  # .469 +.005/-.005
SCREW_HOLE_SPEC = HoleSpec(
    "counterbore_fillister",
    "#0",
    overrides_mm={
        "HoleDiameter": SCREW_HOLE_DIA,
        "CounterBoreDiameter": SCREW_CBORE_DIA,
        "CounterBoreDepth": SCREW_CBORE_DEPTH,
    },
)
# The floor between the counterbore and the underside carries the height's
# .XXX row and the depth's own band.
if not (
    math.isclose(rack.SCREW_FLOOR_BAND, BAND + SCREW_CBORE_DEPTH_BAND[0])
    and -SCREW_CBORE_DEPTH_BAND[1] == SCREW_CBORE_DEPTH_BAND[0]
    and math.isclose(rack.TAP_BAND, BAND)
):
    raise AssertionError(
        "the rack's floor band is not this rail's .XXX height and counterbore depth bands"
    )
# The screws find their holes: each hole was struck from its own tap, so the
# shank's float in #51 need only carry the transfer.
SCREW_FLOAT_RADIAL = (SCREW_HOLE_DIA - _screw.SHANK_DIA) / 2.0
if SCREW_FLOAT_RADIAL < math.hypot(HOLE_TRANSFER_BAND, HOLE_TRANSFER_BAND):
    raise AssertionError("the rack screws cannot find their struck holes")
# The head enters the narrowest printed counterbore (picked up on the #51
# hole) with the shank anywhere in that float (which bounds the transfer the
# head actually follows), and bears on its floor outside the hole. The least
# margin the shop reads is .001 in (tolerance-policy.md, "Checks in spec
# modules and tests").
SCREW_HEAD_ENTRY_MIN = (
    SCREW_CBORE_DIA + SCREW_CBORE_DIA_BAND[1] - 2.0 * SCREW_FLOAT_RADIAL - _screw.HEAD_DIA
)
if not (SCREW_HOLE_DIA < _screw.HEAD_DIA and SCREW_HEAD_ENTRY_MIN >= 0.0254 - 1e-9):
    raise AssertionError("the rack-screw head does not seat in its counterbore")
# The counterbore's wall to the front face at the top edge (rule 17; RV-01):
# the hole follows the strip (front set, the tap's .XXX place across it, the
# transfer), the counterbore at its printed largest, the .010 edge break.
# The strip lies Rx180 (build_pd_paper_drive_assembly), so the face its taps
# are located from is the machine-rear one: a strip narrower by its receiving
# room brings the taps that much nearer the rail's front face.
_STRIP_WIDTH_ROOM = rack.RACK_THICKNESS - rack.PURCHASED_RACK_FACE_WIDTH_MIN_MM
_SCREW_HOLE_Z_BAND = (
    rack.FRONT_SET_BAND + _STRIP_WIDTH_ROOM + rack.TAP_BAND + HOLE_TRANSFER_BAND
)
SCREW_CBORE_FRONT_WALL_MIN = (
    SCREW_HOLE_Z
    - _SCREW_HOLE_Z_BAND
    - (SCREW_CBORE_DIA + SCREW_CBORE_DIA_BAND[0]) / 2.0
    - EDGE_BREAK
)
SCREW_CBORE_FRONT_WALL_NOMINAL = SCREW_HOLE_Z - SCREW_CBORE_DIA / 2.0
SCREW_CBORE_FRONT_WALL_TEXT = (
    f"WALL {f'{math.floor(round(SCREW_CBORE_FRONT_WALL_MIN / MM_PER_IN * 1000.0, 6)) / 1000.0:.3f}'.removeprefix('0')}"
    " MIN TO FRONT FACE"
)
if SCREW_CBORE_FRONT_WALL_MIN <= 0.0:
    raise AssertionError("a rack-screw counterbore breaks the rail's front face")
if SCREW_CBORE_FRONT_WALL_MIN < WALL_FLOOR_MM:
    _declared = _config.parts("pd-platen-bottom-guide").get("machinist_exceptions") or ()
    if not any(
        isinstance(entry, dict) and entry.get("id") == "RV-01" and entry.get("kind") == "minor"
        for entry in _declared
    ):
        raise AssertionError("pd-platen-bottom-guide: no minor RV-01 declares the counterbore wall")
# The stepped holes keep clear of every through tap along the rail: the
# stations' half-pitch slip, the transfers and each feature's radius, the
# counterbore's at its printed largest.
SCREW_HOLE_TAP_WALL_MIN = min(
    abs(x - t)
    for x in SCREW_HOLE_X
    for t in (*PLATEN_TAP_X, *LOCK_TAP_X)
) - (
    rack.TAP_STATION_SLIP_MAX
    + 2.0 * HOLE_TRANSFER_BAND
    + BAND
    + (SCREW_CBORE_DIA + SCREW_CBORE_DIA_BAND[0]) / 2.0
    + _TAP_MAJOR / 2.0
)
if SCREW_HOLE_TAP_WALL_MIN < WALL_FLOOR_MM:
    raise AssertionError("a rack-screw hole crowds a bottom-guide tap")

# --- The print ---------------------------------------------------------------
# The length prints .XX (the rail's ends meet the platen's, printed .XX); the
# height .XXX (the floor and tap walls above read it); the depth carries
# MHA-PD-11's one-sided band as native LIMITs; the lock taps' stations from
# the left end and row from the underside at .XXX. The transferred holes
# carry no location: their callouts name the part they are struck from.
LOCK_LOCATION_NAMES = ("LockTap1X", "LockTap2X", "LockTap3X", "LockTap4X", "LockTapY")
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GuideProfile": {"Length", "Height"},
    "Guide": {"Depth"},
    "LockHoles": set(LOCK_LOCATION_NAMES),
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GuideProfile": {"Length": 2, "Height": PLACES},
    "Guide": {"Depth": GUIDE_DEPTH_PLACES},
    "LockHoles": dict.fromkeys(LOCK_LOCATION_NAMES, PLACES),
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {f: set(d) for f, d in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked bottom-guide dimension needs native precision")
DRAWING_NOMINALS_MM = {
    "Length": GUIDE_LENGTH,
    "Height": GUIDE_HEIGHT,
    "Depth": GUIDE_DEPTH,
    **{f"LockTap{k + 1}X": x for k, x in enumerate(LOCK_TAP_X)},
    "LockTapY": LOCK_TAP_Y,
}
ISOMETRIC_VIEW_SCALE = (1, 2)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
