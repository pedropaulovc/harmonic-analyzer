"""The removable #25 sprocket's seat interface (MHA-PD-09 on MHA-DT-11 / MHA-PD-22)."""

from __future__ import annotations

import math

import pytest

import _config
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm
import build_dt_drive_train_assembly as bdt
import dt_crank_hub_geometry as hub
import dt_vn_crank_seat_drive_pin_spec as crank_pin
import dt_crankshaft_spec as crank
import pd_transgear_drive_collar_spec as collar
import pd_vn_transgear_knob_drive_pin_spec as knob_pin
import pd_vn_transgear_latch_pin_spec as dowel_spec
import pd_transgear_removable_spec as spec
import _sprocket_seat_geometry as seat_geometry


@pytest.mark.parametrize(("configuration", "teeth"), spec.CONFIGS)
def test_registered_configuration_resolves_its_teeth(
    configuration: str, teeth: int
) -> None:
    assert spec.configuration_teeth(configuration) == teeth


@pytest.mark.parametrize("configuration", ["", "t12", "unregistered"])
def test_unregistered_mounted_selection_is_refused(configuration: str) -> None:
    with pytest.raises(ValueError, match="unknown removable sprocket configuration"):
        spec.configuration_teeth(configuration)


def test_mounted_selections_resolve_through_the_part_configurations() -> None:
    assert spec.CRANK_TEETH == spec.configuration_teeth(spec.CRANK_CONFIG)
    assert spec.KNOB_TEETH == spec.configuration_teeth(spec.KNOB_CONFIG)


def test_seat_spigot_rim_is_the_recorded_shortfall() -> None:
    rim = (
        seat_geometry.SEAT_SPIGOT_DIA / 2.0
        - seat_geometry.PIN_CIRCLE_RADIUS
        - seat_geometry.DRIVE_PIN_HOLE_DIA / 2.0
    )
    assert 0.0 < rim < 1.5
    assert seat_geometry.SEAT_SPIGOT_RIM == pytest.approx(rim)


def test_one_drive_pin_hole_serves_both_seats_at_the_d14_press() -> None:
    # #290 fit row D14: .0930 REAM_H7 (.0930/.0935) for the 98381A 3/32
    # dowel (+.0001/+.0003), a .00035 to .00105 press.
    hole = seat_geometry.DRIVE_PIN_HOLE_DIA + min(seat_geometry.DRIVE_PIN_HOLE_BAND)
    hole_max = seat_geometry.DRIVE_PIN_HOLE_DIA + max(seat_geometry.DRIVE_PIN_HOLE_BAND)
    assert (hole / 25.4, hole_max / 25.4) == pytest.approx((0.0930, 0.0935))
    assert (
        crank.DRIVE_PIN_HOLE_DIA
        == collar.PIN_HOLE_DIA
        == seat_geometry.DRIVE_PIN_HOLE_DIA
    )
    assert (
        crank.DRIVE_PIN_HOLE_BAND
        == collar.PIN_HOLE_BAND
        == seat_geometry.DRIVE_PIN_HOLE_BAND
    )
    assert crank.HOLE_CALLOUT_PLACES == collar.PIN_HOLE_PLACES == 4
    press = tuple(value / 25.4 for value in crank.DRIVE_PIN_PRESS_INTERFERENCE)
    assert press == pytest.approx((0.00035, 0.00105))
    # Each pin centre .2756 +/-.0009 on both shafts and in the wheel.
    assert crank.DRIVE_PIN_OFFSET_TOL == collar.PIN_OFFSET_TOL == spec.PIN_LOCATION_TOL
    assert seat_geometry.DRIVE_PIN_OFFSET_TOL == pytest.approx(0.0009 * 25.4)
    assert seat_geometry.DRIVE_PIN_OFFSET_PLACES == 4
    # The wheel's drilled bore and pin holes are the seat's (.406, .098).
    assert (spec.BORE_DIA, spec.PIN_HOLE_DIA) == (
        seat_geometry.BORE_DIA,
        seat_geometry.PIN_HOLE_DIA,
    )
    assert (
        seat_geometry.BORE_DIA / 25.4,
        seat_geometry.PIN_HOLE_DIA / 25.4,
    ) == pytest.approx((0.406, 0.098))


@pytest.mark.parametrize(
    ("plate_height", "inner_r"),
    [(spec.ANSI_PLATE_HEIGHT, 8.928), (4.8, 9.449)],
    ids=["ansi", "cad"],
)
def test_wrapped_t12_plate_inner_edge(plate_height: float, inner_r: float) -> None:
    # Hand check: rollers on the 24.535 pitch circle, 30 deg apart; the chord
    # midpoint sits r_p cos 15 deg from the axis, the plate h/2 inside it.
    chord_mid = spec.pitch_dia(12) / 2.0 * math.cos(math.radians(15.0))
    assert chord_mid == pytest.approx(11.849, abs=5e-4)
    got = spec.chain_plate_inner_radius(12, plate_height)
    assert got == pytest.approx(inner_r, abs=5e-4)


def _plate_edge_reach(teeth: int, plate_height: float, wheel_offset: float) -> float:
    """Closest approach to the shaft axis of any wrapped plate's inner edge,
    the wheel's centre ``wheel_offset`` off that axis along +Y, swept over the
    chain's phase: rollers on the pitch circle, each plate's inner edge the
    roller chord moved h/2 toward the wheel's centre."""
    rp = spec.pitch_dia(teeth) / 2.0
    step = 2.0 * math.pi / teeth
    best = math.inf
    for k in range(720):
        for n in range(teeth):
            t0 = n * step + step * k / 720.0
            ends = []
            for t in (t0, t0 + step):
                x, y = rp * math.cos(t), rp * math.sin(t) + wheel_offset
                ends.append((x, y))
            mid = t0 + step / 2.0
            nx, ny = (
                -math.cos(mid) * plate_height / 2.0,
                -math.sin(mid) * plate_height / 2.0,
            )
            (ax, ay), (bx, by) = ((x + nx, y + ny) for x, y in ends)
            # Distance from the origin to segment AB.
            dx, dy = bx - ax, by - ay
            u = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
            best = min(best, math.hypot(ax + u * dx, ay + u * dy))
    return best


def _wheel_float(hole_dia: float) -> float:
    """The wheel's worst offset from the shaft axis riding on its two pins:
    the holes drilled to their largest over the smallest stock dowel, plus
    a pin centre and its hole centre each at their location limit, opposite
    ways along the pins' line."""
    # The holes are drilled to the wheel's own sheet, in its unit (#2124).
    wheel_unit = drawing_unit(
        "parts/pd-transgear-removable", _config.parts("pd-transgear-removable")
    )
    hole_max = hole_dia + drilled_oversize_mm(unit=wheel_unit)
    dowel_min = crank_pin.DIA + dowel_spec.DIA_BAND_IN[0] * dowel_spec.MM_PER_IN
    return (
        (hole_max - dowel_min) / 2.0
        + crank.DRIVE_PIN_OFFSET_TOL
        + seat_geometry.DRIVE_PIN_OFFSET_TOL
    )


def test_chain_on_the_floated_crank_wheel_keeps_its_radial_air() -> None:
    """Codex P2 on a1ee741dc: the crank wheel rides two pins in drilled slip
    holes, so a bought chain following it closes on the shaft-fixed
    spigot and on the hub relief.  Judge the corner the prints allow, every
    diameter at its largest printed size and the hub at the far side of its
    bore clearance; the gate must report that corner's air, and it must stay
    positive."""
    wheel = _wheel_float(seat_geometry.PIN_HOLE_DIA)
    assert wheel == pytest.approx(crank.WHEEL_SEAT_FLOAT, abs=1e-4)
    # The bore is no stop: its tightest clearance on the pilot is wider.
    assert (seat_geometry.BORE_DIA - hub.SHAFT_DIA) / 2.0 > wheel
    hub_float = (hub.HUB_BORE_DIA_MAX - (hub.SHAFT_DIA + hub.SHAFT_DIA_BAND[1])) / 2.0
    spigot_max = crank.SPIGOT_DIA + max(seat_geometry.SPIGOT_DIA_BAND)
    relief_max = hub.RELIEF_DIA_MAX
    for height, spigot_air, relief_air in (
        (
            spec.ANSI_PLATE_HEIGHT,
            bdt.CHAIN_SPIGOT_RADIAL_AIR_ANSI,
            bdt.CHAIN_RELIEF_RADIAL_AIR_ANSI,
        ),
        (4.8, bdt.CHAIN_SPIGOT_RADIAL_AIR_CAD, bdt.CHAIN_RELIEF_RADIAL_AIR_CAD),
    ):
        # The gate's air is the floated corner's, not the centred wheel's.
        corner = _plate_edge_reach(spec.CRANK_TEETH, height, wheel) - spigot_max / 2.0
        assert spigot_air == pytest.approx(corner, abs=1e-4)
        assert corner >= bdt.CHAIN_RADIAL_AIR_WORST_MIN > 0.0
        corner = (
            _plate_edge_reach(spec.CRANK_TEETH, height, wheel + hub_float)
            - relief_max / 2.0
        )
        assert relief_air == pytest.approx(corner, abs=1e-4)
        assert corner >= bdt.CHAIN_RADIAL_AIR_WORST_MIN
    # Negative control: additional pin clearance floats the bought plate past
    # the permitted radial-air floor, whatever crank configuration is selected.
    loose = (
        spec.chain_plate_inner_radius(spec.CRANK_TEETH, spec.ANSI_PLATE_HEIGHT)
        - spigot_max / 2.0 - bdt.CHAIN_RADIAL_AIR_WORST_MIN + 0.02
    )
    corner = (
        _plate_edge_reach(spec.CRANK_TEETH, spec.ANSI_PLATE_HEIGHT, loose)
        - spigot_max / 2.0
    )
    assert corner < bdt.CHAIN_RADIAL_AIR_WORST_MIN
    with pytest.raises(AssertionError, match="radial air"):
        bdt.chain_radial_air("spigot", spec.ANSI_PLATE_HEIGHT, spigot_max, loose)


def test_bought_chain_reach_about_the_seat_face() -> None:
    # PEER 25R: W 0.125 in between the inner plates, G 0.185 in centreline to
    # the connecting link's clip.  Floated frontmost the rear inner plate lies
    # on the seat face; rearmost the front one lies on the wheel's front face.
    w, g = 0.125 * 25.4, 0.185 * 25.4
    assert seat_geometry.CHAIN_REACH_FRONT == pytest.approx(w / 2.0 + g)
    thinnest = seat_geometry.PLATE + min(seat_geometry.PLATE_BAND)
    assert seat_geometry.chain_reach_rear(thinnest) == pytest.approx(w / 2.0 + g - 2.7)
    # The inner plates straddle even the thickest wheel.
    assert seat_geometry.PLATE + max(seat_geometry.PLATE_BAND) < w


def test_knob_pin_holes_obey_the_wall_floor_or_run_through() -> None:
    # The shipped holes run the whole collar.
    assert collar.PIN_HOLE_DEPTH == collar.LENGTH
    assert collar.pin_hole_meets_wall_floor(collar.LENGTH, collar.PIN_HOLE_DEPTH)
    # Negative control: the old blind hole, reamed to the pin's press depth
    # (4.7625 - 2.4 = 2.3625) in the first 3.6 collar, left a 1.2375 floor.
    # The old guard only refused a breakthrough (floor > 0) and passed it.
    old_depth = knob_pin.LENGTH - seat_geometry.DRIVE_PIN_PROUD
    assert old_depth == pytest.approx(2.3625)
    first_collar = 3.6
    assert 0.0 < first_collar - old_depth < collar.WALL_FLOOR
    assert not collar.pin_hole_meets_wall_floor(first_collar, old_depth)
    # Blind in the 4.000 collar it would leave 1.6375, over the floor.
    assert collar.pin_hole_meets_wall_floor(collar.LENGTH, old_depth)
    # A blind hole is fine exactly at the floor, and not a hair under it.
    assert collar.pin_hole_meets_wall_floor(3.6, 3.6 - collar.WALL_FLOOR)
    assert not collar.pin_hole_meets_wall_floor(3.6, 3.6 - collar.WALL_FLOOR + 0.01)


def test_knob_pin_tip_stays_inside_the_thinnest_wheel_under_the_thumbnut() -> None:
    # The press stop sets the tip at .091-.098; the thinnest wheel is 2.7.
    assert knob_pin.PROUD_RANGE == pytest.approx((2.3114, 2.4892))
    assert knob_pin.THINNEST_PLATE == pytest.approx(2.7)
    assert knob_pin.TIP_INSET_WORST == pytest.approx(0.2108)
    assert knob_pin.checked_tip_inset(2.7 - knob_pin.TIP_INSET_MIN, 2.7) == (
        pytest.approx(knob_pin.TIP_INSET_MIN)
    )
    # Negative control: pressed to a floor like the crank's pins, the pin's
    # proud carries the depth band and the dowel's length grade (2.754 max).
    # The old check held that against the NOMINAL 2.8 plate and passed it; on
    # the thinnest wheel the tip stands out under the thumbnut's neck.
    floor_pressed_max = (
        seat_geometry.DRIVE_PIN_PROUD + crank.DRIVE_PIN_DEPTH_TOL + seat_geometry.DRIVE_PIN_LENGTH_GRADE
    )
    assert floor_pressed_max < seat_geometry.PLATE
    with pytest.raises(AssertionError, match="thumbnut"):
        knob_pin.checked_tip_inset(floor_pressed_max, knob_pin.THINNEST_PLATE)
    with pytest.raises(AssertionError):
        knob_pin.checked_tip_inset(2.7 - knob_pin.TIP_INSET_MIN + 0.01, 2.7)


def test_knob_pin_pressed_end_stays_inside_the_collar() -> None:
    # Nominal: the set body less (4.7625 - 2.4).  Worst: the longest 3/16
    # dowel set lowest in the shortest fitted body.
    assert collar.LENGTH == pytest.approx(6.1722)
    assert collar.PIN_REAR_INSET == pytest.approx(3.8097)
    assert collar.PIN_REAR_INSET_WORST == pytest.approx(1.1811)
    # Negative control: the crank's 1/4 dowel set to the same stop in the
    # same shortest collar would stand out of its rear face toward the 12T.
    assert collar.pin_rear_inset(
        collar.LENGTH_FITTED_MIN,
        crank_pin.LENGTH + seat_geometry.DRIVE_PIN_LENGTH_GRADE,
        min(knob_pin.PROUD_RANGE),
    ) == pytest.approx(-0.4064)


def test_knob_pin_sheet_prints_the_press_stop_range() -> None:
    notes = " ".join(
        _config.parts("pd-vn-transgear-knob-drive-pin")["installation_notes"].split()
    )
    assert f"{knob_pin.PROUD_TEXT} PROUD OF THE SEAT FACE" in notes


_CRANK_SEAT = dict(
    seat_face=crank.SEAT_COLLAR,
    seat_face_band=crank.SEAT_COLLAR_BAND,
    hub_rear_band=crank.HUB_LENGTH_BAND,
    plate_min=seat_geometry.PLATE + min(seat_geometry.PLATE_BAND),
)


def test_crank_pin_tips_are_checked_against_the_hub_rear_face() -> None:
    # Hand check, dome-root stations: the seat at its forward printed limit,
    # the longest tip in front of it, hub rear long .990 + .004; floated onto
    # the short hub (.990 - .010, the title block's side) the thinnest wheel
    # moves off the seat by the seat's rear printed limit less the wheel and
    # the short hub.
    air, engagement = crank.drive_pin_front_clearances(
        crank.DRIVE_PIN_PROUD_RANGE, hub_rear=crank.HUB_LENGTH, **_CRANK_SEAT
    )
    least, most = crank.DRIVE_PIN_PROUD_RANGE
    seat_low, seat_high = (crank.SEAT_COLLAR + d for d in sorted(crank.SEAT_COLLAR_BAND))
    assert air == pytest.approx(seat_low - most - (25.146 + 0.1016))
    assert engagement == pytest.approx(least - (seat_high - 2.7 - (25.146 - 0.254)))
    assert (air, engagement) == (
        crank.DRIVE_PIN_HUB_AIR_WORST,
        crank.DRIVE_PIN_ENGAGEMENT_WORST,
    )
    # The longest pin standing past the thinnest wheel is not a contact.
    assert max(crank.DRIVE_PIN_PROUD_RANGE) > seat_geometry.PLATE + min(seat_geometry.PLATE_BAND)


def test_crank_pin_check_refuses_a_hub_the_old_plate_check_passed() -> None:
    proud = crank.DRIVE_PIN_PROUD_RANGE
    # The old check: both limits inside the NOMINAL plate.  It never looked at
    # the hub, so it passes these pins whatever the hub does.
    assert 0.0 < proud[0] < proud[1] < seat_geometry.PLATE
    # Negative control: a hub 0.2 longer closes the tip's air.
    with pytest.raises(AssertionError, match="hub's rear face"):
        crank.drive_pin_front_clearances(
            proud, hub_rear=crank.HUB_LENGTH + 0.2, **_CRANK_SEAT
        )
    # Negative control: a hub 1.1 shorter lets the wheel float off the pins.
    with pytest.raises(AssertionError, match="leaves the drive pins"):
        crank.drive_pin_front_clearances(
            proud, hub_rear=crank.HUB_LENGTH - 1.1, **_CRANK_SEAT
        )


def test_moved_seat_refuses_the_hub_it_left_behind() -> None:
    # Ruling 2026-09-30: the seat face came 1.8 forward (30.5 -> 28.7 from
    # the dome root) and the hub shortened with it (27.0 -> 25.2; .990 since
    # #290).
    proud = crank.DRIVE_PIN_PROUD_RANGE
    assert crank.SEAT_COLLAR == pytest.approx(28.7)
    assert crank.HUB_LENGTH == pytest.approx(0.99 * 25.4)
    first = dict(_CRANK_SEAT, seat_face=30.5)
    # A pair moved together keeps the same air: only the offset matters.
    air, _ = crank.drive_pin_front_clearances(
        proud, hub_rear=crank.HUB_LENGTH + 1.8, **first
    )
    assert air == pytest.approx(crank.DRIVE_PIN_HUB_AIR_WORST)
    # Negative control: the first hub under the moved seat meets the pins.
    with pytest.raises(AssertionError, match="hub's rear face"):
        crank.drive_pin_front_clearances(proud, hub_rear=27.0, **_CRANK_SEAT)
