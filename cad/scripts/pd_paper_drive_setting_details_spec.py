"""MHA-PD-00's geometric assembly settings as model dimensions (DETAILS F-L).

Rule 22 (R5 machinist review of MHA-PD-00): every measurable setting prints
on a view, setting diagram or setting table.  Owner policy (via MainBuild,
2026-11-17): a setting a model dimension can carry is an associative native
dimension, never a table cell.  The four groups here are those: the collar's
drive dowels proud of its front face (F), the plate-locating dowels proud of
the arm's rear face (H), the feed rack's crest drop below the platen and its
front face behind the bottom guide's (J), and the latch dowel proud of the
arm's tip (L).

``build_pd_paper_drive_assembly`` authors each group as one hidden
construction sketch, every line anchored on the model face it measures from
and its length driven from a global, toleranced to the band its step prints;
the builder proves each line's end points are its own placed faces.  The
setting details on MHA-PD-00's SETTING DETAILS sheet import the dimensions;
the steps keep their values and cite the detail.  No solid or pose changes.

Sketch planes: ``Right`` (sketch u, v = machine -Z, Y; the side views) and
``Front`` (sketch u, v = machine X, Y).
"""

from __future__ import annotations

from dataclasses import dataclass

from pd_rack_pinion_spec import MM_PER_IN, inch_text

from _cone_axis_constants import FRAME_FRONT_COLUMN_Z
from _column_clamp_interface import ARC_DEPTH, BAR_DEPTH
import _paper_drive_placement as placement
import _transgear_arm_plate_locating_interface as locating
import pd_feed_rack_spec as feed_rack
import pd_platen_bottom_guide_spec as bottom_guide
import pd_transgear_arm_geometry as arm
import pd_transgear_drive_collar_spec as collar
import pd_vn_transgear_knob_drive_pin_spec as drive_pin
import pd_vn_transgear_latch_pin_spec as latch_pin
import transgear_cluster_fit as cluster
import transgear_hanger_joints as joints

PLACES = 3
_GRID_MM = MM_PER_IN / 10**PLACES


def _on_grid(value_mm: float) -> bool:
    steps = value_mm / _GRID_MM
    return abs(steps - round(steps)) < 1e-6


def _grid_in(value_mm: float) -> float:
    """``value_mm`` rounded to the nearest .001 inch, in mm."""
    return round(value_mm / _GRID_MM) * _GRID_MM


@dataclass(frozen=True)
class SettingLine:
    """One setting: a construction line from ``start`` (on the face it is
    measured from) to ``end``, machine mm.  ``length_mm`` drives it from
    ``global_name``; ``band_mm`` is the (low, high) window its step prints,
    or None where the title block's .XXX row governs.  ``via`` is a point
    on the line's axis behind ``start`` for an inclined line (its helper leg
    fixes the direction); ``text`` is where the dimension's text stands."""

    dimension: str
    global_name: str
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    length_mm: float
    band_mm: tuple[float, float] | None
    text: tuple[float, float, float]
    via: tuple[float, float, float] | None = None

    @property
    def deviations_mm(self) -> tuple[float, float] | None:
        """The band as (lower, upper) deviations about ``length_mm``."""
        if self.band_mm is None:
            return None
        return (self.band_mm[0] - self.length_mm, self.band_mm[1] - self.length_mm)

    @property
    def symmetric(self) -> bool:
        low, high = self.deviations_mm or (0.0, 0.0)
        return abs(low + high) < 1e-9

    @property
    def printed(self) -> str:
        """The dimension as the sheet prints it, in inches."""
        nominal = inch_text(self.length_mm, PLACES)
        if self.band_mm is None:
            return nominal
        low, high = self.deviations_mm
        if self.symmetric:
            return f"{nominal} \u00b1{inch_text(high, PLACES)}"
        return f"{nominal} +{inch_text(high, PLACES)}/-{inch_text(-low, PLACES)}"


@dataclass(frozen=True)
class SettingDetail:
    """One lettered setting detail: its hidden sketch ``feature`` on
    ``plane``, the instances its view shows, its view and crop."""

    letter: str
    feature: str
    plane: str
    orientation: str
    scale: tuple[float, float]
    centre: tuple[float, float, float]
    radius: float
    instances: frozenset[str]
    lines: tuple[SettingLine, ...]
    step_keys: tuple[str, ...]
    title: str

    @property
    def view_name(self) -> str:
        return f"DETAIL {self.letter}"


def sketch_uv(plane: str, point: tuple[float, float, float]) -> tuple[float, float]:
    """A machine point's sketch coordinates on ``plane``."""
    x, y, z = point
    if plane == "Right":
        return (-z, y)
    if plane == "Front":
        return (x, y)
    raise ValueError(f"no sketch frame for plane {plane!r}")


# --- the model faces (machine mm), from the builder's own sources -----------
# The bar's front face carries the platen's back face, which carries the
# bottom guide's front face (build_pd_paper_drive_assembly's depth chain).
BAR_FRONT_Z = FRAME_FRONT_COLUMN_Z - ARC_DEPTH - BAR_DEPTH
RACK_FRONT_Z = BAR_FRONT_Z + feed_rack.FRONT_BEHIND_PLATEN
RACK_TOP_Y = placement.RACK_TIP_Y + feed_rack.RACK_HEIGHT
# The collar's drive dowels: the collar on F, the upper dowel (+Y) of the pair.
COLLAR_FRONT_Z = cluster.F_Z - collar.LENGTH
KNOB_AXIS_XY = placement.KNOB_SHAFT_XY
DRIVE_PIN_Y = KNOB_AXIS_XY[1] + collar.PIN_CIRCLE_RADIUS
# The plate-locating dowels stand proud of the arm's rear face into the plate.
ARM_REAR_Z = arm.FRONT_FACE_MACHINE_Z + arm.THICKNESS


def on_arm(station: float, offset: float = 0.0) -> tuple[float, float]:
    """Machine xy of the hanger-frame point ``P + station*U + offset*N``."""
    return (
        placement.PIVOT_XY[0] + station * arm.ARM_U[0] + offset * arm.ARM_N[0],
        placement.PIVOT_XY[1] + station * arm.ARM_U[1] + offset * arm.ARM_N[1],
    )


LOCATOR_XY = on_arm(*arm.LOCATOR_SITES_MM[0])
# The latch dowel: pressed along U to the floor of the arm tip's hole, its
# proud end past the square tip face at TIP_STATION.
LATCH_FLOOR_XY = on_arm(arm.TIP_STATION - arm.PIN_HOLE_DEPTH)
LATCH_MOUTH_XY = on_arm(arm.TIP_STATION)
LATCH_PROUD_MODEL = latch_pin.PROUD


# --- the bands the details and steps print ----------------------------------
# Rule 4 (review of run 20261117T144118108Z-771678f99db440ccbcec03874c9b1aca):
# an explicit band is a plain inch step, and converted limits such as
# .094 +.004/-.003 read as nobody's choice. A press window prints the widest
# plain symmetric band about its grid nominal that lies inside the part
# specs' window, and the step prints that band's limits.
PLAIN_STEPS_IN = (0.030, 0.025, 0.020, 0.015, 0.010, 0.005, 0.003, 0.002, 0.001)


def plain_band(
    nominal_mm: float, window_mm: tuple[float, float]
) -> tuple[float, float]:
    """``nominal_mm`` +/- the widest plain inch step inside ``window_mm``."""
    for step_in in PLAIN_STEPS_IN:
        half = step_in * 25.4
        if (
            window_mm[0] - 1e-9 <= nominal_mm - half
            and nominal_mm + half <= window_mm[1] + 1e-9
        ):
            return (nominal_mm - half, nominal_mm + half)
    raise AssertionError(f"no plain band about {nominal_mm} fits {window_mm}")


DRIVE_PIN_PROUD_NOMINAL = _grid_in(collar.DRIVE_PIN_PROUD)
DRIVE_PIN_PROUD_BAND = plain_band(DRIVE_PIN_PROUD_NOMINAL, drive_pin.PROUD_RANGE)
LATCH_PROUD_NOMINAL = _grid_in(latch_pin.PROUD)
LATCH_PROUD_BAND = plain_band(LATCH_PROUD_NOMINAL, joints.LATCH_PIN_PROUD_RANGE)
RACK_FRONT_BAND = (
    feed_rack.FRONT_BEHIND_PLATEN - feed_rack.FRONT_SET_BAND,
    feed_rack.FRONT_BEHIND_PLATEN + feed_rack.FRONT_SET_BAND,
)
# The crest drop prints as the step's .100 +/-.002: its nominal on the grid,
# 0.006 mm off the model's datum-derived drop, which no sheet can show.
RACK_CREST_NOMINAL = _grid_in(placement.RACK_CREST_DROP)
RACK_CREST_BAND = (
    RACK_CREST_NOMINAL - bottom_guide.CREST_SET_BAND,
    RACK_CREST_NOMINAL + bottom_guide.CREST_SET_BAND,
)

COLLAR_DOWELS = SettingDetail(
    letter="F",
    feature="CollarDowelSetting",
    plane="Right",
    orientation="*Right",
    scale=(5.0, 1.0),
    centre=(KNOB_AXIS_XY[0], DRIVE_PIN_Y + 1.0, COLLAR_FRONT_Z - 1.2),
    radius=0.024,
    instances=frozenset(
        {
            "pd-transgear-drive-collar-1",
            "pd-vn-transgear-knob-drive-pin-1",
            "pd-vn-transgear-knob-drive-pin-2",
        }
    ),
    lines=(
        SettingLine(
            dimension="CollarDowelProud",
            global_name="CollarDowelProud",
            start=(KNOB_AXIS_XY[0], DRIVE_PIN_Y, COLLAR_FRONT_Z),
            end=(
                KNOB_AXIS_XY[0],
                DRIVE_PIN_Y,
                COLLAR_FRONT_Z - _grid_in(collar.DRIVE_PIN_PROUD),
            ),
            length_mm=_grid_in(collar.DRIVE_PIN_PROUD),
            band_mm=DRIVE_PIN_PROUD_BAND,
            # Above the dowel, in front of the collar's face.
            text=(KNOB_AXIS_XY[0], DRIVE_PIN_Y + 3.2, COLLAR_FRONT_Z - 1.2),
        ),
    ),
    step_keys=("collar-pins-pressed",),
    title="DOWELS PROUD OF THE COLLAR FRONT FACE",
)

LOCATING_DOWELS = SettingDetail(
    letter="H",
    feature="LocatingDowelSetting",
    plane="Right",
    orientation="*Right",
    scale=(5.0, 1.0),
    centre=(LOCATOR_XY[0], LOCATOR_XY[1] + 1.0, ARM_REAR_Z + locating.PROUD_MM / 2.0),
    radius=0.024,
    instances=frozenset(
        {
            "pd-transgear-arm-1",
            "pd-vn-transgear-arm-plate-locating-pin-1",
            "pd-vn-transgear-arm-plate-locating-pin-2",
        }
    ),
    lines=(
        SettingLine(
            dimension="LocatingDowelProud",
            global_name="LocatingDowelProud",
            start=(*LOCATOR_XY, ARM_REAR_Z),
            end=(*LOCATOR_XY, ARM_REAR_Z + locating.PROUD_MM),
            length_mm=locating.PROUD_MM,
            # The title block's .XXX +/-.005 is the proud's band (#2630).
            band_mm=None,
            text=(
                LOCATOR_XY[0],
                LOCATOR_XY[1] + 3.2,
                ARM_REAR_Z + locating.PROUD_MM / 2.0,
            ),
        ),
    ),
    step_keys=("arm-plate-fitted",),
    title="DOWELS PROUD OF THE ARM REAR FACE",
)

# J: both lines start on the rack's front face.  The crest drop runs up it
# from the crest's front corner to the platen's bottom edge level (its upper
# extension line runs along that edge); the front set runs across the rack's
# flat top from the guide's front face to the rack's.
_RACK_SIDE_X = 0.0
RACK_SETTINGS = SettingDetail(
    letter="J",
    feature="RackSetting",
    plane="Right",
    orientation="*Right",
    scale=(5.0, 1.0),
    centre=(_RACK_SIDE_X, placement.RACK_TIP_Y + 1.6, RACK_FRONT_Z - 1.3),
    radius=0.030,
    instances=frozenset({"pd-platen-1", "pd-platen-bottom-guide-1", "pd-feed-rack-1"}),
    lines=(
        SettingLine(
            dimension="RackCrestDrop",
            global_name="RackCrestDrop",
            start=(_RACK_SIDE_X, placement.RACK_TIP_Y, RACK_FRONT_Z),
            end=(_RACK_SIDE_X, placement.RACK_TIP_Y + RACK_CREST_NOMINAL, RACK_FRONT_Z),
            length_mm=RACK_CREST_NOMINAL,
            band_mm=RACK_CREST_BAND,
            # In front of the rack, under the platen.
            text=(_RACK_SIDE_X, placement.RACK_TIP_Y + 1.3, RACK_FRONT_Z - 5.2),
        ),
        SettingLine(
            dimension="RackFrontSet",
            global_name="RackFrontSet",
            start=(_RACK_SIDE_X, RACK_TOP_Y, BAR_FRONT_Z),
            end=(_RACK_SIDE_X, RACK_TOP_Y, RACK_FRONT_Z),
            length_mm=feed_rack.FRONT_BEHIND_PLATEN,
            band_mm=RACK_FRONT_BAND,
            # Under the rack's crests, in front of both extension lines: the
            # value is wider than the 1 mm leg (centred on it, the guide's
            # extension line ran through it; run
            # 20261117T144118108Z-771678f99db440ccbcec03874c9b1aca).
            text=(_RACK_SIDE_X, placement.RACK_TIP_Y - 1.6, BAR_FRONT_Z - 3.0),
        ),
    ),
    step_keys=("rack-screwed", "guides-screwed"),
    title="RACK CRESTS BELOW THE PLATEN, RACK BEHIND THE GUIDE",
)

_LATCH_LENGTH = _grid_in(LATCH_PROUD_MODEL)
_LATCH_END_XY = on_arm(arm.TIP_STATION + _LATCH_LENGTH)
_LATCH_MID_XY = on_arm(arm.TIP_STATION + _LATCH_LENGTH / 2.0, 3.0)
LATCH_DOWEL = SettingDetail(
    letter="L",
    feature="LatchDowelSetting",
    plane="Front",
    orientation="*Front",
    scale=(2.0, 1.0),
    centre=(*_LATCH_MID_XY, arm.PIN_MACHINE_Z),
    radius=0.024,
    instances=frozenset({"pd-transgear-arm-1", "pd-vn-transgear-latch-pin-1"}),
    lines=(
        SettingLine(
            dimension="LatchDowelProud",
            global_name="LatchDowelProud",
            start=(*LATCH_MOUTH_XY, arm.PIN_MACHINE_Z),
            end=(*_LATCH_END_XY, arm.PIN_MACHINE_Z),
            length_mm=_LATCH_LENGTH,
            band_mm=LATCH_PROUD_BAND,
            # Far enough off the dowel that the stacked limits clear its edge
            # (at 5.0 the dowel's edge crossed '+.025'; run
            # 20261117T144118108Z-771678f99db440ccbcec03874c9b1aca).
            text=(
                *on_arm(arm.TIP_STATION + _LATCH_LENGTH / 2.0, 9.0),
                arm.PIN_MACHINE_Z,
            ),
            via=(*LATCH_FLOOR_XY, arm.PIN_MACHINE_Z),
        ),
    ),
    step_keys=("latch-pin-pressed",),
    title="DOWEL PROUD OF THE ARM TIP",
)

DETAILS: tuple[SettingDetail, ...] = (
    COLLAR_DOWELS,
    LOCATING_DOWELS,
    RACK_SETTINGS,
    LATCH_DOWEL,
)
DETAILS_BY_STEP = {key: detail for detail in DETAILS for key in detail.step_keys}
DRAWING_DIMENSIONS = {
    detail.feature: {line.dimension for line in detail.lines} for detail in DETAILS
}
DRAWING_PRECISION = {
    detail.feature: {line.dimension: PLACES for line in detail.lines}
    for detail in DETAILS
}

if len({detail.letter for detail in DETAILS}) != len(DETAILS):
    raise AssertionError("each setting detail takes its own letter")
if len({line.dimension for detail in DETAILS for line in detail.lines}) != sum(
    len(detail.lines) for detail in DETAILS
):
    raise AssertionError("each setting dimension takes its own name")
for _detail in DETAILS:
    for _line in _detail.lines:
        if _line.band_mm is not None:
            if not all(_on_grid(limit) for limit in (*_line.band_mm, _line.length_mm)):
                raise AssertionError(
                    f"{_line.dimension}: its band is off the .001 grid"
                )
            if not _line.band_mm[0] < _line.length_mm < _line.band_mm[1]:
                raise AssertionError(f"{_line.dimension}: nominal outside its band")
        elif not _on_grid(_line.length_mm):
            raise AssertionError(
                f"{_line.dimension}: an untoleranced setting off the grid"
            )
        _start = sketch_uv(_detail.plane, _line.start)
        _end = sketch_uv(_detail.plane, _line.end)
        _length = ((_end[0] - _start[0]) ** 2 + (_end[1] - _start[1]) ** 2) ** 0.5
        if abs(_length - _line.length_mm) > 1e-6:
            raise AssertionError(f"{_line.dimension}: line is not its driven length")
        if (
            _line.via is None
            and min(abs(_end[0] - _start[0]), abs(_end[1] - _start[1])) > 1e-9
        ):
            raise AssertionError(
                f"{_line.dimension}: a single line runs along a sketch axis"
            )
