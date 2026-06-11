r"""Reproduction script: cone gear shaft (book ch. 12, pp. 16-21) -- stepped.

Steel shaft carrying the 20-gear cone set (all gears fixed to and
rotating with the shaft), with bearing journals into the pivot block
(large end -- the cone set pivots out of engagement, ch. 25) and the
green post (thin end). At DP 30 the small gears cannot clear a 3/8 in
shaft (the 6T gear's OD is 6.77 mm), so the shaft steps down at the
thin end to match the configured gear bores (`build_cone_gear.py`
``BoreDia``, DIMENSIONS.md Appendix C #7): the p.18 photos visibly
show a thin rod past the smallest gears. Gears attach by means the
book never shows (p.21 macro shows solder blobs at the small gears) --
no keyseat, the shaft steps are plain. The "150 mm" stack annotation
reconciles as gear stack 131.6 + 64T face + air (M6.7 exact-tracking
pitch, see DIMENSIONS.md ch. 12 notes).

Sections, large (pivot) end at z = 0. M6.7 (true-cone mesh, see the
assembly docstring): gear seats at the exact-tracking stack pitch
6.584 mm (= drum z-pitch x cos 21.1 deg), seat centres at
28.25 + 6.584 j, gear faces 6.5 -- each step lands in the 0.08 mm air
gap between adjacent gear faces:

* 3/8 in x 136.88 -- pivot journal 25 (64T at stations 14.9..24.9) +
  seats T120..T024
* 1/4 in x 6.59 -- T018 seat
* 3/16 in x 6.58 -- T012 seat
* 1/8 in x 39.95 -- T006 seat + thin-tip journal into the green post
  (the M6.7 shaft line passes 0.39 clear of the last drum gear's tooth
  tips, so the photo-true 1/8 in tip needs no narrowing)

Dimensions: cad/DIMENSIONS.md "Chapter 12" -- base dia legacy (med),
length 190 = pivot journal + stack + thin-tip journal through the knob
post at station 177 (derived, low), step diameters = gear bores
(Appendix C #7).

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

PIVOT_JOURNAL = 25.0  # mm, large-end journal into the pivot block (low)

# (diameter in inches, section end station in mm from the pivot end).
# M6.7 exact-tracking seat pitch 6.58390 (= 7.0568 drum z-pitch x
# cos 21.0976 deg): seat j spans 28.25 + 6.5839 j +- 3.25; each step
# station sits in the 0.08 air gap between faces (T024 north face
# 136.84 | 136.88 | T018 south face 136.93, and so on). Diameters
# mirror build_cone_gear.bore_dia_in (snug perpendicular seats).
SECTIONS = [
    (0.375, 136.88),  # pivot journal + 64T seat + T120..T024
    (0.25, 143.47),  # T018 seat
    (0.1875, 150.05),  # T012 seat
    (0.125, 190.0),  # T006 seat + thin-tip journal (knob post at 177)
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
