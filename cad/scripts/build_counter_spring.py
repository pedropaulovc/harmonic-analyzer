r"""Reproduction script: counter spring (book ch. 19, pp. 44-45).

The "long spring [that] towers above the machine": a slender close-wound
extension spring from the summing-lever boss hook up to the curved, tapered
gooseneck post. It counterbalances the accumulated pull of the 20 channel
springs; tension is set by sliding the post (square-head screw).

M6.4 revision: the M2 "300 x O22, wire 2.5" read came from the cut-off p1
front page (the spring exits the page top). Recalibrated against the ch. 19
full-machine photo (gooseneck scale 0.515 px/mm, top ~ y 1438) and the p3
90-degree page: body ~315 long, OD ~12.5, wire ~1.8, visibly close-wound
(dark, no light through the coils). The bottom wire is a LONG straight drop
(40 mm) from the coil to the ring that hangs on the summing-lever boss
J-hook (build_boss_hook.py, rod along X at (95, 1015)); the top hook hangs
on the X-pin under the gooseneck tip lug at (95, 1373). Both loops lie in
the YZ plane after the assembly's 90-degree Y-rotation, so each encircles
its X-rod nail-through-ring style (the p.43 black hook + chrome ring chain
collapsed to loop-on-hook -- simplification). See DIMENSIONS.md ch. 19.

Layout: coil axis along +Y from the origin (helix base circle on the Top
plane); the helix starts and ends on the +X side (whole number of coils).
In the machine the origin lands at (95, 1052, 0): bottom ring centre at
y 1012, top loop centre at y 1370.6.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_counter_spring.py
"""

from __future__ import annotations

import sys

from _common import (
    SPRING_BLACK,
    apply_color,
    apply_material,
    blank_sketch,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)
from _features import (
    add_spring_end_hooks,
    insert_helix,
)

PART_NAME = "counter-spring"
MATERIAL = "Alloy Steel"  # see _common.apply_material docstring

COIL_BODY_LENGTH = 315.0  # DIMENSIONS.md ch19: ch.19 photo, gooseneck-scaled (low)
COIL_OD = 12.5  # DIMENSIONS.md ch19: scaled vs gooseneck tube O16 (low)
WIRE_DIA = 1.8  # DIMENSIONS.md ch19: close-wound dark coil (low)
COIL_COUNT = 165  # close-wound: pitch 1.91 leaves a 0.11 sweep-merge gap (derived)
BOTTOM_LEAD = 40.0  # straight drop, coil bottom -> boss-hook ring centre
# (body bottom y 1052 - ring centre y 1012; see build_summing_assembly.py)
TOP_LEAD = 2.0 * WIRE_DIA  # standard short hook onto the gooseneck tip pin

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

    await add_spring_end_hooks(
        adapter,
        MEAN_RADIUS,
        WIRE_DIA,
        COIL_BODY_LENGTH,
        leads=(BOTTOM_LEAD, TOP_LEAD),
    )

    # Helix base sketch stays unabsorbed-and-shown after InsertHelix (see
    # _spring.build_spring) — blank it so it doesn't render in assemblies.
    blank_sketch(adapter, "Sketch1")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, SPRING_BLACK)  # ch30 plates: see _common palette
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
