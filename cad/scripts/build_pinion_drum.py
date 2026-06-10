r"""Reproduction script: pinion gear drum (book ch. 25, pp. 66-69).

A single long toothed drum (42 teeth, ~150 mm) that meshes the whole cylinder
gear set at once -- engaged via a small ball-handle lever during setup to turn
all 20 cylinder gears together and align their 3 mm notches (top = cosine,
rotated 90 deg = sine).

Same gear system as the cone/cylinder sets (DP 30, PA 14.5 deg -- the tip-
radius ratio to the meshing 120T cylinder gear confirms the common DP); the
tooth ring reuses the cone gear's live-validated equation-curve technique at
fixed N = 42 (literal numeric expressions, document units = inches, radians).

No bore/mounting is modeled: the book gives no bore data and the drum mounts
through the setup-lever pivot hardware, which is authored with the other
Phase-3-dependent parts (plan M4d) -- same deferral pattern as the cone-gear
stepped shaft (DIMENSIONS.md Appendix C #7).

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Layout: drum axis = Z through the origin, drum z = 0..150 mm.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinion_drum.py
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

PART_NAME = "pinion-drum"
MATERIAL = "Brass"  # ch. 25 photos: brass drum

TEETH = 42  # DIMENSIONS.md ch25: counted, frame v4_pinion_018 (high)
DRUM_LENGTH = 150.0  # mm, ch25: spans the 20 x 7.5 mm cylinder stack (med)


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    await build_fixed_gear(adapter, TEETH, DRUM_LENGTH)
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
