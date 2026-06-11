r"""Reproduction script: channel spring (book ch. 17, pp. 38-41).

One of the 20 helical extension springs that couple each top lever to the
summing lever. The p. 41 inset photo carries the chapter's only dimension
callout -- 32 mm spanning the coiled body (resolving the "free length or
coil OD" ambiguity logged in DIMENSIONS.md). Wire diameter, coil OD and
coil count are scaled from the same inset (close-wound, coils just
distinguishable).

M4 (Phase 3 landed): bent-wire end hooks per the p. 41 inset -- each is an
axial lead + 270-degree loop at the coil mean radius, swept in the Front
plane (see ``_common.add_spring_end_hooks``). The top hook's wire profile
sits on an offset reference plane at the coil's far end.

M6.4: this script builds the FREE spring (32 body, as photographed on the
table). In the machine the springs are visibly stretched ~2x (p. 40-41:
open coils between lever tab and summing-lever plate); the installed
geometry is a separate part -- see build_channel_spring_installed.py,
which reuses :func:`build_spring` with the stretched body length.

Dimensions: cad/DIMENSIONS.md "Chapter 17".

Layout: coil axis along +Y from the origin (helix base circle on the Top
plane); the helix starts and ends on the +X side (whole number of coils).
Hook eye centres land at y = -HOOK_LEAD and y = body + HOOK_LEAD.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_channel_spring.py
"""

from __future__ import annotations

import sys

from _common import (
    add_spring_end_hooks,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    insert_helix,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "channel-spring"
MATERIAL = "Alloy Steel"  # see _common.apply_material docstring

COIL_BODY_LENGTH = 32.0  # DIMENSIONS.md ch17: p.41 inset callout (high)
COIL_OD = 6.5  # DIMENSIONS.md ch17: scaled from p.41 inset (low)
WIRE_DIA = 1.0  # DIMENSIONS.md ch17: scaled from p.41 inset (low)
COIL_COUNT = 28  # close-wound: body length / ~1.14 mm pitch (derived, low)

MEAN_RADIUS = (COIL_OD - WIRE_DIA) / 2.0
HOOK_LEAD = 2.0 * WIRE_DIA  # _common.add_spring_end_hooks default
EYE_C2C = COIL_BODY_LENGTH + 2.0 * HOOK_LEAD  # hook eye centres, 36.0 free


async def build_spring(adapter, part_name: str, body_length: float) -> dict[str, str]:
    """Build a channel spring with the given coil body length (mm)."""
    from solidworks_mcp.adapters.base import SweepParameters

    pitch = body_length / COIL_COUNT  # whole coils: both ends land at +X

    check("create_part", await adapter.create_part())

    # Helix path from a base circle on the Top plane (consumed while open).
    check("create_sketch helix base", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, MEAN_RADIUS, "helix base")
    await ensure_fully_defined(adapter, "helix base sketch")
    helix_name = insert_helix(adapter, body_length, pitch)

    # Wire cross-section at the helix start point (+X side).
    check("create_sketch wire profile", await adapter.create_sketch("Front"))
    await define_circle(adapter, MEAN_RADIUS, 0.0, WIRE_DIA / 2.0, "wire profile")
    await ensure_fully_defined(adapter, "wire profile sketch")
    check("exit_sketch wire profile", await adapter.exit_sketch())

    check(
        "sweep wire along helix",
        await adapter.create_sweep(SweepParameters(path=helix_name)),
    )

    await add_spring_end_hooks(adapter, MEAN_RADIUS, WIRE_DIA, body_length)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, part_name)


async def build(adapter) -> dict[str, str]:
    return await build_spring(adapter, PART_NAME, COIL_BODY_LENGTH)


if __name__ == "__main__":
    sys.exit(run_build(build))
