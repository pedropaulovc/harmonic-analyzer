"""Measured native spring placements for the supported assembly presets.

Analytic spring_mount_geom poses remain the force/catalog model. Assemblies use
these measured poses directly; unsupported stations never trigger fitting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

import _config
from spring_mount_geom import SpringPose

_UNIT_AXIS_ABS_TOL = 1e-12
_VALID_CLOCKINGS = ("standard", "half_turn")


def _pose_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"Calibrated native spring {label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Calibrated native spring {label} must be a finite number")
    return number


def _pose_xy(value: object, label: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(
            f"Calibrated native spring {label} must contain exactly two finite numbers"
        )
    if any(
        isinstance(component, bool) or not isinstance(component, Real)
        for component in value
    ):
        raise ValueError(
            f"Calibrated native spring {label} must contain exactly two finite numbers"
        )
    xy = (float(value[0]), float(value[1]))
    if not all(math.isfinite(component) for component in xy):
        raise ValueError(
            f"Calibrated native spring {label} must contain exactly two finite numbers"
        )
    return xy


def _spring_pose(values: dict, *, expected_clocking: str) -> SpringPose:
    length_mm = _pose_number(values["length_mm"], "length")
    if length_mm <= 0.0:
        raise ValueError("Calibrated native spring length must be positive")
    lower_eye_xy = _pose_xy(values["lower_eye_xy"], "lower_eye_xy")
    upper_eye_xy = _pose_xy(values["upper_eye_xy"], "upper_eye_xy")
    axis_xy = _pose_xy(values["axis_xy"], "axis_xy")
    centre_xy = _pose_xy(values["centre_xy"], "centre_xy")
    if not math.isclose(
        math.hypot(*axis_xy), 1.0, rel_tol=0.0, abs_tol=_UNIT_AXIS_ABS_TOL
    ):
        raise ValueError("Calibrated native spring axis_xy must be unit length")
    clocking = values["clocking"]
    if clocking not in _VALID_CLOCKINGS:
        raise ValueError(
            "Calibrated native spring clocking must be 'standard' or 'half_turn'"
        )
    if clocking != expected_clocking:
        raise ValueError(
            f"Calibrated native spring clocking must be {expected_clocking!r}"
        )
    return SpringPose(
        length_mm=length_mm,
        lower_eye_xy=lower_eye_xy,
        upper_eye_xy=upper_eye_xy,
        axis_xy=axis_xy,
        centre_xy=centre_xy,
        clocking=clocking,
    )


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


def _spring(record: dict, *, expected_clocking: str) -> SettledSpring:
    pose = _spring_pose(record["pose"], expected_clocking=expected_clocking)
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
            return _spring(record, expected_clocking="standard")
    raise ValueError(f"No native spring calibration for amplitude {amplitude_mm!r} mm")


def counter_seat() -> tuple[SettledSpring, float]:
    """Return the fixed counter placement and gooseneck height for this bank."""
    record = _active_preset()["counter"]
    return (
        _spring(record, expected_clocking="half_turn"),
        _pose_number(record["gooseneck_origin_y_mm"], "gooseneck_origin_y_mm"),
    )
