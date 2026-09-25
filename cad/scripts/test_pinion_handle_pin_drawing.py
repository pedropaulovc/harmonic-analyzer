"""Release contracts for the separate MHA-136 upper-handle retention pin."""

from __future__ import annotations

import math

import pytest

import build_drive_train_assembly as assembly
import pinion_handle_geometry as handle_geometry
import pinion_handle_pin_spec as pin_spec


def test_assembly_places_pin_coaxial_and_flush_in_rotated_handle() -> None:
    """The placed pin crosses the socket at its matched arbor-hole station."""
    pin_axis = assembly.HANDLE_PIN_ROWS[2]
    pin_start = tuple(assembly.HANDLE_PIN_ORIGIN)
    pin_end = tuple(
        pin_start[axis] + pin_spec.PIN_LEN * pin_axis[axis] for axis in range(3)
    )

    tilt = math.radians(assembly.HANDLE_TILT_DEG)
    handle_axes = (
        (math.cos(tilt), math.sin(tilt), 0.0),
        (-math.sin(tilt), math.cos(tilt), 0.0),
        (0.0, 0.0, 1.0),
    )
    handle_origin = (
        assembly.APINION_X,
        assembly.APINION_Y,
        assembly.HANDLE_Z,
    )

    def in_handle_frame(point: tuple[float, ...]) -> tuple[float, ...]:
        offset = tuple(point[axis] - handle_origin[axis] for axis in range(3))
        return tuple(
            sum(offset[axis] * basis[axis] for axis in range(3))
            for basis in handle_axes
        )

    local_start = in_handle_frame(pin_start)
    local_end = in_handle_frame(pin_end)
    socket_mid_station = (
        handle_geometry.GRIP_LEN / 2.0
        + handle_geometry.WALL_T
        + handle_geometry.TUBE_LEN / 2.0
    )
    arbor_hole_station = (
        assembly.ARBOR_Z0
        + assembly.ARBOR_RETENTION_PIN_STATION
        - assembly.HANDLE_Z
    )

    assert socket_mid_station == pytest.approx(arbor_hole_station)
    assert local_start == pytest.approx(
        (0.0, -handle_geometry.TUBE_OD / 2.0, socket_mid_station)
    )
    assert local_end == pytest.approx(
        (0.0, handle_geometry.TUBE_OD / 2.0, socket_mid_station)
    )
