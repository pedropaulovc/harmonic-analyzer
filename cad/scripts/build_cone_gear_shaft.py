r"""Reproduction script: cone gear shaft (book ch. 12, pp. 16-21) -- stepped.

Steel shaft carrying the 20-gear cone set (all gears fixed to and
rotating with the shaft), with its large-end bearing journal in the green
pivot post and its thin end located by the external spacer and cup-ended
adjuster -- the post and adjuster carrier both stand on the swing platform,
so the whole set pivots out of engagement as one
unit (ch. 25; p. 18 "pivot"). At the finer module DP 49.82 (ch13 OD 62.2) the
tip gears are tiny -- T006 OD is 4.08 mm -- so the shaft steps down far
more at the thin end to match the configured gear bores AND stay inside
each gear's root circle (`build_cone_gear.py` ``BoreDia``, DIMENSIONS.md
Appendix C #7). Gears attach by means the book never shows (p.21 macro
shows solder blobs at the small gears) -- no keyseat, the shaft steps are
plain; the four yellow tip gears (T006..T024) are a harder high-zinc
yellow metal soldered on.

Sections, FRONT STUB end at z = 0.  The v2 post puts that end at cone
station -61.9068609979, 1.0 mm proud of the post front face.  An integral
Ø12.2308 journal runs to z = 43.011 in the post's Ø12.2808 bore, then
steps to the existing 3/8 in gear-seat shaft. M6.7
(true-cone mesh, see the assembly docstring): gear seats at the
exact-tracking stack pitch 6.8889 mm (= drum z-pitch 7.0565 x
cos 12.52 deg), seat centres at FRONT_STUB + 28.25 + 6.8889 j, gear
faces 6.5 -- each step lands in the ~0.39 mm air gap between adjacent
gear faces (stations below quoted from the legacy pivot end):

* 12.2308 mm x 43.011 -- v2 pivot-post bearing journal, 0.05 diametral
  running clearance
* 3/8 in x 141.9 -- 64T at stations 14.9..24.9 + seats T120..T024
* 1/4 in x 148.8 -- T018 seat
* 1/8 in x 155.7 -- T012 seat
* 1/32 in x 146.2723 -- shortened T006 tip journal reaching the adjuster cup.
  WARNING: a 0.79 mm x ~34 mm steel tip journal is mechanically
  marginal (it follows from the 62.2 OD anchor, low confidence) --
  flagged for Phase 3 rebuild validation; a real builder would more
  likely keep the tip gears larger (i.e. the 62.2 reading may be low).

Dimensions: cad/DIMENSIONS.md "Chapter 12" -- the journal comes from the
manually rederived v2 post bore and its 42.011 axial body; the gear-seat
stations and diameters remain the legacy/derived stack (Appendix C #7).

Build: five coaxial Front-plane circles extruded +Z to each section's end
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
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _gear import volume_check
from cone_gear_shaft_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    SECTIONS,
)

PART_NAME = "cone-gear-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# FRONT_STUB = 61.9068609979: with the final coupled-layout post centred at
# cone station -39.90136099793 and spanning 42.011 along that axis, the shaft begins 1.0 mm
# proud of the front face.  The Ø12.2308 integral journal occupies local
# 0..43.011 in the post's Ø12.2808 bore; downstream 3/8-in and smaller gear
# seats retain their world stations because every old local end receives the
# 49.6068609979 stub delta.

# SECTIONS (diameter in inches, section end station in mm from the FRONT STUB
# end) now lives in cone_gear_shaft_spec.py -- the pure-data contract the
# drawing shares -- and is imported above; the derivation stays here. M6.7
# exact-tracking seat pitch 6.8889 (= 7.0565 drum z-pitch x cos 12.5188 deg,
# the shallower incline at DP 49.82): seat j spans 28.25 + 6.8889 j +- 3.25
# from the pivot end; each step station sits in the ~0.39 air gap between
# faces (T024 north 141.72 | 141.9 | T018 south 142.11, and so on). Diameters
# mirror build_cone_gear.bore_dia_in (snug perpendicular seats), stepping much
# finer than the old DP 30 shaft because the tip gears shrank: T006 OD is now
# 4.08 mm. WARNING the 1/32" (0.79 mm) tip journal is mechanically marginal --
# it follows from the 62.2 OD anchor (ch13, low confidence) and is flagged
# for Phase 3 rebuild validation.


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): one diameter + one end station per
    # section. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units. The section diameters
    # come from SECTIONS in inches (the first is the metric v2 journal converted
    # to inches by the pure-data spec). The end stations are extrude DEPTHS
    # (feature parameters); each is named Sec{i}End and driven by its SecEnd{i}
    # global below, so the knobs really reshape the shaft AND the stations are
    # markable manufacturing dimensions for the drawing.
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
            adapter,
            0.0,
            0.0,
            dia_in * IN / 2.0,
            label,
            dims=sec,
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
        depth_dim = name_dimensions(adapter, f"Sec{i}", [f"Sec{i}End"])
        drive_jobs += [(depth_dim[0], f'"SecEnd{i}"')]
        volume += math.pi * (dia_in * IN / 2.0) ** 2 * (end_z - prev_end)
        await volume_check(adapter, label, volume, 0.005 * volume)
        prev_end = end_z

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven cone-gear shaft (equations neutral)", volume, 0.005 * volume
    )

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
