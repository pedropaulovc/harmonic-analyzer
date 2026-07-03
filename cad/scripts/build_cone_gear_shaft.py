r"""Reproduction script: cone gear shaft (book ch. 12, pp. 16-21) -- stepped.

Steel shaft carrying the 20-gear cone set (all gears fixed to and
rotating with the shaft), with bearing journals into the pivot block
(large end -- the cone set pivots out of engagement, ch. 25) and the
green post (thin end). At the finer module DP 49.82 (ch13 OD 62.2) the
tip gears are tiny -- T006 OD is 4.08 mm -- so the shaft steps down far
more at the thin end to match the configured gear bores AND stay inside
each gear's root circle (`build_cone_gear.py` ``BoreDia``, DIMENSIONS.md
Appendix C #7). Gears attach by means the book never shows (p.21 macro
shows solder blobs at the small gears) -- no keyseat, the shaft steps are
plain; the four yellow tip gears (T006..T024) are a harder high-zinc
yellow metal soldered on.

Sections, FRONT STUB end at z = 0 (ch30 GT: the big end runs 35.8 past
the old pivot-end origin, through the swing post journal, ending in the
boss the photos show at machine z -123 -- see FRONT_STUB). M6.7
(true-cone mesh, see the assembly docstring): gear seats at the
exact-tracking stack pitch 6.8889 mm (= drum z-pitch 7.0565 x
cos 12.52 deg), seat centres at FRONT_STUB + 28.25 + 6.8889 j, gear
faces 6.5 -- each step lands in the ~0.39 mm air gap between adjacent
gear faces (stations below quoted from the legacy pivot end):

* 3/8 in x 141.9 -- pivot journal 25 (64T at stations 14.9..24.9) +
  seats T120..T024
* 1/4 in x 148.8 -- T018 seat
* 1/8 in x 155.7 -- T012 seat
* 1/32 in x 190.0 -- T006 seat + thin-tip journal into the green post.
  WARNING: a 0.79 mm x ~34 mm steel tip journal is mechanically
  marginal (it follows from the 62.2 OD anchor, low confidence) --
  flagged for Phase 3 rebuild validation; a real builder would more
  likely keep the tip gears larger (i.e. the 62.2 reading may be low).

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

    uv run python cad\scripts\build_cone_gear_shaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    SketchDims,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
)
from _gear import volume_check

PART_NAME = "cone-gear-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

PIVOT_JOURNAL = 25.0  # mm, large-end journal into the pivot block (low)

FRONT_STUB = 35.8  # ch30 GT (2026-07-02): the 3/8" big end runs ON past the old
# pivot-end origin, through the nested swing-journal block and out the crank
# pedestal's front wall window, ending in the boss the photos show proud of
# the pedestal's curved flank (GT cone_front world (-127, 101, -123); the stub
# end lands at machine z -123.0).
# The part origin is now this FRONT END; the old pivot-end stations below are
# all shifted by FRONT_STUB, and the assembly places the shaft at
# cone_station(-35.8) (build_drive_train_assembly SHAFT_FRONT_STATION).

# (diameter in inches, section end station in mm from the FRONT STUB end;
# comments quote the legacy pivot-end stations). M6.7 exact-tracking seat
# pitch 6.8889 (= 7.0565 drum z-pitch x cos 12.5188 deg, the shallower
# incline at DP 49.82): seat j spans 28.25 + 6.8889 j +- 3.25 from the pivot
# end; each step station sits in the ~0.39 air gap between faces (T024 north
# 141.72 | 141.9 | T018 south 142.11, and so on). Diameters mirror
# build_cone_gear.bore_dia_in (snug perpendicular seats), stepping much finer
# than the old DP 30 shaft because the tip gears shrank: T006 OD is now
# 4.08 mm. WARNING the 1/32" (0.79 mm) tip journal is mechanically marginal --
# it follows from the 62.2 OD anchor (ch13, low confidence) and is flagged
# for Phase 3 rebuild validation.
SECTIONS = [
    (0.375, FRONT_STUB + 141.9),  # front stub + pivot journal + 64T + T120..T024
    (0.25, FRONT_STUB + 148.8),  # T018 seat
    (0.125, FRONT_STUB + 155.7),  # T012 seat
    (0.03125, FRONT_STUB + 190.0),  # T006 seat + thin-tip journal
]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): one diameter + one end station per
    # section. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units. The section diameters
    # come from SECTIONS in inches (converted to mm here so a single global drives
    # the on-axis circle's diameter dim). The end stations are extrude DEPTHS
    # (feature parameters, not sketch dims), so nothing drives them; they stay
    # editable knobs matching the exemplars.
    for i, (dia_in, end_z) in enumerate(SECTIONS):
        await set_global(adapter, f"SecDia{i}", f"{dia_in * IN}mm")
        await set_global(adapter, f"SecEnd{i}", f"{end_z}mm")

    drive_jobs: list[tuple[str, str]] = []

    volume = 0.0
    prev_end = 0.0
    for i, (dia_in, end_z) in enumerate(SECTIONS):
        label = f"section d{dia_in:g}in to z={end_z:g}"
        # On-axis circle (centre at the origin): define_circle records ONLY the
        # diameter dim (the X/Z centre slots are relations, not display dims).
        sec = SketchDims()
        check(f"create_sketch {label}", await adapter.create_sketch("Front"))
        await define_circle(
            adapter, 0.0, 0.0, dia_in * IN / 2.0, label, dims=sec,
            names=(f"Sec{i}Cx", f"Sec{i}Cz", f"Sec{i}Dia"),
            drives=(None, None, f'"SecDia{i}"'),
        )
        await ensure_fully_defined(adapter, f"{label} sketch")
        check(f"exit_sketch {label}", await adapter.exit_sketch())
        name_last_feature(adapter, f"Sec{i}Profile")
        drive_jobs += sec.apply(adapter, f"Sec{i}Profile")
        check(
            f"extrude {label}",
            await adapter.create_extrusion(ExtrusionParameters(depth=end_z)),
        )
        name_last_feature(adapter, f"Sec{i}")
        volume += math.pi * (dia_in * IN / 2.0) ** 2 * (end_z - prev_end)
        await volume_check(adapter, label, volume, 0.005 * volume)
        prev_end = end_z

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven cone-gear shaft (equations neutral)", volume, 0.005 * volume)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
