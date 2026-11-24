"""The MHA-MG-00 magnifier assembly settings: the builder's and the sheet's.

Four settings belong to no single part: the press gauge the wheel axle is
pressed to in the bar, from the spacer's outer face (the press's setting),
the drum's outer face below the wheel's spigot end, the endshake the first
nut sets, and the axle's thread end past the second nut (the press's
acceptance). A fifth length, the axle's plain end below the bar's far face
(where the press leaves it), prints as a reference no step reads. Each one
is printed as a native model dimension
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

# The shoulder past the spacer's OUTER face, the spacer on the shank against
# the bar's front face: the model's step station (.768). Owner ruling
# 2026-11-24, fit audit part 2, C11 ("Yes, set to the trial stack"): no step
# sets or reads it any more (the dry trial sets the axle, accepted at the
# thread end past the second nut, the first nut on thread and the plain end
# not proud: mg_wheel_group.TRIAL_*), so it prints as a reference.
PRESS_GAUGE = _pin.PRESS_GAUGE
# The modelled endshake sits mid-band, so its band prints symmetric.
ENDSHAKE = _group.ENDSHAKE
ENDSHAKE_TOL = _group.ENDSHAKE_MAX - _group.ENDSHAKE
if abs((_group.ENDSHAKE - _group.ENDSHAKE_MIN) - ENDSHAKE_TOL) > 1e-9:
    raise AssertionError("the endshake band is not symmetric about its model value")

# The stack lengths the MHA-MG-00 sheet prints, each a model length on the
# same chain (rule 22: a measurable setting prints on a view even though the
# steps print in ASSEMBLY.md). The endshake prints banded
# (DIMENSION_TOLERANCES), the drum recess and the thread end as their two
# limits (LIMIT_DIMENSIONS); the model's own pose sits inside them.
# The axle's plain end below the bar's far face: where the nominal setting
# leaves it, a window the axle spec proves from the printed shank, spacer,
# step station and bar depth (its low limit keeps the end inside the bore).
# The steps read it only against the trial's own reading, so it prints as
# a reference (REFERENCE_DIMENSIONS), as the step station does.
BAR_FAR_D = -_pin.BAR_DEPTH
BACK_END_D = _pin.BACK_Y
BACK_END_SUNK_LIMITS = (_pin.BACK_END_SUNK_MIN, _pin.BACK_END_SUNK_MAX)
if not BACK_END_SUNK_LIMITS[0] < BACK_END_D - BAR_FAR_D < BACK_END_SUNK_LIMITS[1]:
    raise AssertionError("the model's plain end is outside its proven window")
# The bonded drum's outer face below the spigot end (the wheel hub's front
# face): the window the printed spigot and drum lengths prove. Owner ruling
# 2026-11-24, fit audit part 2, S4: the drum step accepts it by sight (hard
# against the boss, not proud by straightedge), so it prints as a reference.
# The geom asserts the near limit >= -1e-9 mm; rounding (and + 0.0, for
# -0.0) drops the float residue.
DRUM_RECESS = _wheel.SPIGOT_LEN - _wheel.DRUM_LEN
DRUM_RECESS_LIMITS = tuple(round(limit, 6) + 0.0 for limit in _wheel.DRUM_RECESS)
if not DRUM_RECESS_LIMITS[0] <= DRUM_RECESS < DRUM_RECESS_LIMITS[1]:
    raise AssertionError("the model's drum recess is outside its proven window")
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
    THREAD_PAST_LOCKNUT_DIMENSION: THREAD_PAST_LOCKNUT_LIMITS,
}
_legs = dict(zip(CHAIN_LEG_DIMENSIONS, zip(CHAIN_D, CHAIN_D[1:])))
for _name, (_low, _high) in LIMIT_DIMENSIONS.items():
    _length = _legs[_name][1] - _legs[_name][0]
    if not _low < _length < _high:
        raise AssertionError(f"{_name}: the model's {_length:.4f} mm is outside {_low}-{_high}")
LIMIT_PRECISION = 3
# Printed as (value) through the native prefix/suffix channel, no band.
REFERENCE_DIMENSIONS = frozenset(
    {BACK_END_SUNK_DIMENSION, PRESS_GAUGE_DIMENSION, DRUM_RECESS_DIMENSION}
)
DRAWING_PRECISION = {
    FEATURE: {
        ENDSHAKE_DIMENSION: 3,
        **{
            name: LIMIT_PRECISION
            for name in (*LIMIT_DIMENSIONS, BACK_END_SUNK_DIMENSION, DRUM_RECESS_DIMENSION)
        },
        PRESS_GAUGE_DIMENSION: _pin.PRESS_GAUGE_PLACES,
    }
}
TOLERANCE_PRECISION = 3
DIMENSION_TOLERANCES = {
    ENDSHAKE_DIMENSION: ENDSHAKE_TOL,
}
_forms = (REFERENCE_DIMENSIONS, set(DIMENSION_TOLERANCES), set(LIMIT_DIMENSIONS))
if set().union(*_forms) != set(DRAWING_PRECISION[FEATURE]) or sum(map(len, _forms)) != len(
    DRAWING_PRECISION[FEATURE]
):
    raise AssertionError("each stack setting is exactly one of banded, limits or a reference")

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
        # The step station past the spacer's outer face is the model's
        # nominal, printed REF (owner ruling 2026-11-24, fit audit part 2,
        # C11: the axle is set to the trial stack). The acceptance, the
        # number pair a depth rod reads at the second nut (owner ruling
        # 2026-11-06, Q1), is ThreadPastLocknut on DETAIL B, the view that
        # draws the nuts (#2286 option A).
        PRESS_GAUGE_DIMENSION: (4, "SHOULDER PAST\nSPACER FACE"),
        # One reason line; the steps carry how the nuts set and lock it
        # (owner ruling 2026-11-06, Q2).
        ENDSHAKE_DIMENSION: (4, "WHEEL FREE, NO RATTLE"),
        # Each limit pair names the two faces it reads between (r3 of #2286
        # read two acceptances). The plain end below the far face prints as
        # a reference, where the nominal setting leaves it; the steps name
        # the caliper depth rod.
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

