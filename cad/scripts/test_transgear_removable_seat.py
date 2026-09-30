"""The removable #25 sprocket's seat interface (MHA-081 on MHA-026 / MHA-078)."""

from __future__ import annotations

import math

import pytest

import _config
import build_transgear_knob_shaft as knob
import crank_seat_drive_pin_spec as crank_pin
import crankshaft_spec as crank
import transgear_knob_drive_pin_spec as knob_pin
import transgear_removable_spec as spec


def test_seat_spigot_rim_is_the_recorded_shortfall() -> None:
    rim = (
        spec.SEAT_SPIGOT_DIA / 2.0
        - spec.PIN_CIRCLE_RADIUS
        - spec.DRIVE_PIN_HOLE_DIA / 2.0
    )
    assert 0.0 < rim < 1.5
    assert spec.SEAT_SPIGOT_RIM == pytest.approx(rim)


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
    # The shared seat stays inside a real chain's plates with running air.
    assert got - spec.SEAT_SPIGOT_DIA / 2.0 >= 0.15


def test_bought_chain_reach_about_the_seat_face() -> None:
    # PEER 25R: W 0.125 in between the inner plates, G 0.185 in centreline to
    # the connecting link's clip.  Floated frontmost the rear inner plate lies
    # on the seat face; rearmost the front one lies on the wheel's front face.
    w, g = 0.125 * 25.4, 0.185 * 25.4
    assert spec.CHAIN_REACH_FRONT == pytest.approx(w / 2.0 + g)
    thinnest = spec.PLATE + min(spec.PLATE_BAND)
    assert spec.chain_reach_rear(thinnest) == pytest.approx(w / 2.0 + g - 2.7)
    # The inner plates straddle even the thickest wheel.
    assert spec.PLATE + max(spec.PLATE_BAND) < w


def test_knob_pin_holes_obey_the_wall_floor_or_run_through() -> None:
    # The shipped holes run the whole collar.
    assert knob.PIN_HOLE_DEPTH == knob.COLLAR_LEN
    assert knob.pin_hole_meets_wall_floor(knob.COLLAR_LEN, knob.PIN_HOLE_DEPTH)
    # Negative control: the old blind hole, reamed to the pin's press depth
    # (4.7625 - 2.4 = 2.3625) in the 3.6 collar, left a 1.2375 floor.  The old
    # guard only refused a breakthrough (floor > 0) and passed it.
    old_depth = knob_pin.LENGTH - spec.DRIVE_PIN_PROUD
    assert old_depth == pytest.approx(2.3625)
    assert 0.0 < knob.COLLAR_LEN - old_depth < knob.WALL_FLOOR
    assert not knob.pin_hole_meets_wall_floor(knob.COLLAR_LEN, old_depth)
    # A blind hole is fine exactly at the floor, and not a hair under it.
    assert knob.pin_hole_meets_wall_floor(3.6, 3.6 - 1.5)
    assert not knob.pin_hole_meets_wall_floor(3.6, 3.6 - 1.49)


def test_knob_pin_tip_stays_inside_the_thinnest_wheel_under_the_thumbnut() -> None:
    # The press stop sets the tip at 2.4 +/-0.10; the thinnest wheel is 2.7.
    assert knob_pin.PROUD_RANGE == pytest.approx((2.30, 2.50))
    assert knob_pin.THINNEST_PLATE == pytest.approx(2.7)
    assert knob_pin.TIP_INSET_WORST == pytest.approx(0.20)
    assert knob_pin.checked_tip_inset(2.7 - knob_pin.TIP_INSET_MIN, 2.7) == (
        pytest.approx(knob_pin.TIP_INSET_MIN)
    )
    # Negative control: pressed to a floor like the crank's pins, the pin's
    # proud carries the depth band and the dowel's length grade (2.754 max).
    # The old check held that against the NOMINAL 2.8 plate and passed it; on
    # the thinnest wheel the tip stands out under the thumbnut's neck.
    floor_pressed_max = (
        spec.DRIVE_PIN_PROUD + crank.DRIVE_PIN_DEPTH_TOL + crank.DRIVE_PIN_LENGTH_GRADE
    )
    assert floor_pressed_max == pytest.approx(2.754)
    assert floor_pressed_max < spec.PLATE
    with pytest.raises(AssertionError, match="thumbnut"):
        knob_pin.checked_tip_inset(floor_pressed_max, knob_pin.THINNEST_PLATE)
    with pytest.raises(AssertionError):
        knob_pin.checked_tip_inset(2.7 - knob_pin.TIP_INSET_MIN + 0.01, 2.7)


def test_knob_pin_pressed_end_stays_inside_the_collar() -> None:
    # Longest 3/16 dowel set lowest, collar at the loosest .X row:
    # 3.6 - 0.8 - (4.7625 + 0.254 - 2.30).
    assert knob.PIN_REAR_INSET_WORST == pytest.approx(0.0835)
    # Negative control: the crank's 1/4 dowel set to the same stop would
    # stand out of the collar's rear face toward the 120T disc.
    assert (
        knob.pin_rear_inset(
            knob.COLLAR_LEN - crank.STATION_ROW,
            crank_pin.LENGTH + crank.DRIVE_PIN_LENGTH_GRADE,
            min(knob_pin.PROUD_RANGE),
        )
        < 0.0
    )


def test_knob_pin_sheet_prints_the_press_stop_range() -> None:
    notes = " ".join(
        _config.parts("transgear-knob-drive-pin")["installation_notes"].split()
    )
    low, high = knob_pin.PROUD_RANGE
    assert f"{low:.2f}-{high:.2f} PROUD OF THE SEAT FACE" in notes


_CRANK_SEAT = dict(
    seat_face=crank.SEAT_COLLAR,
    seat_face_band=crank.SEAT_COLLAR_BAND,
    hub_rear_tol=crank.HUB_LENGTH_TOL,
    plate_min=spec.PLATE + min(spec.PLATE_BAND),
)


def test_crank_pin_tips_are_checked_against_the_hub_rear_face() -> None:
    # Hand check, dome-root stations: seat forward 30.5 - 0.5, tip 2.754 in
    # front of it, hub rear long 27.0 + 0.05; floated onto the short hub the
    # thinnest wheel moves 30.6 - 2.7 - 26.95 off the seat.
    air, engagement = crank.drive_pin_front_clearances(
        crank.DRIVE_PIN_PROUD_RANGE, hub_rear=crank.HUB_LENGTH, **_CRANK_SEAT
    )
    assert crank.DRIVE_PIN_PROUD_RANGE == pytest.approx((2.046, 2.754))
    assert air == pytest.approx(30.0 - 2.754 - 27.05)
    assert engagement == pytest.approx(2.046 - 0.95)
    assert (air, engagement) == (
        crank.DRIVE_PIN_HUB_AIR_WORST,
        crank.DRIVE_PIN_ENGAGEMENT_WORST,
    )
    # The longest pin standing past the thinnest wheel is not a contact.
    assert max(crank.DRIVE_PIN_PROUD_RANGE) > spec.PLATE + min(spec.PLATE_BAND)


def test_crank_pin_check_refuses_a_hub_the_old_plate_check_passed() -> None:
    proud = crank.DRIVE_PIN_PROUD_RANGE
    # The old check: both limits inside the NOMINAL plate.  It never looked at
    # the hub, so it passes these pins whatever the hub does.
    assert 0.0 < proud[0] < proud[1] < spec.PLATE
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
