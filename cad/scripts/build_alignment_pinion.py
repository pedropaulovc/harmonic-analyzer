r"""Reproduction script: alignment pinion drum (book ch. 25).

The long brass pinion used to set the machine to sines or cosines: with
the cone set swung clear, a lever engages this drum with the cylinder
train so turning it "moves all the cylinder gears as one" (p. 66). 42
teeth (counted on the p. 67 plate), the same DP 30 / PA 14.5 deg system
as the cylinder gears it must mesh with, and a drum long enough to span
all 20 stations at once. The knurled end collars and end journals are
simplified away -- the swing straps (build_pinion_bracket.py) butt
against the plain drum end faces.

Layout: axis Z, drum z 0..150. The ch30/M6.8 model carries it in the
DISENGAGED rest state (p. 68 "gap"), so no tooth-phase seed is needed.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_alignment_pinion.py
"""

from __future__ import annotations

import sys

from _common import (
    apply_material,
    check,
    report_mass_properties,
    run_build,
    save_part_and_images,
)
from _gear import build_fixed_gear

PART_NAME = "alignment-pinion"
MATERIAL = "Brass"  # p.67: brass drum, same finish as the cylinder train

TEETH = 42  # DIMENSIONS.md ch25: counted on the p.67 plate (high)
FACE_WIDTH = 150.0  # DIMENSIONS.md ch25: spans the 20-station stack (derived)


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    await build_fixed_gear(adapter, TEETH, FACE_WIDTH)
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
