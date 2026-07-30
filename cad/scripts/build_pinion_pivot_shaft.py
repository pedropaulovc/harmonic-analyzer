r"""Reproduction script: pinion strap torque shaft (book ch. 25).

The plain Ø6.35 rod the two pinion swing brackets pivot on, running
parallel under the alignment-pinion drum through both pivot blocks'
east bores (p. 68 close-ups; the engage lever and its cam pins live on
the SEPARATE lift rod in the west bores -- build_pinion_lift_rod.py).

Layout: shaft axis Z, z 0..192 (PR7: ends FLUSH with the pivot blocks'
outer faces, machine -104/+88, instead of 2 proud), each end crowned by
a shallow spherical cap (sagitta 1.2 -- the p.69 close-up's domed end
visible inside the strap bore).

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_pivot_shaft.py
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
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _saved_part_guard import require_saved_drawing_properties
from pinion_pivot_shaft_spec import (
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    ISO_VIEW_NOTE,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SHAFT_LEN,
    SHAFT_LENGTH_TOLERANCE_MM,
)

PART_NAME = "pinion-pivot-shaft"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.67)
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "End View Note",
    "Iso View Note",
)

SHAFT_R = SHAFT_DIA / 2.0
CAP_R = (SHAFT_R**2 + CAP_SAG**2) / (2.0 * CAP_SAG)  # 4.80 sphere radius
V_CAP = math.pi * CAP_SAG**2 * (3.0 * CAP_R - CAP_SAG) / 3.0  # 19.85 each
V_SHAFT = math.pi * SHAFT_R**2 * SHAFT_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the shaft diameter and length. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 6.35 = 6.35 in). The
    # extrude length is a feature parameter (built with the literal below);
    # ShaftLen is declared so a GUI edit sees the knob.
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLen", f"{SHAFT_LEN}mm")
    await set_global(adapter, "CapSag", f"{CAP_SAG}mm")

    drive_jobs: list[tuple[str, str]] = []

    # On-axis rod (origin centre): define_circle emits only the diameter dim, so
    # only the "Dia" slot is recorded -- the X/Z names are ignored.
    shaft = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        SHAFT_R,
        "shaft",
        dims=shaft,
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

    # Crowned end caps (PR7): a shallow spherical cap proud of each flat end
    # (sagitta CAP_SAG), revolved about the shaft axis from a Top-plane
    # profile (u, v) -> (X, -Z): radial base line at the end face, arc from
    # the rim to the on-axis apex, on-axis close line doubling as the revolve
    # axis edge (the handle-ball idiom: centerline overlapping the axis edge).
    # Constraint accounting per cap (4 free points after merges): base
    # horizontal + close vertical (directions), rim h-dist (radius), sagitta
    # v-dist (apex), one station anchor (origin-coincident at the front end,
    # a driven v-dist at the back end), arc radius (centre resolved to the
    # outward-bulge solution as drawn; the volume gate arbitrates the lobe).
    from solidworks_mcp.adapters.base import RevolveParameters

    for tag, z_end, sign in (("front", 0.0, -1.0), ("back", SHAFT_LEN, 1.0)):
        v_base = -z_end
        v_apex = -(z_end + sign * CAP_SAG)
        v_centre = -(z_end + sign * (CAP_SAG - CAP_R))
        cap = SketchDims()
        check(f"create_sketch cap {tag}", await adapter.create_sketch("Top"))
        set_sketch_direct_db(adapter, True)
        check(
            f"cap {tag} centerline",
            await adapter.add_centerline(0.0, v_base, 0.0, v_apex),
        )
        base = check(
            f"cap {tag} base",
            await adapter.add_line(0.0, v_base, SHAFT_R, v_base),
        )
        # add_arc sweeps CCW p1 -> p2: the minor (outward-bulge) lobe is
        # rim -> apex at the front end, apex -> rim at the back end.
        p1, p2 = (
            ((0.0, v_apex), (SHAFT_R, v_base))
            if sign > 0
            else ((SHAFT_R, v_base), (0.0, v_apex))
        )
        arc = check(
            f"cap {tag} arc",
            await adapter.add_arc(0.0, v_centre, p1[0], p1[1], p2[0], p2[1]),
        )
        close = check(
            f"cap {tag} close",
            await adapter.add_line(0.0, v_apex, 0.0, v_base),
        )
        set_sketch_direct_db(adapter, False)
        check(
            f"cap {tag} base horizontal",
            await adapter.add_sketch_constraint(base, None, "horizontal"),
        )
        check(
            f"cap {tag} close vertical",
            await adapter.add_sketch_constraint(close, None, "vertical"),
        )
        check(
            f"cap {tag} rim reach",
            await adapter.add_sketch_dimension(
                f"{base}.end", "origin", "horizontal_distance", SHAFT_R
            ),
        )
        cap.record(f"Cap{tag.capitalize()}Rim", '"ShaftDia" / 2')
        check(
            f"cap {tag} sagitta",
            await adapter.add_sketch_dimension(
                f"{close}.start", f"{close}.end", "vertical_distance", CAP_SAG
            ),
        )
        cap.record(f"Cap{tag.capitalize()}Sag", '"CapSag"')
        if z_end:
            check(
                f"cap {tag} on axis",
                await adapter.add_sketch_constraint(
                    f"{base}.start", "origin", "vertical_points"
                ),
            )
            check(
                f"cap {tag} station",
                await adapter.add_sketch_dimension(
                    f"{base}.start", "origin", "vertical_distance", z_end
                ),
            )
            cap.record(f"Cap{tag.capitalize()}Z", '"ShaftLen"')
        else:
            check(
                f"cap {tag} station",
                await adapter.add_sketch_constraint(
                    f"{base}.start", "origin", "coincident"
                ),
            )
        check(
            f"cap {tag} radius",
            await adapter.add_sketch_dimension(arc, None, "radial", CAP_R),
        )
        cap.record(
            f"Cap{tag.capitalize()}R",
            '("ShaftDia" / 2 * "ShaftDia" / 2 + "CapSag" * "CapSag") / (2 * "CapSag")',
        )
        await ensure_fully_defined(adapter, f"cap {tag} sketch")
        check(f"exit_sketch cap {tag}", await adapter.exit_sketch())
        name_last_feature(adapter, f"Cap{tag.capitalize()}Profile")
        drive_jobs += cap.apply(adapter, f"Cap{tag.capitalize()}Profile")
        check(
            f"revolve cap {tag}",
            await adapter.create_revolve(RevolveParameters(angle=360.0)),
        )
        name_last_feature(adapter, f"Cap{tag.capitalize()}")
        volume = await volume_check(adapter, f"cap {tag}", volume + V_CAP, 0.03 * V_CAP)

    # Named central axis (Axis1) for the assembly swing revolute: the pinion
    # swing group pivots on this shaft (p2 engage DOF, build_drive_train).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "shaft axis")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven shaft (equations neutral)", volume, 0.005 * V_SHAFT
    )

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    set_dimension_bilateral_tolerance(
        adapter, "ShaftProfile", "ShaftDia", *deviations(SHAFT_DIA_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "Shaft", "Depth", SHAFT_LENGTH_TOLERANCE_MM
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
            "Iso View Note": ISO_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
