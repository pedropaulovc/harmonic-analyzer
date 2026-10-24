"""The MHA-MG-00 magnifier assembly settings: the builder's and the sheet's.

Two settings belong to no single part: the press gauge the wheel axle is pressed
to in the bar, and the endshake the first nut sets. Each one is printed as a
native model dimension on the MHA-MG-00 sheet. A construction chain in the
assembly carries both (the ms-measuring-stick ClampedSetting pattern). It runs
along the axle centreline on the Right plane, through four stations: the bar
front face, the shank step, the wheel's spigot face and the front washer. The
chain is blanked, so it prints only in the drawing view that dimensions it.

Two more are the lever group's operator settings: the clamp station on the
lever and the output fixture's drop below the lever axis. A second blanked
chain on the Front plane carries them (LEVER_FEATURE), from the lever rod's
west tip along its axis to the clamp centre, then down the vertical-rod line
to the fixture axis. They print at the title block's general tolerance.

The native setting callout text and its display-dimension compartments belong
to these model dimensions too: SETTING_CALLOUTS is authored before assembly
save and only read back by the drawing. BOM rows, steps, checks and the map of
axle dimensions the drawing imports stay in mg_magnifier_assembly_sheet, so
edits to that sheet-only wording do not rebuild the assembly.
"""

from __future__ import annotations

import magnifying_bracket_joint_layout as _bracket
import mg_magnifying_lever_geom as _lever
import mg_output_fixture_geom as _fixture
import mg_wheel_axle_spec as _pin
import mg_wheel_bar_geom as _bar
import mg_wheel_group as _group
from sh_vn_music_wire_lever_geom import WHEEL_X
from mg_wheel_bar_geom import WHEEL_BAR_Y

# Native saved-view contract, captured before rebasing standard Front to -Z.
# These preserve the fitter package's physical projections, not sheet wording.
# The ISO prefix opts the named isometric into shared pictorial display checks.
DRAWING_BACK_VIEW = "MG BACK"
DRAWING_LEFT_VIEW = "MG LEFT"
DRAWING_ISOMETRIC_VIEW = "ISO MG BACK-TOP-LEFT"
DRAWING_STANDARD_VIEWS = {
    DRAWING_BACK_VIEW: 1,  # swStandardViews_e.swFrontView: viewer at +Z
    DRAWING_LEFT_VIEW: 4,  # swStandardViews_e.swRightView: viewer at +X
    DRAWING_ISOMETRIC_VIEW: 7,  # swStandardViews_e.swIsometricView: +X+Y+Z
}

# The axle centreline in the machine frame: x, y of the bore; z runs from the
# bar's front face forward (-z), station d at z = BAR_FRONT_Z - d.
AXLE_X = WHEEL_X
AXLE_Y = WHEEL_BAR_Y
BAR_FRONT_Z = _bar.BAR_FRONT_Z

PRESS_GAUGE = _pin.PRESS_GAUGE
PRESS_GAUGE_TOL = _pin.PRESS_GAUGE_TOL
# The press gauge prints as a REFERENCE nominal, (38.10): its acceptance is
# the function it serves, checked at the nuts once they are set and printed
# on its callout (machinist review of 179705ff2: a ±0.05 band on a hand press
# is unneeded precision when the function itself is checkable). The stack
# shows a press to nominal passes that check. PRESS_GAUGE_TOL is the press
# allocation the wheel-group stack spends (mg_wheel_group corners), inside
# this window. Low: the shortest gauge whose full thread still runs past the
# locknut's outer face at the thick-stack corner (LOCKNUT_THREAD_MARGIN) --
# 38.048. High: the tightest of three upper limits, at the thin-stack corner:
# at most THREAD_PAST_LOCKNUT_LIMIT of thread past the locknut (38.183), the
# first nut clear of the axle's thread relief (38.214) and the step inside the hub
# (38.807). The callout names the thread-past-locknut limit as the high
# side's acceptance, so it must govern.
PRESS_GAUGE_LOW_LIMIT = PRESS_GAUGE - PRESS_GAUGE_TOL - _group.LOCKNUT_THREAD_MARGIN
_PRESS_GAUGE_HIGH_LIMITS = {
    "thread past locknut": _pin.THREAD_PAST_LOCKNUT_LIMIT
    - _group.THREAD_PAST_LOCKNUT_MAX,
    "nut run-out": _group.NUT_RUNOUT_MARGIN,
    "step inside hub": _group.STEP_INSIDE_HUB,
}
PRESS_GAUGE_HIGH_LIMIT = (
    PRESS_GAUGE + PRESS_GAUGE_TOL + min(_PRESS_GAUGE_HIGH_LIMITS.values())
)
if min(_PRESS_GAUGE_HIGH_LIMITS, key=_PRESS_GAUGE_HIGH_LIMITS.get) != (
    "thread past locknut"
):
    raise AssertionError(
        "the press gauge's high limit no longer protects the thread end"
    )
if not (
    PRESS_GAUGE_LOW_LIMIT
    <= PRESS_GAUGE - PRESS_GAUGE_TOL
    < PRESS_GAUGE + PRESS_GAUGE_TOL
    <= PRESS_GAUGE_HIGH_LIMIT
):
    raise AssertionError("the press allocation leaves the wheel-group stack window")
# The modelled endshake sits mid-band, so its band prints symmetric.
ENDSHAKE = _group.ENDSHAKE
ENDSHAKE_TOL = _group.ENDSHAKE_MAX - _group.ENDSHAKE
if abs((_group.ENDSHAKE - _group.ENDSHAKE_MIN) - ENDSHAKE_TOL) > 1e-9:
    raise AssertionError("the endshake band is not symmetric about its model value")

# Chain stations d (from the bar front face) along the axle centreline.
STEP_D = PRESS_GAUGE
HUB_FRONT_D = _group.HUB_FRONT_D
WASHER_D = _group.FRONT_WASHER_D
if abs((WASHER_D - HUB_FRONT_D) - ENDSHAKE) > 1e-9:
    raise AssertionError("the front washer no longer sits one endshake off the hub")
if not 0.0 < HUB_FRONT_D - STEP_D:
    raise AssertionError("the shank step must stand inside the wheel hub")
CHAIN_D = (0.0, STEP_D, HUB_FRONT_D, WASHER_D)

FEATURE = "AxleStackReference"
PRESS_GAUGE_DIMENSION = "PressGauge"
ENDSHAKE_DIMENSION = "Endshake"
DRAWING_PRECISION = {FEATURE: {PRESS_GAUGE_DIMENSION: 2, ENDSHAKE_DIMENSION: 2}}
TOLERANCE_PRECISION = 2
DIMENSION_TOLERANCES = {ENDSHAKE_DIMENSION: ENDSHAKE_TOL}
# Printed as (value) through the native prefix/suffix channel, no band.
REFERENCE_DIMENSIONS = frozenset({PRESS_GAUGE_DIMENSION})
if REFERENCE_DIMENSIONS | set(DIMENSION_TOLERANCES) != set(
    DRAWING_PRECISION[FEATURE]
) or REFERENCE_DIMENSIONS & set(DIMENSION_TOLERANCES):
    raise AssertionError("each stack setting is either banded or a reference")

# --- The lever group's settings (LEVER_FEATURE, Front plane: sketch x is
# machine x, sketch y machine y) ---------------------------------------------
# The nominal machine pose is unchanged. At fit-up the far-face projection
# controls installation; the free tip may shift within accepted part bands.
LEVER_AXIS_Y = _bracket.BRACKET_ORIGIN[1]
LEVER_TIP_X = _bracket.BRACKET_ORIGIN[0] + _lever.BRACKET_LOCAL_X
CLAMP_STATION = _lever.CLAMP_LOCAL_X
CLAMP_CENTRE_X = LEVER_TIP_X - CLAMP_STATION
FIXTURE_AXIS_Y = _fixture.FIXTURE_AXIS_Y
FIXTURE_DROP = LEVER_AXIS_Y - FIXTURE_AXIS_Y
if not 0.0 < FIXTURE_DROP:
    raise AssertionError("the output fixture must hang below the lever axis")
LEVER_FEATURE = "LeverSettingReference"
CLAMP_STATION_DIMENSION = "ClampStation"
FIXTURE_DROP_DIMENSION = "FixtureDrop"
LEVER_DRAWING_DIMENSIONS = {
    LEVER_FEATURE: {CLAMP_STATION_DIMENSION, FIXTURE_DROP_DIMENSION}
}
LEVER_DRAWING_PRECISION = {
    LEVER_FEATURE: {CLAMP_STATION_DIMENSION: 1, FIXTURE_DROP_DIMENSION: 1}
}

# A separate native installation witness: flat tip proud of the far neck face.
# .XX general tolerance is an assembly setting, not a manufactured shoulder.
THREAD_FEATURE = "LeverThreadSetting"
THREAD_PROJECTION_DIMENSION = "ThreadProjection"
THREADED_TIP_X = LEVER_TIP_X - _lever.ROD_LENGTH
THREAD_FAR_FACE_X = _bracket.BRACKET_ORIGIN[0] - _lever.NECK_HALF_X
THREAD_PROJECTION = _lever.THREAD_PROJECTION
THREAD_DRAWING_DIMENSIONS = {THREAD_FEATURE: {THREAD_PROJECTION_DIMENSION}}
THREAD_DRAWING_PRECISION = {THREAD_FEATURE: {THREAD_PROJECTION_DIMENSION: 2}}
THREAD_PROJECTION_TOL = _lever.THREAD_PROJECTION_TOL
INSTALLED_FULL_ENGAGEMENT_MIN = _lever.INSTALLED_FULL_ENGAGEMENT_MIN

# Native IDisplayDimension.SetText compartments (swDimensionTextParts_e):
# 3 = swDimensionTextCalloutAbove, 4 = swDimensionTextCalloutBelow. These are
# model annotations, not sheet prose: imported SetText writes through to the
# source. Keep their text and native compartments under one model authority.
# Above-callouts must stay on one line: SOLIDWORKS stores a line break there
# but prints none of the callout (run 20261012T185729782Z). Below ones can wrap.
SETTING_CALLOUTS = {
    FEATURE: {
        # The reference gauge's acceptance, both sides of the stack window
        # (PRESS_GAUGE_LOW_LIMIT, PRESS_GAUGE_HIGH_LIMIT), in the axle
        # drawing's thread-length wording (mg_wheel_group).
        PRESS_GAUGE_DIMENSION: (
            3,
            "ACCEPT: LOCKNUT ON FULL THREAD, THREAD END "
            f"{_pin.THREAD_PAST_LOCKNUT_LIMIT:.1f} MAX PAST IT",
        ),
        ENDSHAKE_DIMENSION: (
            4,
            "WHEEL FREE, NO RATTLE;\nSET BY THE FIRST NUT,\nLOCKED BY THE SECOND",
        ),
    },
    LEVER_FEATURE: {
        CLAMP_STATION_DIMENSION: (3, "CLAMP STATION: SETS MAGNIFICATION"),
        FIXTURE_DROP_DIMENSION: (4, "FIXTURE DROP:\nSETS TRACE HEIGHT"),
    },
    THREAD_FEATURE: {
        THREAD_PROJECTION_DIMENSION: (
            4,
            "FLAT LEVER TIP\nPROUD OF FAR\nBRACKET FACE",
        ),
    },
}

