"""Offline contracts for the rocker arm outline template (MHA-CH-006-TL-13)."""

from __future__ import annotations

import inspect
import math
import re
import tomllib
from types import SimpleNamespace

import pytest

import _config
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_outline_template_spec as spec
import draw_ch_rocker_arm_tl_outline_template as drawing
import export_features
from _paths import CAD_ROOT
from _printed_tolerance import printed_deviations

STEM = "ch_rocker_arm_tl_outline_template"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    keeps = (drawing.FRONT_KEEP, drawing.RIGHT_KEEP, drawing.DETAIL_KEEP)
    assert set().union(*keeps) == marked
    assert sum(len(keep) for keep in keeps) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {name for _feature, name in spec.DRAWING_BANDS} <= marked
    assert set(drawing.CALLOUTS_BELOW) <= marked
    banded = {name for _feature, name in spec.DRAWING_BANDS}
    basic = {name for _feature, name in spec.BASIC_DIMENSIONS}
    assert basic <= set(drawing.FRONT_KEEP) and not basic & banded
    assert spec.REFERENCE_DIMENSIONS <= set(drawing.DETAIL_KEEP)
    assert not spec.REFERENCE_DIMENSIONS & banded


def test_number_is_the_parent_number_plus_tool_suffix_thirteen() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    assert (
        _config.parts("ch-rocker-arm-tl-outline-template")["number"]
        == f"{parent}-TL-13"
    )
    assert spec.ROCKER_NUMBER == parent


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert not re.search(r"SCRIBE THE|FILE TO|SAW|TRAMMEL", spec.DRAWING_NOTES.upper())


def test_apex_bands_sit_mid_zone_inside_the_rocker_arc_zone() -> None:
    """Both arcs of the rocker may come out 0..+0.5 high; the template's
    printed apex limits sit in the middle quarter of that zone."""
    features = _features()
    top = features["top_edge"]["height_above_pivot"]
    bottom = features["bottom_edge"]["depth"]
    assert top == [8.23, 8.27]
    assert bottom == [7.73, 7.77]
    zone_top = (
        rocker.TOP_EDGE_ABOVE_PIVOT,
        rocker.TOP_EDGE_ABOVE_PIVOT + rocker.TOP_EDGE_BAND[0],
    )
    zone_bottom = (rocker.ARM_DEPTH - zone_top[1], rocker.ARM_DEPTH - zone_top[0])
    for (low, high), (zone_low, zone_high) in ((top, zone_top), (bottom, zone_bottom)):
        assert zone_low < low < high < zone_high
        assert math.isclose(
            (low + high) / 2.0, (zone_low + zone_high) / 2.0, abs_tol=1e-9
        )
        assert high - low <= 0.25 * (zone_high - zone_low) + 1e-9


_ROCKER_BOT_END_Y = rocker.CENTER_Y - rocker.R_BOTTOM * math.cos(rocker._ALPHA_BOT)
_ROCKER_TIP_Y = rocker.TOP_END_Y - rocker.TIP_FACE * math.cos(rocker._ALPHA_TOP)
# The rocker's BASIC +X outline corners and arc centre, in the template frame.
_ROCKER_TOP_END = (rocker.TOP_END_X, rocker.TOP_END_Y - rocker.PIVOT_MID_Y)
_ROCKER_TIP = (rocker.ROD_TIP_X, _ROCKER_TIP_Y - rocker.PIVOT_MID_Y)
_ROCKER_BOT_END = (rocker.BOT_END_X, _ROCKER_BOT_END_Y - rocker.PIVOT_MID_Y)
_ROCKER_CENTRE_Y = rocker.CENTER_Y - rocker.PIVOT_MID_Y
_MID_ZONE = (rocker.TOP_EDGE_BAND[0] - rocker.TOP_EDGE_BAND[1]) / 2.0


def _into_material(point, start, end) -> float:
    """``point``'s offset from the rocker line start -> end, + into the arm."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    normal = (-dy / length, dx / length)
    middle = (0.0, _ROCKER_CENTRE_Y - (rocker.R_TOP + rocker.R_BOTTOM) / 2.0)
    if (middle[0] - start[0]) * normal[0] + (middle[1] - start[1]) * normal[1] < 0.0:
        normal = (-normal[0], -normal[1])
    return (point[0] - start[0]) * normal[0] + (point[1] - start[1]) * normal[1]


@pytest.mark.parametrize(
    ("template_line", "rocker_line"),
    [
        (
            ((spec.TOP_END_X, spec.TOP_END_Y), (spec.TIP_X, spec.TIP_Y)),
            (_ROCKER_TOP_END, _ROCKER_TIP),
        ),
        (
            ((spec.TIP_X, spec.TIP_Y), (spec.BOT_END_X, spec.BOT_END_Y)),
            (_ROCKER_TIP, _ROCKER_BOT_END),
        ),
    ],
    ids=["tip land", "tapered end"],
)
def test_straight_edges_sit_mid_zone_along_their_own_normals(
    template_line, rocker_line
) -> None:
    """The lower outline's 0.5 Ⓤ0 zone lies wholly inside the material, so
    each land and taper aims half the zone in along its own normal. The old
    rigid +Y shift left the near-vertical land 0.045 OUTSIDE the zone."""
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        point = tuple(
            a + fraction * (b - a) for a, b in zip(*template_line, strict=True)
        )
        # Three-place stations and the radial land: 2 microns at most.
        assert math.isclose(
            _into_material(point, *rocker_line), _MID_ZONE, abs_tol=0.002
        )


def test_arcs_keep_the_rocker_radii_and_their_mid_zone_residual_is_bounded() -> None:
    """Both arcs keep the rocker's R800/R816 about a centre raised by half the
    zone: mid-zone on the mirror line, short of it by half the zone times
    (1 - cos phi) off it, never past it."""
    assert (spec.R_TOP, spec.R_BOTTOM) == (rocker.R_TOP, rocker.R_BOTTOM)
    assert (spec.R_TOP, spec.R_BOTTOM) == (800.0, 816.0)
    assert math.isclose(spec.CENTER_Y - _ROCKER_CENTRE_Y, _MID_ZONE, abs_tol=1e-9)
    for name, radius, end_x in (
        ("top", spec.R_TOP, spec.TOP_END_X),
        ("bottom", spec.R_BOTTOM, spec.BOT_END_X),
    ):
        worst = 0.0
        for step in range(11):
            x = end_x * step / 10.0
            y = spec.CENTER_Y - math.sqrt(radius**2 - x**2)
            # + toward the arcs' centre: outside the top edge, inside the bottom.
            toward_centre = radius - math.hypot(x, y - _ROCKER_CENTRE_Y)
            residual = _MID_ZONE - toward_centre
            assert math.isclose(
                residual, spec.arc_mid_zone_residual(radius, x), abs_tol=1e-9
            )
            worst = max(worst, residual)
        phi = math.asin(end_x / radius)
        assert math.isclose(worst, _MID_ZONE * (1.0 - math.cos(phi)), abs_tol=1e-5)
        assert math.isclose(worst, spec.ARC_MID_ZONE_RESIDUAL[name], abs_tol=1e-12)
        assert 0.0 < worst


def test_outline_corners_lie_on_their_arcs() -> None:
    def radius(x: float, y: float) -> float:
        return math.hypot(x, y - spec.CENTER_Y)

    assert math.isclose(
        radius(spec.TOP_END_X, spec.TOP_END_Y), spec.R_TOP, abs_tol=1e-9
    )
    assert math.isclose(
        radius(spec.BOT_END_X, spec.BOT_END_Y), spec.R_BOTTOM, abs_tol=1e-9
    )
    # The tip land is radial, so its foot lies TIP_FACE beyond the top arc.
    assert math.isclose(
        radius(spec.TIP_X, spec.TIP_Y), spec.R_TOP + spec.TIP_FACE, abs_tol=1e-9
    )
    # The tapered end runs inward and down from the tip to the bottom arc's end.
    assert spec.BOT_END_X < spec.TIP_X and spec.BOT_END_Y < spec.TIP_Y


def test_locator_play_and_edge_band_fit_a_quarter_of_the_rocker_zone() -> None:
    """The pin's worst-case play in BOTH bores (template and rocker, each at
    its largest, the pin at its smallest) moves the template off the arm's
    pivot; with the outline profile's half-zone about the template's own hole
    and slot, and the arcs' mid-zone residual, it stays inside the quarter of
    the rocker's arc zone the gauge may spend, centred on the aim: half of
    that quarter either side."""
    hole = _features()["pivot_hole"]
    assert hole["dia"] == [6.5, 6.515]
    rocker_bore = (
        rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1],
        rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0],
    )
    assert spec.PIN_GAUGE_MAX < hole["dia"][0]
    assert spec.PIN_GAUGE_MAX < rocker_bore[0]
    registration = (hole["dia"][1] - spec.PIN_GAUGE_MIN) / 2.0 + (
        rocker_bore[1] - spec.PIN_GAUGE_MIN
    ) / 2.0
    zone = rocker.TOP_EDGE_BAND[0] - rocker.TOP_EDGE_BAND[1]
    residual = max(spec.ARC_MID_ZONE_RESIDUAL.values())
    assert (
        spec.OUTLINE_PROFILE_ZONE / 2.0 + residual + registration
        <= 0.25 * zone / 2.0 + 1e-9
    )
    assert spec.LOCATOR_REGISTRATION_MAX >= registration


def test_pivot_callout_names_the_bought_locating_pin() -> None:
    inches = f"{spec.PIN_GAUGE_IN:.4f}"
    assert spec.PIN_GAUGE_MAX == pytest.approx(float(inches) * 25.4)
    assert f"{inches} IN, CLASS X MINUS" in spec.PIVOT_CALLOUT
    assert "PIN GAUGE" in spec.PIVOT_CALLOUT
    inventory = tomllib.loads(
        (CAD_ROOT / "process" / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )
    pin = inventory["gauges"]["vermont-class-x-2558-minus"]
    assert pin["kind"] == "pin_gauge" and pin["make"] == "Vermont Gage"
    assert pin["dia_in"]["value"] == spec.PIN_GAUGE_IN
    assert "Class X minus" in pin["name"] + pin["note"]


def test_prechips_envelope_is_the_outline_extents_with_the_pin_voids() -> None:
    from prechips.model import FixtureSolid

    for solid in spec.PRECHIPS_SOLIDS:
        FixtureSolid.model_validate(solid)
    plate, hole, slot = spec.PRECHIPS_SOLIDS
    xs, ys = zip(*spec.outline_points(), strict=True)
    low = (min(xs), min(ys), 0.0)
    high = (max(xs), max(ys), spec.THICK)
    assert plate["shape"] == "box" and plate["supply"] == "made"
    for axis in range(3):
        assert math.isclose(plate["at_mm"][axis], low[axis], abs_tol=1e-3)
        assert math.isclose(
            plate["at_mm"][axis] + plate["size_mm"][axis], high[axis], abs_tol=1e-3
        )
    assert hole["void"] is True and hole["shape"] == "cylinder"
    assert hole["at_mm"] == [0.0, 0.0, 0.0] and hole["axis"] == [0.0, 0.0, 1.0]
    assert hole["dia_mm"] == spec.PIVOT_HOLE_DIA and hole["length_mm"] == spec.THICK
    assert slot["void"] is True and slot["shape"] == "cylinder"
    assert slot["at_mm"] == [spec.ROD_SLOT_X, spec.ROD_SLOT_Y, 0.0]
    assert slot["dia_mm"] == spec.ROD_SLOT_WIDTH and slot["length_mm"] == spec.THICK


def test_rod_slot_station_is_the_rockers_rod_pin_hole() -> None:
    """The slot sits at the rocker's rod-pin hole (its datum C) in this
    frame, to the printed three places, and runs radially from the pivot."""
    station = (rocker.ROD_HOLE_X, rocker.ROD_HOLE_Y - rocker.PIVOT_MID_Y)
    slot = _features()["rod_slot"]
    assert slot["at"][:2] == [spec.ROD_SLOT_X, spec.ROD_SLOT_Y]
    assert math.dist(slot["at"][:2], station) <= math.sqrt(2.0) * 0.0005
    # The outboard end's centre lies on the radial through the pivot.
    assert math.isclose(
        slot["end"][0] * spec.ROD_SLOT_Y - slot["end"][1] * spec.ROD_SLOT_X,
        0.0,
        abs_tol=1e-9,
    )
    assert math.dist(slot["end"][:2], slot["at"][:2]) == pytest.approx(
        spec.ROD_SLOT_FLAT / 2.0
    )
    assert slot["dimension_type"] == "basic"


def test_rod_slot_width_is_a_matched_fit_on_a_pin_the_shop_owns() -> None:
    inventory = tomllib.loads(
        (CAD_ROOT / "process" / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )
    pins = inventory["gauges"]["pin-gauges"]
    assert "class ZZ minus" in pins["note"]
    low, high = pins["range_mm"]
    assert low <= spec.ROD_PIN_MAX <= high
    step = pins["resolution_in"]["value"]
    assert math.isclose(
        spec.ROD_PIN_GAUGE_IN / step, round(spec.ROD_PIN_GAUGE_IN / step)
    )
    # The pin enters the rocker's #47 hole at its smallest; the next size up
    # in the set would not.
    assert spec.ROD_PIN_MAX < 1.994 < (spec.ROD_PIN_GAUGE_IN + step) * 25.4
    clearance = (
        spec.ROD_SLOT_WIDTH - spec.ROD_PIN_MAX,
        spec.ROD_SLOT_WIDTH_MAX - spec.ROD_PIN_MIN,
    )
    assert 0.0 < spec.ROD_SLOT_CLEARANCE[0] <= clearance[0]
    assert clearance[1] <= spec.ROD_SLOT_CLEARANCE[1]
    assert spec.ROD_SLOT_CLEARANCE == (0.001, 0.017)
    assert spec.ROD_SLOT_CALLOUT.splitlines() == [
        "0.001-0.017 DIAMETRAL",
        "CLEARANCE ON PIN GAUGE",
        "0.0780 IN (CLASS ZZ MINUS)",
    ]
    slot = _features()["rod_slot"]
    assert slot["note"] == " ".join(spec.ROD_SLOT_CALLOUT.splitlines())
    assert slot["width_nominal"] == spec.ROD_SLOT_WIDTH
    assert "RodSlotWidth" in spec.REFERENCE_DIMENSIONS
    assert drawing.CALLOUTS_BELOW["RodSlotWidth"] == spec.ROD_SLOT_CALLOUT


def test_rod_slot_run_takes_the_pin_wherever_the_rocker_puts_its_hole() -> None:
    run = _features()["rod_slot"]["length"]
    band = printed_deviations(spec.ROD_SLOT_FLAT, spec.ROD_SLOT_PLACES)
    assert run == pytest.approx(
        [spec.ROD_SLOT_FLAT + band[0], spec.ROD_SLOT_FLAT + band[1]]
    )
    reach = spec.ROD_HOLE_RADIAL + spec.ROD_HOLE_PLAY + band[1]
    assert run[0] / 2.0 >= reach
    assert spec.ROD_SLOT_WEB_MIN >= 1.5
    # The three-place run states its function and the hole it reaches.
    assert drawing.CALLOUTS_BELOW["RodSlotFlat"] == spec.ROD_SLOT_FLAT_CALLOUT
    assert spec.ROD_SLOT_FLAT_CALLOUT == "PIN REACH TO ROD-PIN\nHOLE, MHA-CH-006"
    # The station's flag says the slot is radial (its axis passes the pivot).
    assert drawing.CALLOUTS_BELOW["RodSlotX"] == "ROD SLOT, RADIAL TO PIVOT"
    assert spec.ROD_SLOT_AXIS == pytest.approx(
        (spec.ROD_SLOT_X / spec.ROD_SLOT_LEVER, spec.ROD_SLOT_Y / spec.ROD_SLOT_LEVER)
    )


# #1545 (approved 2026-10-15): of the rocker's 0.25 half-zone either side of
# the aim, filing to the scribed line keeps at least this much.
_FILING_RESIDUAL = 0.09


def test_rod_slot_clocking_keeps_every_outline_edge_inside_the_template_share() -> None:
    half_zone = (rocker.TOP_EDGE_BAND[0] - rocker.TOP_EDGE_BAND[1]) / 2.0
    assert half_zone - spec.END_STATION_SHARE >= _FILING_RESIDUAL - 1e-9
    worst = max(spec.outline_clocking_errors())
    assert worst == pytest.approx(spec.ROD_CLOCKING_WORST)
    assert worst <= spec.END_STATION_SHARE


def test_a_round_rod_hole_would_not_clock_the_template_closely_enough() -> None:
    """A round hole in place of the slot takes the rocker hole's radial
    position error across it too: the tail end then leaves the share."""
    round_hole = spec.ROD_HOLE_RADIAL + spec.ROD_HOLE_PLAY + spec.ROD_SLOT_PLAY
    assert max(spec.outline_clocking_errors(round_hole)) > spec.END_STATION_SHARE


def test_inventory_record_binds_this_part_without_hand_solids() -> None:
    inventory = tomllib.loads(
        (CAD_ROOT / "process" / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )
    records = [
        record
        for table in inventory.values()
        if isinstance(table, dict)
        for record in table.values()
        if isinstance(record, dict) and record.get("cad") == STEM
    ]
    assert len(records) == 1
    assert "solids" not in records[0]


def _inventory_note() -> str:
    inventory = tomllib.loads(
        (CAD_ROOT / "process" / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )
    return inventory["gauges"]["rocker-profile-gauge"]["note"]


def test_inventory_acceptance_is_the_drawings_one_profile_zone() -> None:
    """TOML cannot import the spec: the note's printed zone and its DTI
    half-zone must equal OUTLINE_PROFILE_ZONE, and the slot pin the spec's."""
    note = _inventory_note()
    printed = re.search(
        r"surface profile (\d+\.\d+) all around the outline to A\|C \(datum A the"
        r" pivot hole, C the rod slot\) about BASIC R800/R816",
        note,
    )
    assert printed, note
    assert float(printed.group(1)) == spec.OUTLINE_PROFILE_ZONE
    dti = re.search(
        r"DTI within \+/-(\d+\.\d+) of nominal about the pivot and rod slot"
        r" \(pins in both; the slot's pin is the (\d\.\d{4}) in from"
        r" gauges\.pin-gauges\) at (\d+) stations",
        note,
    )
    assert dti, note
    assert float(dti.group(1)) == spec.OUTLINE_PROFILE_ZONE / 2.0 == spec.DTI_ACCEPTANCE
    assert float(dti.group(2)) == spec.ROD_PIN_GAUGE_IN
    assert not re.search(r"(?i)light.gap|\bscrib|\bfil(e|ed|ing) to\b", note)


def test_outline_profile_is_one_frame_all_around_to_a_and_c() -> None:
    """One 0.06 surface profile all around the outline, to the pivot hole
    (A) then the rod slot (C), on BASIC R800/R816; every outline feature
    the rocker's inspection reads against the template carries it."""
    assert spec.OUTLINE_PROFILE_DATUMS == ("A", "C")
    assert drawing.OUTLINE_PROFILE_TEXT == f"{spec.OUTLINE_PROFILE_ZONE:.2f}"
    assert drawing.DETAIL_LETTER not in spec.OUTLINE_PROFILE_DATUMS
    features = _features()
    for name in ("top_edge", "bottom_edge", "rod_tip_land", "tail_tip_land"):
        fields = features[name]
        assert "surface_profile" in fields["requirements"], name
        assert fields["surface_profile"] == spec.OUTLINE_PROFILE_ZONE
        assert fields["surface_profile_datums"] == list(spec.OUTLINE_PROFILE_DATUMS)
        assert set(fields["surface_profile_governs"]) <= set(fields["requirements"])
    assert features["pivot_hole"]["datum"] == spec.PIVOT_DATUM
    assert features["rod_slot"]["datum"] == spec.ROD_SLOT_DATUM
    source = inspect.getsource(drawing._add_outline_profile)
    assert "all_around=True" in source
    assert 'characteristic="profile_surface"' in source
    assert "datums=OUTLINE_PROFILE_DATUMS" in source
    assert "tolerance=OUTLINE_PROFILE_TEXT" in source
    build = inspect.getsource(drawing.build)
    assert "_add_datums(adapter, front)" in build
    assert "_add_outline_profile(adapter, front)" in build


def test_both_radii_are_basic_under_the_profile() -> None:
    basic = set(spec.BASIC_DIMENSIONS)
    assert {
        ("OutlineProfile", "TopRadius"),
        ("OutlineProfile", "BottomRadius"),
    } <= basic
    features = _features()
    for name, radius in (("top_edge", spec.R_TOP), ("bottom_edge", spec.R_BOTTOM)):
        assert features[name]["dimension_type"] == "basic"
        assert features[name]["radius"] == radius == features[name]["radius_nominal"]
    assert features["top_edge"]["surface_profile_governs"] == {"radius": "decreases"}
    assert features["bottom_edge"]["surface_profile_governs"] == {"radius": "increases"}


def test_the_profile_zone_has_one_literal() -> None:
    """0.06 is written once, in the spec; the drawing and the rocker's
    profile check derive it (the inventory note is pinned above)."""
    scripts = CAD_ROOT / "scripts"
    spec_source = (scripts / "ch_rocker_arm_tl_outline_template_spec.py").read_text(
        encoding="utf-8"
    )
    assert len(re.findall(r"(?<![\d.])0\.06(?!\d)", spec_source)) == 1
    assert "OUTLINE_PROFILE_ZONE = 0.06" in spec_source
    for stem in (
        "draw_ch_rocker_arm_tl_outline_template",
        "ch_rocker_arm_profile_check",
    ):
        source = (scripts / f"{stem}.py").read_text(encoding="utf-8")
        assert not re.search(r"(?<![\d.])0\.0[36](?!\d)", source), stem


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (
                    name,
                    requirement,
                    band,
                    places,
                )
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement, nominal, band)
                assert abs(nominal - round(nominal, places)) < 1e-9, (
                    name,
                    requirement,
                    nominal,
                )
            checked += 1
    assert checked


class _SlotView:
    """A recording IView double for detail A's place-move-crop."""

    def __init__(
        self, *, crop_status: int = 1, crops: bool = True, moves: bool = True
    ) -> None:
        self.ScaleRatio = tuple(float(value) for value in drawing.DETAIL_SCALE)
        self.Position = (0.300, 0.100)
        self.crop_status = crop_status
        self.crops = crops
        self.moves = moves
        self.cropped = False
        self.calls: list[str] = []
        self.CropViewJaggedOutline = False
        self.CropViewNoOutline = False

    def SetViewPosition(self, target, _update) -> bool:  # noqa: N802
        self.calls.append("SetViewPosition")
        if self.moves:
            self.Position = tuple(float(value) for value in target)
        return True

    def GetOutline(self):  # noqa: N802
        if self.cropped:
            return (0.060, 0.025, 0.090, 0.055)
        return (-0.600, -0.050, 0.860, 0.100)

    def Crop2(self, jagged, no_outline, intensity) -> int:  # noqa: N802
        self.calls.append(f"Crop2({jagged}, {no_outline}, {intensity})")
        self.cropped = self.crops
        return self.crop_status

    def IsCropped(self) -> bool:  # noqa: N802
        return self.cropped

    def UpdateViewDisplayGeometry(self) -> None:  # noqa: N802
        self.calls.append("UpdateViewDisplayGeometry")


class _SlotModel:
    def ClearSelection2(self, _all) -> None:  # noqa: N802
        pass

    def EditRebuild3(self) -> None:  # noqa: N802
        pass


def _crop_slot(monkeypatch, view: _SlotView) -> list[tuple]:
    """Place, move and crop detail A on a *Front double at 5:1 whose model
    origin sits a fixed offset from the view's position."""
    log: list[tuple] = []
    offset = (-0.650, -0.030)
    ratio = drawing.DETAIL_RATIO

    def place(_adapter, _source, orientation, x, y, *, scale):
        log.append(("place", orientation, (x, y), scale))
        return view

    def model_point(_adapter, _view, point, *, label):
        return (
            view.Position[0] + offset[0] + ratio * point[0],
            view.Position[1] + offset[1] + ratio * point[1],
        )

    def circle(_adapter, _view, center, radius, *, label, add_to_db=False):
        log.append(("circle", center, radius, add_to_db))
        return object()

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "model_point_in_view", model_point)
    monkeypatch.setattr(drawing, "_sketch_circle", circle)
    monkeypatch.setattr(drawing, "_activate_view", lambda *_a, **_k: "Drawing View4")
    adapter = SimpleNamespace(currentModel=_SlotModel())
    assert drawing._placed_rod_slot_view(adapter) is view
    drawing._crop_rod_slot_view(adapter, view)
    return log


def test_rod_slot_detail_is_a_cropped_front_model_view(monkeypatch) -> None:
    # Farm leaf edd99d0f (5dea45dfb): the native detail imported RodSlotWidth
    # but not RodSlotFlat, so the detail is a model view cropped after import.
    view = _SlotView()
    log = _crop_slot(monkeypatch, view)
    assert log[0] == ("place", "*Front", drawing.DETAIL_CENTER, drawing.DETAIL_SCALE)
    kind, center, radius, add_to_db = log[1]
    assert kind == "circle" and not add_to_db
    assert center == pytest.approx(drawing.DETAIL_CENTER, abs=1e-12)
    assert radius == pytest.approx(drawing.DETAIL_CROP_RADIUS)
    assert view.calls[0] == "SetViewPosition"
    assert "Crop2(False, False, 1)" in view.calls
    source = (
        CAD_ROOT / "scripts" / "draw_ch_rocker_arm_tl_outline_template.py"
    ).read_text(encoding="utf-8")
    assert ".CreateDetailViewAt4(" not in source


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"crop_status": 0}, "not cropped"),
        ({"crops": False}, "not cropped"),
        ({"moves": False}, "rod slot centre sits at"),
    ],
)
def test_rod_slot_detail_fails_loud_when_the_seat_does_not_obey(
    monkeypatch, kwargs, message
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _crop_slot(monkeypatch, _SlotView(**kwargs))


@pytest.mark.parametrize("crop_drops", [(), ("RodSlotFlat",)])
def test_rod_slot_detail_is_dimensioned_before_it_is_cropped(
    monkeypatch, crop_drops
) -> None:
    calls: list[str] = []
    events: list[tuple[str, dict]] = []
    names: list[str] = []

    def curate(_adapter, _view, *, keep, view_label, dimensions_by_feature):
        calls.append("import")
        names[:] = sorted(keep)
        return ["curated"]

    def crop(_adapter, _view):
        calls.append("crop")
        names[:] = [name for name in names if name not in crop_drops]

    def read(_adapter, _view):
        calls.append("read")
        return sorted(names)

    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "_crop_rod_slot_view", crop)
    monkeypatch.setattr(drawing, "_view_dimension_names", read)
    monkeypatch.setattr(
        drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    if crop_drops:
        with pytest.raises(RuntimeError, match="lost \\['RodSlotFlat'\\]"):
            drawing._dimension_then_crop_rod_slot_view(object(), object())
    else:
        assert drawing._dimension_then_crop_rod_slot_view(object(), object()) == [
            "curated"
        ]
    assert calls == ["import", "read", "crop", "read"]
    assert events[0][0] == "rod_slot_detail.crop"
    assert events[0][1]["lost"] == ",".join(crop_drops)


def test_rod_slot_detail_circle_and_label_stay_clear_of_the_notes_and_frame() -> None:
    x, y = drawing.DETAIL_CENTER
    crop = drawing.DETAIL_CROP_RADIUS
    # The circle sits under the notes and right of the frame border.
    assert y + crop < drawing.NOTES_XY[1] - 0.010
    assert x - crop > 0.020 and y - crop > 0.010
    # The width's dimension line stands outside the circle, and the label's
    # top centre is right of it.
    width_x = drawing.DETAIL_KEEP["RodSlotWidth"][0]
    assert width_x > x + crop
    assert drawing.DETAIL_LABEL_XY[0] - 0.010 > width_x
    assert drawing.DETAIL_LABEL_TEXT == "DETAIL D\nSCALE 5 : 1"
    # The run's value and flag sit right of the circle, under the label. Its
    # widest line, "PIN REACH TO ROD-PIN", printed 51.4 mm wide and centred on
    # the dimension (farm run 3111b8f0a's layout audit: text-on-line against
    # the circle at +0.037), so the whole line must clear the circle's extent.
    flat_x, flat_y = drawing.DETAIL_KEEP["RodSlotFlat"]
    assert flat_x - 0.0514 / 2.0 > x + crop and flat_y < y - 0.010
    assert flat_y < drawing.DETAIL_LABEL_XY[1] - 0.015
