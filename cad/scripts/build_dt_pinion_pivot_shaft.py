r"""Reproduction script: pinion strap torque shaft (book ch. 25).

The plain Ø6.35 rod the two pinion swing brackets pivot on, running
parallel under the alignment-pinion drum through both pivot blocks'
east bores (p. 68 close-ups; the engage lever and its cam pins live on
the SEPARATE lift rod in the west bores -- build_dt_pinion_lift_rod.py).

Layout: shaft axis Z, z 0..SHAFT_LEN (PR7: ends FLUSH with the pivot blocks'
outer faces -- pinion_rig_layout -- instead of 2 proud), each end crowned by
a shallow spherical cap (sagitta 1.2 -- the p.69 close-up's domed end
visible inside the strap bore).  Every sketch is on the Right plane (sketch
u = -z), the MHA-CH-05 idiom, so the diameter, the body length, the crown
and the overall length all import into the drawing's side view.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_pinion_pivot_shaft.py
"""

from __future__ import annotations

import math
import sys

from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _document_units import apply_package_model_units
from _part_properties import part_drawing_unit
from dt_pinion_pivot_shaft_spec import (
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISO_VIEW_NOTE,
    PIN_HOLE_BAND,
    PIN_HOLE_DIA,
    PIN_HOLE_Z,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SHAFT_LEN,
    SURFACE_FINISHES,
    UNIT,
)

PART_NAME = "dt-pinion-pivot-shaft"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.67)
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Iso View Note",
)

SHAFT_R = SHAFT_DIA / 2.0
CAP_R = (SHAFT_R**2 + CAP_SAG**2) / (2.0 * CAP_SAG)  # 4.80 sphere radius
V_CAP = math.pi * CAP_SAG**2 * (3.0 * CAP_R - CAP_SAG) / 3.0  # 19.85 each
V_SHAFT = math.pi * SHAFT_R**2 * SHAFT_LEN


def _pin_hole_removed() -> float:
    """Volume one diametral X hole of PIN_HOLE_DIA takes out of the solid
    shaft: the hole's chord width times the shaft's full chord at each height
    (Simpson over the hole's y extent) -- the MHA-DT-17 pin-hole integral."""
    r = PIN_HOLE_DIA / 2.0
    n = 2000
    h = 2.0 * r / n

    def slab(y: float) -> float:
        width = 2.0 * math.sqrt(max(r * r - y * y, 0.0))
        return width * 2.0 * math.sqrt(max(SHAFT_R**2 - y * y, 0.0))

    total = slab(-r) + slab(r)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * slab(-r + i * h)
    return total * h / 3.0


async def _shaft_profile(adapter) -> list[tuple[str, str]]:
    """The plain half-profile on the Right plane (sketch u = -z), revolved
    into the body: the front end face on the origin, the body running to
    u = -SHAFT_LEN.  The printed diameter and the body length (the overall
    length less both crowns) are its driving dimensions, so both import into
    the side view (the build_ch_pivot_shaft idiom, mirrored to +Z)."""
    from solidworks_mcp.adapters.base import RevolveParameters

    dims = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "shaft axis centerline",
        await adapter.add_centerline(0.0, 0.0, -SHAFT_LEN, 0.0),
    )
    points = [
        (0.0, 0.0),
        (0.0, SHAFT_R),
        (-SHAFT_LEN, SHAFT_R),
        (-SHAFT_LEN, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    n = len(lines)
    for i, line in enumerate(lines):
        (_, v1), (_, v2) = points[i], points[(i + 1) % n]
        direction = "horizontal" if v1 == v2 else "vertical"
        check(
            f"shaft {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    body = lines[1]
    await dimension_between(
        adapter,
        f"{body}.start",
        f"{body}.end",
        "horizontal_distance",
        SHAFT_LEN,
        "shaft ShaftLength",
    )
    dims.record("ShaftLength", '"ShaftLen"')
    await add_diametric_linear_dimension(
        adapter, axis, body, (-SHAFT_LEN / 2.0, SHAFT_R + 5.0), "ShaftDia"
    )
    dims.record("ShaftDia", '"ShaftDia"')
    await anchor_point_to_origin(adapter, f"{lines[0]}.start", 0.0, 0.0, "shaft anchor")
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs = dims.apply(adapter, "ShaftProfile")
    check("revolve shaft", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Shaft")
    return drive_jobs


async def _cap(adapter, tag: str, u_end: float, sign: float) -> list[tuple[str, str]]:
    """One shallow spherical crown CAP_SAG proud of the end face at sketch
    ``u_end`` (``sign`` +1 at the front end, the crown toward +u = -z; -1 at
    the back end), on the Right plane: radial base line on the end face, arc
    from the rim to the on-axis apex, on-axis close line doubling as the
    revolve axis edge.  Constraint accounting (4 free points after merges):
    base vertical + close horizontal (directions), rim reach (radius), crown
    height (apex), one station anchor (origin-coincident at the front end, a
    driven distance at the back end), arc radius (the outward lobe as drawn;
    the volume gate arbitrates it)."""
    from solidworks_mcp.adapters.base import RevolveParameters

    u_apex = u_end + sign * CAP_SAG
    u_centre = u_end - sign * (CAP_R - CAP_SAG)
    name = f"Cap{tag}Profile"
    dims = SketchDims()
    check(f"create_sketch {name}", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    check(
        f"{name} centerline",
        await adapter.add_centerline(u_end, 0.0, u_apex, 0.0),
    )
    base = check(f"{name} base", await adapter.add_line(u_end, 0.0, u_end, SHAFT_R))
    # add_arc sweeps CCW p1 -> p2: the outward lobe runs rim -> apex where the
    # crown points toward -u (back end) and apex -> rim toward +u (front end).
    rim, apex = (u_end, SHAFT_R), (u_apex, 0.0)
    p1, p2 = (rim, apex) if sign < 0 else (apex, rim)
    arc = check(
        f"{name} arc",
        await adapter.add_arc(u_centre, 0.0, p1[0], p1[1], p2[0], p2[1]),
    )
    close = check(f"{name} close", await adapter.add_line(u_apex, 0.0, u_end, 0.0))
    set_sketch_direct_db(adapter, False)
    check(
        f"{name} base vertical",
        await adapter.add_sketch_constraint(base, None, "vertical"),
    )
    check(
        f"{name} close horizontal",
        await adapter.add_sketch_constraint(close, None, "horizontal"),
    )
    await dimension_between(
        adapter, f"{base}.end", "origin", "vertical_distance", SHAFT_R, f"{name} rim"
    )
    dims.record(f"Cap{tag}Rim", '"ShaftDia" / 2')
    await dimension_between(
        adapter,
        f"{close}.start",
        f"{close}.end",
        "horizontal_distance",
        CAP_SAG,
        f"{name} height",
    )
    dims.record(f"Cap{tag}Sag", '"CapSag"')
    if u_end:
        check(
            f"{name} on axis",
            await adapter.add_sketch_constraint(
                f"{base}.start", "origin", "horizontal_points"
            ),
        )
        await dimension_between(
            adapter,
            f"{base}.start",
            "origin",
            "horizontal_distance",
            abs(u_end),
            f"{name} station",
        )
        dims.record(f"Cap{tag}Z", '"ShaftLen"')
    else:
        check(
            f"{name} station",
            await adapter.add_sketch_constraint(
                f"{base}.start", "origin", "coincident"
            ),
        )
    check(
        f"{name} radius",
        await adapter.add_sketch_dimension(arc, None, "radial", CAP_R),
    )
    dims.record(
        f"Cap{tag}R",
        '("ShaftDia" / 2 * "ShaftDia" / 2 + "CapSag" * "CapSag") / (2 * "CapSag")',
    )
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    name_last_feature(adapter, name)
    drive_jobs = dims.apply(adapter, name)
    check(
        f"revolve {tag} cap",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, f"Cap{tag}")
    return drive_jobs


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations): the shaft diameter and length. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 6.35 = 6.35 in).
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLen", f"{SHAFT_LEN}mm")
    await set_global(adapter, "CapSag", f"{CAP_SAG}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    for tag, z_hole in zip(("Front", "Back"), PIN_HOLE_Z):
        await set_global(adapter, f"PinHole{tag}Z", f"{z_hole}mm")

    drive_jobs = await _shaft_profile(adapter)
    volume = await volume_check(adapter, "shaft", V_SHAFT, 0.005 * V_SHAFT)

    # Crowned end caps (PR7): a shallow spherical cap proud of each flat end
    # (sagitta CAP_SAG).
    drive_jobs += await _cap(adapter, "Front", 0.0, 1.0)
    volume = await volume_check(adapter, "cap front", volume + V_CAP, 0.03 * V_CAP)
    drive_jobs += await _cap(adapter, "Back", -SHAFT_LEN, -1.0)
    volume = await volume_check(adapter, "cap back", volume + V_CAP, 0.03 * V_CAP)

    # Option E-a set-pin holes: one diametral cross hole along X under each
    # strap's mid-plane in the physical back-stop stack, where the match-drill
    # puts it (dt_pinion_pivot_shaft_spec.PIN_HOLE_Z), sketched on the
    # Right Plane (normal X; sketch u = -z) and cut mid-plane twice the shaft
    # diameter deep -- the MHA-DT-17 pin-hole idiom.  The origin sits on the
    # front end face, so each circle's axial anchor is its station from that
    # end.  A mirror station (z < 0) lies outside the shaft and cuts nothing,
    # and the removed volume is gated at 5% of the two holes, so a missing or
    # misplaced cut fails loud.
    #
    # The same sketch carries the overall length, tip to tip, as a construction
    # axis from the front crown's apex (u = +CAP_SAG) to the back one's: the
    # drawing prints it as a reference (the build_ch_pivot_shaft idiom).  It is
    # drawn off the inference engine: both ends lie on the crowns' apex
    # vertices, which a snapped relation would over-define.
    v_holes = 2.0 * _pin_hole_removed()
    pin_holes = SketchDims()
    check("create_sketch pin holes", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    overall = check(
        "tip-to-tip axis",
        await adapter.add_centerline(CAP_SAG, 0.0, -(SHAFT_LEN + CAP_SAG), 0.0),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "tip-to-tip axis horizontal",
        await adapter.add_sketch_constraint(overall, None, "horizontal"),
    )
    check(
        "tip-to-tip axis on the shaft axis",
        await adapter.add_sketch_constraint(
            f"{overall}.start", "origin", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{overall}.start",
        "origin",
        "horizontal_distance",
        CAP_SAG,
        "front crown tip",
    )
    pin_holes.record("FrontTip", '"CapSag"')
    await dimension_between(
        adapter,
        f"{overall}.start",
        f"{overall}.end",
        "horizontal_distance",
        SHAFT_LEN + 2.0 * CAP_SAG,
        "overall length",
    )
    pin_holes.record("OverallLength", '"ShaftLen" + 2 * "CapSag"')
    for tag, z_hole in zip(("Front", "Back"), PIN_HOLE_Z):
        await define_circle(
            adapter,
            -z_hole,
            0.0,
            PIN_HOLE_DIA / 2.0,
            f"{tag.lower()} pin hole",
            dims=pin_holes,
            names=(
                f"PinHole{tag}Z",
                f"PinHole{tag}Y",
                # The front hole's size prints: its callout stands under the
                # profile's front end, clear of the diameter at the back.
                "PinHoleDia" if tag == "Front" else f"PinHole{tag}Dia",
            ),
            drives=(f'"PinHole{tag}Z"', None, '"PinHoleDia"'),
        )
    await ensure_fully_defined(adapter, "pin holes sketch")
    check("exit_sketch pin holes", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin_holes.apply(adapter, "PinHoleProfile")
    cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=2.0 * SHAFT_DIA, both_directions=True)
    )
    if not cut.is_success:
        raise RuntimeError(f"pin hole cut failed: {cut.error}")
    name_last_feature(adapter, "PinHoles")
    volume = await volume_check(adapter, "pin holes", volume - v_holes, 0.05 * v_holes)

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
        adapter,
        "ShaftProfile",
        "ShaftDia",
        *deviations(SHAFT_DIA_BAND),
        display_unit=UNIT,
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "PinHoleProfile",
        "PinHoleDia",
        *deviations(PIN_HOLE_BAND),
        display_unit=UNIT,
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)  # lengths at .XX
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Iso View Note": ISO_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
