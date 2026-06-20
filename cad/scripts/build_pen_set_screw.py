r"""Reproduction script: pen set screw (book ch. 24, pp. 64-65).

The small screw with the black knurled knob that threads up through the
pen frame's bottom rail to set the pen-to-paper angle. M4 finishing pass:
knob reeded with 22 axial Ø1 mm grooves (tube-frame fluting recipe,
``_features.add_reeded_head_and_thread``) and a cosmetic M3 thread on the
shank (annotation only -- keeps M6 interference checks clean).

The stepped body is two coaxial merged extrusions, NOT a profile revolve:
circular patterns of cuts on stepped REVOLVED bodies fail to create (see
``build_thumb_screw.py``).

Dimensions: cad/DIMENSIONS.md "Chapter 24" — photo-scaled (low); groove
count/size photo-estimated (low).

Layout: axis along +X from the knob face at x=0.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pen_set_screw.py
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

PART_NAME = "pen-set-screw"
MATERIAL = "Brass"  # see _common.apply_material docstring

KNOB_DIA = 9.0  # DIMENSIONS.md ch24: black knurled knob (low)
KNOB_LENGTH = 5.0
SHANK_DIA = 3.0  # threads into the pen frame's Ø3 hole
SHANK_LENGTH = 15.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    for label, dia, length in (
        ("knob", KNOB_DIA, KNOB_LENGTH),
        ("shank", SHANK_DIA, KNOB_LENGTH + SHANK_LENGTH),
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
        (KNOB_DIA / 2.0) ** 2 * KNOB_LENGTH + (SHANK_DIA / 2.0) ** 2 * SHANK_LENGTH
    )
    await volume_check(adapter, "stepped blank", v_blank, 0.005 * v_blank)

    await add_reeded_head_and_thread(
        adapter, KNOB_DIA, KNOB_LENGTH, SHANK_DIA, SHANK_LENGTH, groove_count=22
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
