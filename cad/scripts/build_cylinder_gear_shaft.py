r"""Reproduction script: cylinder gear arbor (book ch. 13, pp. 22-25).

Plain Ø3/8 in steel STATIONARY arbor carrying the 20 identical cylinder
gears with their integral eccentric cams (~134 mm stack at 7.06 mm
Z-pitch, alternating with the black connecting rods that ride the cams).
No keyseat: gear k turns k/80 rev per crank turn (ch. 29 gear law), so
the 20 gears all spin at DIFFERENT speeds and cannot be keyed to a
common shaft -- they run free on this fixed arbor (DIMENSIONS.md ch. 13,
"M6.2 keyway refutation"; the legacy keyseat was fiction, removed in
M6.2). The arbor is clamped in the pedestal supports at both ends.

Dimensions: cad/DIMENSIONS.md "Chapter 13" - dia legacy (med), length
derived from the stack + eight-views 8/8 pedestals (low).

Layout: arbor axis along +Y from the origin, plain cylinder y 0..200.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_cylinder_gear_shaft.py
"""

from __future__ import annotations

import sys

from _common import (
    IN,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    name_bore_axis,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
)

PART_NAME = "cylinder-gear-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

SHAFT_DIA = 0.375 * IN  # ch13: = cam bore (legacy parameters.kcl)
SHAFT_LENGTH = 200.0  # ch13: 134 stack + journal/clamp each end (derived)

SHAFT_RADIUS = SHAFT_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    check("create_sketch shaft", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, SHAFT_RADIUS, "shaft circle")
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LENGTH)),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after shaft: {res.data.volume:.1f} mm^3")
    # expected: pi * 4.7625^2 * 200 = ~14,251 mm^3

    # Named central axis (arbor axis along +Y through the origin) so the
    # cylinder gears ride it coincident axis-to-axis in the assembly.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
