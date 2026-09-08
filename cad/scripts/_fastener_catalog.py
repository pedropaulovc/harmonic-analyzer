"""Authoritative physical specification for every threaded fastener.

Fasteners remain ordinary, deterministic SOLIDWORKS parts.  Assembly scripts
insert and mate one seed component through the public COM API, then use native
local linear/circular component-pattern features where the hole layout repeats.
Keeping identity here prevents material, thread, head, and finish choices from
drifting between the part builder and its assembly placements.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class HeadStyle(StrEnum):
    FILLISTER = "fillister"
    HEX = "hex"
    # Integral washer + hex + turned collar/tip stack (knife-hanger stud).
    HEX_STACK = "hex-stack"
    KNURLED_THUMB = "knurled-thumb"
    ROUND = "round"
    SET_SCREW = "set-screw"
    SHOULDER = "shoulder"
    SQUARE = "square"


class DriveStyle(StrEnum):
    EXTERNAL_HEX = "external-hex"
    EXTERNAL_SQUARE = "external-square"
    KNURLED = "knurled"
    SLOT = "slot"


class Finish(StrEnum):
    BLACK = "black"
    BRASS = "brass"
    POLISHED = "polished"


@dataclass(frozen=True, slots=True)
class FastenerSpec:
    part_name: str
    thread: str
    length_mm: float
    model_diameter_mm: float
    head: HeadStyle
    drive: DriveStyle
    material: str
    finish: Finish


def _steel(
    part_name: str,
    thread: str,
    length_mm: float,
    model_diameter_mm: float,
    head: HeadStyle,
    drive: DriveStyle,
    finish: Finish = Finish.POLISHED,
) -> FastenerSpec:
    return FastenerSpec(
        part_name,
        thread,
        length_mm,
        model_diameter_mm,
        head,
        drive,
        "Plain Carbon Steel",
        finish,
    )


def _brass(
    part_name: str,
    thread: str,
    length_mm: float,
    model_diameter_mm: float,
    head: HeadStyle,
    drive: DriveStyle,
) -> FastenerSpec:
    return FastenerSpec(
        part_name,
        thread,
        length_mm,
        model_diameter_mm,
        head,
        drive,
        "Brass",
        Finish.BRASS,
    )


FASTENERS: dict[str, FastenerSpec] = {
    "bracket-screw": _steel(
        "bracket-screw", "#8-32", 12.0, 3.15, HeadStyle.FILLISTER, DriveStyle.SLOT
    ),
    "clamp-screw": _steel(
        "clamp-screw", "#8-32", 28.0, 3.15, HeadStyle.FILLISTER, DriveStyle.SLOT
    ),
    "cone-lock-knob": _steel(
        "cone-lock-knob", "1/4-20", 6.35, 6.35,
        HeadStyle.KNURLED_THUMB, DriveStyle.KNURLED,
    ),
    "cone-pivot-screw": _steel(
        "cone-pivot-screw", "#10-24", 14.60, 6.35,
        HeadStyle.SHOULDER, DriveStyle.SLOT,
    ),
    "cone-tip-adjuster": _steel(
        "cone-tip-adjuster", "5/16-18", 14.0, 6.2,
        HeadStyle.SET_SCREW, DriveStyle.SLOT, Finish.BLACK,
    ),
    "cone-tip-pinch-screw": _steel(
        "cone-tip-pinch-screw", "#3-48", 8.0, 1.7,
        HeadStyle.FILLISTER, DriveStyle.SLOT,
    ),
    "crank-retainer-screw": _brass(
        "crank-retainer-screw", "#0-80", 1.55, 1.10,
        HeadStyle.FILLISTER, DriveStyle.SLOT,
    ),
    "fillister-screw": _brass(
        "fillister-screw", "#4-40", 4.0, 2.0,
        HeadStyle.FILLISTER, DriveStyle.SLOT,
    ),
    "foot-screw": _steel(
        "foot-screw", "#4-40", 8.0, 2.0,
        HeadStyle.FILLISTER, DriveStyle.SLOT, Finish.BLACK,
    ),
    "frame-side-screw": _steel(
        "frame-side-screw", "#10-24", 12.7, 3.45,
        HeadStyle.FILLISTER, DriveStyle.SLOT,
    ),
    "gooseneck-set-screw": _steel(
        "gooseneck-set-screw", "1/4-20", 16.0, 4.7,
        HeadStyle.SQUARE, DriveStyle.EXTERNAL_SQUARE, Finish.BLACK,
    ),
    "hanger-screw": _steel(
        "hanger-screw", "#6-32", 11.5, 2.4,
        HeadStyle.HEX, DriveStyle.EXTERNAL_HEX, Finish.BLACK,
    ),
    "hex-bolt": _steel(
        "hex-bolt", "5/16-18", 32.0, 7.8,
        HeadStyle.HEX, DriveStyle.EXTERNAL_HEX, Finish.BLACK,
    ),
    "knife-hanger-stud": _steel(
        "knife-hanger-stud", "1/2-13", 48.75, 12.7,
        HeadStyle.HEX_STACK, DriveStyle.EXTERNAL_HEX,
    ),
    "lag-screw": _steel(
        "lag-screw", "9/16-12", 63.0, 12.0,
        HeadStyle.ROUND, DriveStyle.SLOT, Finish.BLACK,
    ),
    "pen-set-screw": _brass(
        "pen-set-screw", "#4-40", 15.0, 2.0,
        HeadStyle.KNURLED_THUMB, DriveStyle.KNURLED,
    ),
    "slotted-screw": _steel(
        "slotted-screw", "#8-32", 22.0, 3.15,
        HeadStyle.FILLISTER, DriveStyle.SLOT,
    ),
    "swing-stop-screw": _steel(
        "swing-stop-screw", "#8-32", 14.0, 3.15,
        HeadStyle.FILLISTER, DriveStyle.SLOT,
    ),
    # 11 (was 12): the head top must hold >= 0.25 below the one-piece
    # top-frame casting underside y 999.7 (build_magnifier_assembly tscrew).
    "thumb-screw": _brass(
        "thumb-screw", "#4-40", 11.0, 2.0,
        HeadStyle.KNURLED_THUMB, DriveStyle.KNURLED,
    ),
}


def fastener(part_name: str) -> FastenerSpec:
    """Return one fastener specification, failing loud on an unregistered part."""
    try:
        return FASTENERS[part_name]
    except KeyError as exc:
        raise KeyError(f"threaded fastener is not registered: {part_name}") from exc
