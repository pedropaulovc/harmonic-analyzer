"""Measured native spring placements for the supported assembly presets.

Analytic spring_mount_geom poses remain the force/catalog model. Assemblies use
these measured poses directly; unsupported stations never trigger fitting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
from spring_mount_geom import SpringPose


@dataclass(frozen=True, slots=True)
class SettledSpring:
    pose: SpringPose
    lower_maximum_distance_mm: float
    upper_maximum_distance_mm: float


def _active_preset() -> dict:
    name = _config.machine("amplitude", "preset")
    presets = _config.machine("springs", "presets")
    if name not in presets:
        raise ValueError(f"No native spring calibration for preset {name!r}")
    preset = presets[name]
    if _config.amplitudes() != preset["amplitudes_mm"]:
        raise ValueError(
            f"Preset {name!r} does not match its calibrated amplitude vector; "
            "use the exact stations in machine/springs.yaml. "
            "Uncalibrated amplitudes are not fitted or interpolated."
        )
    return preset


def _maximum_distance(measured_mm: float) -> float:
    measured_mm = float(measured_mm)
    if not math.isfinite(measured_mm) or measured_mm < 0.0:
        raise ValueError(
            "Calibrated native contact distance must be finite and nonnegative"
        )
    guard = float(_config.machine("springs", "native_distance_guard_mm"))
    resolution = float(_config.machine("springs", "calibration_resolution_mm"))
    if not math.isfinite(guard) or guard <= 0.0:
        raise ValueError("Native contact distance guard must be finite and positive")
    if not math.isfinite(resolution) or resolution <= 0.0:
        raise ValueError(
            "Native contact calibration resolution must be finite and positive"
        )
    # These bound readback uncertainty; they never offset a component placement.
    return max(guard, measured_mm + resolution)


def _spring(record: dict) -> SettledSpring:
    values = record["pose"]
    pose = SpringPose(
        length_mm=float(values["length_mm"]),
        lower_eye_xy=tuple(values["lower_eye_xy"]),
        upper_eye_xy=tuple(values["upper_eye_xy"]),
        axis_xy=tuple(values["axis_xy"]),
        centre_xy=tuple(values["centre_xy"]),
        clocking=values["clocking"],
    )
    distances = record["final_distance_mm"]
    return SettledSpring(
        pose,
        _maximum_distance(distances["lower"]),
        _maximum_distance(distances["upper"]),
    )


def channel_seat(amplitude_mm: float) -> SettledSpring:
    """Return the measured placement for an exact calibrated channel station."""
    _active_preset()
    for record in _config.machine("springs", "channel_seats"):
        if amplitude_mm == record["amplitude_mm"]:
            return _spring(record)
    raise ValueError(f"No native spring calibration for amplitude {amplitude_mm!r} mm")


def counter_seat() -> tuple[SettledSpring, float]:
    """Return the fixed counter placement and gooseneck height for this bank."""
    record = _active_preset()["counter"]
    return _spring(record), float(record["gooseneck_origin_y_mm"])
