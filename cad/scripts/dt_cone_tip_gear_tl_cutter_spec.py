r"""MHA-DT-37-TL-00: the DT6-FORM1 fly cutter as set up, pure data.

PURE DATA, no SolidWorks/COM and no drawing imports.  Shop tooling, issue
#2358: the bit MHA-DT-37-TL-01 in the bar MHA-DT-37-TL-02's cross hole,
clamped by one bought #4-40 x 1/4 cup-point set screw (MHA-SH-VN-54, the
shared native).  The ``_tl_`` stem keeps the fixture out of every machine
assembly and BOM (``_buildgraph.is_shop_fixture``).

Assembly frame = the bar's part frame: bar axis +Y, the cutting end face on
y = 0, the collet end up.  The bit lies along +X through the cross hole, its
face (its Top Plane) on the XY plane facing +Z: with the spindle turning
forward (clockwise seen from above, from +Y) the tip moves toward +Z, so the
face leads.  The set screw stands on the axis below the bit, its cup on the
bit's shank.

The setting the fitter makes is the stick-out, the tip's reach beyond the
bar's surface; the swing radius is the tip's radius about the bar axis.
Neither changes the tooth space (the face form makes it at any radius); both
are references, and the stick-out window is what the fixture's proofs need.
"""

from __future__ import annotations

import math

import dt_cone_tip_gear_spec as tip
import dt_cone_tip_gear_tl_cutter_bar_spec as bar
import dt_cone_tip_gear_tl_form_cutter_spec as bit
import sh_vn_arbor_set_screw_spec as set_screw
from _assembly_contract import assembly_contract

ASM_NAME = "dt-cone-tip-gear-tl-cutter"
# Literal, so only this kit's contract re-keys the sheets that read it.
CONTRACT = assembly_contract("dt-cone-tip-gear-tl-cutter")
DRAWING_NUMBER = CONTRACT.number
INCH = 25.4

BAR = bar.STEM
BIT = bit.STEM
SET_SCREW = "sh-vn-arbor-set-screw"
QUANTITIES = {BAR: 1, BIT: 1, SET_SCREW: 1}

# --- The setting: stick-out and swing radius ----------------------------------
STICK_OUT = 2.54  # .100 nominal: P1 beyond the bar's surface
STICK_OUT_WINDOW = (2.032, 3.048)  # .080-.120, read with a caliper
SWING_RADIUS = bar.BAR_RADIUS + STICK_OUT
# Both print as references: the assembly's own model dimensions on its hidden
# settings sketch (build_dt_cone_tip_gear_tl_cutter_assembly), one
# construction chain along the bit's axis at the cross-hole station from the
# bar's axis through the bar's surface to P1.  Neither depends on how the
# bit's form edges are built.
SETTINGS_SKETCH = "CutterSettingsReference"
STICK_OUT_DIMENSION = "StickOut"
SWING_RADIUS_DIMENSION = "SwingRadius"
# The chain (assembly X, Y; mm): bar axis, bar surface, P1.
SETTINGS_CHAIN = (
    (0.0, bar.CROSS_HOLE_STATION),
    (bar.BAR_RADIUS, bar.CROSS_HOLE_STATION),
    (SWING_RADIUS, bar.CROSS_HOLE_STATION),
)
# The settings print at the title block's .XXX.
SETTINGS_PLACES = 3
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    SETTINGS_SKETCH: {STICK_OUT_DIMENSION, SWING_RADIUS_DIMENSION},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    SETTINGS_SKETCH: {
        STICK_OUT_DIMENSION: SETTINGS_PLACES,
        SWING_RADIUS_DIMENSION: SETTINGS_PLACES,
    },
}

# --- Poses (assembly frame, mm; rows are the images of the part axes) ----------
BAR_POSITION = (0.0, 0.0, 0.0)
BAR_ROWS = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
# Bit X (toward its tip) -> +X, bit Y (the face normal) -> +Z, bit Z -> -Y.
BIT_ROWS = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))


def bit_position(stick_out: float = STICK_OUT) -> tuple[float, float, float]:
    """The bit's origin, P1, on the cross-hole axis ``stick_out`` past the bar."""
    return (bar.BAR_RADIUS + stick_out, bar.CROSS_HOLE_STATION, 0.0)


BIT_POSITION = bit_position()
# The screw's cup end (its Y = 0) on the bit's top, its socket toward the
# cutting end: screw Y -> -Y.
SET_SCREW_POSITION = (0.0, bar.CROSS_HOLE_STATION - bit.BIT_RADIUS, 0.0)
SET_SCREW_ROWS = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))

# --- Proofs, at every stick-out in the window ---------------------------------
# (a) The tool never reaches inside the T006 root circle: it runs off over
#     both Ø.0625 stems by MHA-DT-37's own margin.
RUNOFF_OVER_STEMS = bit.FORM_RADIUS_MIN - tip.STEM_MAX_DIA_MM / 2.0
if RUNOFF_OVER_STEMS < tip.CUTTER_RUNOFF_MM - 1e-9:
    raise AssertionError("the bit reaches nearer the stems than the T006 root")
# The plunge: blank OD to the root at the gear's standard depth.
PLUNGE_DEPTH = tip.OUTSIDE_DIA / 2.0 - bit.ROOT_RADIUS
# (b) At full depth the bar's surface stands clear of the gear blank.
BAR_CLEARANCE_MIN = STICK_OUT_WINDOW[0] - PLUNGE_DEPTH
if BAR_CLEARANCE_MIN < 0.5:
    raise AssertionError("the bar would come within .020 of the gear blank")
# (c) The cutter's footprint at full depth, along the gear axis, half each way
#     of the bar axis: it clears the leaves' ends over the pivot (the head
#     side holds the spigot, which is longer).
RUNOFF_HALF_CHORD = math.sqrt(
    (bar.BAR_RADIUS + STICK_OUT_WINDOW[1]) ** 2
    - (bar.BAR_RADIUS + STICK_OUT_WINDOW[1] - PLUNGE_DEPTH) ** 2
)
if RUNOFF_HALF_CHORD >= min(tip.PIVOT_LENGTH_MM, tip.SPIGOT_LENGTH_MM):
    raise AssertionError("the cutter cannot run off the leaves over a stem")
# (d) Nothing under the face reaches past the face's own sweep.
TRAILING_REACH_EXCESS = max(
    bit.trailing_reach_excess_mm(bar.BAR_RADIUS + stick_out)
    for stick_out in STICK_OUT_WINDOW
)
if TRAILING_REACH_EXCESS >= 0.0:
    raise AssertionError("the clearance faces recut the tooth space")
# (e) The bit's tail stays inside the bar's far side and under the screw; the
#     tail never swings wider than the tip.
TAIL_X_RANGE = tuple(bar.BAR_RADIUS + s - bit.BIT_LENGTH for s in STICK_OUT_WINDOW)
if not -bar.BAR_RADIUS < TAIL_X_RANGE[0] < TAIL_X_RANGE[1] < -set_screw.MAJOR_DIA:
    raise AssertionError("the bit's tail must stay inside the bar, past the screw")
# (f) Seated on the bit, the screw keeps 1.5D of thread at the bar's shortest
#     cross-hole station (its socket face then stands proudest).
if bar.SET_SCREW_ENGAGED_MIN < bar.SET_SCREW_MIN_ENGAGEMENT:
    raise AssertionError("the seated set screw must keep 1.5D of thread")
# (g) The flat's .063 nominal (bit.FACE_HEIGHT, .0005 above the axis), its
#     band (bit.FLAT_DEPTH_TOL, the title block's .XXX) and the rod's
#     half-band set the face at most bit.FLAT_FACE_OFFSET_MAX off the bar
#     axis.  At the shortest swing, on the form's deepest point, that turns
#     the rake by RAKE_ERROR_DEG_MAX (1.40 deg) and moves each face point
#     outward by sqrt(r^2 + e^2) - r: under .002 mm, near-uniform across the
#     form, which the plunge to over-pins absorbs.  What changes the tooth
#     space's shape is that shift's spread across the form's depth (.0002
#     mm), held under half the MHA-DT-37 sheet 2 table's last place.
#     The same offset slides the cutting edge along the relieved walls: the
#     form widens or narrows uniformly by FACE_SHIFT_WIDTH_MAX (2 e tan(side)),
#     which the plunge to over-pins also takes up, held under half the gear's
#     tooth-thickness band so the plunge keeps the other half; and the edge
#     runs forward by FACE_SHIFT_FORWARD_MAX (e tan(front)), still clear of
#     the stems by the (a) runoff.
_SWING_MIN = bar.BAR_RADIUS + STICK_OUT_WINDOW[0]
_FORM_R_MIN = _SWING_MIN - bit.FORM_DEPTH
_FORM_R_MAX = _SWING_MIN + bit.FORM_X_MAX


def _face_shift(radius: float) -> float:
    offset = bit.FLAT_FACE_OFFSET_MAX
    return math.hypot(radius, offset) - radius


RAKE_ERROR_DEG_MAX = math.degrees(math.asin(bit.FLAT_FACE_OFFSET_MAX / _FORM_R_MIN))
RAKE_ERROR_DEG_LIMIT = 1.5
FORM_DISTORTION_MAX = _face_shift(_FORM_R_MIN) - _face_shift(_FORM_R_MAX)
FORM_DISTORTION_LIMIT = 0.5 * INCH * 10.0**-bit.FORM_PLACES
if RAKE_ERROR_DEG_MAX > RAKE_ERROR_DEG_LIMIT:
    raise AssertionError("the flat's band lets the rake drift past its limit")
if FORM_DISTORTION_MAX >= FORM_DISTORTION_LIMIT:
    raise AssertionError("the flat's band would distort the tooth space")
FACE_SHIFT_WIDTH_MAX = 2.0 * bit.FLAT_FACE_OFFSET_MAX * bit.TAN_SIDE
FACE_SHIFT_WIDTH_LIMIT = 0.5 * abs(
    tip.TOOTH_THICKNESS_BAND[1] - tip.TOOTH_THICKNESS_BAND[0]
)
FACE_SHIFT_FORWARD_MAX = bit.FLAT_FACE_OFFSET_MAX * bit.TAN_FRONT
if FACE_SHIFT_WIDTH_MAX >= FACE_SHIFT_WIDTH_LIMIT:
    raise AssertionError("the flat's band would move the form past the gear's band")
if RUNOFF_OVER_STEMS - FACE_SHIFT_FORWARD_MAX < tip.CUTTER_RUNOFF_MM - 1e-9:
    raise AssertionError("a high face would carry the edge nearer the stems")

# --- Sheet words ---------------------------------------------------------------
BOM_COMPONENTS = (BAR, BIT, SET_SCREW)
BOM_ITEMS = {BAR: "1", BIT: "2", SET_SCREW: "3"}


def _window_text() -> str:
    low, high = (tip.inch_text(value, 3) for value in STICK_OUT_WINDOW)
    return f"{low}-{high}"


# Item 3's cup bears on item 2's plain round: the stick-out is an adjustable
# clamp setting (drawing-guidelines rule 23), so the steps set it, then prove
# the clamp holds it.  Ends and faces go by view names (rule 22): item 1's
# cutting end is its bottom end in the front view.
ASSEMBLY_STEPS = "\n".join(
    (
        "FITTING",
        "1. SLIDE ITEM 2 INTO ITEM 1'S CROSS HOLE, FORM END RIGHT, FACE",
        "   TOWARD THE VIEWER (FRONT VIEW).",
        f"2. SET THE STICK-OUT {_window_text()} (CALIPER).",
        "3. TURN ITEM 2 UNTIL ITS FACE IS PARALLEL TO ITEM 1'S AXIS: A",
        "   SQUARE ON ITEM 1'S BOTTOM END (FRONT VIEW) SHOWS NO LIGHT",
        "   BETWEEN ITS BLADE AND THE FACE.",
        "4. TIGHTEN ITEM 3, CUP END FIRST, UP THROUGH ITEM 1'S BOTTOM END",
        "   (FRONT VIEW) ONTO ITEM 2'S ROUND SHANK.",
        "5. CHECK: ITEM 2 DOES NOT TURN OR SLIDE BY HAND.",
        f"6. CHECK: THE STICK-OUT STILL READS {_window_text()} (CALIPER).",
        "7. IF STEP 5 OR 6 FAILS, LOOSEN ITEM 3 AND REPEAT FROM STEP 2.",
    )
)
# Named above each value; steps 2 and 6 name the stick-out's window.
DIMENSION_CALLOUTS: dict[str, str] = {
    STICK_OUT_DIMENSION: "STICK-OUT",
    SWING_RADIUS_DIMENSION: "SWING RADIUS",
}
ISO_NOTE = "ISOMETRIC VIEW SCALE 2:1"
