"""The kinematic probe's crank T12 -> knob T24 chain-ratio check, SolidWorks-free.

The probe must tell the exact 12:24 tooth ratio from the wrong couplings a Belt/
Chain feature can bake in: the #25 outside (tip) diameters, or the pitch-circle
diameters p/sin(180/N) typed instead of the per-tooth N*p/pi.
"""

from __future__ import annotations

import pytest

import pd_transgear_removable_spec as removable
from build_kinematic_probe import (
    CHAIN_RATIO,
    CRANK_TOL,
    DRIVE_DEG,
    READ_SLACK_DEG,
    check_chain_ratio,
)

T12 = removable.TEETH["T12"]
T24 = removable.TEETH["T24"]
OD_RATIO = removable.outside_dia(T12) / removable.outside_dia(T24)
PITCH_CIRCLE_RATIO = removable.pitch_dia(T12) / removable.pitch_dia(T24)


def test_exact_tooth_ratio_passes() -> None:
    check_chain_ratio(DRIVE_DEG * CHAIN_RATIO, DRIVE_DEG)


def test_worst_admitted_reading_slack_passes() -> None:
    # The least crank the drive gate admits, both readings off by (just under)
    # the per-reading slack in opposite directions: a legitimate solve.
    crank = DRIVE_DEG - CRANK_TOL
    slack = 0.99 * READ_SLACK_DEG
    check_chain_ratio(crank * CHAIN_RATIO + slack, crank - slack)
    check_chain_ratio(crank * CHAIN_RATIO - slack, crank + slack)


@pytest.mark.parametrize(
    "wrong_ratio",
    [
        pytest.param(OD_RATIO, id="outside-diameter"),
        pytest.param(PITCH_CIRCLE_RATIO, id="pitch-circle"),
        # Halfway to each wrong coupling must already read as wrong, so the
        # band cannot straddle the midpoint between right and wrong.
        pytest.param((OD_RATIO + CHAIN_RATIO) / 2.0, id="outside-diameter-midpoint"),
        pytest.param(
            (PITCH_CIRCLE_RATIO + CHAIN_RATIO) / 2.0, id="pitch-circle-midpoint"
        ),
    ],
)
def test_wrong_diameter_coupling_is_rejected(wrong_ratio: float) -> None:
    with pytest.raises(RuntimeError, match="chain ratio"):
        check_chain_ratio(DRIVE_DEG * wrong_ratio, DRIVE_DEG)


def test_dropped_belt_mate_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="chain ratio"):
        check_chain_ratio(0.0, DRIVE_DEG)


def _sw_rotation(m: list[list[float]]) -> list[float]:
    """``Transform2.ArrayData``'s rotation for column-vector matrix ``m``:
    the part's axes are its rows, i.e. ``m`` transposed, flattened."""
    return [m[c][r] for r in range(3) for c in range(3)]


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)] for r in range(3)
    ]


def _rz(deg: float) -> list[list[float]]:
    import math

    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


@pytest.mark.parametrize(
    "frame",
    [
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],  # identity disc
        [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]],  # Ry180 feed sleeve
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]],  # Rx180
    ],
)
def test_signed_spin_reads_alike_whatever_the_insertion_frame(
    frame: list[list[float]],
) -> None:
    """Two parts Lock-mated on one global Z axis spin by the same signed angle
    even when one was inserted flipped (run 20261001T051043622Z read the Ry180
    feed sleeve +1.50 against its identity disc's -1.50)."""
    from build_kinematic_probe import _rel_z_angle_deg

    for spin in (1.5, -7.0, 30.0):
        before = _sw_rotation(_matmul(_rz(40.0), frame))
        after = _sw_rotation(_matmul(_rz(40.0 + spin), frame))
        # The identity frame keeps the sign the probe's constants were set on.
        assert _rel_z_angle_deg(after, before) == pytest.approx(-spin)
