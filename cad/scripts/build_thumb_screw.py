r"""Reproduction script: reeded thumb screw (book ch. 20, p. 48).

The knurled ("reeded") thumb screw that locks the magnifying-lever clamp
block (a second identical one locks the output fixture). M4 finishing
pass: head reeded with 24 axial Ø1 mm grooves (tube-frame fluting recipe,
``_features.add_reeded_head_and_thread``) and a cosmetic M3 thread on the
shank (annotation only -- keeps M6 interference checks clean).

The stepped body is two coaxial merged extrusions (cone-gear-shaft
recipe), NOT a profile revolve: circular patterns of cuts on stepped
REVOLVED bodies fail to create (probe-verified on SW 2026 -- plain
revolved cylinders pattern fine, stepped ones never do; identical
geometry from stacked extrusions patterns fine).

Dimensions: cad/DIMENSIONS.md "Chapter 20" — photo-scaled vs the Ø6
lever rod (low); groove count/size photo-estimated (low).

Layout: screw axis along +X from the origin (head face at x=0).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_thumb_screw.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    volume_check,
)
from _features import add_reeded_head_and_thread

PART_NAME = "thumb-screw"
MATERIAL = "Brass"  # see _common.apply_material docstring

HEAD_DIA = 10.0  # DIMENSIONS.md ch20: knurled head, p.48 (low)
HEAD_LENGTH = 5.0  # DIMENSIONS.md ch20 (low)
SHANK_DIA = 3.0  # DIMENSIONS.md ch20: matches clamp screw hole (low)
SHANK_LENGTH = 12.0  # DIMENSIONS.md ch20 (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    for label, dia, length in (
        ("head", HEAD_DIA, HEAD_LENGTH),
        ("shank", SHANK_DIA, HEAD_LENGTH + SHANK_LENGTH),
    ):
        check(f"create_sketch {label}", await adapter.create_sketch("Right"))
        await define_circle(adapter, 0.0, 0.0, dia / 2.0, label)
        await ensure_fully_defined(adapter, f"{label} sketch")
        check(f"exit_sketch {label}", await adapter.exit_sketch())
        check(
            f"extrude {label}",
            await adapter.create_extrusion(ExtrusionParameters(depth=length)),
        )
    v_blank = math.pi * (
        (HEAD_DIA / 2.0) ** 2 * HEAD_LENGTH + (SHANK_DIA / 2.0) ** 2 * SHANK_LENGTH
    )
    await volume_check(adapter, "stepped blank", v_blank, 0.005 * v_blank)

    await add_reeded_head_and_thread(
        adapter, HEAD_DIA, HEAD_LENGTH, SHANK_DIA, SHANK_LENGTH, groove_count=24
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
