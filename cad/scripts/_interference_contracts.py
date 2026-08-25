"""Explicit, volume-bounded interference-fit contracts for assembly gates.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from pinion_bracket_geometry import PIN_BORE, PIN_SEAT
from pinion_cam_pin_geometry import PIN_DIA


def _smooth_annulus_limit_mm3(
    major_d: float,
    tap_d: float,
    length: float,
) -> float:
    """Return a 10%-headroom bound for smooth thread-envelope engagement."""
    return 1.10 * math.pi * (major_d**2 - tap_d**2) * length / 4.0


def _numbered_pairs(
    first_stem: str,
    numbers: range,
    second_stem: str,
    limit: float,
    *,
    second_number: int | None = 1,
) -> dict[frozenset[str], float]:
    """Build exact numbered component pairs, optionally matching suffixes."""
    return {
        frozenset(
            (
                f"{first_stem}-{number}",
                f"{second_stem}-{number if second_number is None else second_number}",
            )
        ): limit
        for number in numbers
    }


_CAM_PIN_OVERLAP_MM3 = math.pi * (PIN_DIA**2 - PIN_BORE**2) * PIN_SEAT / 4.0
_CAM_PIN_GATE_LIMIT_MM3 = 1.10 * _CAM_PIN_OVERLAP_MM3

_DRIVE_TRAIN_ALLOWED_PAIRS = {
    frozenset(("pinion-bracket-1", "pinion-cam-pin-1")): _CAM_PIN_GATE_LIMIT_MM3,
    frozenset(("pinion-bracket-2", "pinion-cam-pin-2")): _CAM_PIN_GATE_LIMIT_MM3,
    frozenset(("cone-tip-adjuster-1", "cone-tip-block-1")): _smooth_annulus_limit_mm3(
        7.9502, 6.528, 6.0
    ),
    frozenset(
        ("cone-tip-pinch-screw-1", "cone-tip-block-1")
    ): _smooth_annulus_limit_mm3(2.8448, 2.261, 1.925),
}

_FRAME_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "lag-screw",
        range(1, 5),
        "rocker-arm-support",
        _smooth_annulus_limit_mm3(12.7, 12.30376, 6.35),
    ),
    **_numbered_pairs(
        "frame-side-screw",
        range(1, 5),
        "top-frame",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 12.7),
    ),
    frozenset(("gooseneck-set-screw-1", "top-frame-1")): _smooth_annulus_limit_mm3(
        6.35, 5.105, 6.95
    ),
}

_MAGNIFIER_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "clamp-screw",
        range(1, 3),
        "column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 4.85),
    ),
    frozenset(("thumb-screw-1", "magnifying-clamp-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 3.9
    ),
}

_SUMMING_ALLOWED_PAIRS = _numbered_pairs(
    "knife-hanger-stud",
    range(1, 3),
    "knife-mount",
    _smooth_annulus_limit_mm3(12.7, 10.716, 11.5735),
    second_number=None,
)

_PEN_ALLOWED_PAIRS = {
    frozenset(("pen-set-screw-1", "pen-frame-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 5.0
    ),
    frozenset(("hanger-screw-1", "pen-hanger-1")): _smooth_annulus_limit_mm3(
        4.1656, 3.454, 3.0
    ),
}

_PAPER_DRIVE_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "clamp-screw",
        range(1, 3),
        "column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 9.0124),
    ),
    **_numbered_pairs(
        "clamp-screw",
        range(3, 5),
        "column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 9.0124),
        second_number=2,
    ),
    **_numbered_pairs(
        "fillister-screw",
        range(1, 5),
        "platen",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 4.0),
    ),
    **_numbered_pairs(
        "fillister-screw",
        range(5, 10),
        "platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 5.2678),
    ),
    **_numbered_pairs(
        "fillister-screw",
        range(10, 15),
        "platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 5.2678),
        second_number=2,
    ),
    **_numbered_pairs(
        "fillister-screw",
        range(15, 19),
        "platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 4.35),
    ),
    **_numbered_pairs(
        "fillister-screw",
        range(19, 23),
        "platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 4.35),
        second_number=2,
    ),
    **_numbered_pairs(
        "bracket-screw",
        range(1, 3),
        "support-bar",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 8.7),
    ),
}

# The cone-platform pivot screw now carries its full McMaster #10-24 thread
# envelope. Bound its exact nested tap engagement by the same conservative
# smooth-annulus contract as every other migrated stock thread.
_HARMONIC_ANALYZER_ALLOWED_PAIRS = {
    frozenset(
        (
            "frame-1/harmonic-base-1",
            "drive-train-1/cone-pivot-screw-1",
        )
    ): _smooth_annulus_limit_mm3(4.826, 3.797, 9.525),
    **_numbered_pairs(
        "drive-train-1/cone-lock-knob",
        range(1, 2),
        "frame-1/harmonic-base",
        _smooth_annulus_limit_mm3(6.35, 5.105, 1.5875),
    ),
    **_numbered_pairs(
        "drive-train-1/swing-stop-screw",
        range(1, 2),
        "frame-1/harmonic-base",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 6.0),
    ),
    **_numbered_pairs(
        "drive-train-1/slotted-screw",
        range(1, 5),
        "frame-1/harmonic-base",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 6.65),
    ),
    **_numbered_pairs(
        "drive-train-1/foot-screw",
        range(1, 2),
        "frame-1/harmonic-base",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 8.725),
    ),
    **_numbered_pairs(
        "drive-train-1/foot-screw",
        range(2, 4),
        "frame-1/harmonic-base",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 4.525),
    ),
    **_numbered_pairs(
        "channel-1/frame-side-screw",
        range(1, 3),
        "frame-1/top-frame",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 8.6624),
    ),
}

_BY_ASSEMBLY: dict[str, Mapping[frozenset[str], float]] = {
    "drive-train": _DRIVE_TRAIN_ALLOWED_PAIRS,
    "frame": _FRAME_ALLOWED_PAIRS,
    "magnifier": _MAGNIFIER_ALLOWED_PAIRS,
    "summing": _SUMMING_ALLOWED_PAIRS,
    "pen": _PEN_ALLOWED_PAIRS,
    "paper-drive": _PAPER_DRIVE_ALLOWED_PAIRS,
    "harmonic-analyzer": _HARMONIC_ANALYZER_ALLOWED_PAIRS,
}


def allowed_interference_pairs(name: str) -> Mapping[frozenset[str], float]:
    """Return exact intended-fit pairs and maximum overlap volumes for *name*."""
    return _BY_ASSEMBLY.get(name, {})
