r"""Reproduction script: counter spring (book ch. 19, pp. 44-45).

The "long spring [that] towers above the machine": a heavy close-wound
extension spring from the summing-lever hook up to the curved, tapered
gooseneck post. It counterbalances the accumulated pull of the 20 channel
springs; tension is set by sliding the post (square-head screw).

No numeric dimensions are stated; everything here is photo-scaled (book
p. 45 + photogrammetry 195253322) against the ch. 6 frame anchors -- see the
M2 revision note in DIMENSIONS.md ch. 19 (the first-pass 45 x 80 mm estimate
was wrong by ~4x). End hooks deferred to the Phase 3 rebuild, as with the
channel spring.

Layout: coil axis along +Y from the origin (helix base circle on the Top
plane); the helix starts and ends on the +X side (whole number of coils).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_counter_spring.py
"""

from __future__ import annotations

import sys

from _common import (
    check,
    define_circle,
    ensure_fully_defined,
    insert_helix,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "counter-spring"

COIL_BODY_LENGTH = 300.0  # DIMENSIONS.md ch19: scaled, gooseneck rise (low)
COIL_OD = 22.0  # DIMENSIONS.md ch19: scaled vs gooseneck tube (low)
WIRE_DIA = 2.5  # DIMENSIONS.md ch19: scaled, heavy wire (low)
COIL_COUNT = 110  # close-wound: body length / ~2.73 mm pitch (derived, low)

MEAN_RADIUS = (COIL_OD - WIRE_DIA) / 2.0
PITCH = COIL_BODY_LENGTH / COIL_COUNT  # whole coils: both ends land at +X


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import SweepParameters

    check("create_part", await adapter.create_part())

    check("create_sketch helix base", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, MEAN_RADIUS, "helix base")
    await ensure_fully_defined(adapter, "helix base sketch")
    helix_name = insert_helix(adapter, COIL_BODY_LENGTH, PITCH)

    check("create_sketch wire profile", await adapter.create_sketch("Front"))
    await define_circle(adapter, MEAN_RADIUS, 0.0, WIRE_DIA / 2.0, "wire profile")
    await ensure_fully_defined(adapter, "wire profile sketch")
    check("exit_sketch wire profile", await adapter.exit_sketch())

    check(
        "sweep wire along helix",
        await adapter.create_sweep(SweepParameters(path=helix_name)),
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
