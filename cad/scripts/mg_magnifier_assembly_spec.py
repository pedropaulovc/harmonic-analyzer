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
DIMENSION_TOLERANCES = {
    PRESS_GAUGE_DIMENSION: PRESS_GAUGE_TOL,
    ENDSHAKE_DIMENSION: ENDSHAKE_TOL,
}

# --- The lever group's settings (LEVER_FEATURE, Front plane: sketch x is
# machine x, sketch y machine y) ---------------------------------------------
# The lever rod lies along machine x at the bracket's height; its west dome
# tip is the collar station east of the bracket (Ry(180) placement).
LEVER_AXIS_Y = _bracket.BRACKET_ORIGIN[1]
LEVER_TIP_X = _bracket.BRACKET_ORIGIN[0] + _lever.COLLAR_LOCAL_X
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

# Native IDisplayDimension.SetText compartments (swDimensionTextParts_e):
# 3 = swDimensionTextCalloutAbove, 4 = swDimensionTextCalloutBelow. These are
# model annotations, not sheet prose: imported SetText writes through to the
# source. Keep their text and native compartments under one model authority.
# Above-callouts must stay on one line: SOLIDWORKS stores a line break there
# but prints none of the callout (run 20261012T185729782Z). Below ones can wrap.
SETTING_CALLOUTS = {
    FEATURE: {
        # The wheel-group stack spends this band to keep the locknut on full
        # thread (LOCKNUT_THREAD_MARGIN 0.002); state the protected function.
        PRESS_GAUGE_DIMENSION: (
            3,
            "PRESS GAUGE: KEEPS MHA-MG-VN-52 LOCKNUT ON FULL THREAD",
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
}
