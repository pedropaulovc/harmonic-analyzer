"""The MHA-MG-00 magnifier assembly settings: the builder's and the sheet's.

Five settings belong to no single part: the press gauge the wheel axle is
pressed to in the bar, from the spacer's outer face (the press's setting),
the axle's plain end below the bar's far face (where that press leaves it),
the drum's outer face below the wheel's spigot end,
the endshake the first nut sets, and the axle's thread end past the second
nut (the press's acceptance). Each one is printed as a native model dimension
on the MHA-MG-00 sheet. A construction chain in the assembly carries them all
(the ms-measuring-stick ClampedSetting pattern). It runs along the axle
centreline on the Right plane, through ten stations (CHAIN_D), from the bar's
far face to the axle's thread end. The chain is blanked, so it prints only in
the drawing views that dimension it.

Two more are the lever group's operator settings: the clamp station on the
lever and the output fixture's drop below the lever axis. A second blanked
chain on the Front plane carries them (LEVER_FEATURE), from the lever rod's
west tip along its axis to the clamp centre, then down the vertical-rod line
to the fixture axis. They print at the title block's general tolerance.

Every printed length is in the assembly contract's ``drawing_unit`` (UNIT).

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
import mg_magnifying_wheel_geom as _wheel
import mg_wheel_group as _group
from sh_vn_music_wire_lever_geom import WHEEL_X
from mg_wheel_bar_geom import WHEEL_BAR_Y
from _assembly_contract import assembly_contract

ASM_NAME = "mg-magnifier"
# A literal stem: the build graph narrows this drawing's assemblies/*
# dependency to exactly the contracts its closure names.
UNIT = assembly_contract("mg-magnifier").drawing_unit

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
# The press gauge: the shoulder past the spacer's OUTER face, the spacer on
# the shank against the bar's front face, .768 +/-.002 (owner ruling
# 2026-11-21, "fit at assembly": MHA-MG-00 sets the pin's press depth from
# the spacer's outer face, so the spacer's length leaves the nut stack). It
# is the press's setting; the thread end past the second nut stays its
# acceptance (owner ruling 2026-11-06, Q1), checked once the nuts are set.
# The stack shows a press inside the band passes that check: PRESS_GAUGE_TOL
# is the press allocation the wheel-group stack spends (mg_wheel_group
# corners), inside this window. Low: the shortest gauge whose full thread
# still runs past the locknut's outer face at the thick-stack corner
# (LOCKNUT_THREAD_MARGIN). High: the tightest of three upper limits, at the
# thin-stack corner: at most THREAD_PAST_LOCKNUT_LIMIT of thread past the
# locknut, the first nut clear of the axle's thread relief and the step
# inside the hub. The acceptance callout names the thread-past-locknut
# limit, so it must govern.
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

# The press and thread-end settings the MHA-MG-00 steps read with a caliper
# depth rod, each a model length on the same chain (rule 22: a measurable
# setting prints on a view even though the steps print in ASSEMBLY.md).
# Each prints as its two limits; the model's own pose sits inside them.
# The axle's plain end below the bar's far face: the window the axle spec
# proves from the printed shank, spacer, gauge and bar depth.
BAR_FAR_D = -_pin.BAR_DEPTH
BACK_END_D = _pin.BACK_Y
BACK_END_SUNK_LIMITS = (_pin.BACK_END_SUNK_MIN, _pin.BACK_END_SUNK_MAX)
# The pressed drum's outer face below the spigot end (the wheel hub's front
# face): the window the printed spigot and drum lengths prove. The geom
# asserts the near limit >= -1e-9 mm; rounding (and + 0.0, for -0.0) drops
# the float residue the limits' places check would reject.
DRUM_RECESS = _wheel.SPIGOT_LEN - _wheel.DRUM_LEN
DRUM_RECESS_LIMITS = tuple(round(limit, 6) + 0.0 for limit in _wheel.DRUM_RECESS)
# The axle's thread end (the dome's tangent) past the second nut's outer face:
# the press's one acceptance (owner ruling 2026-11-06, Q1), read on the stack.
# High: the axle's limit. Low: the locknut on full thread, i.e. at least the
# dome's incomplete pitch past it (mg_wheel_group.LOCKNUT_THREAD_MARGIN).
LOCKNUT_FACE_D = _group.LOCKNUT_FACE_D
THREAD_END_D = _pin.THREAD_END_Y
THREAD_PAST_LOCKNUT_LIMITS = (_pin.TIP_INCOMPLETE, _pin.THREAD_PAST_LOCKNUT_LIMIT)

# Chain stations d (from the bar front face) along the axle centreline: the
# bar's far face, the axle's plain end, the bar front face, the spacer's
# outer face, the shank step, the drum's outer face, the wheel's spigot face,
# the front washer, the second nut's outer face and the axle's thread end.
SPACER_FACE_D = _group.BACK_WASHER_D
STEP_D = SPACER_FACE_D + PRESS_GAUGE
if abs(STEP_D - _pin.STEP_Y) > 1e-5:
    raise AssertionError("the press gauge no longer lands the step on the pin's station")
HUB_FRONT_D = _group.HUB_FRONT_D
WASHER_D = _group.FRONT_WASHER_D
DRUM_FACE_D = HUB_FRONT_D - DRUM_RECESS
if abs((WASHER_D - HUB_FRONT_D) - ENDSHAKE) > 1e-9:
    raise AssertionError("the front washer no longer sits one endshake off the hub")
if not 0.0 < HUB_FRONT_D - STEP_D:
    raise AssertionError("the shank step must stand inside the wheel hub")
CHAIN_D = (
    BAR_FAR_D,
    BACK_END_D,
    0.0,
    SPACER_FACE_D,
    STEP_D,
    DRUM_FACE_D,
    HUB_FRONT_D,
    WASHER_D,
    LOCKNUT_FACE_D,
    THREAD_END_D,
)
if any(near >= far for near, far in zip(CHAIN_D, CHAIN_D[1:])):
    raise AssertionError(f"the axle stack stations are out of order: {CHAIN_D}")
# The chain's anchor station, the bar front face (d = 0).
CHAIN_ORIGIN_INDEX = CHAIN_D.index(0.0)

FEATURE = "AxleStackReference"
PRESS_GAUGE_DIMENSION = "PressGauge"
ENDSHAKE_DIMENSION = "Endshake"
BACK_END_SUNK_DIMENSION = "BackEndSunk"
DRUM_RECESS_DIMENSION = "DrumRecess"
THREAD_PAST_LOCKNUT_DIMENSION = "ThreadPastLocknut"
# Each leg's dimension name, in chain order; the printed ones are named above.
CHAIN_LEG_DIMENSIONS = (
    BACK_END_SUNK_DIMENSION,
    "PlainEndToFrontFace",
    "FrontFaceToSpacerFace",
    PRESS_GAUGE_DIMENSION,
    "StepToDrumFace",
    DRUM_RECESS_DIMENSION,
    ENDSHAKE_DIMENSION,
    "WasherToLocknutFace",
    THREAD_PAST_LOCKNUT_DIMENSION,
)
if len(CHAIN_LEG_DIMENSIONS) != len(CHAIN_D) - 1:
    raise AssertionError("every axle stack leg needs one dimension name")
LIMIT_DIMENSIONS = {
    BACK_END_SUNK_DIMENSION: BACK_END_SUNK_LIMITS,
    DRUM_RECESS_DIMENSION: DRUM_RECESS_LIMITS,
    THREAD_PAST_LOCKNUT_DIMENSION: THREAD_PAST_LOCKNUT_LIMITS,
}
_legs = dict(zip(CHAIN_LEG_DIMENSIONS, zip(CHAIN_D, CHAIN_D[1:])))
for _name, (_low, _high) in LIMIT_DIMENSIONS.items():
    _length = _legs[_name][1] - _legs[_name][0]
    if not _low < _length < _high:
        raise AssertionError(f"{_name}: the model's {_length:.4f} mm is outside {_low}-{_high}")
LIMIT_PRECISION = 3
DRAWING_PRECISION = {
    FEATURE: {
        PRESS_GAUGE_DIMENSION: _pin.PRESS_GAUGE_PLACES,
        ENDSHAKE_DIMENSION: 3,
        **{name: LIMIT_PRECISION for name in LIMIT_DIMENSIONS},
    }
}
TOLERANCE_PRECISION = 3
DIMENSION_TOLERANCES = {
    PRESS_GAUGE_DIMENSION: PRESS_GAUGE_TOL,
    ENDSHAKE_DIMENSION: ENDSHAKE_TOL,
}
if set(DIMENSION_TOLERANCES) & set(LIMIT_DIMENSIONS) or (
    set(DIMENSION_TOLERANCES) | set(LIMIT_DIMENSIONS)
) != set(DRAWING_PRECISION[FEATURE]):
    raise AssertionError("each stack setting is exactly one of banded or limits")

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
# .XX, not .X: both set the output (magnification, trace height).
LEVER_DRAWING_PRECISION = {
    LEVER_FEATURE: {CLAMP_STATION_DIMENSION: 2, FIXTURE_DROP_DIMENSION: 2}
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
assert _lever.LEVER_UNIT == UNIT, "the lever charges this sheet's projection band in its unit"
INSTALLED_FULL_ENGAGEMENT_MIN = _lever.INSTALLED_FULL_ENGAGEMENT_MIN

# Native IDisplayDimension.SetText compartments (swDimensionTextParts_e):
# 3 = swDimensionTextCalloutAbove, 4 = swDimensionTextCalloutBelow. These are
# model annotations, not sheet prose: imported SetText writes through to the
# source. Keep their text and native compartments under one model authority.
# Above-callouts must stay on one line: SOLIDWORKS stores a line break there
# but prints none of the callout (run 20261012T185729782Z). Below ones can wrap.
SETTING_CALLOUTS = {
    FEATURE: {
        # The press gauge is the press's setting, from the spacer's outer
        # face (owner ruling 2026-11-21). Its acceptance, the number pair a
        # depth rod reads at the second nut (owner ruling 2026-11-06, Q1), is
        # ThreadPastLocknut on DETAIL B, the view that draws the nuts. Farm
        # rounds 1-3 of #2286 gated the pair as a callout on DETAIL A, which
        # draws no nut; Main chose option A on 2026-11-08.
        PRESS_GAUGE_DIMENSION: (4, "PRESS SETTING:\nSHOULDER PAST\nSPACER FACE"),
        # One reason line; the steps carry how the nuts set and lock it
        # (owner ruling 2026-11-06, Q2).
        ENDSHAKE_DIMENSION: (4, "WHEEL FREE, NO RATTLE"),
        # Each limit pair names the two faces it reads between; the press's
        # setting and its one acceptance say which they are (r3 of #2286
        # read two acceptances). The plain end's window is where a press to
        # the gauge leaves it, read to record a re-press. The steps name the
        # caliper depth rod.
        BACK_END_SUNK_DIMENSION: (4, "PLAIN END BELOW\nFAR FACE"),
        DRUM_RECESS_DIMENSION: (4, "DRUM FACE BELOW\nSPIGOT END"),
        THREAD_PAST_LOCKNUT_DIMENSION: (4, "ACCEPTANCE:\nTHREAD END PAST\nSECOND NUT"),
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

