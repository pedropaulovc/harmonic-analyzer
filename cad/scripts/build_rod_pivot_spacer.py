"""Native annular fitted rod-pivot spacer, axis Z, Z=0..length."""

from __future__ import annotations

import math
import sys

from _common import (
    apply_material, check, define_circle, ensure_fully_defined, force_rebuild,
    name_dimensions, name_last_feature, run_build, save_part_and_images, volume_check,
)
import rod_pivot_spec as pivot

PART_NAME = "rod-pivot-spacer"
MATERIAL = "Brass"


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create pivot spacer", await adapter.create_part())
    check("sketch spacer", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, pivot.SPACER_OD / 2.0, "spacer outside")
    await define_circle(adapter, 0.0, 0.0, pivot.SPACER_ID / 2.0, "spacer bore")
    await ensure_fully_defined(adapter, "spacer profile")
    check("exit spacer", await adapter.exit_sketch())
    name_last_feature(adapter, "SpacerProfile")
    check("extrude spacer", await adapter.create_extrusion(ExtrusionParameters(depth=pivot.SPACER_LENGTH)))
    name_last_feature(adapter, "Spacer")
    name_dimensions(adapter, "Spacer", ["Length"])
    await force_rebuild(adapter)
    volume = math.pi / 4.0 * (pivot.SPACER_OD**2 - pivot.SPACER_ID**2) * pivot.SPACER_LENGTH
    await volume_check(adapter, "fitted pivot spacer", volume, 0.002 * volume)
    await apply_material(adapter, MATERIAL)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
