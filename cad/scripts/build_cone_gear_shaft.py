r"""Reproduction script: cone gear shaft (book ch. 12, pp. 16-21) -- stepped.

Steel shaft carrying the 20-gear cone set (150 mm annotated stack, all
gears fixed to and rotating with the shaft), with bearing journals into
the pivot block (large end -- the cone set pivots out of engagement,
ch. 25) and the green post (thin end). At DP 30 the small gears cannot
clear a 3/8 in shaft (the 6T gear's OD is 6.77 mm), so the shaft steps
down at the thin end to match the configured gear bores
(`build_cone_gear.py` ``BoreDia``, DIMENSIONS.md Appendix C #7): the
p.18 photos visibly show a thin rod past the smallest gears. Gears
attach by means the book never shows (p.21 macro shows solder blobs at
the small gears) -- no keyseat, the shaft steps are plain.

Sections, large (pivot) end at y = 0, gear seats at the 7.5 mm stack
pitch (150 mm / 20 gears, annotated p.18):

* 3/8 in x 152.5 -- pivot journal 25 + 17 seats (T120..T024)
* 1/4 in x 7.5 -- T018 seat
* 3/16 in x 7.5 -- T012 seat
* 1/8 in x 57.5 -- T006 seat + thin-tip journal into the green post

Dimensions: cad/DIMENSIONS.md "Chapter 12" -- base dia legacy (med),
length derived from the annotated 150 mm stack + p.18 top-down end
allowances (low), step diameters = gear bores (Appendix C #7).

Build: four coaxial Top-plane circles extruded +Y to each section's end
station with ``merge_result`` -- each smaller cylinder is contained in
its larger neighbour over the shared length, so the union is exactly the
stepped shaft (volume check is exact per section, no offset planes
needed).

Layout: shaft axis along +Y, large (pivot) end at the origin.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_cone_gear_shaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)
from _gear import volume_check

PART_NAME = "cone-gear-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

SEAT_PITCH = 7.5  # mm, 150 stack / 20 gears (annotated p.18)
PIVOT_JOURNAL = 25.0  # mm, large-end journal into the pivot block (low)

# (diameter in inches, section end station in mm from the pivot end).
# Diameters mirror build_cone_gear.bore_dia_in; stations accumulate
# 25 pivot journal + 17/1/1/1 seats + 50 thin-tip journal = 225 total.
SECTIONS = [
    (0.375, PIVOT_JOURNAL + 17 * SEAT_PITCH),  # 152.5: pivot + T120..T024
    (0.25, PIVOT_JOURNAL + 18 * SEAT_PITCH),  # 160.0: T018 seat
    (0.1875, PIVOT_JOURNAL + 19 * SEAT_PITCH),  # 167.5: T012 seat
    (0.125, 225.0),  # T006 seat + 50 thin-tip journal
]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    volume = 0.0
    prev_end = 0.0
    for dia_in, end_y in SECTIONS:
        label = f"section d{dia_in:g}in to y={end_y:g}"
        check(f"create_sketch {label}", await adapter.create_sketch("Top"))
        await define_circle(adapter, 0.0, 0.0, dia_in * IN / 2.0, label)
        await ensure_fully_defined(adapter, f"{label} sketch")
        check(f"exit_sketch {label}", await adapter.exit_sketch())
        check(
            f"extrude {label}",
            await adapter.create_extrusion(ExtrusionParameters(depth=end_y)),
        )
        volume += math.pi * (dia_in * IN / 2.0) ** 2 * (end_y - prev_end)
        await volume_check(adapter, label, volume, 0.005 * volume)
        prev_end = end_y

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
