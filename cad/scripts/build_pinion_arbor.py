r"""Reproduction script: alignment-pinion arbor (book ch. 25; PR7).

The steel shaft the brass zeroing drum presses onto (review item 14:
only the GEAR is brass -- the arbor is plain carbon steel, and thicker
than the old integral Ø6.35 stubs: Ø8, back-derived from the tee
handle's tubular cap hub OD ~10.5 in ``page002_img07``). It rides the
swing brackets' Ø8 top bores, runs south through the front strap to
seat inside the handle's blind cap (machine z -135), and north to the
free end proud behind the back strap (GT pinion_back +91.25), crowned
like the other rod ends (PR7 item 13).

Layout: axis Z, z 0..226.25 (machine -135..+91.25 at the assembly's
insert z0); crowned cap on the BACK end only (the front end hides
inside the handle cap).

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_arbor.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _part_pmi import author_part_pmi
from pinion_arbor_spec import (
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    SHAFT_DIA,
    SHAFT_LEN,
)

PART_NAME = "pinion-arbor"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.67; item 14)

# SHAFT_DIA 8.0: thicker than the retired Ø6.35 stubs -- the handle's cap
# hub (OD 10.5) implies ~8 (img07); build_alignment_pinion BORE_DIA,
# build_pinion_handle TUBE_ID and the strap ArborBore must match.
# SHAFT_LEN 226.25: machine -135 (the flat front tip seats flush ON the
# handle cap's bore floor: HANDLE_Z -144 + 9 = -135) .. +91.25 (GT
# pinion_back free end).
# CAP_SAG 1.2: back-end crown (item 13).
# Nominals live in pinion_arbor_spec.py, shared with the drawing recipe.

SHAFT_R = SHAFT_DIA / 2.0
CAP_R = (SHAFT_R**2 + CAP_SAG**2) / (2.0 * CAP_SAG)  # 7.27
V_CAP = math.pi * CAP_SAG**2 * (3.0 * CAP_R - CAP_SAG) / 3.0  # 31.1
V_SHAFT = math.pi * SHAFT_R**2 * SHAFT_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLen", f"{SHAFT_LEN}mm")
    await set_global(adapter, "CapSag", f"{CAP_SAG}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Shaft along +Z: on-axis circle (origin centre), only the diameter dim.
    shaft = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, SHAFT_R, "shaft", dims=shaft,
        names=("ShaftCx", "ShaftCz", "ShaftDia"),
        drives=(None, None, '"ShaftDia"'),
    )
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs += shaft.apply(adapter, "ShaftProfile")
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LEN)),
    )
    name_last_feature(adapter, "Shaft")
    depth_dim = name_dimensions(adapter, "Shaft", ["Depth"])
    drive_jobs += [(depth_dim[0], '"ShaftLen"')]
    volume = await volume_check(adapter, "shaft", V_SHAFT, 0.005 * V_SHAFT)

    # Back-end crown (the pivot-shaft cap idiom; apex -> rim is the minor CCW
    # lobe at a +Z end).
    v_base, v_apex = -SHAFT_LEN, -(SHAFT_LEN + CAP_SAG)
    v_centre = -(SHAFT_LEN + CAP_SAG - CAP_R)
    cap = SketchDims()
    check("create_sketch back cap", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    check("back cap centerline", await adapter.add_centerline(0.0, v_base, 0.0, v_apex))
    base = check("back cap base", await adapter.add_line(0.0, v_base, SHAFT_R, v_base))
    arc = check(
        "back cap arc",
        await adapter.add_arc(0.0, v_centre, 0.0, v_apex, SHAFT_R, v_base),
    )
    close = check("back cap close", await adapter.add_line(0.0, v_apex, 0.0, v_base))
    set_sketch_direct_db(adapter, False)
    check("back cap base horizontal", await adapter.add_sketch_constraint(base, None, "horizontal"))
    check("back cap close vertical", await adapter.add_sketch_constraint(close, None, "vertical"))
    check(
        "back cap rim reach",
        await adapter.add_sketch_dimension(
            f"{base}.end", "origin", "horizontal_distance", SHAFT_R
        ),
    )
    cap.record("CapRim", '"ShaftDia" / 2')
    check(
        "back cap sagitta",
        await adapter.add_sketch_dimension(
            f"{close}.start", f"{close}.end", "vertical_distance", CAP_SAG
        ),
    )
    cap.record("CapSagDim", '"CapSag"')
    check(
        "back cap on axis",
        await adapter.add_sketch_constraint(f"{base}.start", "origin", "vertical_points"),
    )
    check(
        "back cap station",
        await adapter.add_sketch_dimension(
            f"{base}.start", "origin", "vertical_distance", SHAFT_LEN
        ),
    )
    cap.record("CapZ", '"ShaftLen"')
    check(
        "back cap radius",
        await adapter.add_sketch_dimension(arc, None, "radial", CAP_R),
    )
    cap.record(
        "CapR",
        '("ShaftDia" / 2 * "ShaftDia" / 2 + "CapSag" * "CapSag") / (2 * "CapSag")',
    )
    await ensure_fully_defined(adapter, "back cap sketch")
    check("exit_sketch back cap", await adapter.exit_sketch())
    name_last_feature(adapter, "BackCapProfile")
    drive_jobs += cap.apply(adapter, "BackCapProfile")
    check("revolve back cap", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "BackCap")
    volume = await volume_check(adapter, "back cap", volume + V_CAP, 0.03 * V_CAP)

    # Named central axis (Axis1): journals in the straps' Ø8 top bores; the
    # drum and tee handle both seat on it (build_drive_train).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "arbor axis")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven arbor (equations neutral)", volume, 0.005 * V_SHAFT)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # GD&T lives on the MODEL as DimXpert PMI; the drawing imports it.
    author_part_pmi(adapter, datums=PART_DATUMS, controls=GEOMETRIC_CONTROLS)
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
