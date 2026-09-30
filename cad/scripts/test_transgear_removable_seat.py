"""The removable #25 sprocket's seat interface (MHA-081 on MHA-026 / MHA-078)."""

from __future__ import annotations

import math

import pytest

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
