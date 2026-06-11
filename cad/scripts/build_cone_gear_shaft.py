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

Sections, large (pivot) end at z = 0, gear seats at the 7.5 mm stack
pitch (150 mm / 20 gears, annotated p.18). M6.6 (canted gear seats):
each step ends shy of its nominal seat boundary so the larger section's
east surface line stays out of the next CANTED gear's vertical slab
(the inclined cylinder's surface reaches r*sin(19.8) past its end
station in z, and r/cos(19.8) in plan -- both bit as real
interferences), and the tip is turned down from the photo-suggested
1/8 in: the inclined shaft line converges toward the drum as z grows,
passing only 1.30 mm outside the 120T tip circle at the last drum
gear's face -- a 1/8 in rod (r 1.59) would rub those tooth tips, the
0.08 in tip clears them by 0.22:

* 3/8 in x 150.5 -- pivot journal 25 + seats T120..T024 (shy of 152.5:
  east line out of T018's slab)
* 1/4 in x 8.1 -- T018 seat (shy of 160: east line out of T012's slab)
* 0.08 in x 66.4 -- T012/T006 region + thin-tip journal into the green
  post (T012 rides it canted with a loose 1/4 in bore; the parked
  perpendicular T006 is snug at station 178)

Dimensions: cad/DIMENSIONS.md "Chapter 12" -- base dia legacy (med),
length derived from the annotated 150 mm stack + p.18 top-down end
allowances (low), step diameters = gear bores (Appendix C #7).

Build: four coaxial Front-plane circles extruded +Z to each section's end
station with ``merge_result`` -- each smaller cylinder is contained in
its larger neighbour over the shared length, so the union is exactly the
stepped shaft (volume check is exact per section, no offset planes
needed).

Layout: shaft axis along +Z, large (pivot) end at the origin -- along
the assembly depth like the gears (`build_cone_gear.py` axis = Z), so
the drive-train assembly inclines the whole cone set with one Ry(-19.8)
rotation (DIMENSIONS.md ch. 13 drive-train layout).

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
# Sections feed build_cone_gear.bore_dia_in; end stations sit shy of the
# nominal 25 + k * 7.5 seat boundaries and the tip is 0.08 in -- M6.6
# canted-slab / drum-tip clearances, see docstring. Total 225.
SECTIONS = [
    (0.375, 150.5),  # pivot journal + seats T120..T024
    (0.25, 158.6),  # T018 seat
    (0.08, 225.0),  # T012/T006 region + thin-tip journal
]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    volume = 0.0
    prev_end = 0.0
    for dia_in, end_z in SECTIONS:
        label = f"section d{dia_in:g}in to z={end_z:g}"
        check(f"create_sketch {label}", await adapter.create_sketch("Front"))
        await define_circle(adapter, 0.0, 0.0, dia_in * IN / 2.0, label)
        await ensure_fully_defined(adapter, f"{label} sketch")
        check(f"exit_sketch {label}", await adapter.exit_sketch())
        check(
            f"extrude {label}",
            await adapter.create_extrusion(ExtrusionParameters(depth=end_z)),
        )
        volume += math.pi * (dia_in * IN / 2.0) ** 2 * (end_z - prev_end)
        await volume_check(adapter, label, volume, 0.005 * volume)
        prev_end = end_z

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
