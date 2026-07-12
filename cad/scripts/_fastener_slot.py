"""Shared native driver-slot geometry for slotted fastener heads."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any

from _common import (
    SketchDims,
    check,
    define_centered_rectangle,
    ensure_fully_defined,
    name_last_feature,
    volume_check,
)


class FastenerAxis(StrEnum):
    Y = "y"
    Z = "z"


def slot_strip_area(radius_mm: float, width_mm: float) -> float:
    """Area of a centred width-``w`` strip clipped by a radius-``r`` circle."""
    half = width_mm / 2.0
    if not 0.0 < half < radius_mm:
        raise ValueError("slot width must be positive and smaller than head diameter")
    return 2.0 * (
        half * math.sqrt(radius_mm**2 - half**2)
        + radius_mm**2 * math.asin(half / radius_mm)
    )


async def add_slotted_drive(
    adapter: Any,
    *,
    axis: FastenerAxis,
    head_radius_mm: float,
    head_face_offset_mm: float,
    width_mm: float,
    depth_mm: float,
    expected_volume_mm3: float,
) -> tuple[float, list[tuple[str, str]]]:
    """Cut a native straight driver slot from the fastener's outer head face."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    base_plane = "Top Plane" if axis is FastenerAxis.Y else "Front Plane"
    check(
        "create_plane DriverFace",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane=base_plane,
                offset=head_face_offset_mm,
            )
        ),
    )
    name_last_feature(adapter, "DriverFace")

    slot = SketchDims()
    check("create_sketch driver slot", await adapter.create_sketch("DriverFace"))
    await define_centered_rectangle(
        adapter,
        head_radius_mm + 0.5,
        width_mm / 2.0,
        "driver slot",
        dims=slot,
        name_width="SlotLen",
        drive_width=None,
        name_depth="SlotWidth",
        drive_depth=None,
        name_corner=("SlotCx", "SlotCz"),
        drive_corner=(None, None),
    )
    await ensure_fully_defined(adapter, "driver slot sketch")
    check("exit_sketch driver slot", await adapter.exit_sketch())
    name_last_feature(adapter, "DriverSlotProfile")
    drive_jobs = slot.apply(adapter, "DriverSlotProfile")

    # FeatureCut4 cuts opposite the sketch normal by default. A head face on
    # the negative side of its principal plane has material toward +axis.
    reverse = head_face_offset_mm < 0.0
    check(
        "cut slotted drive",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=depth_mm, reverse_direction=reverse)
        ),
    )
    name_last_feature(adapter, "DriverSlot")
    removed = slot_strip_area(head_radius_mm, width_mm) * depth_mm
    remaining = expected_volume_mm3 - removed
    await volume_check(adapter, "slotted driver", remaining, max(0.05 * removed, 0.1))
    return remaining, drive_jobs
