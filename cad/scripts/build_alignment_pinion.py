r"""Reproduction script: alignment pinion drum (book ch. 25).

The long brass pinion used to set the machine to sines or cosines: with
the cone set swung clear, a lever engages this drum with the cylinder
train so turning it "moves all the cylinder gears as one" (p. 66). 42
teeth (counted on the p. 67 plate), the same DP 30 / PA 14.5 deg system
as the cylinder gears it must mesh with, and a drum long enough to span
all 20 stations at once. Each end carries an integral Ø6.35 arbor stub
riding its swing bracket's top bore (build_pinion_bracket.py); the front
stub runs on through the strap to take the turning handle
(build_pinion_handle.py). The knurled end collars are simplified away.

Layout: axis Z, drum z 0..150, front stub z -9..0, back stub z 150..164.
The ch30/M6.8 model carries it in the DISENGAGED rest state (p. 68
"gap"), so no tooth-phase seed is needed.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_alignment_pinion.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    volume_check,
)
from _gear import build_fixed_gear

PART_NAME = "alignment-pinion"
MATERIAL = "Brass"  # p.67: brass drum, same finish as the cylinder train

TEETH = 42  # DIMENSIONS.md ch25: counted on the p.67 plate (high)
FACE_WIDTH = 150.0  # DIMENSIONS.md ch25: covers all 20 drum stations (derived)
STUB_DIA = 6.35  # arbor stubs riding the strap top bores (derived)
STUB_FRONT = 8.0  # through the 5 strap, seating 2 deep in the handle hub
# bore and stopping 0.43 clear of the handle's internal ball solid (derived)
STUB_BACK = 14.0  # through the 5 strap + 9 tail (photo-scaled, low)

STUB_R = STUB_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    v_gear = await build_fixed_gear(adapter, TEETH, FACE_WIDTH)

    # Front arbor stub z -9..0 (flip: offset 0, extrude -Z off the gear face).
    check("create_sketch front stub", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, STUB_R, "front stub")
    await ensure_fully_defined(adapter, "front stub sketch")
    check("exit_sketch front stub", await adapter.exit_sketch())
    extrude_at_offset(adapter, STUB_FRONT, 0.0, flip=True)
    v_front = math.pi * STUB_R**2 * STUB_FRONT
    v_gear = await volume_check(adapter, "front stub", v_gear + v_front, 0.02 * v_front)

    # Back arbor stub z 150..164.
    check("create_sketch back stub", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, STUB_R, "back stub")
    await ensure_fully_defined(adapter, "back stub sketch")
    check("exit_sketch back stub", await adapter.exit_sketch())
    extrude_at_offset(adapter, STUB_BACK, FACE_WIDTH)
    v_back = math.pi * STUB_R**2 * STUB_BACK
    await volume_check(adapter, "back stub", v_gear + v_back, 0.02 * v_back)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
