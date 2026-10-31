r"""MHA-MG-06 output fixture: drawing-free geometry and installed pose.

PURE DATA, no SolidWorks/COM imports and no drawing spec, title block or
registry in its import closure. The assembly and lever wire share the
fixture's shape and pose without importing its drawing contracts.
Shared interference oracles deliberately restate test-pinned limit literals;
they do not import this pose module. Release exporters remain pinned to
archived CAD; the geometry cutover accompanies the asset refresh in #1351.
Bands, places, worst-case walls and sheet text live in
``mg_output_fixture_spec``.

The fixture (book ch. 20 p. 48, the photographed small hex block on the
vertical rod) is a 7/16 brass hex bar: the vertical rod slides through a
cross bore across the hex corners, a turned spigot on one end carries the
full-radius groove the lever wire hooks into, and an axial #4-40 tap from
the spigot face down to the rod bore takes the thumb screw that locks the
fixture to the rod.

Part frame: the origin is the rod-bore centre, on the hex axis.  The hex axis
is local +X, from the free end (x = FREE_END_X) through the shoulder
(x = SHOULDER_X) to the spigot face (x = SPIGOT_FACE_X).  The flats face
+/-Z and the corners lie on +/-Y; the rod bore runs along local Y through the
corners, centred between the flats.  The hook
point is the groove's +Z tangent station: the wire's centre where it sits in
the groove root with its running clearance.

Installed pose: ``Ry(180 deg + FIXTURE_YAW_DEG)`` about the vertical rod, so
local +X runs back through the spigot toward the bracket and the hook lands
on the lever wire's start (``sh_vn_music_wire_lever_geom.WIRE_START``). Option A1
(#1559, the true plumb plane of ch30 p.4): the rod axis sits in the drum's
wire lane and the hook lies in the rod's own plane (dz = 0), so the lever
wire runs coplanar with the drum lane.
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from mg_magnifying_vertical_rod_geom import ROD_DIA as VROD_DIA

# --- Stock: 7/16 hex brass bar (independent of the larger MG-02 clamp) -------
# As bought: the sheet prints the flats as the stock's (7/16 in) REF.
HEX_AF = 7.0 / 16.0 * 25.4  # 11.1125 across the flats
# Centre to a corner: the hex's half-extent along local Y.
HEX_CORNER_RADIUS = HEX_AF / math.sqrt(3.0)

# --- Stations along the hex axis (local x; origin on the rod-bore axis) ----------
# The free end's and the spigot face's stations, and the groove's station and
# root Ø below, set the installed hook and the bracket arm's load: they keep
# their millimetre nominals and print rounded (.209, .50, .15, .30).
ROD_STATION = 5.30  # free end to the rod-bore axis
FREE_END_X = -ROD_STATION
# Spigot face back to the shoulder: the lathe's own length from the faced end.
SPIGOT_LENGTH = 6.604  # .26
# The spigot face's station from the bore axis (.500).
_FACE_STATION = 12.70
HEX_LENGTH = ROD_STATION + _FACE_STATION - SPIGOT_LENGTH  # free end to the shoulder
SHOULDER_X = FREE_END_X + HEX_LENGTH
SPIGOT_FACE_X = SHOULDER_X + SPIGOT_LENGTH
OVERALL_LENGTH = HEX_LENGTH + SPIGOT_LENGTH

# --- Rod bore: across the corners, along local Y, through the hex axis --------
# Centred between the flats by the hex sketch's symmetry: no location from a
# flat (mg_output_fixture_spec takes the drill's run-off as its offset).
# Drilled running clearance on the vertical rod: the smallest drill-index
# drill whose size prints exactly at .XXX and clears the rod by .007 or more.
_CLEARANCE_DRILLS_IN = {
    "#12": 0.189,
    "#11": 0.191,
    "#9": 0.196,
    "#8": 0.199,
    "#7": 0.201,
    "#6": 0.204,
    "#4": 0.209,
    "#3": 0.213,
    "#2": 0.221,
    "#1": 0.228,
}
ROD_BORE_CLEARANCE_MIN = 0.1778  # .007 diametral
ROD_BORE_DRILL, ROD_BORE_DIA = min(
    (
        (drill, round(size_in * 25.4, 6))
        for drill, size_in in _CLEARANCE_DRILLS_IN.items()
        if size_in * 25.4 >= VROD_DIA + ROD_BORE_CLEARANCE_MIN - 1e-9
    ),
    key=lambda row: row[1],
)

# --- Spigot and its full-radius wire groove ------------------------------------
# The groove arc's centre sits exactly on the spigot OD (OD = root Ø + 2R), so
# the groove is a true semicircle, as deep as its radius: a centre inside the
# OD would cut a re-entrant (undercut) groove, not turnable.  The radius is
# its LIMIT's upper value (.047), the root Ø the hook's (exempt above), so
# the OD follows them and prints rounded (.40).
GROOVE_RADIUS = 1.1938  # .047
GROOVE_ROOT_DIA = 7.7
SPIGOT_DIA = GROOVE_ROOT_DIA + 2.0 * GROOVE_RADIUS
# The internal corner where the spigot turns up to the hex shoulder: a
# .008 tool-nose radius.  It stays on the shoulder face inside the flats and
# short of the groove.
SHOULDER_FILLET_R = 0.2032  # .008
# The groove's station from the spigot face: its face-side lip holds the wall
# target at the worst case; the shoulder side takes the rest of the spigot.
GROOVE_STATION = 3.75
GROOVE_X = SPIGOT_FACE_X - GROOVE_STATION
# The groove arc meets the OD at a mouth on each side, GROOVE_HALF_OPENING
# from GROOVE_X (the full radius: the centre is on the OD).
GROOVE_CENTRE_R = GROOVE_ROOT_DIA / 2.0 + GROOVE_RADIUS
GROOVE_HALF_OPENING = math.sqrt(
    max(GROOVE_RADIUS**2 - (GROOVE_CENTRE_R - SPIGOT_DIA / 2.0) ** 2, 0.0)
)
GROOVE_MOUTHS = (GROOVE_X - GROOVE_HALF_OPENING, GROOVE_X + GROOVE_HALF_OPENING)

# --- Thumb-screw tap: axial #4-40 from the spigot face into the rod bore --------
THREAD = "#4-40"
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]
# Where the tap's axis breaks into the rod bore.
TAP_BREAKOUT_X = ROD_BORE_DIA / 2.0
# Full thread from the spigot face to that breakout: the callout's thread
# depth, its nominal (REF on the sheet: the rod bore ends the thread).
TAP_LENGTH = SPIGOT_FACE_X - TAP_BREAKOUT_X
# The tap drill runs on to the bore axis: its full Ø clears the near wall and
# its point stops in the bore, short of the far wall (the spec proves both at
# the printed worst case).  A blind tap, not up-to-next: the callout states
# the drill depth and the REF thread depth instead of a THRU the far wall
# would contradict.
TAP_DRILL_DEPTH = SPIGOT_FACE_X
TAP_SPEC = HoleSpec(
    "tapped",
    THREAD,
    end="blind",
    depth_mm=TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": TAP_LENGTH},
)
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)

# --- Lever wire hook ------------------------------------------------------------
WIRE_DIA = 0.8
WIRE_CLEARANCE = 0.25
HOOK_RADIAL_OFFSET = GROOVE_ROOT_DIA / 2.0 + WIRE_DIA / 2.0 + WIRE_CLEARANCE
HOOK_LOCAL = (GROOVE_X, 0.0, HOOK_RADIAL_OFFSET)

# --- Installed pose (magnifier frame) -------------------------------------------
FIXTURE_AXIS_Y = 919.7  # the hex axis's height on the vertical rod
# The vertical rod's axis: the drum's wire lane (sh_vn_music_wire_lever_geom.DRUM_END_Z,
# asserted equal there). A literal, so this part's recipe closure stays free of
# the wheel and paper modules.
VROD_Z = -173.5192
# The lever wire leaves in the rod's plane (option A1): dz = 0.
HOOK_TARGET_Z = VROD_Z


def fixture_yaw_rad(hook_x: float, hook_z: float, target_dz: float) -> float:
    """Yaw ``phi`` of the pose ``Ry(pi + phi)`` that puts a local hook at
    (``hook_x``, ``hook_z``) at machine dz = ``target_dz`` from the rod axis.

    Under ``Ry(pi + phi)`` the local hook lands at dz = x sin(phi) - z cos(phi),
    which is ``hypot(x, z) * sin(phi - atan2(z, x))``."""
    return math.atan2(hook_z, hook_x) + math.asin(
        target_dz / math.hypot(hook_x, hook_z)
    )


FIXTURE_YAW_RAD = fixture_yaw_rad(HOOK_LOCAL[0], HOOK_LOCAL[2], HOOK_TARGET_Z - VROD_Z)
FIXTURE_YAW_DEG = math.degrees(FIXTURE_YAW_RAD)
# The hook's machine offset from the fixture origin under Ry(180 + yaw).
HOOK_OFFSET_X = -(
    HOOK_LOCAL[0] * math.cos(FIXTURE_YAW_RAD)
    + HOOK_LOCAL[2] * math.sin(FIXTURE_YAW_RAD)
)
HOOK_OFFSET_Z = HOOK_LOCAL[0] * math.sin(FIXTURE_YAW_RAD) - HOOK_LOCAL[2] * math.cos(
    FIXTURE_YAW_RAD
)

# --- Import-time geometry guards -------------------------------------------------
if abs(HOOK_OFFSET_Z - (HOOK_TARGET_Z - VROD_Z)) > 1e-9:
    raise AssertionError("MHA-MG-06 yaw does not put the hook in the rod's plane")
if HOOK_OFFSET_X >= 0.0:
    raise AssertionError("MHA-MG-06 hook must sit on the bracket side of the rod")
if abs(GROOVE_CENTRE_R - SPIGOT_DIA / 2.0) > 1e-9:
    raise AssertionError(
        "MHA-MG-06 groove centre is not on the spigot OD (semicircle)"
    )
if not SHOULDER_X < GROOVE_MOUTHS[0] < GROOVE_MOUTHS[1] < SPIGOT_FACE_X:
    raise AssertionError("MHA-MG-06 groove runs off the spigot")
if not SPIGOT_DIA < HEX_AF:
    raise AssertionError("MHA-MG-06 spigot leaves no shoulder inside the flats")
if not SHOULDER_FILLET_R < (HEX_AF - SPIGOT_DIA) / 2.0:
    raise AssertionError("MHA-MG-06 shoulder fillet runs off the shoulder onto a flat")
if not SHOULDER_X + SHOULDER_FILLET_R < GROOVE_MOUTHS[0]:
    raise AssertionError("MHA-MG-06 shoulder fillet runs into the groove")
if not ROD_BORE_DIA < HEX_AF:
    raise AssertionError("MHA-MG-06 rod bore breaks through a flat")
if not TAP_DRILL_DIA < ROD_BORE_DIA:
    raise AssertionError("MHA-MG-06 tap drill does not end inside the rod bore")
if not 0.0 < TAP_LENGTH < TAP_DRILL_DEPTH:
    raise AssertionError("MHA-MG-06 tap drill stops short of the thread it carries")
if not THREAD_MAJOR < GROOVE_ROOT_DIA:
    raise AssertionError("MHA-MG-06 thread breaks into the groove")
if not VROD_DIA < ROD_BORE_DIA:
    raise AssertionError("MHA-MG-06 rod bore does not clear the vertical rod")
